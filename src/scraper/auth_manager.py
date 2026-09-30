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

    async def get_context(self, p, headless: bool = True, silent: bool = False, load_session: bool = True) -> BrowserContext:
        """
        Creates a browser context. Loads session if exists.
        """
        browser = await p.chromium.launch(headless=headless, args=['--disable-blink-features=AutomationControlled'])
        
        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080},
        }

        if load_session and os.path.exists(self.session_file):
            if not silent: print(f"[+] Trovata sessione esistente per {self.platform}. Caricamento in corso...")
            context = await browser.new_context(storage_state=self.session_file, **context_kwargs)
        else:
            if not silent: print(f"[-] Creazione nuovo contesto pulito per {self.platform}...")
            context = await browser.new_context(**context_kwargs)
            
        return context

    def _fetch_latest_linkedin_otp(self, imap_user: str, imap_pass: str, max_wait_sec: int = 90) -> str:
        """Legge la casella IMAP in attesa del codice PIN inviato da LinkedIn."""
        import imaplib
        import email
        import re
        import time
        from email.utils import parsedate_to_datetime
        from datetime import datetime, timezone, timedelta
        from email.header import decode_header
        
        print(f"[*] [IMAP] In ascolto su {imap_user} per il PIN di verifica LinkedIn (max {max_wait_sec}s)...", flush=True)
        clean_pass = imap_pass.replace(" ", "")
        start_time = time.time()
        folders_to_try = ["LinkedIn", '"[Gmail]/Tutti i messaggi"', "INBOX"]
        
        while time.time() - start_time < max_wait_sec:
            try:
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(imap_user, clean_pass)
                
                for folder in folders_to_try:
                    status, _ = mail.select(folder)
                    if status != "OK":
                        continue
                    
                    status, data = mail.search(None, '(OR FROM "linkedin" SUBJECT "codice")')
                    if status != "OK" or not data or not data[0]:
                        status, data = mail.search(None, '(FROM "linkedin")')
                        
                    if status == "OK" and data and data[0]:
                        mail_ids = data[0].split()
                        for m_id in reversed(mail_ids[-5:]):
                            res, msg_data = mail.fetch(m_id, '(RFC822)')
                            for response_part in msg_data:
                                if isinstance(response_part, tuple):
                                    msg = email.message_from_bytes(response_part[1])
                                    subject = msg.get("Subject", "")
                                    decoded_subj = ""
                                    for part, enc in decode_header(subject):
                                        if isinstance(part, bytes):
                                            decoded_subj += part.decode(enc or "utf-8", errors="ignore")
                                        else:
                                            decoded_subj += str(part)
                                    
                                    # Verifica che l'email sia recente (entro gli ultimi 15 minuti)
                                    date_hdr = msg.get("Date")
                                    if date_hdr:
                                        try:
                                            msg_dt = parsedate_to_datetime(date_hdr)
                                            if msg_dt.tzinfo is None:
                                                msg_dt = msg_dt.replace(tzinfo=timezone.utc)
                                            now = datetime.now(timezone.utc)
                                            if (now - msg_dt).total_seconds() > 900:
                                                continue
                                        except Exception:
                                            pass
                                            
                                    # 1. Cerca PIN a 6 cifre nell'oggetto
                                    subj_codes = re.findall(r'\b(\d{6})\b', decoded_subj)
                                    if subj_codes:
                                        code = subj_codes[0]
                                        print(f"[+] [IMAP] PIN LinkedIn estratto dall'oggetto: {code}", flush=True)
                                        mail.logout()
                                        return code
                                        
                                    # 2. Cerca PIN nel corpo dell'email
                                    body = ""
                                    if msg.is_multipart():
                                        for part in msg.walk():
                                            if part.get_content_type() in ("text/plain", "text/html"):
                                                payload = part.get_payload(decode=True)
                                                if payload:
                                                    body += payload.decode(errors="ignore")
                                    else:
                                        payload = msg.get_payload(decode=True)
                                        if payload:
                                            body = payload.decode(errors="ignore")
                                            
                                    body_codes = re.findall(r'\b(\d{6})\b', body)
                                    if body_codes:
                                        code = body_codes[0]
                                        print(f"[+] [IMAP] PIN LinkedIn estratto dal corpo: {code}", flush=True)
                                        mail.logout()
                                        return code
                mail.logout()
            except Exception:
                pass
            time.sleep(3)
            
        print("[-] [IMAP] Nessun PIN LinkedIn ricevuto entro il tempo limite.", flush=True)
        return ""

    async def _handle_linkedin_login(self, page: Page):
        email = os.getenv("LINKEDIN_EMAIL")
        password = os.getenv("LINKEDIN_PASSWORD")
        imap_user = os.getenv("LINKEDIN_IMAP_USER") or os.getenv("INDEED_IMAP_USER") or email
        imap_pass = os.getenv("LINKEDIN_IMAP_PASSWORD") or os.getenv("INDEED_IMAP_PASSWORD")
        
        if not email or not password:
            raise ValueError("Credenziali LINKEDIN mancanti nel file .env")

        print("\n" + "="*65)
        print("🔑 AUTENTICAZIONE LINKEDIN (ACCESSO RISERVATO - MAI GUEST)")
        print("="*65)
        print(f"[*] Navigazione verso {self.login_url}...", flush=True)
        
        try:
            await page.goto(self.login_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Gestione banner cookie se presente
            try:
                cookie_btn = page.locator("button:has-text('Accetta'), button:has-text('Accept'), button#onetrust-accept-btn-handler").first
                if await cookie_btn.count() > 0 and await cookie_btn.is_visible():
                    await cookie_btn.click()
                    await page.wait_for_timeout(500)
            except Exception:
                pass

            # Loop dinamico di monitoraggio dello stato della pagina (fino a 60 secondi)
            for attempt in range(60):
                await page.wait_for_timeout(1000)
                cur_url = page.url.lower()

                # Caso 1: Siamo già nel feed di LinkedIn
                if "/feed" in cur_url:
                    print("[+] 🎉 Autenticato con successo nel feed di LinkedIn!", flush=True)
                    return

                # Caso 2: Checkpoint PIN di sicurezza rilevato (sfida email)
                pin_input = page.locator("input#input__email_verification_pin, input[name='pin']").first
                has_pin_visible = (await pin_input.count() > 0 and await pin_input.is_visible())
                if "checkpoint" in cur_url or "challenge" in cur_url or has_pin_visible:
                    print("[*] 🛡️ Rilevato Checkpoint di Sicurezza LinkedIn (Richiesta codice email).", flush=True)
                    if not (imap_user and imap_pass):
                        raise RuntimeError("Credenziali IMAP mancanti per risolvere il checkpoint PIN LinkedIn.")
                    
                    pin = self._fetch_latest_linkedin_otp(imap_user, imap_pass, max_wait_sec=90)
                    if not pin:
                        raise RuntimeError("Impossibile recuperare il PIN LinkedIn dalla casella email entro il timeout.")
                    
                    print(f"[*] Inserimento PIN LinkedIn ({pin})...", flush=True)
                    if await pin_input.count() > 0:
                        await pin_input.fill(pin)
                    else:
                        txt_inp = page.locator("input[type='text']:visible, input[type='tel']:visible, input[type='number']:visible").first
                        await txt_inp.fill(pin)
                        
                    await page.wait_for_timeout(500)
                    pin_btn = page.locator("button#email-pin-submit-button, button[type='submit']:visible, button:has-text('Invia'), button:has-text('Submit')").first
                    if await pin_btn.count() > 0:
                        await pin_btn.click()
                    else:
                        await pin_input.press("Enter")
                    
                    print("[*] PIN inviato. Attesa redirect a /feed/...", flush=True)
                    for _ in range(20):
                        await page.wait_for_timeout(1000)
                        if "/feed" in page.url.lower():
                            print("[+] 🎉 Checkpoint superato con successo! Login LinkedIn completato.", flush=True)
                            return
                    continue

                # Caso 3: Modulo di Login visibile (email / password)
                pass_field = page.locator("input#password:visible, input#session_password:visible, input[type='password']:visible").first
                if await pass_field.count() > 0:
                    user_field = page.locator("input#username:visible, input#session_key:visible, input[type='email']:visible, input[type='text']:visible").first
                    if await user_field.count() > 0:
                        try:
                            user_val = await user_field.input_value()
                            if not user_val:
                                print(f"[*] Inserimento email: {email}", flush=True)
                                await user_field.fill(email)
                                await page.wait_for_timeout(300)
                        except Exception:
                            pass
                    
                    print("[*] Inserimento password LinkedIn...", flush=True)
                    await pass_field.fill(password)
                    await page.wait_for_timeout(300)
                    
                    submit_btn = page.locator("button[type='submit']:visible, button.btn__primary--large:visible").first
                    if await submit_btn.count() > 0:
                        await submit_btn.click()
                    else:
                        await pass_field.press("Enter")
                    print("[*] Credenziali inviate. Attesa risposta da LinkedIn...", flush=True)
                    await page.wait_for_timeout(3000)
                    continue

            # Se dopo tutti i tentativi non siamo su /feed/
            if "/feed" in page.url.lower():
                print("[+] Login LinkedIn completato con successo.", flush=True)
                return
            else:
                raise RuntimeError(f"Login LinkedIn fallito. URL di destinazione: {page.url}")
                
        except Exception as e:
            print(f"[-] Errore durante il login LinkedIn: {e}", flush=True)
            try:
                os.makedirs("data", exist_ok=True)
                await page.screenshot(path="data/linkedin_login_error.png")
                print("[-] Screenshot salvato in data/linkedin_login_error.png", flush=True)
            except Exception:
                pass
            raise e

    async def perform_login_if_needed(self):
        """
        Controlla se siamo già loggati e, in caso contrario, esegue il login e salva la sessione.
        """
        async with async_playwright() as p:
            # Apriamo inizialmente headless per controllare se la sessione funziona
            context = await self.get_context(p, headless=True, silent=True)
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)
            
            needs_login = False
            
            print(f"[*] Verifico lo stato del login su {self.platform}...", flush=True)
            if self.platform == "linkedin":
                if not os.path.exists(self.session_file):
                    needs_login = True
                else:
                    try:
                        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
                        await page.wait_for_timeout(2000)
                        cur = page.url.lower()
                        if "login" in cur or "signup" in cur or "checkpoint" in cur or "uas" in cur or "/feed" not in cur:
                            needs_login = True
                        else:
                            # Verifichiamo la presenza di elementi autenticati
                            nav = page.locator("nav.global-nav, .global-nav__me, a[href*='/in/'], button:has-text('Avvia un post'), div.feed-shared-update-v2")
                            if await nav.count() == 0:
                                needs_login = True
                    except Exception as e:
                        print(f"[-] Controllo sessione LinkedIn: {e}", flush=True)
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
                print(f"[*] Sessione scaduta o inesistente per {self.platform}. Avvio procedura di autenticazione...", flush=True)
                import sys
                force_headless = os.getenv("HEADLESS", "true").lower() in ("true", "1") or (sys.platform != "win32" and not os.getenv("DISPLAY"))
                context = await self.get_context(p, headless=force_headless, load_session=False)
                page = await context.new_page()
                await Stealth().apply_stealth_async(page)
                
                if self.platform == "linkedin":
                    await self._handle_linkedin_login(page)
                elif self.platform == "indeed":
                    await self._handle_indeed_login(page)
                
                # Salviamo la sessione aggiornata
                await context.storage_state(path=self.session_file)
                print(f"[+] Sessione salvata con successo in {self.session_file}", flush=True)
                await context.close()
            else:
                print(f"[+] Sessione valida per {self.platform}.", flush=True)

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
