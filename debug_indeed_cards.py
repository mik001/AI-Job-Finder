import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def debug_escape():
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
        await page.wait_for_timeout(2000)
        
        # Cookie
        try:
            btn = page.locator("button#onetrust-accept-btn-handler")
            if await btn.count() > 0:
                await btn.first.click()
                await page.wait_for_timeout(500)
        except:
            pass
            
        job_links = page.locator("h2.jobTitle a, a.jcs-JobTitle")
        count = await job_links.count()
        print(f"Trovati {count} annunci.")
        
        for i in range(min(count, 5)):
            link = job_links.nth(i)
            title = await link.inner_text()
            print(f"\n[*] Annuncio {i+1}: {title}")
            
            # Premiamo Escape per chiudere qualsiasi modal o dialog
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)
            
            # Clicchiamo via javascript o con force=True
            await page.evaluate("(el) => el.click()", await link.element_handle())
            await page.wait_for_timeout(1000)
            
            pane = page.locator("#jobsearch-ViewjobPaneWrapper")
            if await pane.count() > 0:
                text = await pane.inner_text()
                print(f"  [+] Descrizione estratta ({len(text)} caratteri)")
            else:
                print("  [-] Nessun pannello.")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_escape())
