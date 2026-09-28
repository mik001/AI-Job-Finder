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
            # Paginazione su Indeed: ogni pagina ha circa 10-15 offerte (start incrementa di 10)
            for start in range(0, max_results, 10):
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
                    print(f"[-] Errore caricamento pagina Indeed ({search_url}): {e}")
                    break

                page_title = await page.title()
                if "security check" in page_title.lower():
                    print(f"[-] Security Check rilevato su Indeed per '{keywords}', ricreo contesto pulito...")
                    await context.close()
                    context, page = await self._create_context()
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(2000)
                    await self._handle_popups(page)

                card_locators = page.locator("div.cardOutline")
                count = await card_locators.count()
                
                if count == 0:
                    # Nessun annuncio trovato per questa pagina, abbiamo finito
                    break
                    
                print(f"[+] Indeed - Pagina {start // 10 + 1}: Trovate {count} offerte.")
                
                for i in range(count):
                    try:
                        await self._handle_popups(page)
                        card = card_locators.nth(i)
                        
                        # Estrazione dati rapidi dalla card HTML
                        card_html = await card.inner_html()
                        soup = BeautifulSoup(card_html, "html.parser")
                        
                        # Titolo
                        title_el = soup.find("h2") or soup.find("a", class_=lambda c: c and "jcs-JobTitle" in c)
                        title = title_el.text.strip().split("\n")[0] if title_el else "Titolo Sconosciuto"
                        
                        # Link / URL Canonico
                        jk_tag = soup.find(lambda tag: tag.has_attr("data-jk"))
                        if jk_tag and jk_tag.get("data-jk"):
                            job_url = f"https://it.indeed.com/viewjob?jk={jk_tag['data-jk']}"
                        else:
                            link_el = soup.find("a", href=True)
                            job_url = ""
                            if link_el and link_el.get("href"):
                                href = link_el["href"]
                                if "jk=" in href:
                                    jk_val = href.split("jk=")[1].split("&")[0]
                                    job_url = f"https://it.indeed.com/viewjob?jk={jk_val}"
                                elif href.startswith("/"):
                                    job_url = "https://it.indeed.com" + href.split("?")[0]
                                else:
                                    job_url = href.split("?")[0]
                            
                        # Azienda
                        comp_el = (soup.find("span", {"data-testid": "company-name"}) or 
                                   soup.find("span", class_=lambda c: c and "company" in c))
                        company = comp_el.text.strip().split("\n")[0] if comp_el else "Azienda Sconosciuta"
                        
                        # Sede / Località
                        loc_el = (soup.find("div", {"data-testid": "text-location"}) or 
                                  soup.find("div", class_=lambda c: c and "location" in c))
                        loc = loc_el.text.strip() if loc_el else ""
                        if loc:
                            company = f"{company} ({loc})"
                            
                        # Deduplicazione preventiva
                        if job_url in seen_urls:
                            continue
                        seen_urls.add(job_url)
                            
                        # Chiudi eventuali dialog o popup premendo Escape
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(100)
                        
                        # Clicchiamo specificamente il link del titolo per attivare il cambio di annuncio nel pannello destro
                        title_link = card.locator("h2.jobTitle a, a.jcs-JobTitle, a[id*='job_']").first
                        if await title_link.count() > 0:
                            link_el = await title_link.element_handle()
                            await page.evaluate("(el) => el.click()", link_el)
                        else:
                            card_el = await card.element_handle()
                            if card_el:
                                await page.evaluate("(el) => el.click()", card_el)
                                
                        await page.wait_for_timeout(900)
                        
                        # Estrazione dal pannello laterale ViewjobPaneWrapper
                        pane = page.locator("#jobsearch-ViewjobPaneWrapper")
                        desc_text = ""
                        if await pane.count() > 0:
                            pane_html = await pane.inner_html()
                            pane_soup = BeautifulSoup(pane_html, "html.parser")
                            desc_div = pane_soup.find("div", id="jobDescriptionText") or pane_soup.find(class_=lambda c: c and "jobsearch-jobDescriptionText" in c)
                            if desc_div:
                                desc_text = desc_div.get_text(separator="\n", strip=True)
                            else:
                                desc_text = pane_soup.get_text(separator="\n", strip=True)
                                
                        if not desc_text:
                            desc_text = "Descrizione non disponibile."
                            
                        jobs_found.append({
                            "title": title,
                            "company": company,
                            "url": job_url,
                            "description": desc_text,
                            "source": "Indeed"
                        })
                        
                        print(f"    [Indeed] Estratto: {title} @ {company}")
                        
                        if len(jobs_found) >= max_results:
                            break
                            
                    except Exception as card_err:
                        # In caso di micro-glitch su una singola card, continua con le altre
                        continue
                    
                if len(jobs_found) >= max_results:
                    break
                
                # Se non siamo autenticati, Indeed blocca la pagina 2 con redirect forzato (page-two-signin).
                # Con la sessione attiva in indeed_session.json, invece, il ciclo continua fluidamente
                # su Pagina 2, Pagina 3, ecc., estraendo tutti gli annunci della giornata!
                if not self.is_authenticated and start == 0:
                    print(f"    [i] Modalità Guest Indeed: Pagina 1 completata ({len(jobs_found)} offerte).")
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
