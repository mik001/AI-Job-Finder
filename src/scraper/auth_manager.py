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
            elif self.platform == "indeed":
                if not os.path.exists(self.session_file):
                    needs_login = True
                else:
                    try:
                        await page.goto("https://it.indeed.com/", wait_until="domcontentloaded", timeout=15000)
                        await page.wait_for_timeout(1500)
                        if "auth" in page.url or "login" in page.url:
                            needs_login = True
                        else:
                            # Verifichiamo se compare il pulsante di accesso non autenticato
                            accedi = page.locator("a[href*='secure.indeed.com/auth'], a:has-text('Accedi')")
                            profile = page.locator("a[data-gnav-element-name='Profile'], [aria-label*='Profilo'], [aria-label*='Account']")
                            if await accedi.count() > 0 and await profile.count() == 0:
                                needs_login = True
                    except Exception:
                        needs_login = True
            
            await context.close()

            if needs_login:
                print(f"[*] Sessione scaduta o inesistente per {self.platform}. Avvio procedura di login...")
                # Riapriamo in modalità visibile (headless=False) per permettere all'utente di inserire il codice OTP
                context = await self.get_context(p, headless=False)
                page = await context.new_page()
                await Stealth().apply_stealth_async(page)
                
                if self.platform == "linkedin":
                    await self._handle_linkedin_login(page)
                elif self.platform == "indeed":
                    await self._handle_indeed_login(page)
                
                # Salviamo la sessione
                await context.storage_state(path=self.session_file)
                print(f"[+] Sessione salvata in {self.session_file}")
                await context.close()
            else:
                print(f"[+] Sessione valida per {self.platform}.")

    def _fetch_latest_indeed_otp(self, imap_user: str, imap_pass: str, max_wait_sec: int = 60) -> str:
        """Legge la casella IMAP in attesa del codice OTP inviato da Indeed."""
        import imaplib
        import email
        import re
        import time
        from email.utils import parsedate_to_datetime
        from datetime import datetime, timezone, timedelta
        
        print(f"[*] [IMAP] In ascolto su {imap_user} per l'email con il codice Indeed (max {max_wait_sec}s)...")
        clean_pass = imap_pass.replace(" ", "")
        start_time = time.time()
        
        while time.time() - start_time < max_wait_sec:
            try:
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(imap_user, clean_pass)
                mail.select("INBOX")
                
                status, data = mail.search(None, '(OR FROM "indeed" SUBJECT "Indeed")')
                if status == "OK" and data[0]:
                    mail_ids = data[0].split()
                    for m_id in reversed(mail_ids[-5:]):
                        res, msg_data = mail.fetch(m_id, '(RFC822)')
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                date_hdr = msg.get("Date")
                                if date_hdr:
                                    try:
                                        msg_dt = parsedate_to_datetime(date_hdr)
                                        now = datetime.now(timezone.utc)
                                        if now - msg_dt > timedelta(minutes=10):
                                            continue
                                    except Exception:
                                        pass
                                        
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        ctype = part.get_content_type()
                                        if ctype == "text/plain":
                                            body += part.get_payload(decode=True).decode(errors="ignore")
                                        elif ctype == "text/html":
                                            body += part.get_payload(decode=True).decode(errors="ignore")
                                else:
                                    body = msg.get_payload(decode=True).decode(errors="ignore")
                                    
                                codes = re.findall(r'\b(\d{6})\b', body)
                                if codes:
                                    code = codes[0]
                                    print(f"[+] [IMAP] Codice OTP intercettato: {code}")
                                    mail.logout()
                                    return code
                mail.logout()
            except Exception as e:
                pass
            time.sleep(3)
            
        print("[-] [IMAP] Nessun codice OTP ricevuto entro il timeout.")
        return ""

    async def _handle_indeed_login(self, page: Page):
        """
        Gestisce il login su Indeed:
        - Se sono configurate le credenziali IMAP, estrae l'OTP e fa login in modo 100% autonomo.
        - Altrimenti, apre la schermata e attende l'inserimento manuale del codice da parte dell'utente.
        """
        print("\n" + "="*65)
        print("🔑 AUTENTICAZIONE INDEED (AUTO-RECOVERY / RINNOVO SESSIONE)")
        print("="*65)
        print("[*] Apertura schermata di login Indeed...")
        await page.goto(self.login_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        # Gestione banner cookie
        try:
            cookie_btn = page.locator("button#onetrust-accept-btn-handler, button:has-text('Accetta tutti i cookie'), button:has-text('Rifiuta tutti')").first
            if await cookie_btn.count() > 0:
                await cookie_btn.click()
                await page.wait_for_timeout(500)
        except Exception:
            pass
            
        indeed_email = os.getenv("INDEED_EMAIL")
        imap_pass = os.getenv("INDEED_IMAP_PASSWORD")
        imap_user = os.getenv("INDEED_IMAP_USER") or indeed_email
        
        if indeed_email:
            try:
                email_input = page.locator("input[type='email'], input[name='__email']").first
                if await email_input.count() > 0:
                    await email_input.fill(indeed_email)
                    print(f"[*] Inserita email configurata: {indeed_email}")
                    await email_input.press("Enter")
                    await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"[-] Compilazione email: {e}")
                
            # Se compare il link per accedere con codice numerico invece di Google SSO
            codice_link = page.locator("a:has-text('Accedi con un codice'), button:has-text('Accedi con un codice')")
            if await codice_link.count() > 0:
                print("[*] Clic su 'Accedi con un codice'...")
                await codice_link.first.click()
                await page.wait_for_timeout(2000)
                
            # Se abbiamo le credenziali IMAP configurate, estraiamo l'OTP automaticamente
            if imap_user and imap_pass:
                print("[*] Rilevate credenziali IMAP: avvio estrazione autonoma del codice OTP...")
                otp = self._fetch_latest_indeed_otp(imap_user, imap_pass, max_wait_sec=60)
                if otp:
                    print(f"[*] Inserimento automatico codice OTP {otp}...")
                    code_input = page.locator("input#passcode-input, input[name='passcode']").first
                    if await code_input.count() > 0:
                        await code_input.fill(otp)
                        await page.wait_for_timeout(500)
                        await code_input.press("Enter")
                    else:
                        text_inp = page.locator("input[type='text']:visible, input:not([type='hidden']):visible").first
                        if await text_inp.count() > 0:
                            await text_inp.fill(otp)
                            await text_inp.press("Enter")
                            
                    # Attesa finalizzazione login
                    for _ in range(15):
                        await page.wait_for_timeout(2000)
                        cur_url = page.url
                        if "indeed.com" in cur_url and "/auth" not in cur_url and "login" not in cur_url:
                            print("[+] Login Indeed completato con successo in modalità 100% autonoma!")
                            return
                            
        print("\n👉 ISTRUZIONI PER L'ACCESSO MANUALE:")
        print("   1. Nella finestra del browser aperta, completa l'inserimento dell'email e del codice OTP.")
        print("   2. Una volta completato il login, questo script salverà automaticamente la sessione.")
        print("   (La sessione dura mesi e sbloccherà la paginazione su tutte le pagine successive!)\n")
        
        # Polling attesa completamento login manuale (fino a 180 secondi)
        for _ in range(90):
            await asyncio.sleep(2)
            try:
                current_url = page.url
                if "indeed.com" in current_url and "/auth" not in current_url and "login" not in current_url and "security check" not in current_url.lower():
                    cookies = await page.context.cookies()
                    has_session = any("SESSION" in c["name"].upper() or "CTK" in c["name"].upper() or "ACCOUNT" in c["name"].upper() for c in cookies)
                    if has_session:
                        print(f"[+] Login Indeed completato con successo! Cattura sessione in corso...")
                        await page.wait_for_timeout(2000)
                        return
            except Exception:
                pass
                
        print("[-] Tempo per il login scaduto (180s). Se hai effettuato l'accesso, la sessione verrà comunque salvata.")

if __name__ == "__main__":
    import sys
    target_platform = sys.argv[1] if len(sys.argv) > 1 else "linkedin"
    
    async def run_auth():
        print(f"[*] Avvio AuthManager per: {target_platform.upper()}")
        manager = AuthManager(target_platform)
        await manager.perform_login_if_needed()
    
    asyncio.run(run_auth())
