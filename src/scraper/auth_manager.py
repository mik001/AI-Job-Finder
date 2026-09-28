import os
import json
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import Stealth
from dotenv import load_dotenv

load_dotenv()

class AuthManager:
    def __init__(self, platform: str, session_file: str = "session.json"):
        self.platform = platform
        self.session_file = f"{platform}_{session_file}"
        self.login_url = self._get_login_url()

    def _get_login_url(self) -> str:
        urls = {
            "linkedin": "https://www.linkedin.com/login",
            "indeed": "https://secure.indeed.com/account/login",
            "glassdoor": "https://www.glassdoor.it/profile/login_input.htm",
            "wellfound": "https://wellfound.com/login"
        }
        return urls.get(self.platform, "")

    async def get_context(self, p, headless: bool = True, silent: bool = False) -> BrowserContext:
        """
        Creates a browser context. Loads session if exists.
        """
        browser = await p.chromium.launch(headless=headless, args=['--disable-blink-features=AutomationControlled'])
        
        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080},
        }

        if os.path.exists(self.session_file):
            if not silent: print(f"[+] Trovata sessione esistente per {self.platform}. Caricamento in corso...")
            context = await browser.new_context(storage_state=self.session_file, **context_kwargs)
        else:
            if not silent: print(f"[-] Nessuna sessione trovata per {self.platform}. Creazione nuovo contesto...")
            context = await browser.new_context(**context_kwargs)
            
        return context

    async def _handle_linkedin_login(self, page: Page):
        email = os.getenv("LINKEDIN_EMAIL")
        password = os.getenv("LINKEDIN_PASSWORD")
        
        if not email or not password:
            raise ValueError("Credenziali LINKEDIN mancanti nel file .env")

        try:
            await page.goto(self.login_url)
            # LinkedIn cambia spesso gli ID e inserisce honeypot nascosti. Filtriamo solo gli elementi visibili.
            user_sel = "input#username:visible, input#session_key:visible, input[autocomplete='username']:visible, input[type='email']:visible, input[type='text']:visible"
            pass_sel = "input#password:visible, input#session_password:visible, input[type='password']:visible"
            
            # 1. Cerchiamo l'email (se c'è la pagina "Bentornato", potrebbe mancare)
            try:
                await page.wait_for_selector(user_sel, timeout=5000)
                await page.locator(user_sel).first.type(email, delay=100)
            except:
                print("[*] Campo email non trovato. Probabile schermata 'Piacere di rivederti'.")
            
            # 2. Inseriamo la password
            await page.wait_for_selector(pass_sel, timeout=10000)
            await page.locator(pass_sel).first.type(password, delay=100)
            
            # Click e attesa navigazione
            # Premiamo semplicemente Invio per fare submit ed evitare altri honeypot invisibili
            await page.keyboard.press("Enter")
            
            # Attendi che il feed si carichi per confermare il login
            await page.wait_for_url("**/feed/**", timeout=20000)
            print("[+] Login LinkedIn completato con successo.")
        except Exception as e:
            print(f"[-] Errore durante il login: {e}")
            await page.screenshot(path="linkedin_login_error.png")
            raise e

    async def perform_login_if_needed(self):
        """
        Controlla se siamo già loggati e, in caso contrario, esegue il login e salva la sessione.
        Mostra una finestra non-headless se il login è necessario, per eventuali captcha.
        """
        async with async_playwright() as p:
            # Apriamo inizialmente headless per controllare se la sessione funziona
            context = await self.get_context(p, headless=True)
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)
            
            needs_login = False
            
            print(f"[*] Verifico lo stato del login su {self.platform}...")
            if self.platform == "linkedin":
                await page.goto("https://www.linkedin.com/feed/")
                if "login" in page.url or "signup" in page.url:
                    needs_login = True
            # TODO: Aggiungere check per altre piattaforme
            
            await context.close()

            if needs_login:
                print(f"[*] Sessione scaduta o inesistente per {self.platform}. Avvio procedura di login...")
                # Riapriamo in modalità visibile (headless=False) nel caso ci sia un Captcha
                context = await self.get_context(p, headless=False)
                page = await context.new_page()
                await Stealth().apply_stealth_async(page)
                
                if self.platform == "linkedin":
                    await self._handle_linkedin_login(page)
                
                # Salviamo la sessione
                await context.storage_state(path=self.session_file)
                print(f"[+] Sessione salvata in {self.session_file}")
                await context.close()
            else:
                print(f"[+] Sessione valida per {self.platform}.")

if __name__ == "__main__":
    # Test script veloce
    async def test():
        manager = AuthManager("linkedin")
        await manager.perform_login_if_needed()
    
    asyncio.run(test())
