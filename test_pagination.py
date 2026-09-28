import asyncio
import os
import sys
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from src.scraper.auth_manager import AuthManager

async def debug_html():
    auth_manager = AuthManager("linkedin")
    url = "https://www.linkedin.com/jobs/search/?keywords=Developer&location=Italia&sortBy=DD"
    
    async with async_playwright() as p:
        context = await auth_manager.get_context(p, headless=True)
        page = await context.new_page()
        print("[*] Visito:", url)
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        for _ in range(5):
            await page.evaluate("""
                var list = document.querySelector('.jobs-search-results-list');
                if(list) list.scrollBy(0, 2000);
                else window.scrollBy(0, 2000);
            """)
            await page.wait_for_timeout(1000)
            
        html = await page.content()
        with open("linkedin_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("[+] HTML salvato in linkedin_debug.html")
        await context.close()

if __name__ == "__main__":
    asyncio.run(debug_html())
