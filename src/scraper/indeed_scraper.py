import os
import asyncio
from playwright.async_api import async_playwright, Page
from playwright_stealth import Stealth
from bs4 import BeautifulSoup
from typing import List, Dict, Set
from src.scraper.auth_manager import AuthManager

class IndeedScraper:
    def __init__(self):
        self.auth_manager = AuthManager("indeed")
        # fromage=1 filtra esclusivamente le ultime 24 ore (giornaliero)
        self.base_url = "https://it.indeed.com/jobs?q={keywords}&l={location}&fromage=1&sort=date&start={start}"
        self.p = None
        self.browser = None
        self.session_file = self.auth_manager.session_file
        self.is_authenticated = os.path.exists(self.session_file)

    async def init_browser(self):
        """Inizializza un browser Chromium dedicato con Playwright."""
        self.is_authenticated = os.path.exists(self.session_file)
        self.p = await async_playwright().start()
        self.browser = await self.p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )

    async def close_browser(self):
        """Chiude le risorse del browser."""
        if self.browser:
            await self.browser.close()
        if self.p:
            await self.p.stop()

    async def _create_context(self):
        """Crea un contesto stealth isolato caricando la sessione Indeed se disponibile."""
        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080},
            "locale": "it-IT"
        }
        if self.is_authenticated and os.path.exists(self.session_file):
            context = await self.browser.new_context(storage_state=self.session_file, **context_kwargs)
        else:
            context = await self.browser.new_context(**context_kwargs)
            
        await Stealth().apply_stealth_async(context)
        page = await context.new_page()
        return context, page

    async def _handle_popups(self, page: Page):
        """Gestisce banner cookie e popup di iscrizione/newsletter su Indeed."""
        try:
            cookie_btn = page.locator("button#onetrust-accept-btn-handler, button:has-text('Accetta tutto'), button:has-text('Accetto')")
            if await cookie_btn.count() > 0:
                await cookie_btn.first.click()
                await page.wait_for_timeout(500)
        except Exception:
            pass

        # Chiudi eventuali popup "Ricevi nuovi annunci via email"
        try:
            close_btn = page.locator("button[aria-label='chiudi'], button[aria-label='close'], button.icl-CloseButton, button#mosaic-provider-jobcards-modal-close-button")
            if await close_btn.count() > 0:
                await close_btn.first.click()
                await page.wait_for_timeout(300)
        except Exception:
            pass

    async def run(self, keywords: str, location: str, max_results: int = 50, seen_urls: Set[str] = None) -> List[Dict]:
        """
        Scrape delle offerte su Indeed per le keyword e la location specificate.
        Sfrutta il pannello 'Click-to-load' per estrarre la descrizione completa a zero latenza.
        """
        if seen_urls is None:
            seen_urls = set()
            
        print(f"[*] Avvio scraping Indeed per '{keywords}' in '{location}' (ultime 24h)...")
        
        jobs_found = []
        context, page = await self._create_context()
        
        try:
            # Paginazione su Indeed (start=0, 10, 20...)
            for start in range(0, max_results, 10):
                if start > 0:
                    try:
                        await page.close()
                    except Exception:
                        pass
                    page = await context.new_page()
                    await asyncio.sleep(1.5)

                search_url = self.base_url.format(
                    keywords=keywords.replace(" ", "+"),
                    location=location.replace(" ", "+"),
                    start=start
                )
                
                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(2000)
                    await self._handle_popups(page)
                except Exception as e:
                    print(f"[-] Errore caricamento pagina Indeed ({search_url}): {e}", flush=True)
                    break

                page_title = await page.title()
                if "security check" in page_title.lower() or "just a moment" in page_title.lower():
                    print(f"[-] Security Check rilevato su Indeed per '{keywords}' (start={start}). Attendo 3s...", flush=True)
                    await page.wait_for_timeout(3000)
                    page_title = await page.title()
                    if "security check" in page_title.lower() or "just a moment" in page_title.lower():
                        print(f"[-] Pagina Indeed bloccata da verifica, proseguo.", flush=True)
                        break

                # Estraiamo l'intero DOM della pagina in BeautifulSoup istantaneamente
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                cards_soup = soup.find_all("div", class_=lambda c: c and "cardOutline" in c)
                
                if not cards_soup:
                    cards_soup = soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in c)
                
                count = len(cards_soup)
                if count == 0:
                    break
                    
                print(f"[+] Indeed - Pagina {start // 10 + 1}: Trovate {count} offerte.", flush=True)
                
                for i, c_soup in enumerate(cards_soup):
                    try:
                        # Titolo
                        title_el = c_soup.find("h2") or c_soup.find("a", class_=lambda c: c and "jcs-JobTitle" in c)
                        title = title_el.text.strip().split("\n")[0] if title_el else "Titolo Sconosciuto"
                        
                        # Link & JK
                        title_link = c_soup.find("a", class_=lambda c: c and "jcs-JobTitle" in c) or c_soup.find("a", href=True)
                        href = title_link.get("href", "") if title_link else ""
                        
                        jk = ""
                        jk_tag = c_soup.find(lambda tag: tag.has_attr("data-jk"))
                        if jk_tag:
                            jk = jk_tag["data-jk"]
                        elif "jk=" in href:
                            jk = href.split("jk=")[1].split("&")[0]
                            
                        job_url = f"https://it.indeed.com/viewjob?jk={jk}" if jk else ("https://it.indeed.com" + href.split("?")[0] if href.startswith("/") else href)
                        
                        # Azienda
                        comp_el = (c_soup.find("span", {"data-testid": "company-name"}) or 
                                   c_soup.find("span", class_=lambda c: c and "company" in c))
                        company = comp_el.text.strip().split("\n")[0] if comp_el else "Azienda Sconosciuta"
                        
                        # Sede / Località
                        loc_el = (c_soup.find("div", {"data-testid": "text-location"}) or 
                                  c_soup.find("div", class_=lambda c: c and "location" in c))
                        loc = loc_el.text.strip() if loc_el else ""
                        if loc:
                            company = f"{company} ({loc})"
                            
                        # Deduplicazione preventiva istantanea a zero latenza
                        if job_url in seen_urls:
                            print(f"    [Indeed] Salto già esaminato: {title} @ {company}", flush=True)
                            continue
                        seen_urls.add(job_url)
                        
                        desc_text = ""
                        if jk:
                            title_btn = page.locator(f"[data-jk='{jk}'] h2, [data-jk='{jk}'] a, a[data-jk='{jk}']").first
                            if await title_btn.count() > 0:
                                try:
                                    await title_btn.evaluate("""
                                        (el) => {
                                            const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                                            el.dispatchEvent(evt);
                                        }
                                    """)
                                    try:
                                        await page.wait_for_selector("#jobsearch-ViewjobPaneWrapper", timeout=800)
                                    except Exception:
                                        pass
                                        
                                    if not page.url.startswith("https://it.indeed.com/jobs"):
                                        await page.go_back(wait_until="domcontentloaded")
                                        await page.wait_for_timeout(400)
                                    else:
                                        pane = page.locator("#jobsearch-ViewjobPaneWrapper")
                                        if await pane.count() > 0:
                                            p_html = await pane.inner_html()
                                            psoup = BeautifulSoup(p_html, "html.parser")
                                            d_el = psoup.find(class_=lambda c: c and ("simple-job-description-html" in c or "jobsearch-jobDescriptionText" in c)) or psoup.find(id="jobDescriptionText")
                                            if d_el:
                                                desc_text = d_el.get_text(separator="\n", strip=True)
                                            else:
                                                desc_text = psoup.get_text(separator="\n", strip=True)
                                except Exception:
                                    pass
                                    
                        # Fallback al testo completo della card
                        if not desc_text or len(desc_text) < 50:
                            card_texts = [t.strip() for t in c_soup.stripped_strings if t.strip() and t.strip().lower() not in ("annuncio", "candidati facilmente", "salva")]
                            desc_text = "\n".join(card_texts)
                            
                        if not desc_text:
                            desc_text = "Descrizione non disponibile."
                            
                        jobs_found.append({
                            "title": title,
                            "company": company,
                            "url": job_url,
                            "description": desc_text,
                            "source": "Indeed"
                        })
                        
                        print(f"    [Indeed] Estratto: {title} @ {company} ({len(desc_text)} car)", flush=True)
                        
                        if len(jobs_found) >= max_results:
                            break
                            
                    except Exception as card_err:
                        continue
                    
                if len(jobs_found) >= max_results or count < 10:
                    break
                
                if not self.is_authenticated and start == 0:
                    print(f"    [i] Modalità Guest Indeed: Pagina 1 completata ({len(jobs_found)} offerte).", flush=True)
                    break
                
        finally:
            try:
                await context.close()
            except Exception:
                pass
                
        return jobs_found

if __name__ == "__main__":
    async def test():
        scraper = IndeedScraper()
        await scraper.init_browser()
        results = await scraper.run("Risorse Umane", "Italia", max_results=3)
        print(f"\nTOTALE RACCOLTO: {len(results)}")
        for r in results:
            print(f"- {r['title']} @ {r['company']}")
            print(f"  URL: {r['url']}")
            print(f"  Desc: {r['description'][:150]}...\n")
        await scraper.close_browser()
        
    asyncio.run(test())
