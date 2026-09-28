import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

async def test_indeed_description():
    url = "https://it.indeed.com/jobs?q=Risorse+Umane&l=Italia&fromage=1&sort=date"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        await Stealth().apply_stealth_async(context)
        page = await context.new_page()
        
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # Accetta cookie se presenti
        try:
            cookie_btn = page.locator("button#onetrust-accept-btn-handler")
            if await cookie_btn.count() > 0:
                await cookie_btn.first.click()
                await page.wait_for_timeout(1000)
        except:
            pass
            
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        
        cards = soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in c) or soup.find_all("div", class_=lambda c: c and "cardOutline" in c)
        
        if cards:
            first_card = cards[0]
            # Cerchiamo il link o il job key (jk)
            link_tag = first_card.find("a", href=True)
            job_url = ""
            if link_tag:
                href = link_tag["href"]
                if href.startswith("/"):
                    job_url = "https://it.indeed.com" + href
                else:
                    job_url = href
                    
            print(f"[*] URL dell'annuncio: {job_url}")
            
            # Navighiamo direttamente alla pagina del lavoro
            await page.goto(job_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            
            job_html = await page.content()
            job_soup = BeautifulSoup(job_html, "html.parser")
            
            # Su Indeed la descrizione completa risiede classicamente in #jobDescriptionText
            desc_div = job_soup.find("div", id="jobDescriptionText") or job_soup.find("div", class_="jobsearch-jobDescriptionText")
            
            if desc_div:
                desc_text = desc_div.get_text(separator="\n", strip=True)
                print(f"[+] Descrizione estratta con successo! ({len(desc_text)} caratteri)")
                print("\nAnteprima descrizione:")
                print(desc_text[:300])
            else:
                print("[-] Impossibile trovare #jobDescriptionText. Ispezione in corso...")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_indeed_description())
