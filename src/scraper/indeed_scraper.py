import os
import sys
import asyncio
import subprocess
from typing import List, Dict, Set
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page
from playwright_stealth import Stealth
from src.scraper.auth_manager import AuthManager

try:
    from camoufox.async_api import AsyncCamoufox
    import camoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False

class IndeedScraper:
    def __init__(self, diagnostics=None):
        self.auth_manager = AuthManager("indeed")
        self.diagnostics = diagnostics
        # fromage=1 filtra esclusivamente le ultime 24 ore (giornaliero)
        self.base_url = "https://it.indeed.com/jobs?q={keywords}&l={location}&fromage=1&sort=date&start={start}"
        self.p = None
        self.browser = None
        self.camoufox_cm = None
        self.session_file = self.auth_manager.session_file
        self.is_authenticated = os.path.exists(self.session_file)
        self.use_camoufox = CAMOUFOX_AVAILABLE

    def _ensure_xvfb(self):
        """Garantisce uno schermo virtuale Xvfb ad alta risoluzione (1920x1080) su Linux (evita il bug 1x1 screen bot detection)."""
        if sys.platform != "win32" and not os.getenv("DISPLAY"):
            display = ":99"
            os.environ["DISPLAY"] = display
            try:
                subprocess.Popen(
                    ["Xvfb", display, "-screen", "0", "1920x1080x24", "-ac", "+extension", "GLX", "+render", "-noreset"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print(f"[*] [Indeed] Display Xvfb 1920x1080 avviato su {display}", flush=True)
            except Exception as e:
                print(f"[-] [Indeed] Xvfb setup note: {e}", flush=True)

    async def init_browser(self):
        """Inizializza Camoufox Stealth Browser con proxy residenziale Iliadbox o fallback Chromium."""
        self.is_authenticated = os.path.exists(self.session_file)
        proxy_url = os.getenv("INDEED_PROXY_SERVER", "socks5://172.18.0.1:1080")
        proxy_active = False

        if proxy_url:
            try:
                import socket
                clean_host = proxy_url.split("://")[-1].split(":")[0]
                clean_port = int(proxy_url.split(":")[-1])
                s = socket.socket()
                s.settimeout(0.5)
                s.connect((clean_host, clean_port))
                s.close()
                proxy_active = True
                print(f"[*] [Indeed] Tunnel residenziale Iliadbox attivo: {proxy_url}", flush=True)
            except Exception:
                proxy_active = False

        proxy_dict = {"server": proxy_url} if proxy_active else None

        # Tentativo 1: Stealth Camoufox Engine
        if self.use_camoufox:
            try:
                self._ensure_xvfb()
                camoufox_kwargs = {
                    "headless": False if os.getenv("DISPLAY") else True,
                    "humanize": True,
                    "geoip": True,
                    "os": "windows",
                    "exclude_addons": [camoufox.DefaultAddons.UBO],
                }
                if proxy_dict:
                    camoufox_kwargs["proxy"] = proxy_dict

                print("[*] [Indeed] Avvio motore Camoufox Stealth Anti-Detect...", flush=True)
                self.camoufox_cm = AsyncCamoufox(**camoufox_kwargs)
                self.browser = await self.camoufox_cm.__aenter__()
                print("[+] [Indeed] Camoufox avviato con successo.", flush=True)
                return
            except Exception as camoufox_err:
                print(f"[-] [Indeed] Fallback su Chromium: Errore avvio Camoufox ({camoufox_err})", flush=True)
                self.use_camoufox = False

        # Tentativo 2: Playwright Chromium con Stealth
        self.p = await async_playwright().start()
        launch_kwargs = {
            "headless": True,
            "args": [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--window-size=1920,1080',
                '--disable-dev-shm-usage',
                '--lang=it-IT,it'
            ]
        }
        if proxy_dict:
            launch_kwargs["proxy"] = proxy_dict

        self.browser = await self.p.chromium.launch(**launch_kwargs)
        print("[*] [Indeed] Browser Chromium Playwright avviato in modalità standard.", flush=True)

    async def close_browser(self):
        """Chiude le risorse del browser."""
        if self.camoufox_cm:
            try:
                await self.camoufox_cm.__aexit__(None, None, None)
            except Exception:
                pass
            self.camoufox_cm = None
            self.browser = None

        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None

        if self.p:
            try:
                await self.p.stop()
            except Exception:
                pass
            self.p = None

    async def _create_context(self):
        """Crea un contesto isolato caricando la sessione Indeed se disponibile."""
        context_kwargs = {
            "locale": "it-IT",
            "timezone_id": "Europe/Rome"
        }
        if not self.use_camoufox:
            context_kwargs["user_agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            context_kwargs["viewport"] = {"width": 1920, "height": 1080}

        if self.is_authenticated and os.path.exists(self.session_file):
            context = await self.browser.new_context(storage_state=self.session_file, **context_kwargs)
        else:
            context = await self.browser.new_context(**context_kwargs)

        if not self.use_camoufox:
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
        Sfrutta Camoufox, proxy residenziale Iliadbox e pannello 'Click-to-load' per descrizione completa.
        """
        if seen_urls is None:
            seen_urls = set()

        print(f"[*] Avvio scraping Indeed per '{keywords}' in '{location}' (ultime 24h)...", flush=True)

        jobs_found = []
        try:
            if not self.browser:
                await self.init_browser()
            if not self.browser:
                raise RuntimeError("Inizializzazione browser non riuscita")
            context, page = await self._create_context()
        except Exception as ctx_err:
            print(f"[-] [Indeed] Impossibile avviare contesto browser ({ctx_err}). Attivazione fallback autonomo via Search Engine Index...", flush=True)
            return self._fallback_search_engine(keywords, location, max_results=max_results, seen_urls=seen_urls)

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
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
                    await page.wait_for_timeout(2000)
                    await self._handle_popups(page)
                except Exception as e:
                    print(f"[-] Errore caricamento pagina Indeed ({search_url}): {e}", flush=True)
                    break

                page_title = await page.title()
                if "security check" in page_title.lower() or "just a moment" in page_title.lower() or "challenge" in page_title.lower() or "ci siamo quasi" in page_title.lower():
                    print(f"[*] Verifica Cloudflare rilevata su Indeed per '{keywords}' (start={start}). Risoluzione...", flush=True)
                    try:
                        box_el = page.locator("#cf-box-container")
                        if await box_el.count() > 0:
                            box = await box_el.first.bounding_box()
                            if box and box['width'] > 50:
                                click_x = box['x'] + 28
                                click_y = box['y'] + (box['height'] / 2)
                                await page.mouse.move(click_x, click_y, steps=20)
                                await page.wait_for_timeout(300)
                                await page.mouse.click(click_x, click_y)
                                for _ in range(8):
                                    await page.wait_for_timeout(1000)
                                    page_title = await page.title()
                                    if "security check" not in page_title.lower() and "ci siamo quasi" not in page_title.lower():
                                        break
                    except Exception:
                        pass

                    page_title = await page.title()
                    if "security check" in page_title.lower() or "just a moment" in page_title.lower() or "ci siamo quasi" in page_title.lower():
                        print(f"[-] Pagina Indeed bloccata da verifica Cloudflare, proseguo.", flush=True)
                        if self.diagnostics:
                            await self.diagnostics.capture_screenshot(page, f"indeed_challenge_{keywords[:15]}")
                        break
                    else:
                        print(f"[+] [Indeed] Verifica Cloudflare superata!", flush=True)

                if self.diagnostics and start == 0:
                    await self.diagnostics.capture_screenshot(page, f"indeed_search_{keywords[:15]}")

                # Estraiamo il DOM della pagina con BeautifulSoup
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

                        # Deduplicazione preventiva
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

                    except Exception:
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

        # Se il browser scraping diretto è bloccato da Cloudflare, attiviamo il fallback autonomo
        if not jobs_found:
            print("[*] [Indeed] Pagine dirette non accessibili (WAF / login obbligatorio). Attivazione fallback autonomo via Search Engine Index...", flush=True)
            jobs_found = self._fallback_search_engine(keywords, location, max_results=max_results, seen_urls=seen_urls)

        return jobs_found

    def _fallback_search_engine(self, keywords: str, location: str, max_results: int = 30, seen_urls: Set[str] = None) -> List[Dict]:
        """
        Estrazione autonoma ad alta affidabilità di offerte Indeed tramite Tavily Search Engine Index.
        Zero blocchi Cloudflare, zero dipendenze da sessioni, 100% autonomo su VPS.
        """
        import os
        from tavily import TavilyClient

        if seen_urls is None:
            seen_urls = set()

        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            print("[-] [Indeed Engine] TAVILY_API_KEY non configurata per fallback.", flush=True)
            return []

        print(f"[*] [Indeed Engine] Ricerca autonoma annunci per '{keywords}' in '{location}'...", flush=True)
        client = TavilyClient(api_key=api_key)
        query = f'site:it.indeed.com/viewjob "{keywords}" {location}'
        try:
            res = client.search(
                query=query,
                search_depth="advanced",
                max_results=min(max_results, 15)
            )
            jobs = []
            for r in res.get("results", []):
                url = r.get("url", "")
                if "indeed.com/viewjob" not in url and "indeed.com" not in url:
                    continue
                if url in seen_urls:
                    continue

                raw_title = r.get("title", "")
                parts = [p.strip() for p in raw_title.split(" - ") if p.strip()]
                title = parts[0] if parts else raw_title
                company = parts[1] if len(parts) > 1 and "indeed" not in parts[1].lower() else "Azienda su Indeed"
                if len(parts) > 2 and "indeed" not in parts[2].lower():
                    company = f"{company} ({parts[2]})"

                content = r.get("content", "Descrizione non disponibile.")
                jobs.append({
                    "title": title,
                    "company": company,
                    "url": url,
                    "description": content,
                    "source": "Indeed"
                })
                seen_urls.add(url)
                print(f"    [Indeed Engine] Estratto: {title} @ {company}", flush=True)

            print(f"[+] [Indeed Engine] Raccolte {len(jobs)} offerte Indeed via Search Index.", flush=True)
            return jobs
        except Exception as e:
            print(f"[-] [Indeed Engine] Errore estrazione: {e}", flush=True)
            return []

if __name__ == "__main__":
    async def test():
        scraper = IndeedScraper()
        await scraper.init_browser()
        results = await scraper.run("Sviluppatore Python", "Italia", max_results=3)
        print(f"\nTOTALE RACCOLTO: {len(results)}")
        for r in results:
            print(f"- {r['title']} @ {r['company']}")
            print(f"  URL: {r['url']}")
            print(f"  Desc: {r['description'][:150]}...\n")
        await scraper.close_browser()

    asyncio.run(test())
