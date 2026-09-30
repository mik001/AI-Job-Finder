import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from typing import List, Optional
from dotenv import load_dotenv

from enum import Enum

class RejectionReason(str, Enum):
    AGENZIA = "AGENZIA" # Agenzia per il lavoro / intermediazione non desiderata
    LOCATION_INCOMPATIBILE = "LOCATION_INCOMPATIBILE" # Sede o modalità di lavoro (presenza/ibrido/remoto) incompatibile
    RUOLO_NON_ATTINENTE = "RUOLO_NON_ATTINENTE" # Ruolo o mansione non attinente agli obiettivi del candidato
    SENIORITY_INCOMPATIBILE = "SENIORITY_INCOMPATIBILE" # Seniority richiesta esplicitamente non compatibile
    CONTRATTO_INCOMPATIBILE = "CONTRATTO_INCOMPATIBILE" # Tipologia contrattuale non ammessa (es. stage non retribuito, p.iva/part-time indesiderati)
    COMPETENZE_MANCANTI = "COMPETENZE_MANCANTI" # Requisiti tecnici o certificazioni essenziali non possedute
    CATEGORIA_PROTETTA = "CATEGORIA_PROTETTA" # Annuncio riservato ad appartenenti alle Categorie Protette (L.68/99)
    LINGUA = "LINGUA" # Requisito linguistico vincolante non posseduto
    MANCANZA_DATI = "MANCANZA_DATI" # Annuncio vuoto o privo dei dettagli necessari per valutarlo
    ALTRO = "ALTRO" # Qualsiasi altro motivo di scarto specifico
    # Alias retrocompatibili per i dati storici
    LOCATION_ERRATA = "LOCATION_ERRATA"
    NOT_HR = "NOT_HR"

class JobEvaluation(BaseModel):
    is_match: bool = Field(description="True se il lavoro rispetta i criteri dell'utente, False altrimenti.")
    fit_score: int = Field(description="Punteggio da 0 a 100 che indica quanto il lavoro è adatto all'utente.")
    salary_range: Optional[str] = Field(description="La RAL o il range salariale, se menzionato nell'annuncio. Altrimenti null.")
    tech_stack: List[str] = Field(description="Lista delle tecnologie principali richieste.")
    pros: List[str] = Field(description="Aspetti positivi dell'offerta rispetto al profilo.")
    cons: List[str] = Field(description="Aspetti negativi o red flags (es. richiede presenza in ufficio se l'utente vuole solo remote).")
    reasoning: str = Field(description="Una breve spiegazione del perché l'annuncio è stato scartato o approvato.")
    rejection_tag: Optional[RejectionReason] = Field(description="Se is_match=False, scegli obbligatoriamente il motivo di scarto principale dall'Enum (AGENZIA, LOCATION_INCOMPATIBILE, RUOLO_NON_ATTINENTE, SENIORITY_INCOMPATIBILE, CONTRATTO_INCOMPATIBILE, COMPETENZE_MANCANTI, CATEGORIA_PROTETTA, LINGUA, MANCANZA_DATI, ALTRO). Se is_match=True, usa null.", default=None)

class DuplicateCheck(BaseModel):
    is_same_job: bool = Field(description="True se i due annunci descrivono la stessa identica posizione lavorativa (anche se con formattazione, footer o layout differenti). False se sono due ruoli o sedi distinte.")
    confidence: int = Field(description="Punteggio di confidenza da 0 a 100 sulla decisione.")
    reason: str = Field(description="Breve motivazione del perché sono o non sono lo stesso annuncio.")

# APL e Agenzie di Somministrazione generaliste che pubblicano sia ruoli interni di filiale sia missioni per aziende clienti terze.
# Queste realtà NON devono MAI essere auto-scartate a priori: Gemini deve sempre valutare il contesto dell'annuncio.
STAFFING_AGENCIES_DUAL_NATURE = {
    "adecco", "the adecco group", "randstad", "gi group", "gi group holding",
    "manpower", "manpowergroup", "umana", "openjobmetis", "synergie",
    "maw", "men at work", "lavoropiù", "ali lavoro", "areajob", "adhr group",
    "humangest", "sgb humangest holding", "eurofirms", "eurofirms group",
    "in job", "quanta", "articiocco", "temporary", "generazione vincente",
    "job italia", "smart skills center", "etjca", "alisia", "wintime",
    "kelly services", "page personnel", "michael page", "spring professional",
    "badenoch + clark", "experis"
}

class JobEvaluator:
    def __init__(self, user_profile: str, exclude_agencies: bool = True):
        """
        user_profile: Una stringa (o JSON testuale) che descrive cosa cerca l'utente.
        exclude_agencies: Se True, attiva il pre-filtro a monte e la regola di scarto agenzie/headhunting.
        """
        self.user_profile = user_profile
        self.exclude_agencies = exclude_agencies
        
        # Uso di OpenRouter per aggirare i blocchi regionali Free Tier di Google
        api_key = os.getenv("OPENROUTER_API_KEY")
        self.llm = ChatOpenAI(
            model="google/gemini-3.8-flash",
            temperature=0.0,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            max_retries=3,
            max_tokens=4000
        )
        self.duplicate_verifier = self.llm.with_structured_output(DuplicateCheck)
        
        self.structured_llm = self.llm.with_structured_output(JobEvaluation)
        self.blacklist_file = os.path.join("data", "learned_agencies.json")
        self.learned_agencies = self._load_learned_agencies()

    def _normalize_company_name(self, name: str) -> str:
        name = name.lower().strip()
        if "(" in name:
            name = name.split("(")[0].strip()
        for suffix in [" s.p.a.", " spa", " s.r.l.", " srl", " s.a.s.", " sas", " inc.", " ltd"]:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
        return name

    def _load_learned_agencies(self) -> set:
        os.makedirs("data", exist_ok=True)
        if os.path.exists(self.blacklist_file):
            try:
                import json
                with open(self.blacklist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data)
            except Exception:
                return set()
        return set()

    def _save_learned_agencies(self):
        try:
            import json
            os.makedirs("data", exist_ok=True)
            with open(self.blacklist_file, "w", encoding="utf-8") as f:
                json.dump(sorted(list(self.learned_agencies)), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[-] Errore salvataggio blacklist agenzie: {e}")

    def is_dual_nature_staffing(self, company_name: str) -> bool:
        """Riconosce se un'azienda è un'APL che gestisce anche missioni in somministrazione per aziende clienti."""
        norm = self._normalize_company_name(company_name)
        return any(apl in norm for apl in STAFFING_AGENCIES_DUAL_NATURE)

    def evaluate(self, job_title: str, company: str, job_description: str) -> JobEvaluation:
        norm_company = self._normalize_company_name(company)
        is_apl = self.is_dual_nature_staffing(company)
        
        # 1. Pre-filtro blacklist agenzie (Attivo SOLO se exclude_agencies=True)
        if self.exclude_agencies:
            if is_apl:
                print(f"    🏢 [APL Somministrazione] '{company}' gestisce somministrazioni per terzi. Inoltro a Gemini per analisi contesto...")
            elif norm_company and norm_company in self.learned_agencies and norm_company not in ("azienda sconosciuta", "sconosciuta", "sconosciuto", "unknown", "n/a", "none"):
                print(f"    ⚡ [AI-Learned Filter] '{company}' già classificata da Gemini come Headhunting/Consulenza pura. Auto-scarto a zero token!")
                return JobEvaluation(
                    is_match=False,
                    fit_score=0,
                    salary_range=None,
                    tech_stack=[],
                    pros=[],
                    cons=["Azienda già classificata come società di consulenza esterna o headhunting puro da Gemini."],
                    reasoning=f"L'azienda '{company}' è già stata precedentemente identificata da Gemini come società di consulenza esterna/headhunting puro. Scartata in automatico.",
                    rejection_tag=RejectionReason.AGENZIA
                )
        
        if self.exclude_agencies:
            agency_instruction = "          * AGENZIA: se è un'agenzia per il lavoro / società di selezione o headhunting esclusa dai vincoli del candidato.\n"
        else:
            agency_instruction = ""

        prompt = f"""
        Sei un formidabile ed esperto Recruiter AI. Il tuo compito è leggere una Job Description 
        e valutare se è adatta al candidato, in base al suo profilo e ai suoi criteri di ricerca.
        
        PROFILO DEL CANDIDATO E CRITERI:
        {self.user_profile}
        
        ANNUNCIO DI LAVORO:
        Titolo: {job_title}
        Azienda: {company}
        Descrizione: 
        {job_description}
        
        Valuta l'annuncio con attenzione e rigore:
        - Se l'annuncio rispetta i criteri e gli obiettivi del candidato, imposta is_match=True e rejection_tag=None.
        - Se l'annuncio viola i vincoli del candidato (es. sede non compatibile, ruolo errato, ecc.), imposta is_match=False e assegna obbligatoriamente il rejection_tag più calzante:
{agency_instruction}
          * LOCATION_INCOMPATIBILE: se la sede, la distanza o la modalità di lavoro (presenza/ibrido/remoto) non rispetta le richieste del candidato.
          * RUOLO_NON_ATTINENTE: se il ruolo o la mansione proposta non attiene a quanto ricercato dal candidato.
          * SENIORITY_INCOMPATIBILE: se il livello di esperienza/seniority richiesto è incompatibile (se il profilo lo impone come motivo di scarto).
          * CONTRATTO_INCOMPATIBILE: se la tipologia contrattuale non è accettata (es. stage non retribuito o P.IVA se rifiutati).
          * COMPETENZE_MANCANTI: se mancano requisiti tecnici o certificazioni essenziali e bloccanti.
          * CATEGORIA_PROTETTA: se l'annuncio è riservato a Categorie Protette (L. 68/99) e il candidato non vi appartiene.
          * LINGUA: se richiede lingue vincolanti non possedute.
          * MANCANZA_DATI: se l'annuncio non fornisce informazioni sufficienti per valutare il ruolo.
          * ALTRO: qualsiasi altro motivo di scarto specifico spiegato nel reasoning.
        """
        
        print(f"    🤖 Chiamata Gemini 3.8 Flash per valutazione approfondita...")
        result = self.structured_llm.invoke(prompt)
        
        # 2. Se Gemini ha riconosciuto un'agenzia, memorizzala per sempre SOLO se il filtro agenzie è attivo e NON è un'APL di somministrazione
        # NON memorizzare MAI placeholder generici come "azienda sconosciuta"
        GENERIC_PLACEHOLDERS = {"azienda sconosciuta", "sconosciuta", "sconosciuto", "unknown", "n/a", "none", ""}
        if self.exclude_agencies and not result.is_match and result.rejection_tag == RejectionReason.AGENZIA and norm_company:
            if norm_company not in GENERIC_PLACEHOLDERS and not is_apl and norm_company not in self.learned_agencies:
                self.learned_agencies.add(norm_company)
                self._save_learned_agencies()
                print(f"    🧠 [AI-Learned Filter] Nuova società di consulenza/headhunting appresa da Gemini: '{company}' aggiunta al database persistente.")
                
        return result

    def verify_duplicate(self, candidate_title: str, candidate_company: str, candidate_desc: str, existing_title: str, existing_company: str, existing_desc: str) -> DuplicateCheck:
        """Verifica con Gemini se due annunci con azienda/titolo simili sono la stessa identica offerta."""
        prompt = f"""
        Sei un esperto analista di annunci di lavoro.
        Determina se questi due annunci pubblicati sul web rappresentano LA STESSA IDENTICA POSIZIONE lavorativa (anche se con formattazione, footer o piattaforme diverse), oppure se si tratta di due offerte/ruoli distinti.
        
        Ignora differenze superficiali (es. footer "Candidati su LinkedIn/Indeed", link, o formattazione dei paragrafi).
        
        ANNUNCIO GIA' VALUTATO:
        Titolo: {existing_title}
        Azienda: {existing_company}
        Testo:
        {existing_desc[:2000]}
        
        NUOVO ANNUNCIO DA CONFRONTARE:
        Titolo: {candidate_title}
        Azienda: {candidate_company}
        Testo:
        {candidate_desc[:2000]}
        """
        try:
            return self.duplicate_verifier.invoke(prompt)
        except Exception as e:
            print(f"[-] Errore verifica duplicato con Gemini: {e}")
            return DuplicateCheck(is_same_job=False, confidence=0, reason="Errore durante la verifica.")

if __name__ == "__main__":
    test_profile = "Cerco lavoro come Software Engineer in Python. Solo lavoro Full Remote. Mi interessa lavorare con AI e backend. RAL desiderata: almeno 40k."
    test_job = "Siamo alla ricerca di un Python Developer per la nostra sede di Roma (3 giorni in ufficio). Stack: Python, Django. RAL: 35k - 45k."
    
    evaluator = JobEvaluator(test_profile)
    try:
        evaluation = evaluator.evaluate("Python Developer", "Tech S.p.A.", test_job)
        print("Risultato:")
        print(evaluation.model_dump_json(indent=2))
    except Exception as e:
        print("Errore durante la chiamata a Gemini (tramite OpenRouter):", e)
