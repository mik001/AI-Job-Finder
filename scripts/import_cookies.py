import os
import sys
import json
import subprocess

VPS_HOST = "195.201.148.129"

def normalize_cookie_for_playwright(c):
    """Adatta i campi cookie esportati da Cookie-Editor al formato Playwright storage_state."""
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
    print("🍪 IMPORTATORE RAPIDO COOKIE INDEED (DA BROWSER REALE)")
    print("=" * 65)
    print("\nQuesto strumento prende i cookie di Indeed direttamente dal tuo")
    print("browser quotidiano (Brave, Chrome, Firefox) e li invia al VPS.")
    print("Zero captcha, zero blocchi, affidabilita' 100%!\n")

    cookies_json = None
    
    # 1. Prova a leggere dagli appunti di Windows (se hai cliccato 'Export JSON' in Cookie-Editor)
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        clip = root.clipboard_get().strip()
        if clip.startswith("[") and "indeed" in clip.lower():
            parsed = json.loads(clip)
            if isinstance(parsed, list):
                cookies_json = parsed
                print("[+] Rilevati automaticamente i cookie di Indeed dai tuoi appunti (Copia/Incolla)!")
    except Exception:
        pass

    # 2. Se non sono negli appunti, controlla se c'è un file 'cookies.json' nella cartella
    if not cookies_json and os.path.exists("cookies.json"):
        try:
            with open("cookies.json", "r", encoding="utf-8") as f:
                parsed = json.load(f)
            if isinstance(parsed, list):
                cookies_json = parsed
                print("[+] Rilevati cookie dal file 'cookies.json'!")
        except Exception:
            pass

    # 3. Se non trovati, chiedi all'utente di incollarli o salvarli
    if not cookies_json:
        print("👉 ISTRUZIONI (10 secondi):")
        print("1. Nel tuo browser normale (Brave/Chrome), accedi a https://it.indeed.com")
        print("2. Installa l'estensione gratuita 'Cookie-Editor'")
        print("   (Chrome Web Store: https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)")
        print("3. Clicca sull'icona dell'estensione -> 'Export' -> 'Export as JSON'")
        print("4. Esegui di nuovo questo script (leggera' in automatico gli appunti) oppure incolla qui:")
        print("\nIncolla il JSON esportato e premi INVIO (oppure premi CTRL+C per uscire):")
        try:
            raw_input_text = sys.stdin.read().strip()
            if raw_input_text:
                cookies_json = json.loads(raw_input_text)
        except Exception as e:
            print(f"[-] Errore interpretazione JSON: {e}")
            return

    if not cookies_json:
        print("[-] Nessun cookie valido inserito.")
        return

    # Normalizza
    playwright_cookies = [normalize_cookie_for_playwright(c) for c in cookies_json if isinstance(c, dict) and "name" in c and "value" in c]
    print(f"[*] Elaborati {len(playwright_cookies)} cookie per Indeed.")

    storage_state = {
        "cookies": playwright_cookies,
        "origins": []
    }

    session_file = "indeed_session.json"
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, indent=2)
    print(f"[+] File '{session_file}' creato con successo!")

    # Sincronizza sul server VPS Hetzner
    print(f"\n[*] Sincronizzazione immediata sul server VPS ({VPS_HOST})...")
    try:
        subprocess.run(["scp", session_file, f"root@{VPS_HOST}:/opt/ai-job-finder/{session_file}"], check=True)
        ssh_cmd = (
            f"docker cp /opt/ai-job-finder/{session_file} ai_job_finder_scheduler:/app/{session_file} && "
            f"docker cp /opt/ai-job-finder/{session_file} ai_job_finder_ui:/app/{session_file}"
        )
        subprocess.run(["ssh", f"root@{VPS_HOST}", ssh_cmd], check=True)
        print("\n" + "=" * 65)
        print("🚀 SUCCESSO TOTALE! SESSIONE AGGIORNATA SUL SERVER VPS!")
        print("   I tuoi cookie reali sono ora attivi sul server e dureranno mesi.")
        print("=" * 65)
    except Exception as e:
        print(f"[-] Errore invio VPS: {e}")

if __name__ == '__main__':
    main()
