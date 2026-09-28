import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

async def inspect_indeed():
    print("[*] Test esplorativo su Indeed Italia (it.indeed.com)...")
    
    url = "https://it.indeed.com/jobs?q=Risorse+Umane&l=Italia&fromage=1&sort=date"
    print(f"[*] Navigazione verso: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        await Stealth().apply_stealth_async(context)
        page = await context.new_page()
        
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            print(f"[+] Status code risposta: {response.status if response else 'N/D'}")
            await page.wait_for_timeout(3000)
            
            # Gestione cookie banner se presente
            try:
                cookie_btn = page.locator("button#onetrust-accept-btn-handler, button:has-text('Accetta'), button:has-text('Accetto')")
                if await cookie_btn.count() > 0:
                    await cookie_btn.first.click()
                    print("[+] Cookie banner accettato.")
                    await page.wait_for_timeout(1000)
            except Exception as e:
                pass
                
            title = await page.title()
            print(f"[+] Titolo pagina: {title}")
            
            # Verifichiamo se Cloudflare o Captcha è apparso
            content = await page.content()
            if "Just a moment" in title or "Cloudflare" in content or "challenge-running" in content:
                print("[-] Rilevato Cloudflare Challenge / Captcha su Indeed!")
            else:
                print("[+] Nessun blocco Cloudflare immediato rilevato!")
                
            soup = BeautifulSoup(content, "html.parser")
            
            # Selettori standard di Indeed
            # Le card degli annunci sono solitamente: div.job_seen_beacon, td.resultContent, div.cardOutline
            cards = (soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in c) or 
                     soup.find_all("div", class_=lambda c: c and "cardOutline" in c) or
                     soup.find_all("td", class_="resultContent"))
                     
            print(f"[+] Card annunci trovate con selettori base: {len(cards)}")
            
            if cards:
                first = cards[0]
                # Titolo
                title_el = first.find("h2") or first.find("a", class_=lambda c: c and "jcs-JobTitle" in c)
                title_text = title_el.text.strip() if title_el else "N/D"
                
                # Azienda
                comp_el = first.find("span", {"data-testid": "company-name"}) or first.find("span", class_="css-63koeb") or first.find("span", class_=lambda c: c and "company" in c)
                comp_text = comp_el.text.strip() if comp_el else "N/D"
                
                # Sede
                loc_el = first.find("div", {"data-testid": "text-location"}) or first.find("div", class_=lambda c: c and "location" in c)
                loc_text = loc_el.text.strip() if loc_el else "N/D"
                
                print("\nEsempio primo annuncio estratto:")
                print(f"  - Titolo : {title_text}")
                print(f"  - Azienda: {comp_text}")
                print(f"  - Sede   : {loc_text}")
            else:
                # Salviamo HTML per capire la struttura
                with open("indeed_debug.html", "w", encoding="utf-8") as f:
                    f.write(content)
                print("[!] HTML salvato in indeed_debug.html per ispezione classi.")
                
        except Exception as e:
            print(f"[-] Errore durante il test di Indeed: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_indeed())
