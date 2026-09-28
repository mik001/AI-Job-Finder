import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from src.scraper.auth_manager import AuthManager

async def test_pagination_dozens():
    auth_manager = AuthManager("linkedin")
    
    # Query senza filtro 24h per avere migliaia di annunci: "Human Resources" in "Italia"
    base_url = "https://www.linkedin.com/jobs/search/?keywords=Human%20Resources&location=Italia&sortBy=DD&start={start}"
    
    print("[*] Avvio test di paginazione multi-pagina su query ad alto volume...")
    
    async with async_playwright() as p:
        context = await auth_manager.get_context(p, headless=True, silent=True)
        page = await context.new_page()
        
        all_collected_jobs = []
        seen_links = set()
        
        # Testiamo 3 pagine: start=0 (pag 1), start=25 (pag 2), start=50 (pag 3)
        for page_idx, start in enumerate([0, 25, 50], start=1):
            url = base_url.format(start=start)
            print(f"\n[*] --- Navigazione Pagina {page_idx} (start={start}) ---")
            print(f"[*] URL: {url}")
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            
            # Scroll progressivo per caricare lazy-content
            for s in range(5):
                await page.evaluate("""
                    var el = document.querySelector('.scaffold-layout__list') || 
                             document.querySelector('.jobs-search-results-list') || 
                             document.querySelector('div.jobs-search-two-pane__layout');
                    if (el) el.scrollBy(0, 1500);
                    else window.scrollBy(0, 1500);
                """)
                await page.wait_for_timeout(800)
                
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            job_cards = (soup.find_all("div", class_="job-card-container") or 
                         soup.find_all("div", class_="base-card") or 
                         soup.find_all("li", class_="jobs-search-results__list-item"))
            
            page_jobs = []
            for card in job_cards:
                # Estrazione link
                a_tags = card.find_all("a", href=True)
                for a in a_tags:
                    if "/jobs/view/" in a["href"]:
                        clean_url = a["href"].split("?")[0]
                        if not clean_url.startswith("http"):
                            clean_url = "https://www.linkedin.com" + clean_url
                        
                        # Titolo
                        title = a.text.strip().split("\n")[0].strip()
                        if not title:
                            title_el = card.find("h3") or card.find("strong")
                            title = title_el.text.strip().split("\n")[0].strip() if title_el else "N/D"
                            
                        # Azienda
                        comp_el = (card.find("div", class_="artdeco-entity-lockup__subtitle") or 
                                   card.find("span", class_="job-card-container__primary-description") or 
                                   card.find("a", class_=lambda x: x and "company" in x))
                        company = comp_el.text.strip().split("\n")[0].strip() if comp_el else "N/D"
                        
                        if clean_url not in seen_links:
                            seen_links.add(clean_url)
                            page_jobs.append({"title": title, "company": company, "url": clean_url})
                        break
                        
            print(f"[+] Pagina {page_idx}: Trovate {len(job_cards)} card HTML, di cui {len(page_jobs)} annunci unici nuovi.")
            all_collected_jobs.extend(page_jobs)
            
            # Mostra i primi 3 di questa pagina
            for idx, j in enumerate(page_jobs[:3], 1):
                print(f"    {idx}. {j['title']} @ {j['company']} ({j['url']})")
                
        print("\n" + "="*60)
        print(f"TOTALE COMPLESSIVO ESTRATTO NELLE 3 PAGINE: {len(all_collected_jobs)} annunci!")
        print("="*60)
        await context.close()

if __name__ == "__main__":
    asyncio.run(test_pagination_dozens())
