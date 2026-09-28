import asyncio
import os
import sys
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from src.scraper.auth_manager import AuthManager

async def debug_job():
    auth_manager = AuthManager("linkedin")
    url = "https://www.linkedin.com/jobs/view/4470890155/"
    
    async with async_playwright() as p:
        context = await auth_manager.get_context(p, headless=True)
        page = await context.new_page()
        print("[*] Visito:", url)
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        with open("linkedin_job_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("[+] HTML salvato in linkedin_job_debug.html")
        await context.close()

if __name__ == "__main__":
    asyncio.run(debug_job())
