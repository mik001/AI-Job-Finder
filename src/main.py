import asyncio
import os
from src.scraper.linkedin_scraper import LinkedInScraper
from src.scraper.indeed_scraper import IndeedScraper
from src.evaluator.job_evaluator import JobEvaluator
from src.agents.contact_hunter import contact_hunter_app
from src.notifier.whatsapp_notifier import WhatsAppNotifier

# Configurazione del profilo della candidata
CANDIDATE_PROFILE = """
Candidata: 30 anni, 4 anni di esperienza nel settore HR come Recruiter (executive search in Randstad Professional e attualmente in somministrazione).
Obiettivo Principale: Fare esperienza e lavorare come HR INTERNA all'interno del team di un'azienda cliente finale.
Ruoli accettati: Recruiter interna, HR Generalist, HR Specialist, Talent Acquisition, People Operations, o altri ruoli HR.
Località e Modalità di Lavoro: 
- Accetta lavoro in sede o ibrido (es. un paio di giorni a settimana in ufficio) SOLO se a Bari o dintorni.
- Accetta Full Remote (o ibrido con presenza rarissima in sede, es. 1 volta al mese) in tutta Italia.

REGOLA FONDAMENTALE SU AGENZIE E SOMMINISTRAZIONE:
- Categoricamente NO a ruoli interni di filiale presso agenzie per il lavoro (es. fare il recruiter di filiale in Adecco/Randstad/Manpower che seleziona per conto di terzi).
- ACCETTATO CON VALUTAZIONE POSITIVA (is_match=True): Contratti di somministrazione o staff leasing (anche se emessi da Adecco, Randstad, ecc.) IN CUI LA CANDIDATA VIENE INSERITA A LAVORARE DENTRO IL TEAM HR DI UN'AZIENDA CLIENTE FINALE (es. "per conto di nostra azienda cliente cerchiamo HR Generalist/Recruiter"). Questa tipologia di lavoro in azienda terza è considerata un ottimo trampolino di lancio per fare esperienza aziendale ed è da considerare valida se rispetta la sede (Bari o Full Remote).

ALTRE REGOLE MORBIDE (NON SCARTARE):
- La seniority troppo alta (es. Senior/Manager), troppo bassa (es. Stage/Junior) o la modalità Freelance/P.IVA NON DEVONO essere un motivo di scarto. Includile nei 'cons' (warning) ma mantieni is_match=True se l'annuncio rispetta la sede e la natura del ruolo aziendale.
"""

import hashlib
import re

def compute_content_hash(company: str, title: str, description: str) -> str:
    """Calcola un'impronta digitale SHA-256 univoca basata su azienda, titolo e testo dell'annuncio."""
    clean_company = re.sub(r'\W+', '', company.lower())
    clean_title = re.sub(r'\W+', '', title.lower())
    clean_desc = re.sub(r'\s+', ' ', description.lower().strip())[:1500]
    payload = f"{clean_company}_{clean_title}_{clean_desc}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

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
    
    all_jobs = []
    seen_urls = set()
    
    # --- FASE 2A: LINKEDIN ---
    print("\n[*] Fase 2A: Scraping massivo LinkedIn (ultime 24h)...")
    await scraper.auth_manager.perform_login_if_needed()
    await scraper.init_browser()
    
    for sq in search_queries:
        jobs = await scraper.run(keywords=sq["keywords"], location=sq["location"], max_results=100, seen_urls=seen_urls)
        for j in jobs:
            all_jobs.append(j)
            
    await scraper.close_browser()
    print(f"[+] LinkedIn completato: {len(all_jobs)} annunci unici raccolti finora.")
    
    # --- FASE 2B: INDEED ---
    print("\n[*] Fase 2B: Scraping massivo Indeed Italia (ultime 24h, zero login)...")
    indeed_scraper = IndeedScraper()
    await indeed_scraper.init_browser()
    
    for sq in search_queries:
        indeed_jobs = await indeed_scraper.run(keywords=sq["keywords"], location=sq["location"], max_results=50, seen_urls=seen_urls)
        for j in indeed_jobs:
            all_jobs.append(j)
            
    await indeed_scraper.close_browser()
    print(f"[+] Scraping terminato! Totale aggregato (LinkedIn + Indeed): {len(all_jobs)} annunci unici.")
                
    if not all_jobs:
        print("[-] Nessun annuncio trovato o fallimento scraping.")
        return

    print(f"\n[*] Fase 2: Inizio valutazione AI di {len(all_jobs)} annunci unici con Gemini 3.8 Flash...\n")
    
    import csv
    from datetime import datetime
    
    history_file = "history.csv"
    file_exists = os.path.isfile(history_file)
    already_evaluated_urls = set()
    already_evaluated_hashes = {}
    
    if file_exists:
        try:
            with open(history_file, mode="r", encoding="utf-8") as existing_f:
                reader = csv.DictReader(existing_f)
                for row in reader:
                    if row.get("URL"):
                        already_evaluated_urls.add(row["URL"])
                    if row.get("Content_Hash"):
                        already_evaluated_hashes[row["Content_Hash"]] = row
            if already_evaluated_urls or already_evaluated_hashes:
                print(f"[*] Caricati {len(already_evaluated_urls)} URL e {len(already_evaluated_hashes)} fingerprint storici. Verranno saltati per risparmiare chiamate AI.")
        except Exception as e:
            print(f"[-] Avviso lettura storico precedente: {e}")
    
    with open(history_file, mode="a", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["Data", "Piattaforma", "Titolo", "Azienda", "Match", "Rejection_Tag", "Stato_UI", "Content_Hash", "Reasoning", "URL"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
            
        for job in all_jobs:
            if job["url"] in already_evaluated_urls:
                # Già valutato in una precedente run con lo stesso identico URL
                continue
                
            job_hash = compute_content_hash(job["company"], job["title"], job["description"])
            source = job.get("source", "LinkedIn")
            
            # Controllo Repost: se il fingerprint SHA-256 esiste già nello storico
            if job_hash in already_evaluated_hashes:
                prev = already_evaluated_hashes[job_hash]
                print(f"[REPOST RILEVATO] [{source}] '{job['title']} @ {job['company']}' è la ripubblicazione con nuovo ID di un annuncio già valutato (Esito: {prev['Match']}, Tag: {prev.get('Rejection_Tag', '')}). Copia verdetto a 0 token!")
                
                writer.writerow({
                    "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Piattaforma": source,
                    "Titolo": job["title"],
                    "Azienda": job["company"],
                    "Match": prev.get("Match", "NO"),
                    "Rejection_Tag": prev.get("Rejection_Tag", ""),
                    "Stato_UI": "NON_LETTO",
                    "Content_Hash": job_hash,
                    "Reasoning": f"[REPOST RILEVATO DA FINGERPRINT] {prev.get('Reasoning', '')}",
                    "URL": job["url"]
                })
                csvfile.flush()
                continue
                
            try:
                # 3. Valutazione AI
                evaluation = evaluator.evaluate(
                    job_title=job["title"],
                    company=job["company"],
                    job_description=job["description"]
                )
                
                print(f"[{'MATCH' if evaluation.is_match else 'SCARTATO'}] [{source}] {job['title']} @ {job['company']}")
                if not evaluation.is_match and evaluation.rejection_tag:
                    print(f"    Tag Rifiuto: {evaluation.rejection_tag.value}")
                print(f"    Reasoning: {evaluation.reasoning}\n")
                
                # Salvataggio nello storico con Content_Hash per bloccare future ripubblicazioni
                writer.writerow({
                    "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Piattaforma": source,
                    "Titolo": job["title"],
                    "Azienda": job["company"],
                    "Match": "SI" if evaluation.is_match else "NO",
                    "Rejection_Tag": evaluation.rejection_tag.value if (not evaluation.is_match and evaluation.rejection_tag) else "",
                    "Stato_UI": "NON_LETTO",
                    "Content_Hash": job_hash,
                    "Reasoning": evaluation.reasoning,
                    "URL": job["url"]
                })
                csvfile.flush()
                
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
