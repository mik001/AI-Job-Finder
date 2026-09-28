import asyncio
from playwright.async_api import async_playwright, Page
from src.scraper.auth_manager import AuthManager
from bs4 import BeautifulSoup

class LinkedInScraper:
    def __init__(self):
        self.auth_manager = AuthManager("linkedin")
        # f_TPR=r90000 filtra le ultime 25 ore (90.000 secondi) per evitare finestre di vuoto tra scansioni giornaliere
        self.base_url = "https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&f_TPR=r90000&sortBy=DD&start={start}"
        self.p = None
        self.context = None
        self.page = None

    async def init_browser(self):
        from playwright.async_api import async_playwright
        self.p = await async_playwright().start()
        self.context = await self.auth_manager.get_context(self.p, headless=True, silent=True)
        self.page = await self.context.new_page()
        self.desc_page = await self.context.new_page()

    async def close_browser(self):
        try:
            if self.desc_page and not self.desc_page.is_closed():
                await self.desc_page.close()
        except Exception:
            pass
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
        except Exception:
            pass
        if self.context:
            await self.context.close()
        if self.p:
            await self.p.stop()

    async def _safe_goto(self, target_page: Page, url: str, retries: int = 3) -> bool:
        """Navigazione resiliente contro errori transitori di frame detached o timeout."""
        for attempt in range(1, retries + 1):
            try:
                if target_page.is_closed():
                    return False
                await target_page.goto(url, wait_until="domcontentloaded", timeout=25000)
                return True
            except Exception as e:
                err_msg = str(e).lower()
                if "detached" in err_msg or "navigation" in err_msg or "timeout" in err_msg:
                    print(f"[-] Avviso navigazione a {url}: {e} (ritento {attempt}/{retries})...")
                    await asyncio.sleep(2)
                else:
                    print(f"[-] Errore goto {url}: {e}")
                    return False
        return False

    async def _parse_job_card(self, job_element) -> dict:
        """Estrae i dati di base da una card di annuncio."""
        try:
            # Cerca tutti i link nella card per trovare quello dell'annuncio
            a_tags = job_element.find_all("a", href=True)
            link = ""
            title = ""
            for a in a_tags:
                if "/jobs/view/" in a["href"]:
                    link = a["href"]
                    if a.text.strip():
                        title = a.text.strip()
                    break
            
            # Se non ha trovato il titolo nel tag a, cerca negli h3, div o strong
            if not title:
                title_el = job_element.find("strong") or job_element.find("div", class_=lambda x: x and "title" in x)
                title = title_el.text.strip() if title_el else "Titolo Sconosciuto"
                
            # Azienda
            company_el = job_element.find("div", class_="artdeco-entity-lockup__subtitle") or \
                         job_element.find("span", class_="job-card-container__primary-description") or \
                         job_element.find("a", class_=lambda x: x and "company" in x)
            company = company_el.text.strip() if company_el else "Azienda Sconosciuta"
            
            if link and "?" in link:
                link = link.split("?")[0]
            if link and not link.startswith("http"):
                link = "https://www.linkedin.com" + link
                
            return {
                "title": title.split("\n")[0].strip(), # Pulisci a-capo spuri
                "company": company.split("\n")[0].strip(),
                "url": link
            }
        except Exception as e:
            print(f"[-] Errore parsing card: {e}")
            return None

    async def scrape_job_description(self, job_url: str) -> str:
        """Visita la pagina del lavoro su tab dedicato per non disturbare la pagina di ricerca."""
        print(f"[*] Estrazione descrizione da: {job_url}")
        try:
            if not self.desc_page or self.desc_page.is_closed():
                self.desc_page = await self.context.new_page()
                
            success = await self._safe_goto(self.desc_page, job_url, retries=2)
            if not success:
                return "Descrizione non caricata."
            
            # Attesa selettori descrizione
            try:
                await self.desc_page.wait_for_selector("#job-details, article, .jobs-description__content, [id*='AboutTheJob']", timeout=2500)
            except Exception:
                pass 
            
            try:
                await self.desc_page.locator("button.jobs-description__footer-button").click(timeout=1000)
            except Exception:
                pass
                
            html = await self.desc_page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            desc_div = soup.find("div", id="job-details") or \
                       soup.find(id=lambda x: x and "AboutTheJob" in x) or \
                       soup.find("article") or \
                       soup.find("div", class_="jobs-description__content") or \
                       soup.find("div", class_="description__text")
            
            if desc_div:
                return desc_div.get_text(separator="\n", strip=True)
            return "Descrizione non trovata."
        except Exception as e:
            print(f"[-] Impossibile caricare descrizione per {job_url}: {e}")
            return ""

    async def run(self, keywords: str, location: str, max_results: int = 100, seen_urls: set = None):
        if seen_urls is None:
            seen_urls = set()
            
        print(f"[*] Avvio scraping LinkedIn per '{keywords}' in '{location}'...")
        
        jobs_found = []
        page = self.page
        
        # Paginazione (carichiamo fino a 4 pagine, ovvero 100 annunci)
        for start in range(0, max_results, 25):
            search_url = self.base_url.format(
                keywords=keywords.replace(" ", "%20"),
                location=location.replace(" ", "%20"),
                start=start
            )
            
            success = await self._safe_goto(page, search_url, retries=3)
            if not success:
                print(f"[-] Impossibile caricare pagina di ricerca {search_url}, passo alla successiva.")
                break
                
            await page.wait_for_timeout(3000)  # Pausa umana
            
            # Scorriamo l'effettivo pannello scrollabile per attivare il lazy loading di tutte le 25 card
            await page.evaluate("""
                async () => {
                    const listContainer = document.querySelector('.scaffold-layout__list') || document.body;
                    const scrollable = Array.from(listContainer.querySelectorAll('*')).find(el => {
                        const s = window.getComputedStyle(el);
                        return (s.overflowY === 'auto' || s.overflowY === 'scroll') && el.scrollHeight > el.clientHeight;
                    });
                    
                    if (scrollable) {
                        for (let i = 0; i < 5; i++) {
                            scrollable.scrollBy(0, 800);
                            await new Promise(r => setTimeout(r, 500));
                        }
                    } else {
                        for (let i = 0; i < 5; i++) {
                            window.scrollBy(0, 800);
                            await new Promise(r => setTimeout(r, 500));
                        }
                    }
                }
            """)
            await page.wait_for_timeout(1000)
            
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # Cerca le card degli annunci
            job_cards = soup.find_all("div", class_="job-card-container") or soup.find_all("div", class_="base-card") or soup.find_all("li", class_="jobs-search-results__list-item")
            
            if not job_cards:
                break # Nessun annuncio in questa pagina, abbiamo finito
                
            print(f"[+] [LinkedIn] Pagina {start//25 + 1}: Trovate {len(job_cards)} offerte.", flush=True)
            
            for card in job_cards:
                job_data = await self._parse_job_card(card)
                if job_data and job_data["url"]:
                    if job_data["url"] in seen_urls:
                        print(f"    [LinkedIn] Salto già presente: {job_data['title']} @ {job_data['company']}", flush=True)
                        continue # Salta duplicati prima di caricare la pagina pesante
                    
                    seen_urls.add(job_data["url"])
                    
                    desc = await self.scrape_job_description(job_data["url"])
                    job_data["description"] = desc
                    jobs_found.append(job_data)
                    print(f"    [LinkedIn] Estratto: {job_data['title']} @ {job_data['company']} ({len(desc)} car)", flush=True)
                    await page.wait_for_timeout(600)
                    
                    if len(jobs_found) >= max_results:
                        break
                        
            if len(jobs_found) >= max_results or len(job_cards) < 25:
                break
        
        return jobs_found

if __name__ == "__main__":
    # Test script
    async def test():
        scraper = LinkedInScraper()
        jobs = await scraper.run("Python Developer", "Italy", max_results=1)
        for j in jobs:
            print(f"\n--- {j['title']} @ {j['company']} ---")
            print(f"Link: {j['url']}")
            print(f"Descrizione (prime 100 char): {j['description'][:100]}...")
            
    asyncio.run(test())
