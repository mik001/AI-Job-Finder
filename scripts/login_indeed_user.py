import os
import sys
import json
import asyncio
import subprocess
from playwright.async_api import async_playwright

VPS_HOST = "195.201.148.129"

async def main():
    print("=" * 65)
    print("🔑 ACCESSO INTERATTIVO INDEED (RISOLUZIONE CAPTCHA DA DESKTOP)")
    print("=" * 65)
    print("\nSto aprendo la finestra del browser sul tuo desktop...")
    
    async with async_playwright() as p:
        # Avvia browser visibile con accelerazione grafica reale
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--start-maximized'
            ]
        )
        context = await browser.new_context(
            viewport=None,
            locale="it-IT"
        )
        page = await context.new_page()
        
        print("[*] Navigazione su https://secure.indeed.com/auth ...")
        await page.goto("https://secure.indeed.com/auth", wait_until="domcontentloaded")
        
        print("\n" + "=" * 55)
        print("👉 ADESSO TOCCA A TE NELLA FINESTRA DEL BROWSER APERTA:")
        print("   1. Clicca sul checkbox del captcha Cloudflare col mouse.")
        print("   2. Inserisci la tua email e completa il login.")
        print("   3. Appena sei dentro a Indeed, lo script salvera'")
        print("      la sessione e la inviera' automaticamente al VPS!")
        print("=" * 55 + "\n")
        print("[*] In ascolto del completamento del login...", flush=True)
        
        # Aspetta che l'utente completi il login
        while True:
            await page.wait_for_timeout(1500)
            url = page.url
            if ("indeed.com" in url) and ("auth" not in url) and ("challenge" not in url) and ("login" not in url):
                cookies = await context.cookies()
                has_auth = any("PassportAuthProxy" in c["name"] or "rememberMe" in c["name"] or "SHOE" in c["name"] for c in cookies)
                if has_auth:
                    print(f"\n[+] 🎉 LOGIN COMPLETATO CON SUCCESSO! URL: {url}")
                    break
                    
        # Salva la sessione completa in indeed_session.json
        session_file = "indeed_session.json"
        await context.storage_state(path=session_file)
        print(f"[+] Sessione salvata localmente in '{session_file}'.")
        await browser.close()
        
        # Sincronizza sul VPS Hetzner e nei container Docker
        print(f"\n[*] Sincronizzazione immediata sul VPS Hetzner ({VPS_HOST})...")
        try:
            subprocess.run(["scp", session_file, f"root@{VPS_HOST}:/opt/ai-job-finder/{session_file}"], check=True)
            ssh_cmd = (
                f"docker cp /opt/ai-job-finder/{session_file} ai_job_finder_scheduler:/app/{session_file} && "
                f"docker cp /opt/ai-job-finder/{session_file} ai_job_finder_ui:/app/{session_file}"
            )
            subprocess.run(["ssh", f"root@{VPS_HOST}", ssh_cmd], check=True)
            print("\n" + "=" * 65)
            print("🚀 SUCCESSO TOTALE! SESSIONE AGGIORNATA SUL SERVER DI PRODUZIONE!")
            print("   Il server Hetzner ora ha la sessione valida per mesi.")
            print("=" * 65)
        except Exception as e:
            print(f"[-] Nota upload automatico VPS: {e}")
            print(f"Puoi copiare manualmente '{session_file}' sul server.")

if __name__ == '__main__':
    asyncio.run(main())
