import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

class WhatsAppNotifier:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_whatsapp = os.getenv("TWILIO_WHATSAPP_NUMBER")
        self.to_whatsapp = os.getenv("USER_WHATSAPP_NUMBER")
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            print("[-] Credenziali Twilio mancanti. Le notifiche WhatsApp non verranno inviate.")

    def send_job_alert(self, job_title: str, company: str, fit_score: int, job_url: str, recruiters_info: str = ""):
        if not self.client:
            print("[!] Salto notifica WhatsApp (Twilio non configurato).")
            return
            
        message_body = (
            f"🚀 *Nuovo Match Lavorativo!*\n\n"
            f"💼 *Ruolo:* {job_title}\n"
            f"🏢 *Azienda:* {company}\n"
            f"🎯 *Fit Score:* {fit_score}/100\n\n"
        )
        
        if recruiters_info:
            message_body += f"👥 *Contatti Trovati:*\n{recruiters_info}\n\n"
            
        message_body += f"🔗 *Link Annuncio:* {job_url}"
        
        try:
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_whatsapp,
                to=self.to_whatsapp
            )
            print(f"[+] Notifica WhatsApp inviata con successo! (SID: {message.sid})")
        except Exception as e:
            print(f"[-] Errore invio notifica WhatsApp: {e}")

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
