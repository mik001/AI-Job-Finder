import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from typing import List, Optional
from dotenv import load_dotenv

from enum import Enum

class RejectionReason(str, Enum):
    AGENZIA = "AGENZIA" # Società interinale, headhunting, consulenza HR (vietato)
    LOCATION_ERRATA = "LOCATION_ERRATA" # Lavoro in presenza/ibrido fuori da Bari, oppure non full-remote
    NOT_HR = "NOT_HR" # Ruolo tecnico, commerciale, operations (non Risorse Umane)
    CATEGORIA_PROTETTA = "CATEGORIA_PROTETTA" # Annuncio riservato ad appartenenti alle Categorie Protette (L.68/99)
    LINGUA = "LINGUA" # Annuncio in lingua straniera o che richiede lingue diverse dall'Inglese/Italiano
    MANCANZA_DATI = "MANCANZA_DATI" # Annuncio vuoto o privo dei dettagli necessari per valutarlo
    ALTRO = "ALTRO" # Qualsiasi altro motivo di scarto non coperto sopra

class JobEvaluation(BaseModel):
    is_match: bool = Field(description="True se il lavoro rispetta i criteri dell'utente, False altrimenti.")
    fit_score: int = Field(description="Punteggio da 0 a 100 che indica quanto il lavoro è adatto all'utente.")
    salary_range: Optional[str] = Field(description="La RAL o il range salariale, se menzionato nell'annuncio. Altrimenti null.")
    tech_stack: List[str] = Field(description="Lista delle tecnologie principali richieste.")
    pros: List[str] = Field(description="Aspetti positivi dell'offerta rispetto al profilo.")
    cons: List[str] = Field(description="Aspetti negativi o red flags (es. richiede presenza in ufficio se l'utente vuole solo remote).")
    reasoning: str = Field(description="Una breve spiegazione del perché l'annuncio è stato scartato o approvato.")
    rejection_tag: Optional[RejectionReason] = Field(description="Se is_match=False, scegli obbligatoriamente il motivo di scarto principale dall'Enum. Se is_match=True, usa null.", default=None)

class JobEvaluator:
    def __init__(self, user_profile: str):
        """
        user_profile: Una stringa (o JSON testuale) che descrive cosa cerca l'utente.
        """
        self.user_profile = user_profile
        
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
        
        self.structured_llm = self.llm.with_structured_output(JobEvaluation)

    def evaluate(self, job_title: str, company: str, job_description: str) -> JobEvaluation:
        print(f"[*] Valutazione annuncio in corso: {job_title} @ {company}...")
        
        prompt = f"""
        Sei un formidabile Tech Recruiter AI. Il tuo compito è leggere una Job Description 
        e valutare se è adatta al candidato, in base al suo profilo e alle sue richieste.
        
        PROFILO DEL CANDIDATO:
        {self.user_profile}
        
        ANNUNCIO DI LAVORO:
        Titolo: {job_title}
        Azienda: {company}
        Descrizione: 
        {job_description}
        
        Valuta l'annuncio. Sii severo: se l'annuncio richiede palesemente cose che il candidato non vuole 
        (es. 100% in ufficio quando lui chiede remote, o un linguaggio di programmazione che odia), imposta is_match=False.
        """
        
        result = self.structured_llm.invoke(prompt)
        return result

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
