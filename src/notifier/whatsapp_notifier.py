import os
import urllib.parse
import urllib.request
import logging
from typing import Tuple, List, Dict
from dotenv import load_dotenv

from src.config_manager import ConfigManager

load_dotenv()
logger = logging.getLogger(__name__)

class WhatsAppNotifier:
    """Gestore unificato e multi-destinatario delle notifiche WhatsApp tramite CallMeBot e Twilio."""

    def __init__(self):
        self.callmebot_recipients: List[Dict[str, str]] = []
        self.enabled: bool = True
        
        # 1. Carica canali persistenti da ConfigManager
        try:
            cfg = ConfigManager.get_whatsapp_config()
            self.enabled = cfg.get("whatsapp_enabled", True)
            channels = cfg.get("channels", [])
            
            for ch in channels:
                if ch.get("enabled", True):
                    phone = self.normalize_phone(ch.get("phone", ""))
                    apikey = str(ch.get("apikey", "")).strip()
                    name = ch.get("name", "Destinatario")
                    if phone and apikey:
                        self.callmebot_recipients.append({
                            "name": name,
                            "phone": phone,
                            "apikey": apikey
                        })
        except Exception as e:
            logger.warning(f"Errore lettura canali WhatsApp da ConfigManager: {e}")

        # 2. Fallback su variabili d'ambiente (.env) se nessun canale attivo in config
        if not self.callmebot_recipients:
            k1 = os.getenv("CALLMEBOT_API_KEY")
            p1 = os.getenv("USER_WHATSAPP_NUMBER", "")
            if k1 and p1:
                self.callmebot_recipients.append({
                    "name": "Destinatario Primario (.env)",
                    "phone": self.normalize_phone(p1),
                    "apikey": k1.strip()
                })
                
            k2 = os.getenv("CALLMEBOT_API_KEY_2")
            p2 = os.getenv("USER_WHATSAPP_NUMBER_2", "")
            if k2 and p2:
                self.callmebot_recipients.append({
                    "name": "Destinatario Secondario (.env)",
                    "phone": self.normalize_phone(p2),
                    "apikey": k2.strip()
                })
                
            for i in range(3, 10):
                ki = os.getenv(f"CALLMEBOT_API_KEY_{i}")
                pi = os.getenv(f"USER_WHATSAPP_NUMBER_{i}", "")
                if ki and pi:
                    self.callmebot_recipients.append({
                        "name": f"Destinatario {i} (.env)",
                        "phone": self.normalize_phone(pi),
                        "apikey": ki.strip()
                    })

        # 3. Provider di backup: Twilio
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_whatsapp = os.getenv("TWILIO_WHATSAPP_NUMBER")
        self.to_whatsapp = os.getenv("USER_WHATSAPP_NUMBER", "")
        self.twilio_client = None
        if self.account_sid and self.auth_token:
            try:
                from twilio.rest import Client
                self.twilio_client = Client(self.account_sid, self.auth_token)
            except Exception:
                pass

        if not self.enabled:
            print("[-] Notifiche WhatsApp disabilitate da configurazione.")
        elif self.callmebot_recipients:
            dest_list = [f"{r['name']} ({r['phone']})" for r in self.callmebot_recipients]
            print(f"[+] Notificatore WhatsApp attivo con CallMeBot per {len(dest_list)} canali: {', '.join(dest_list)}")
        elif self.twilio_client:
            print("[+] Notificatore WhatsApp configurato con Twilio.")
        else:
            print("[-] Nessun canale WhatsApp attivo (configurabile da Web UI o da .env).")

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Pulisce e standardizza il numero di telefono per l'API CallMeBot."""
        clean = str(phone).replace("whatsapp:", "").replace(" ", "").replace("-", "").strip()
        if clean.startswith("00"):
            clean = "+" + clean[2:]
        return clean

    @classmethod
    def send_callmebot_message(cls, phone: str, apikey: str, text: str) -> Tuple[bool, str]:
        """Invia un singolo messaggio a un numero WhatsApp via API CallMeBot con validazione risposta."""
        clean_phone = cls.normalize_phone(phone)
        clean_apikey = str(apikey).strip()
        
        if not clean_phone or not clean_apikey:
            return False, "Numero di telefono o API Key non valorizzati."
            
        try:
            params = urllib.parse.urlencode({
                "phone": clean_phone,
                "text": text,
                "apikey": clean_apikey
            })
            req_url = f"https://api.callmebot.com/whatsapp.php?{params}"
            req = urllib.request.Request(
                req_url, 
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AIJobFinder/2.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_text = resp.read().decode("utf-8", errors="ignore")
                
                # Controllo semantico dell'output di CallMeBot
                resp_lower = resp_text.lower()
                if "error" in resp_lower or "invalid" in resp_lower or "failed" in resp_lower:
                    # Estrai testo pulito senza tag html
                    import re
                    clean_err = re.sub(r'<[^>]+>', ' ', resp_text).strip()[:180]
                    return False, f"CallMeBot: {clean_err or 'Errore API Key o numero non registrato'}"
                    
                return True, "Messaggio inviato con successo!"
        except urllib.error.HTTPError as e:
            return False, f"Errore server CallMeBot (HTTP {e.code}): {e.reason}"
        except urllib.error.URLError as e:
            return False, f"Errore di connessione a CallMeBot: {e.reason}"
        except Exception as e:
            return False, f"Errore imprevisto: {str(e)}"

    @classmethod
    def send_test_alert(cls, phone: str, apikey: str, recipient_name: str = "") -> Tuple[bool, str]:
        """Invia un messaggio di test immediato per verificare il canale e l'API Key."""
        name_str = f" {recipient_name}" if recipient_name else ""
        msg = (
            f"🔔 *AI Job Finder - Verifica Canale*\n\n"
            f"Ciao{name_str}! 👋\n"
            f"Questo canale WhatsApp è stato collegato con successo al sistema AI Job Finder.\n\n"
            f"🎯 Riceverai qui gli alert in tempo reale ogni volta che l'AI trova una nuova posizione idonea con i contatti dei recruiter aziendali.\n\n"
            f"✅ *Stato canale: ATTIVO & VERIFICATO*"
        )
        return cls.send_callmebot_message(phone, apikey, msg)

    def send_job_alert(self, job_title: str, company: str, fit_score: int, job_url: str, recruiters_info: str = ""):
        """Invia un alert di nuovo match di lavoro a TUTTI i canali WhatsApp attivi."""
        if not self.enabled:
            print("[!] Notifica WhatsApp saltata (notifiche disabilitate nelle impostazioni).")
            return

        # Pulisci eventuali ripetizioni nel titolo dell'annuncio
        clean_title = job_title.strip()
        half_len = len(clean_title) // 2
        if half_len > 3 and clean_title[:half_len] == clean_title[half_len:]:
            clean_title = clean_title[:half_len]

        message_body = (
            f"🚀 *Nuovo Match Lavorativo!*\n\n"
            f"💼 *Ruolo:* {clean_title}\n"
            f"🏢 *Azienda:* {company}\n"
            f"🎯 *Fit Score:* {fit_score}/100\n\n"
        )
        
        if recruiters_info:
            message_body += f"👥 *Contatti Trovati:*\n{recruiters_info}\n\n"
            
        message_body += f"🔗 *Link Annuncio:* {job_url}"
        
        # 1. Invio su tutti i canali CallMeBot configurati
        sent_any = False
        if self.callmebot_recipients:
            for recipient in self.callmebot_recipients:
                phone = recipient["phone"]
                apikey = recipient["apikey"]
                name = recipient.get("name", "Destinatario")
                
                success, msg = self.send_callmebot_message(phone, apikey, message_body)
                if success:
                    print(f"[+] Notifica WhatsApp inviata con successo a {name} ({phone})!")
                    sent_any = True
                else:
                    print(f"[-] Errore invio notifica a {name} ({phone}): {msg}")
                    
            if sent_any:
                return
                
        # 2. Fallback opzionale: Twilio
        if self.twilio_client and self.from_whatsapp and self.to_whatsapp:
            try:
                msg = self.twilio_client.messages.create(
                    body=message_body,
                    from_=self.from_whatsapp,
                    to=self.to_whatsapp
                )
                print(f"[+] Notifica WhatsApp inviata via Twilio! (SID: {msg.sid})")
                return
            except Exception as e:
                print(f"[-] Errore invio notifica Twilio: {e}")
                
        print("[!] Notifica WhatsApp non inviata (nessun destinatario attivo ha ricevuto il messaggio).")

if __name__ == "__main__":
    notifier = WhatsAppNotifier()
    if notifier.callmebot_recipients:
        first = notifier.callmebot_recipients[0]
        print(f"Test invio a: {first['name']} ({first['phone']})")
        ok, res = WhatsAppNotifier.send_test_alert(first["phone"], first["apikey"], first["name"])
        print(f"Risultato test: {ok} -> {res}")
    else:
        print("Nessun destinatario configurato per il test.")
