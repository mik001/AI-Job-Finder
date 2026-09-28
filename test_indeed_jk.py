import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

async def test_indeed_jk():
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
        
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        
        # Cerchiamo gli elementi con data-jk
        jk_elements = soup.find_all(lambda tag: tag.has_attr("data-jk"))
        print(f"[+] Elementi con 'data-jk' trovati: {len(jk_elements)}")
        
        if jk_elements:
            jk = jk_elements[0]["data-jk"]
            direct_url = f"https://it.indeed.com/viewjob?jk={jk}"
            print(f"[*] Navigazione verso URL canonico pulito: {direct_url}")
            
            await page.goto(direct_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)
            
            job_html = await page.content()
            job_soup = BeautifulSoup(job_html, "html.parser")
            
            title = job_soup.find("h1")
            title_text = title.text.strip() if title else "N/D"
            
            desc_div = job_soup.find("div", id="jobDescriptionText") or job_soup.find(class_=lambda c: c and "jobsearch-jobDescriptionText" in c)
            
            if desc_div:
                desc_text = desc_div.get_text(separator="\n", strip=True)
                print(f"[+] SUCCESSO! Titolo: {title_text}")
                print(f"[+] Descrizione estratta: {len(desc_text)} caratteri!")
                print(f"Prime 200 parole:\n{desc_text[:200]}")
            else:
                print("[-] Descrizione non trovata sul direct URL.")
                print(f"Titolo pagina: {await page.title()}")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_indeed_jk())
