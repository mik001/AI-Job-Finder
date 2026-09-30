#!/usr/bin/env python3
"""
Script per il rinnovo interattivo / autonomo della sessione Indeed tramite Camoufox.
Esegue il login su Windows (IP residenziale Iliadbox) con impronta Firefox stealth,
estrae l'OTP fresco via IMAP Gmail, salva 'indeed_session.json' e la sincronizza istantaneamente sul VPS Hetzner.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

import time
import json
import imaplib
import email
import re
import asyncio
import subprocess
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

load_dotenv(".env")

INDEED_EMAIL = os.getenv("INDEED_EMAIL")
IMAP_USER = os.getenv("INDEED_IMAP_USER") or INDEED_EMAIL
IMAP_PASS = os.getenv("INDEED_IMAP_PASSWORD")
VPS_HOST = "195.201.148.129"

def fetch_latest_indeed_otp(imap_user: str, imap_pass: str, min_timestamp: float, max_wait_sec: int = 60) -> str:
    """Intercetta l'OTP inviato da Indeed via IMAP Gmail dopo min_timestamp."""
    print(f"[*] [IMAP] In ascolto su {imap_user} per il nuovo codice Indeed (max {max_wait_sec}s)...", flush=True)
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
                            
                            # Filtro temporale: solo email fresche
                            date_hdr = msg.get("Date")
                            if date_hdr:
                                try:
                                    msg_dt = parsedate_to_datetime(date_hdr)
                                    msg_ts = msg_dt.timestamp()
                                    if msg_ts < (min_timestamp - 30):
                                        continue
                                except Exception:
                                    pass

                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() in ("text/plain", "text/html"):
                                        body += part.get_payload(decode=True).decode(errors="ignore")
                            else:
                                body = msg.get_payload(decode=True).decode(errors="ignore")
                                
                            codes = re.findall(r'\b(\d{6})\b', body)
                            if codes:
                                code = codes[0]
                                print(f"[+] [IMAP] Codice OTP fresco intercettato: {code}", flush=True)
                                mail.logout()
                                return code
            mail.logout()
        except Exception:
            pass
        time.sleep(3)
        
    print("[-] [IMAP] Nessun codice OTP fresco ricevuto entro il timeout.", flush=True)
    return ""

async def login_indeed():
    from camoufox.async_api import AsyncCamoufox
    import camoufox
    
    print("=" * 65)
    print("🦊 RINNOVO SESSIONE INDEED TRAMITE CAMOUFOX (STEALTH ANTIDETECT)")
    print("=" * 65)
    print(f"[*] Account configurato: {INDEED_EMAIL}")
    print("[*] Avvio finestra Camoufox visibile sul tuo desktop...")

    async with AsyncCamoufox(
        headless=False,
        humanize=True,
        os="windows",
        exclude_addons=[camoufox.DefaultAddons.UBO]
    ) as browser:
        context = await browser.new_context(
            locale="it-IT",
            timezone_id="Europe/Rome"
        )
        page = await context.new_page()

        login_url = "https://secure.indeed.com/account/login"
        print(f"[*] Apertura schermata di login: {login_url}...", flush=True)
        await page.goto(login_url, wait_until="domcontentloaded", timeout=30000)

        print("\n" + "=" * 65)
        print("👉 IMPORTANTE: Se sulla finestra del browser compare la schermata")
        print("   'Ulteriore verifica richiesta' di Cloudflare,")
        print("   fai clic con il mouse sulla casella 'Stiamo verificando che tu non sia un robot'!")
        print("=" * 65 + "\n", flush=True)

        # Fase 1: Attesa superamento Cloudflare Turnstile
        for sec in range(90):
            await page.wait_for_timeout(1000)
            cur_title = await page.title()
            cur_url = page.url.lower()

            # Verifichiamo se compare il campo email
            email_inp = page.locator("input[type='email'], input[name='__email'], input#ifl-InputFormField-3").first
            if await email_inp.count() > 0 and await email_input_visible(email_inp):
                print(f"[+] Cloudflare superato! Form di login visibile dopo {sec}s.", flush=True)
                break

            if sec % 10 == 0:
                print(f"[{sec}s] In attesa verifica Cloudflare... (Titolo: '{cur_title}')", flush=True)

        # Fase 2: Inserimento Email
        time_before_otp = time.time()
        email_inp = page.locator("input[type='email'], input[name='__email'], input#ifl-InputFormField-3").first
        if await email_inp.count() > 0:
            print(f"[*] Compilazione email ({INDEED_EMAIL})...", flush=True)
            await email_inp.fill(INDEED_EMAIL)
            await page.wait_for_timeout(400)
            await email_inp.press("Enter")
            await page.wait_for_timeout(2500)

            # Controllo 'Accedi con un codice'
            codice_link = page.locator("a:has-text('Accedi con un codice'), button:has-text('Accedi con un codice')").first
            if await codice_link.count() > 0:
                print("[*] Clic su 'Accedi con un codice'...", flush=True)
                await codice_link.click()
                await page.wait_for_timeout(2000)
                time_before_otp = time.time()

            # Estrazione e inserimento OTP automatico via IMAP
            if IMAP_USER and IMAP_PASS:
                otp = fetch_latest_indeed_otp(IMAP_USER, IMAP_PASS, min_timestamp=time_before_otp, max_wait_sec=60)
                if otp:
                    print(f"[*] Inserimento codice OTP: {otp}...", flush=True)
                    code_input = page.locator("input#passcode-input, input[name='passcode'], input[type='tel']").first
                    if await code_input.count() > 0 and await code_input.is_visible():
                        await code_input.fill(otp)
                    else:
                        txt_inp = page.locator("input[type='text']:visible").first
                        if await txt_inp.count() > 0:
                            await txt_inp.fill(otp)
                    
                    await page.wait_for_timeout(500)
                    submit_btn = page.locator("button[type='submit']:visible, button:has-text('Continua'):visible, button:has-text('Accedi'):visible, button:has-text('Verifica'):visible").first
                    if await submit_btn.count() > 0:
                        print("[*] Clic su pulsante di conferma...", flush=True)
                        await submit_btn.click()
                    else:
                        print("[*] Invio Enter su input OTP...", flush=True)
                        if await code_input.count() > 0:
                            await code_input.press("Enter")

        print("\n[*] Monitoraggio completamento login (max 120s)...", flush=True)
        print("👉 Se necessario, puoi completare l'autenticazione o confermare i passaggi direttamente dalla finestra.", flush=True)

        logged_in = False
        for sec in range(120):
            await page.wait_for_timeout(1000)
            cur_url = page.url.lower()
            cur_title = await page.title()

            cookies = await context.cookies()
            auth_cookie_names = [c["name"] for c in cookies if any(k in c["name"].upper() for k in ("PASSPORT", "BEARER", "TOKEN", "ACCOUNT", "SHI", "PPID", "CTK"))]

            nav_profile = page.locator("a[data-gnav-element-name='Profile'], [aria-label*='Profilo'], [aria-label*='Account']")
            has_profile = await nav_profile.count() > 0

            has_auth = any("PASSPORT" in c["name"].upper() or "BEARER" in c["name"].upper() for c in cookies)

            if has_profile or (has_auth and "auth" not in cur_url and "login" not in cur_url and "security check" not in cur_title.lower()):
                print(f"[+] 🎉 Login rilevato con successo dopo {sec+1}s!", flush=True)
                logged_in = True
                break

            if sec % 10 == 0:
                print(f"[{sec}s] URL: {cur_url[:50]} | Titolo: {cur_title[:30]} | Cookie auth: {auth_cookie_names}", flush=True)

        if not logged_in:
            cookies = await context.cookies()
            auth_cookie_names = [c["name"] for c in cookies if any(k in c["name"].upper() for k in ("PASSPORT", "BEARER", "TOKEN", "ACCOUNT", "SHI", "PPID", "CTK"))]
            if any("PASSPORT" in name.upper() or "BEARER" in name.upper() for name in auth_cookie_names):
                print(f"[+] Cookie Passport/Bearer rilevati ({auth_cookie_names})! Procedo con il salvataggio.", flush=True)
                logged_in = True
            else:
                os.makedirs("data", exist_ok=True)
                await page.screenshot(path="data/login_timeout_screen.png")
                print("[-] Salvato screenshot di debug in data/login_timeout_screen.png", flush=True)

        if logged_in:
            await page.wait_for_timeout(2000)
            await context.storage_state(path="indeed_session.json")
            print("[+] Sessione salvata con successo in indeed_session.json!", flush=True)

            # Sincronizza sul VPS
            try:
                print(f"[*] Sincronizzazione della nuova sessione sul server VPS ({VPS_HOST})...", flush=True)
                subprocess.run(
                    ["scp", "indeed_session.json", f"root@{VPS_HOST}:/opt/ai-job-finder/indeed_session.json"],
                    check=True
                )
                subprocess.run(
                    ["ssh", f"root@{VPS_HOST}", "docker cp /opt/ai-job-finder/indeed_session.json ai_job_finder_ui:/app/indeed_session.json && docker cp /opt/ai-job-finder/indeed_session.json ai_job_finder_scheduler:/app/indeed_session.json"],
                    check=True
                )
                print("[+] 🎉 Sessione sincronizzata con successo su Hetzner VPS nei container di produzione!", flush=True)
            except Exception as sync_err:
                print(f"[-] Errore sincronizzazione SCP: {sync_err}", flush=True)
        else:
            print("[-] Timeout login. Nessuna nuova sessione catturata.", flush=True)

async def email_input_visible(loc):
    try:
        return await loc.is_visible()
    except Exception:
        return False

if __name__ == "__main__":
    asyncio.run(login_indeed())
