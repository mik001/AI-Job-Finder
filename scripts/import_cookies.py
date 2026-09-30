import os
import sys
import json
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

VPS_HOST = "195.201.148.129"

def normalize_cookie_for_playwright(c):
    same_site_map = {
        "no_restriction": "None",
        "lax": "Lax",
        "strict": "Strict",
        "unspecified": "None"
    }
    raw_ss = str(c.get("sameSite", "None")).lower()
    same_site = same_site_map.get(raw_ss, "None")
    
    expires = c.get("expirationDate") or c.get("expires") or -1
    
    return {
        "name": c["name"],
        "value": c["value"],
        "domain": c["domain"],
        "path": c.get("path", "/"),
        "expires": expires,
        "httpOnly": bool(c.get("httpOnly", False)),
        "secure": bool(c.get("secure", True)),
        "sameSite": same_site
    }

def main():
    print("=" * 65)
    print(">>> IMPORTATORE RAPIDO COOKIE INDEED (DA BROWSER REALE) <<<")
    print("=" * 65)

    cookies_json = None
    
    # 1. Prova a leggere da cookies.json se presente
    if os.path.exists("cookies.json"):
        try:
            with open("cookies.json", "r", encoding="utf-8") as f:
                parsed = json.load(f)
            if isinstance(parsed, list) and len(parsed) > 0:
                cookies_json = parsed
                print(f"[+] Rilevati {len(parsed)} cookie dal file 'cookies.json'!")
        except Exception:
            pass

    # 2. Prova a leggere dagli appunti di Windows via PowerShell
    if not cookies_json:
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=5
            )
            raw = res.stdout.strip()
            if raw.startswith("[") and ("indeed" in raw.lower() or "passport" in raw.lower()):
                parsed = json.loads(raw)
                if isinstance(parsed, list) and len(parsed) > 0:
                    cookies_json = parsed
                    print(f"[+] Rilevati automaticamente {len(parsed)} cookie di Indeed dagli appunti!")
        except Exception:
            pass

    if not cookies_json:
        print("[-] Nessun cookie rilevato negli appunti o in cookies.json.")
        print("👉 Assicurati di aver cliccato 'Export as JSON' in Cookie-Editor.")
        return

    # Normalizza per Playwright
    playwright_cookies = [
        normalize_cookie_for_playwright(c) 
        for c in cookies_json 
        if isinstance(c, dict) and "name" in c and "value" in c
    ]
    print(f"[*] Elaborati {len(playwright_cookies)} cookie per Indeed.")

    storage_state = {
        "cookies": playwright_cookies,
        "origins": []
    }

    session_file = "indeed_session.json"
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, indent=2)
    print(f"[+] File '{session_file}' creato con successo in locale!")

    # Sincronizza sul server VPS Hetzner (il file e' in bind-mount nei container)
    print(f"\n[*] Sincronizzazione immediata sul server VPS ({VPS_HOST})...")
    try:
        subprocess.run(["scp", session_file, f"root@{VPS_HOST}:/opt/ai-job-finder/{session_file}"], check=True)
        print("\n" + "=" * 65)
        print(">>> SUCCESSO TOTALE! SESSIONE AGGIORNATA SUL SERVER VPS! <<<")
        print("   I tuoi cookie reali sono ora attivi sul server e dureranno mesi.")
        print("=" * 65)
    except Exception as e:
        print(f"[-] Errore invio VPS: {e}")

if __name__ == '__main__':
    main()
