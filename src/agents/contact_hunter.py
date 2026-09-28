import os
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

# --- Strutture Dati ---
class Recruiter(BaseModel):
    name: str = Field(description="Nome del recruiter o hiring manager")
    linkedin_url: str = Field(description="URL del profilo LinkedIn")
    guessed_email: str = Field(description="Email ipotizzata (es. nome.cognome@azienda.com)")

class AgentState(TypedDict):
    company_name: str
    job_title: str
    search_queries: List[str]
    search_results: List[str]
    found_recruiters: List[Recruiter]
    errors: List[str]

# --- Nodi del Workflow ---
def generate_queries(state: AgentState):
    """Genera le query di ricerca per trovare il recruiter."""
    print(f"[*] Generazione query per trovare l'Hiring Manager di '{state['job_title']}' presso '{state['company_name']}'...")
    
    company = state['company_name']
    role = state['job_title']
    
    # Query ottimizzate per Tavily (linguaggio naturale + target domain)
    queries = [
        f"Find the LinkedIn profiles of the recruiters, HR, or hiring managers at {company}.",
        f"Who is the hiring manager for {role} at {company}? site:linkedin.com/in/"
    ]
    return {"search_queries": queries}

def execute_searches(state: AgentState):
    """Esegue la ricerca usando Tavily Search API."""
    print(f"[*] Esecuzione ricerche su Tavily...")
    
    api_key = os.getenv("TAVILY_API_KEY")
    
    if not api_key:
        return {"errors": ["TAVILY_API_KEY mancante nel file .env"]}

    try:
        tavily_client = TavilyClient(api_key=api_key)
        all_snippets = []
        
        for query in state["search_queries"]:
            # Usiamo include_domains per forzare la ricerca su LinkedIn se necessario, 
            # ma affidiamoci anche all'AI di Tavily per ricerche ampie.
            response = tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=3,
                include_domains=["linkedin.com"]
            )
            
            for result in response.get("results", []):
                snippet = f"Titolo: {result.get('title')}\nLink: {result.get('url')}\nContenuto: {result.get('content')}"
                all_snippets.append(snippet)
        
        return {"search_results": all_snippets}
    
    except Exception as e:
        print(f"[-] Errore in Tavily Search: {e}")
        return {"errors": [str(e)]}

def extract_contacts(state: AgentState):
    """Usa Gemini per estrarre i contatti dai risultati di ricerca."""
    if state.get("errors") or not state.get("search_results"):
        print("[-] Nessun risultato da analizzare o errore precedente.")
        return {"found_recruiters": []}

    print(f"[*] Analisi dei risultati con l'AI per estrarre i contatti...")
    
    # Uso di OpenRouter per aggirare i blocchi regionali Free Tier di Google
    api_key = os.getenv("OPENROUTER_API_KEY")
    llm = ChatOpenAI(
        model="google/gemini-3.8-flash",
        temperature=0.0,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        max_tokens=2000
    )
    
    class ExtractionResult(BaseModel):
        recruiters: List[Recruiter]
        
    structured_llm = llm.with_structured_output(ExtractionResult)
    
    results_text = "\n\n".join(state["search_results"])
    
    prompt = f"""
    Ecco i risultati di una ricerca web tramite Tavily per trovare i recruiter o l'hiring manager per il ruolo 
    '{state['job_title']}' presso l'azienda '{state['company_name']}'.
    
    RISULTATI RICERCA:
    {results_text}
    
    Estrai i nomi, i link ai profili LinkedIn e indovina una possibile email aziendale 
    (il formato tipico in Italia è nome.cognome@azienda.com o n.cognome@azienda.it).
    Restituisci solo persone che sembrano effettivamente lavorare in quell'azienda come HR, Recruiter o Manager.
    """
    
    try:
        res = structured_llm.invoke(prompt)
        return {"found_recruiters": res.recruiters}
    except Exception as e:
        print(f"[-] Errore estrazione AI: {e}")
        return {"errors": [str(e)]}

# --- Costruzione del Grafo ---
workflow = StateGraph(AgentState)

workflow.add_node("generate_queries", generate_queries)
workflow.add_node("execute_searches", execute_searches)
workflow.add_node("extract_contacts", extract_contacts)

workflow.set_entry_point("generate_queries")
workflow.add_edge("generate_queries", "execute_searches")
workflow.add_edge("execute_searches", "extract_contacts")
workflow.add_edge("extract_contacts", END)

contact_hunter_app = workflow.compile()

if __name__ == "__main__":
    initial_state = {
        "company_name": "Bending Spoons",
        "job_title": "Backend Engineer",
        "search_queries": [],
        "search_results": [],
        "found_recruiters": [],
        "errors": []
    }
    
    for event in contact_hunter_app.stream(initial_state):
        for key, value in event.items():
            print(f"--> Completato nodo: {key}")
            
    final_state = event.get(list(event.keys())[0], {})
    
    if final_state.get("found_recruiters"):
        print("\nCONTATTI TROVATI:")
        for rec in final_state["found_recruiters"]:
            print(f"- {rec.name} ({rec.linkedin_url}) -> Email: {rec.guessed_email}")
    else:
        print("\nNessun contatto trovato o errori:")
        print(final_state.get("errors"))
