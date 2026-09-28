import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

async def test_indeed_click_fixed():
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
        
        # Accetta cookie
        try:
            cookie_btn = page.locator("button#onetrust-accept-btn-handler")
            if await cookie_btn.count() > 0:
                await cookie_btn.first.click()
                await page.wait_for_timeout(1000)
        except:
            pass
            
        cards = page.locator("div.cardOutline")
        count = await cards.count()
        print(f"[+] Card (.cardOutline) trovate: {count}")
        
        if count > 0:
            print("[*] Clicco sulla prima card...")
            await cards.first.click()
            await page.wait_for_timeout(2500)
            
            # Leggiamo il pannello destro
            pane = page.locator("#jobsearch-ViewjobPaneWrapper")
            if await pane.count() > 0:
                html = await pane.inner_html()
                soup = BeautifulSoup(html, "html.parser")
                
                title = soup.find("h2") or soup.find("h1")
                title_text = title.text.strip() if title else "N/D"
                
                desc_el = soup.find("div", id="jobDescriptionText") or soup.find("div", class_="jobsearch-jobDescriptionText")
                desc_text = desc_el.get_text(separator="\n", strip=True) if desc_el else soup.get_text(separator="\n", strip=True)
                
                print(f"[+] SUCCESSO TOTALE! Titolo nel pannello: {title_text}")
                print(f"[+] Lunghezza descrizione: {len(desc_text)} caratteri")
                print("\nPrimi 300 caratteri della descrizione:")
                print(desc_text[:300])
            else:
                print("[-] Pannello non trovato.")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_indeed_click_fixed())
