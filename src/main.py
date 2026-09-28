import asyncio
import os
from src.scraper.linkedin_scraper import LinkedInScraper
from src.evaluator.job_evaluator import JobEvaluator
from src.agents.contact_hunter import contact_hunter_app
from src.notifier.whatsapp_notifier import WhatsAppNotifier

# Configurazione del profilo della candidata
CANDIDATE_PROFILE = """
Candidata: 30 anni, 4 anni di esperienza nel settore HR come Recruiter (executive search in Randstad Professional e attualmente in somministrazione).
Obiettivo: Uscire dalle agenzie per il lavoro/società di consulenza e trovare un ruolo HR INTERNO ad un'azienda finale (non agenzia).
Ruoli accettati: Recruiter interna, HR Generalist, HR Specialist, o altri ruoli HR.
Località e Modalità di Lavoro: 
- Accetta lavoro in sede o ibrido (es. un paio di giorni a settimana in ufficio) SOLO se a Bari o dintorni.
- Accetta Full Remote (o ibrido con presenza rarissima in sede, es. 1 volta al mese) in tutta Italia.
Aziende ESCLUSE: Categoricamente NO ad agenzie interinali, società di recruiting, società di consulenza HR, headhunting o simili (es. Randstad, Adecco, PageGroup, GiGroup, ecc.).

ATTENZIONE: La seniority troppo alta (es. Senior/Manager), troppo bassa (es. Stage/Junior) o la modalità Freelance/P.IVA NON DEVONO essere un motivo di scarto (non impostare is_match=False per questi motivi). Includile semplicemente nei 'cons' (aspetti negativi/warning) ma considera l'annuncio VALIDO (is_match=True) se rispetta il vincolo della sede e non è un'agenzia.
"""

async def main():
    print("\n" + "="*50)
    print("🤖 AVVIO AI JOB FINDER 🤖")
    print("="*50 + "\n")
    
    # 1. Inizializzazione Moduli
    scraper = LinkedInScraper()
    evaluator = JobEvaluator(user_profile=CANDIDATE_PROFILE)
    notifier = WhatsAppNotifier()
    
    # Configuriamo un set di query strategiche e ampie per massimizzare il bacino di ricerca
    search_queries = [
        {"keywords": "Risorse Umane", "location": "Italia"},
        {"keywords": "Human Resources", "location": "Italia"},
        {"keywords": "HR", "location": "Italia"},
        {"keywords": "Recruiter OR Recruiting", "location": "Italia"},
        {"keywords": "Talent Acquisition", "location": "Italia"},
        {"keywords": "HR Generalist OR HR Specialist", "location": "Italia"},
        {"keywords": "People Culture", "location": "Italia"},
        {"keywords": "People Operations", "location": "Italia"},
        {"keywords": "Talent Partner OR Talent Specialist", "location": "Italia"},
        {"keywords": "HR Business Partner OR HRBP", "location": "Italia"},
        {"keywords": "Selezione del Personale", "location": "Italia"},
        # Focus Locale Mirato (Bari & Puglia)
        {"keywords": "Risorse Umane", "location": "Bari"},
        {"keywords": "HR", "location": "Puglia"},
        {"keywords": "Recruiter", "location": "Bari"},
        {"keywords": "Talent Acquisition", "location": "Puglia"},
        {"keywords": "Selezione del Personale", "location": "Bari"}
    ]
    
    print("\n[*] Fase 1: Verifica e Login sulle piattaforme...")
    await scraper.auth_manager.perform_login_if_needed()
    await scraper.init_browser()
    
    print("\n[*] Fase 2: Scraping massivo delle Board con query ampie...")
    all_jobs = []
    seen_urls = set()
    
    for sq in search_queries:
        # Passiamo seen_urls allo scraper così salta gli annunci duplicati *prima* di caricarne la descrizione
        jobs = await scraper.run(keywords=sq["keywords"], location=sq["location"], max_results=100, seen_urls=seen_urls)
        for j in jobs:
            all_jobs.append(j)
            
    await scraper.close_browser()
                
    if not all_jobs:
        print("[-] Nessun annuncio trovato o fallimento scraping.")
        return

    print(f"\n[*] Fase 2: Inizio valutazione AI di {len(all_jobs)} annunci unici con Gemini 3.8 Flash...\n")
    
    import csv
    from datetime import datetime
    
    history_file = "history.csv"
    file_exists = os.path.isfile(history_file)
    
    with open(history_file, mode="a", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["Data", "Titolo", "Azienda", "Match", "Rejection_Tag", "Reasoning", "URL"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
            
        for job in all_jobs:
            try:
                # 3. Valutazione AI
                evaluation = evaluator.evaluate(
                    job_title=job["title"],
                    company=job["company"],
                    job_description=job["description"]
                )
                
                print(f"[{'MATCH' if evaluation.is_match else 'SCARTATO'}] {job['title']} @ {job['company']}")
                if not evaluation.is_match and evaluation.rejection_tag:
                    print(f"    Tag Rifiuto: {evaluation.rejection_tag}")
                print(f"    Reasoning: {evaluation.reasoning}\n")
                
                # Salvataggio nello storico
                writer.writerow({
                    "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Titolo": job["title"],
                    "Azienda": job["company"],
                    "Match": "SI" if evaluation.is_match else "NO",
                    "Rejection_Tag": evaluation.rejection_tag.value if (not evaluation.is_match and evaluation.rejection_tag) else "",
                    "Reasoning": evaluation.reasoning,
                    "URL": job["url"]
                })
                
                # Se è un match, cerchiamo il recruiter e notifichiamo
                if evaluation.is_match:
                    print(f"    --> MATCH TROVATO! Avvio Agente per trovare contatti interni a {job['company']}...\n")
                    
                    # 4. Ricerca Contatti
                    initial_state = {
                        "company_name": job["company"],
                        "job_title": job["title"],
                        "search_queries": [],
                        "search_results": [],
                        "found_recruiters": [],
                        "errors": []
                    }
                    
                    final_state = None
                    for event in contact_hunter_app.stream(initial_state):
                        final_state = event.get(list(event.keys())[0], {})
                    
                    recruiters_info = ""
                    if final_state and final_state.get("found_recruiters"):
                        for rec in final_state["found_recruiters"]:
                            recruiters_info += f"- {rec.name} ({rec.linkedin_url}) -> {rec.guessed_email}\n"
                    else:
                        recruiters_info = "Nessun contatto trovato dall'Agente."
                    
                    print(f"    --> Contatti:\n{recruiters_info}")
                    
                    # 5. Notifica
                    notifier.send_job_alert(
                        job_title=job["title"],
                        company=job["company"],
                        fit_score=evaluation.fit_score,
                        job_url=job["url"],
                        recruiters_info=recruiters_info
                    )
                    
                    print("-"*50)
                    
            except Exception as e:
                print(f"[-] Errore durante il processing di {job['title']}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
