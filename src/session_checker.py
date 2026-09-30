import os
import sys
import json
import time
import base64
import logging
from datetime import datetime
from typing import Tuple

logger = logging.getLogger(__name__)

def check_indeed_session(session_file: str = "indeed_session.json") -> Tuple[bool, str]:
    """
    Verifica lo stato della sessione Indeed salvata.
    Ritorna (is_valid: bool, reason: str).
    """
    if not os.path.exists(session_file):
        return False, "File di sessione 'indeed_session.json' non trovato sul server."
        
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        cookies = data.get("cookies", [])
        if not cookies:
            return False, "Nessun cookie presente nel file di sessione."
            
        # 1. Controllo RefreshToken
        refresh_cookie = next((c for c in cookies if "RefreshToken" in c.get("name", "")), None)
        if not refresh_cookie:
            return False, "Token di refresh Indeed mancante."
            
        refresh_exp = refresh_cookie.get("expires", 0)
        if 0 < refresh_exp < time.time():
            return False, "Token di refresh Indeed scaduto."
            
        # 2. Controllo Bearer Token JWT
        bearer_cookie = next((c for c in cookies if "BearerToken" in c.get("name", "")), None)
        if not bearer_cookie:
            return False, "Bearer token di autenticazione Indeed mancante."
            
        bearer_val = bearer_cookie.get("value", "")
        parts = bearer_val.split(".")
        if len(parts) >= 2:
            padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
            exp_ts = payload.get("exp", 0)
            if 0 < exp_ts < time.time():
                exp_date = datetime.fromtimestamp(exp_ts).strftime("%Y-%m-%d %H:%M")
                return False, f"Token di sessione scaduto ({exp_date})."
                
        return True, "Sessione Indeed valida e attiva."
    except Exception as e:
        return False, f"Errore durante la verifica dei cookie: {e}"

def verify_and_notify_session(target_phone: str = "3925435261", force_notify: bool = False) -> Tuple[bool, str]:
    """
    Verifica lo stato della sessione Indeed.
    Se invalida o scaduta, invia una notifica WhatsApp ESCLUSIVAMENTE a target_phone.
    Include una protezione anti-spam (cooldown di 20 ore prima di re-inviare la stessa notifica).
    """
    is_valid, reason = check_indeed_session()
    
    if is_valid:
        print(f"[+] [Session Health] Sessione Indeed verificata: {reason}", flush=True)
        # Se la sessione è valida, rimuoviamo l'eventuale cooldown precedente
        cooldown_file = os.path.join("data", "last_session_alert.json")
        if os.path.exists(cooldown_file):
            try:
                os.remove(cooldown_file)
            except Exception:
                pass
        return True, reason
        
    print(f"[-] [Session Health] Sessione Indeed non valida: {reason}", flush=True)
    
    # Controllo Cooldown anti-spam (20 ore)
    cooldown_file = os.path.join("data", "last_session_alert.json")
    now_ts = time.time()
    
    if not force_notify and os.path.exists(cooldown_file):
        try:
            with open(cooldown_file, "r", encoding="utf-8") as f:
                last_alert_data = json.load(f)
            last_sent = last_alert_data.get("timestamp", 0)
            if now_ts - last_sent < 72000:
                print(f"[*] [Session Health] Notifica gia' inviata a {target_phone} recentemente (cooldown 24h attivo). Salto invio.", flush=True)
                return False, f"Sessione scaduta ({reason}), notifica in cooldown"
        except Exception:
            pass
            
    # Invio notifica WhatsApp esclusivamente a target_phone
    from src.notifier.whatsapp_notifier import WhatsAppNotifier
    notifier = WhatsAppNotifier()
    ok, msg = notifier.send_session_alert(target_phone=target_phone, platform="Indeed", details=reason)
    
    if ok:
        try:
            os.makedirs("data", exist_ok=True)
            with open(cooldown_file, "w", encoding="utf-8") as f:
                json.dump({"timestamp": now_ts, "reason": reason, "target_phone": target_phone}, f)
        except Exception:
            pass
            
    return False, reason

if __name__ == "__main__":
    valid, res = verify_and_notify_session(target_phone="3925435261", force_notify=True)
    print(f"Risultato: {valid} - {res}")
