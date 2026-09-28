import os
import urllib.parse
import urllib.request
from dotenv import load_dotenv

load_dotenv()

class WhatsAppNotifier:
    def __init__(self):
        self.callmebot_api_key = os.getenv("CALLMEBOT_API_KEY")
        self.to_whatsapp = os.getenv("USER_WHATSAPP_NUMBER", "")
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_whatsapp = os.getenv("TWILIO_WHATSAPP_NUMBER")
        
        # Inizializzazione Twilio se configurato
        self.twilio_client = None
        if self.account_sid and self.auth_token:
            try:
                from twilio.rest import Client
                self.twilio_client = Client(self.account_sid, self.auth_token)
            except Exception:
                pass
                
        if self.callmebot_api_key:
            print("[+] Notificatore WhatsApp configurato con CallMeBot (100% Gratuito).")
        elif self.twilio_client:
            print("[+] Notificatore WhatsApp configurato con Twilio.")
        else:
            print("[-] Nessun provider WhatsApp configurato (imposta CALLMEBOT_API_KEY o credenziali Twilio in .env).")

    def send_job_alert(self, job_title: str, company: str, fit_score: int, job_url: str, recruiters_info: str = ""):
        message_body = (
            f"🚀 *Nuovo Match Lavorativo!*\n\n"
            f"💼 *Ruolo:* {job_title}\n"
            f"🏢 *Azienda:* {company}\n"
            f"🎯 *Fit Score:* {fit_score}/100\n\n"
        )
        
        if recruiters_info:
            message_body += f"👥 *Contatti Trovati:*\n{recruiters_info}\n\n"
            
        message_body += f"🔗 *Link Annuncio:* {job_url}"
        
        # 1. Priorità: CallMeBot (gratuito e permanente)
        if self.callmebot_api_key and self.to_whatsapp:
            try:
                clean_phone = self.to_whatsapp.replace("whatsapp:", "").strip()
                params = urllib.parse.urlencode({
                    "phone": clean_phone,
                    "text": message_body,
                    "apikey": self.callmebot_api_key.strip()
                })
                req_url = f"https://api.callmebot.com/whatsapp.php?{params}"
                req = urllib.request.Request(req_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status == 200:
                        print(f"[+] Notifica WhatsApp inviata con successo via CallMeBot a {clean_phone}!")
                        return
            except Exception as e:
                print(f"[-] Errore invio notifica CallMeBot: {e}")
                
        # 2. Fallback: Twilio
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
                
        print("[!] Notifica WhatsApp saltata (nessun provider attivo configurato).")

if __name__ == "__main__":
    # Test veloce
    notifier = WhatsAppNotifier()
    notifier.send_job_alert(
        job_title="Senior Python Developer",
        company="Tech S.p.A.",
        fit_score=95,
        job_url="https://linkedin.com/jobs/view/123456",
        recruiters_info="- Mario Rossi (Recruiter): mario.rossi@tech.com"
    )
