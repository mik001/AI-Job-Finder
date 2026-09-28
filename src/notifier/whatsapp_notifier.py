import os
import urllib.parse
import urllib.request
from dotenv import load_dotenv

load_dotenv()

class WhatsAppNotifier:
    def __init__(self):
        self.callmebot_recipients = []
        
        # Destinatario 1 (Primario)
        k1 = os.getenv("CALLMEBOT_API_KEY")
        p1 = os.getenv("USER_WHATSAPP_NUMBER", "")
        if k1 and p1:
            self.callmebot_recipients.append({"phone": p1.replace("whatsapp:", "").strip(), "apikey": k1.strip()})
            
        # Destinatario 2
        k2 = os.getenv("CALLMEBOT_API_KEY_2")
        p2 = os.getenv("USER_WHATSAPP_NUMBER_2", "")
        if k2 and p2:
            self.callmebot_recipients.append({"phone": p2.replace("whatsapp:", "").strip(), "apikey": k2.strip()})
            
        # Ulteriori destinatari opzionali (CALLMEBOT_API_KEY_3, ecc.)
        for i in range(3, 10):
            ki = os.getenv(f"CALLMEBOT_API_KEY_{i}")
            pi = os.getenv(f"USER_WHATSAPP_NUMBER_{i}", "")
            if ki and pi:
                self.callmebot_recipients.append({"phone": pi.replace("whatsapp:", "").strip(), "apikey": ki.strip()})

        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_whatsapp = os.getenv("TWILIO_WHATSAPP_NUMBER")
        self.to_whatsapp = p1
        
        # Inizializzazione Twilio se configurato
        self.twilio_client = None
        if self.account_sid and self.auth_token:
            try:
                from twilio.rest import Client
                self.twilio_client = Client(self.account_sid, self.auth_token)
            except Exception:
                pass
                
        if self.callmebot_recipients:
            dest_list = [r["phone"] for r in self.callmebot_recipients]
            print(f"[+] Notificatore WhatsApp configurato con CallMeBot per {len(dest_list)} destinatari: {', '.join(dest_list)}")
        elif self.twilio_client:
            print("[+] Notificatore WhatsApp configurato con Twilio.")
        else:
            print("[-] Nessun provider WhatsApp configurato (imposta CALLMEBOT_API_KEY o credenziali Twilio in .env).")

    def send_job_alert(self, job_title: str, company: str, fit_score: int, job_url: str, recruiters_info: str = ""):
        # Pulisci eventuali ripetizioni di titolo
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
        
        # 1. Priorità: CallMeBot (invia a tutti i destinatari configurati)
        sent_any = False
        if self.callmebot_recipients:
            for recipient in self.callmebot_recipients:
                phone = recipient["phone"]
                apikey = recipient["apikey"]
                try:
                    params = urllib.parse.urlencode({
                        "phone": phone,
                        "text": message_body,
                        "apikey": apikey
                    })
                    req_url = f"https://api.callmebot.com/whatsapp.php?{params}"
                    req = urllib.request.Request(req_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        if resp.status == 200:
                            print(f"[+] Notifica WhatsApp inviata con successo via CallMeBot a {phone}!")
                            sent_any = True
                except Exception as e:
                    print(f"[-] Errore invio notifica CallMeBot a {phone}: {e}")
            if sent_any:
                return
                
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
