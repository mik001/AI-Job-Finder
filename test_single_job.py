import asyncio
import os
from playwright.async_api import async_playwright
from src.scraper.linkedin_scraper import LinkedInScraper

async def test_single_job():
    scraper = LinkedInScraper()
    await scraper.auth_manager.perform_login_if_needed()
    await scraper.init_browser()
    
    print("\n[*] Eseguo una singola query per catturare SOLO 1 annuncio...")
    
    # Prendi SOLO il primo annuncio
    jobs = await scraper.run(keywords="Developer", location="Italia", max_results=1)
    
    if jobs:
        j = jobs[0]
        print("\n" + "="*50)
        print("RISULTATI ESTRAZIONE SINGOLO ANNUNCIO:")
        print("="*50)
        print(f"TITOLO  : {j.get('title')}")
        print(f"AZIENDA : {j.get('company')}")
        print(f"URL     : {j.get('url')}")
        print("-"*50)
        desc = j.get('description', '')
        print(f"LUNGHEZZA DESC: {len(desc)} caratteri")
        print(f"PRIMI 200 CARATTERI DELLA DESCRIZIONE:\n{desc[:200]}")
        print("="*50)
    else:
        print("[-] Nessun annuncio trovato!")
        
    await scraper.close_browser()

if __name__ == "__main__":
    asyncio.run(test_single_job())
