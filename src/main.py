import asyncio
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

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

def normalize_tokens(text: str) -> set:
    """Estrae le parole significative escludendo punteggiatura e suffissi legali/generici."""
    if "(" in text:
        text = text.split("(")[0]
    cleaned = re.sub(r'[^\w\s]', ' ', text.lower())
    ignored = {"spa", "srl", "sas", "snc", "inc", "ltd", "group", "gruppo", "italia", "italy", "per", "del", "della", "dei", "con", "and", "the"}
    return set(w for w in cleaned.split() if len(w) > 2 and w not in ignored)

def are_companies_similar(comp_a: str, comp_b: str) -> bool:
    """Verifica se due nomi aziendali sono simili (es. 'Magna International' vs 'Magna Powertrain')."""
    words_a = normalize_tokens(comp_a)
    words_b = normalize_tokens(comp_b)
    if not words_a or not words_b:
        return False
    # Condividono almeno una parola chiave distintiva
    if words_a & words_b:
        return True
    clean_a = "".join(sorted(words_a))
    clean_b = "".join(sorted(words_b))
    return clean_a in clean_b or clean_b in clean_a

def are_titles_similar(tit_a: str, tit_b: str) -> bool:
    """Verifica se due titoli condividono parole chiave essenziali di ruolo (es. 'HR Specialist' vs 'HR Specialist Talent Acquisition')."""
    words_a = normalize_tokens(tit_a)
    words_b = normalize_tokens(tit_b)
    if not words_a or not words_b:
        return False
    # Devono condividere almeno una parola chiave di ruolo
    return len(words_a & words_b) > 0

def find_fuzzy_candidate(job: dict, evaluated_records: list) -> dict:
    """
    Filtro Euristico Locale (Stage 1): Rileva candidati duplicati cross-platform
    anche quando il nome dell'azienda o il titolo presentano leggere variazioni di dicitura.
    """
    for rec in evaluated_records:
        rec_comp = rec.get("Azienda", "")
        if not are_companies_similar(job["company"], rec_comp):
            continue
            
        rec_tit = rec.get("Titolo", "")
        if not are_titles_similar(job["title"], rec_tit):
            continue
            
        # Sia azienda che titolo sono compatibili: calcoliamo similarità testo
        job_desc_words = set(w for w in re.sub(r'[^\w\s]', '', job["description"].lower()).split() if len(w) > 3)
        rec_desc = rec.get("Description", "")
        if rec_desc:
            rec_desc_words = set(w for w in re.sub(r'[^\w\s]', '', rec_desc.lower()).split() if len(w) > 3)
            intersection = len(job_desc_words & rec_desc_words)
            union = len(job_desc_words | rec_desc_words)
            if union > 0 and (intersection / union) >= 0.35:
                return rec
        else:
            return rec
            
    return None

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
    
    # 2. Caricamento Storico Precedente per Deduplicazione a Monte
    import csv
    from datetime import datetime
    
    history_file = "history.csv"
    file_exists = os.path.isfile(history_file)
    already_evaluated_urls = set()
    already_evaluated_hashes = {}
    evaluated_records = []
    
    if file_exists:
        try:
            with open(history_file, mode="r", encoding="utf-8") as existing_f:
                reader = csv.DictReader(existing_f)
                for row in reader:
                    evaluated_records.append(row)
                    if row.get("URL"):
                        already_evaluated_urls.add(row["URL"])
                    if row.get("Content_Hash"):
                        already_evaluated_hashes[row["Content_Hash"]] = row
            if already_evaluated_urls or already_evaluated_hashes:
                print(f"[*] Caricati {len(already_evaluated_urls)} URL e {len(already_evaluated_hashes)} fingerprint storici da {history_file}.")
                print(f"[*] Gli annunci già esaminati verranno saltati istantaneamente sia in fase di scraping che di valutazione AI!\n")
        except Exception as e:
            print(f"[-] Avviso lettura storico precedente: {e}")
            
    all_jobs = []
    # seen_urls parte già popolato con gli URL storici per non ri-scaricare le pagine di dettaglio
    seen_urls = set(already_evaluated_urls)
    
    # --- FASE 2A: LINKEDIN ---
    print("\n[*] Fase 2A: Scraping massivo LinkedIn (ultime 24h)...", flush=True)
    await scraper.auth_manager.perform_login_if_needed()
    await scraper.init_browser()
    
    total_queries = len(search_queries)
    for idx, sq in enumerate(search_queries, 1):
        print(f"\n[LinkedIn {idx}/{total_queries}] Ricerca '{sq['keywords']}' in '{sq['location']}'...", flush=True)
        try:
            jobs = await scraper.run(keywords=sq["keywords"], location=sq["location"], max_results=50, seen_urls=seen_urls)
            for j in jobs:
                all_jobs.append(j)
        except Exception as e:
            print(f"[-] Errore query LinkedIn '{sq['keywords']}' in '{sq['location']}': {e}. Proseguo con le altre query.", flush=True)
            
    await scraper.close_browser()
    print(f"\n[+] LinkedIn completato: {len(all_jobs)} annunci unici raccolti finora.", flush=True)
    
    # --- FASE 2B: INDEED ---
    print("\n[*] Fase 2B: Scraping massivo Indeed Italia (ultime 24h, paginazione autenticata)...", flush=True)
    indeed_scraper = IndeedScraper()
    await indeed_scraper.auth_manager.perform_login_if_needed()
    await indeed_scraper.init_browser()
    
    for idx, sq in enumerate(search_queries, 1):
        print(f"\n[Indeed {idx}/{total_queries}] Ricerca '{sq['keywords']}' in '{sq['location']}'...", flush=True)
        try:
            indeed_jobs = await indeed_scraper.run(keywords=sq["keywords"], location=sq["location"], max_results=30, seen_urls=seen_urls)
            for j in indeed_jobs:
                all_jobs.append(j)
        except Exception as e:
            print(f"[-] Errore query Indeed '{sq['keywords']}' in '{sq['location']}': {e}. Proseguo con le altre query.", flush=True)
            
    await indeed_scraper.close_browser()
    print(f"\n[+] Scraping terminato! Totale aggregato (LinkedIn + Indeed): {len(all_jobs)} annunci unici.", flush=True)
                
    if not all_jobs:
        print("[-] Nessun annuncio trovato o fallimento scraping.")
        return

    print(f"\n[*] Fase 2: Inizio valutazione AI di {len(all_jobs)} annunci unici con Gemini 3.8 Flash...\n")
    
    with open(history_file, mode="a", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["Data", "Piattaforma", "Titolo", "Azienda", "Match", "Rejection_Tag", "Stato_UI", "Content_Hash", "Reasoning", "URL", "Description", "Contatti", "Fit_Score"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists or os.path.getsize(history_file) == 0:
            writer.writeheader()
        
        total_eval_jobs = len(all_jobs)
        print(f"[*] Inizio ciclo di valutazione su {total_eval_jobs} annunci...\n")
        
        for idx, job in enumerate(all_jobs, start=1):
            remaining = total_eval_jobs - idx
            
            if job["url"] in already_evaluated_urls:
                # Già valutato in una precedente run con lo stesso identico URL
                continue
                
            job_hash = compute_content_hash(job["company"], job["title"], job["description"])
            source = job.get("source", "LinkedIn")
            
            print(f"\n[{idx}/{total_eval_jobs} | {remaining} rimanenti] Analisi: '{job['title']}' @ '{job['company']}' ({source})")
            
            # Controllo 1: Hash SHA-256 esatto (già presente nello storico)
            if job_hash in already_evaluated_hashes:
                prev = already_evaluated_hashes[job_hash]
                print(f"    ⚡ [REPOST RILEVATO DA FINGERPRINT] Ripubblicazione con nuovo ID (Esito: {prev['Match']}, Tag: {prev.get('Rejection_Tag', '')}). Copia verdetto a 0 token!")
                
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
                    "URL": job["url"],
                    "Description": job.get("description", "")
                })
                csvfile.flush()
                continue
                
            # Controllo 2: Filtro Fuzzy Cross-Platform (Stage 1) + Conferma Gemini (Stage 2)
            fuzzy_cand = find_fuzzy_candidate(job, evaluated_records)
            if fuzzy_cand:
                cand_source = fuzzy_cand.get("Piattaforma", "Altra")
                print(f"[*] [Fuzzy Filter] Rilevato probabile duplicato cross-platform ({source} vs {cand_source}): '{job['title']} @ {job['company']}'. Chiedo conferma lampo a Gemini...")
                
                check = evaluator.verify_duplicate(
                    candidate_title=job["title"],
                    candidate_company=job["company"],
                    candidate_desc=job["description"],
                    existing_title=fuzzy_cand.get("Titolo", ""),
                    existing_company=fuzzy_cand.get("Azienda", ""),
                    existing_desc=fuzzy_cand.get("Description", fuzzy_cand.get("Reasoning", ""))
                )
                
                if check.is_same_job and check.confidence >= 70:
                    canonical_hash = fuzzy_cand.get("Content_Hash") or job_hash
                    print(f"    ✅ [Gemini: DUPLICATO CONFERMATO ({check.confidence}%)] {check.reason}. Copia esito precedente a 0 token di valutazione completa!")
                    writer.writerow({
                        "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Piattaforma": source,
                        "Titolo": job["title"],
                        "Azienda": job["company"],
                        "Match": fuzzy_cand.get("Match", "NO"),
                        "Rejection_Tag": fuzzy_cand.get("Rejection_Tag", ""),
                        "Stato_UI": "NON_LETTO",
                        "Content_Hash": canonical_hash,
                        "Reasoning": f"[DUPLICATO CROSS-PLATFORM CONFERMATO DA GEMINI] {fuzzy_cand.get('Reasoning', '')}",
                        "URL": job["url"],
                        "Description": job.get("description", "")
                    })
                    csvfile.flush()
                    continue
                else:
                    print(f"    ℹ️ [Gemini: RUOLI DISTINTI ({check.confidence}%)] {check.reason}. Procedo con la valutazione completa.")
            
            try:
                # 3. Valutazione AI Completa
                evaluation = evaluator.evaluate(
                    job_title=job["title"],
                    company=job["company"],
                    job_description=job["description"]
                )
                
                print(f"[{'MATCH' if evaluation.is_match else 'SCARTATO'}] [{source}] {job['title']} @ {job['company']}")
                if not evaluation.is_match and evaluation.rejection_tag:
                    print(f"    Tag Rifiuto: {evaluation.rejection_tag.value}")
                print(f"    Reasoning: {evaluation.reasoning}\n")
                
                recruiters_info = ""
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
                    
                    if final_state and final_state.get("found_recruiters"):
                        for rec in final_state["found_recruiters"]:
                            recruiters_info += f"- **{rec.name}** ([Profilo LinkedIn]({rec.linkedin_url})) ➔ `{rec.guessed_email}`\n"
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

                # Salvataggio nello storico con Content_Hash, Contatti e Fit_Score
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
                    "URL": job["url"],
                    "Description": job.get("description", ""),
                    "Contatti": recruiters_info,
                    "Fit_Score": str(evaluation.fit_score) if evaluation.is_match else ""
                })
                csvfile.flush()
                
                # Aggiungiamo ai record valutati in memoria per permettere il cross-matching in tempo reale
                evaluated_records.append({
                    "Titolo": job["title"],
                    "Azienda": job["company"],
                    "Match": "SI" if evaluation.is_match else "NO",
                    "Rejection_Tag": evaluation.rejection_tag.value if (not evaluation.is_match and evaluation.rejection_tag) else "",
                    "Stato_UI": "NON_LETTO",
                    "Content_Hash": job_hash,
                    "Description": job["description"],
                    "Reasoning": evaluation.reasoning,
                    "URL": job["url"],
                    "Piattaforma": source,
                    "Contatti": recruiters_info,
                    "Fit_Score": str(evaluation.fit_score) if evaluation.is_match else ""
                })
                    
            except Exception as e:
                print(f"[-] Errore durante il processing di {job['title']}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
