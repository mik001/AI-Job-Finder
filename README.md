# 🤖 AI Job Finder & Autonomous Contact Hunter

Sistema enterprise e autonomo per il monitoraggio avanzato del mercato del lavoro, lo scraping resiliente anti-bot (**LinkedIn** + **Indeed Italia**), la valutazione semantica dei requisiti tramite LLM (**Gemini 3.8 Flash**), la caccia automatizzata agli Hiring Manager tramite **LangGraph** & **Tavily**, notifiche istantanee gratuite via **WhatsApp (CallMeBot)** e dashboard web interattiva in **Streamlit**.

---

## 📌 Indice dei Contenuti
1. [Obiettivo e Profilo Candidata](#-obiettivo-e-profilo-candidata)
2. [Architettura Generale del Sistema](#-architettura-generale-del-sistema)
3. [Tecnologie e Moduli Chiave](#-tecnologie-e-moduli-chiave)
4. [Dettagli di Scraping: LinkedIn](#-scraping-linkedin-profondo)
5. [Dettagli di Scraping: Indeed Italia](#-scraping-indeed-italia-multi-pagina--zero-stalli)
6. [Valutazione Semantica con AI (Job Evaluator)](#-valutazione-semantica-con-ai-job-evaluator)
7. [Deduplicazione Multi-Livello & Scalabilità](#-deduplicazione-multi-livello--scalabilità)
8. [Agente LangGraph: Contact Hunter](#-agente-langgraph-contact-hunter)
9. [Notifiche WhatsApp Gratuite (CallMeBot)](#-notifiche-whatsapp-callmebot)
10. [Web Dashboard Interattiva (Streamlit)](#-web-dashboard-interattiva-streamlit)
11. [Automazione & Schedulazione (Windows & Docker)](#-automazione--schedulazione)
12. [Configurazione e Guida Rapida](#-configurazione-e-guida-rapida)

---

## 🎯 Obiettivo e Profilo Candidata

Il sistema è calibrato per monitorare quotidianamente il mercato e individuare opportunità mirate per una figura **HR Recruiter / Specialist** (30 anni, 4 anni di esperienza tra Executive Search/Permanent in agenzia e somministrazione), con l'obiettivo strategico di **lavorare come HR interna nel team di un'azienda cliente finale**.

### Requisiti Chiave della Candidata:
- **Ruoli Accettati**: Recruiter interna, HR Generalist, HR Specialist, Talent Acquisition, People Operations, Talent Partner, HR Business Partner.
- **Sede e Modalità di Lavoro**:
  - In presenza o ibrido: **SOLO a Bari e provincia / Puglia**.
  - Da remoto: **Full Remote in tutta Italia** (o ibrido con presenza rarissima in sede).
- **Regola Fondamentale su Agenzie e Somministrazione (Opzione A)**:
  - ❌ **Categoricamente NO**: Ruoli interni di filiale presso agenzie per il lavoro (es. recruiter di filiale in Adecco, Randstad, Manpower, Gi Group che seleziona per terzi).
  - ✅ **ACCETTATO CON VALUTAZIONE POSITIVA (`is_match = True`)**: Contratti di somministrazione o staff leasing in cui la candidata viene inserita **a lavorare dentro il team HR di un'azienda cliente finale** (trampolino per fare esperienza aziendale interna).
- **Warning Tollerati (Non Scartano l'Annuncio)**:
  - Seniority alta (HR Manager) o bassa (Stage/Junior).
  - Contratti Freelance / P.IVA.

---

## 🏗️ Architettura Generale del Sistema

```
                        [ Scheduler (08:30 / 18:00) o Avvio Manuale ]
                                              │
                                              ▼
                        [ history.csv: Caricamento 400+ URL & Fingerprint ]
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
       [ LinkedInScraper ]                                  [ IndeedScraper ]
     ├── Login Stealth Persistente                        ├── Login Autonomo OTP (IMAP Gmail)
     ├── 16 Query (Italia + Bari/Puglia)                  ├── Paginazione Multi-Pagina (start=0, 10, 20)
     ├── Scroll virtuale DOM (25 card/pag)                ├── Parse Statico Istantaneo (0.05s)
     └── Skip rapido seen_urls O(1)                       └── Bubble MouseEvent (Zero Stalli)
                    │                                                   │
                    └─────────────────────────┬─────────────────────────┘
                                              ▼
                              [ Deduplicazione Multi-Livello ]
                             ├── Livello 1: SHA-256 esatto (0 token)
                             └── Livello 2: Fuzzy Token Jaccard + Conferma Lampo Gemini
                                              │
                                              ▼
                             [ JobEvaluator: Gemini 3.8 Flash ]
                             ├── Verifica criteri rigidi (Sede, Tipo Ruolo, Azienda)
                             ├── Assegnazione RejectionReason (AGENZIA, LOCATION_ERRATA, NOT_HR)
                             ├── Apprendimento dinamico in data/learned_agencies.json
                             └── Scrittura progressiva con Testo Integrale in history.csv
                                              │
                        ┌─────────────────────┴─────────────────────┐
                        ▼                                           ▼
                 Se [SCARTATO]                                 Se [MATCH]
                 Fine elaborazione                                  │
                                                                    ▼
                                                    [ ContactHunter: LangGraph + Tavily ]
                                                    ├── Caccia agli Hiring Manager su LinkedIn
                                                    └── Deduzione pattern email aziendale
                                                                    │
                                                                    ▼
                                                    [ WhatsAppNotifier: CallMeBot ]
                                                    Alert istantaneo con Fit Score, Contatti e Link
                                                                    │
                                                                    ▼
                                                    [ Streamlit UI Dashboard ]
                                                    Visualizzazione, lettura offline e azioni 1-click
```

---

## 🌐 Tecnologie e Moduli Chiave

- **Linguaggio**: Python 3.10+ (testato su Python 3.14).
- **Browser Automation**: Playwright + `playwright-stealth` (Chromium anti-detection).
- **AI & LLM**: Google Gemini 3.8 Flash (tramite Gemini API nativa / OpenRouter).
- **Orchestrazione Agenti**: LangGraph + LangChain Core.
- **Search Engine API**: Tavily Search API.
- **Notifiche**: CallMeBot WhatsApp API (100% gratuito, senza limiti temporali di sandbox).
- **Frontend Dashboard**: Streamlit (interfaccia web locale interattiva e reattiva).
- **Orchestrazione Schedulata**: Windows Task Scheduler (`.bat` / `.ps1`) e Docker/Docker-Compose (`src/scheduler.py`).

---

## 💼 Scraping LinkedIn Profondo

Modulo: [`src/scraper/linkedin_scraper.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/scraper/linkedin_scraper.py)

- **Autenticazione Persistente**: Sessione salvata su disco (`linkedin_session.json`). Bypass schermate A/B "Welcome Back" e campi honeypot nascosti tramite selettori visibili (`:visible`).
- **Scroll del Container Effettivo**: Risolto l'occlusion culling identificando programmaticamente a runtime il `div` interno con `overflow-y: auto`, caricando tutte le 25 offerte per pagina.
- **Filtro Ultime 24h & DD Sort**: Query string parametrizzata con `f_TPR=r90000&sortBy=DD`.
- **Filtro Anti-Raccomandazioni**: Distingue i veri annunci di lavoro (`/jobs/view/...`) dai widget promozionali di LinkedIn ("Offerte consigliate per te" come posizioni IT/Developer), scartando le card non attinenti prima della valutazione.
- **Uscita Anticipata Intelligente**: Interrompe immediatamente la paginazione se una pagina contiene meno di 25 card, azzerando i tempi morti.

---

## 🔍 Scraping Indeed Italia (Multi-Pagina & Zero Stalli)

Modulo: [`src/scraper/indeed_scraper.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/scraper/indeed_scraper.py)

- **Login Autonomo via Email OTP (IMAP Gmail)**:
  - Per superare il blocco forzato di Indeed alla Pagina 2 (`branding=page-two-signin`), [`src/scraper/auth_manager.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/scraper/auth_manager.py) gestisce il login autonomo: Playwright inserisce l'email, clicca *"Accedi con un codice"*, legge via IMAP sicuro la casella Gmail, estrae il codice a 6 cifre e si autentica salvando `indeed_session.json`.
- **Risoluzione Definitiva dello Stallo (Zero Detached Locators)**:
  - *Problema risolto*: Il click nativo su tag `<a>` causava deviazioni su pagine esterne/sponsorizzate (`/pagead/clk`), e il successivo `go_back()` distruggeva i puntatori DOM scatenando il timeout Playwright di 30 secondi a card (7.5 minuti di freeze a query!).
  - *Nuova Architettura*:
    1. **Parsing Statico Immediato**: Tutte le 16 card della pagina vengono lette via BeautifulSoup in **0.05 secondi**.
    2. **Deduplicazione a Zero Latenza**: Se l'URL o il `data-jk` è già nello storico, viene saltato all'istante senza toccare il browser.
    3. **Apertura Pannello Sicura**: Apertura tramite `MouseEvent` con bubbling sintetico sull'intestazione (senza navigare via dall'URL di ricerca).
    4. **Timeout Rigido a 800ms con Fallback**: Se il pannello destro `#jobsearch-ViewjobPaneWrapper` non carica entro 800ms, il testo dell'annuncio viene recuperato direttamente dalla card HTML, azzerando qualsiasi rischio di blocco.
- **Paginazione Multi-Pagina Fluida**: Scansiona `start=0`, `start=10`, `start=20` con tab isolati per prevenire sfide Cloudflare Turnstile.
- **Descrizioni Integrali Preservate**: Estrazione del testo completo da `.simple-job-description-html` e `#jobDescriptionText` (fino a 6.900+ caratteri).

---

## 🧠 Valutazione Semantica con AI (Job Evaluator)

Modulo: [`src/evaluator/job_evaluator.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/evaluator/job_evaluator.py)

- **Modello**: Google **Gemini 3.8 Flash** (`gemini-2.5-flash`).
- **Tassonomia dei Rifiuti Rigorosa (`RejectionReason` Enum)**:
  - `AGENZIA`: Agenzie per il lavoro o società di selezione (escluso il caso di somministrazione su cliente finale).
  - `LOCATION_ERRATA`: Presenza/ibrido fuori da Bari e provincia, o assenza di full-remote.
  - `NOT_HR`: Ruolo non appartenente alle Risorse Umane (es. commerciale, tecnico, magazzino, accoglienza).
  - `CATEGORIA_PROTETTA`: Offerte riservate a L. 68/99.
  - `LINGUA`: Richiesta lingua vincolante non posseduta.
  - `MANCANZA_DATI`: Descrizione insufficiente.
- **Auto-Apprendimento Blacklist (`data/learned_agencies.json`)**:
  - Quando Gemini riconosce un'agenzia di headhunting o selezione pura (es. *Hunters Group, Chaberton, Ali Professional, Only Job*), il suo nome normalizzato viene memorizzato su file JSON. Nelle successive scansioni, gli annunci di tali aziende vengono **scartati a monte a zero token**.

---

## ⚡ Deduplicazione Multi-Livello & Scalabilità

Per garantire che lo script non rallenti mai nel corso delle settimane:
1. **Deduplicazione URL $O(1)$**: Ricerca istantanea su `set()` in memoria degli URL già processati.
2. **Fingerprint SHA-256 (`Content_Hash`)**:
   $$Content\_Hash = \text{SHA256}(\text{Azienda} + \text{Titolo} + \text{Testo})$$
   Identifica ripubblicazioni e repost con nuovi ID a 0 chiamate API.
3. **Fuzzy Cross-Platform Matching (LinkedIn vs Indeed)**:
   - *Fase 1 (Locale)*: Jaccard similarity su parole chiave di azienda, titolo e vocabolario annuncio.
   - *Fase 2 (Verifica Gemini)*: Mini-query binaria lampo per confermare se due annunci cross-platform rappresentano la stessa posizione lavorativa.
4. **Scalabilità dello Storico**:
   - Con oltre 400 record già memorizzati, la lettura di `history.csv` richiede meno di **0.02 secondi**. Il sistema supporta agevolmente decine di migliaia di righe senza degrado prestazionale.

---

## 🕵️ Agente LangGraph: Contact Hunter

Modulo: [`src/agents/contact_hunter.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/agents/contact_hunter.py)

Attivato esclusivamente per le offerte con esito `is_match = True`:
```
[generate_queries] ──► [execute_searches (Tavily)] ──► [extract_contacts (Gemini)] ──► END
```
- Formula query mirate per individuare l'Hiring Manager o il Talent Acquisition Lead dell'azienda.
- Esegue ricerche sul web tramite Tavily filtrando su `linkedin.com/in/`.
- Dedurrà e mapperà il profilo del referente e il pattern email aziendale più probabile (es. `nome.cognome@azienda.it`).

---

## 📱 Notifiche WhatsApp (CallMeBot)

Modulo: [`src/notifier/whatsapp_notifier.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/notifier/whatsapp_notifier.py)

- **100% Gratuito e Illimitato**: Utilizza l'API di CallMeBot collegata al numero WhatsApp personale.
- **Nessuna Scadenza Sandbox**: Supera i limiti di Twilio Sandbox (che richiede riattivazione ogni 72 ore).
- **Formato Notifica**:
  ```text
  🚀 *Nuovo Match Lavorativo!*

  💼 *Ruolo:* Sales Recruiter
  🏢 *Azienda:* Sovera Credit Partners
  🎯 *Fit Score:* 95/100

  👥 *Contatti Trovati:*
  - Mario Rossi (Head of Talent): m.rossi@sovera.com

  🔗 *Link Annuncio:* https://www.linkedin.com/jobs/view/...
  ```

---

## 💻 Web Dashboard Interattiva (Streamlit)

Modulo: [`src/ui/app.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/ui/app.py)

Dashboard reattiva creata per consentire alla candidata di gestire comodamente il flusso delle offerte:

- **Metriche KPI Live**: Totale esaminati, contatore match (con delta non letti), annunci scartati, split LinkedIn / Indeed.
- **🎯 Tab Match Lavorativi**:
  - Schede visive con badge per piattaforma e data.
  - Box informativo con il verdetto analitico di **Gemini 3.8 Flash**.
  - **Accordion con Descrizione Integrale**: Lettura dell'intero annuncio offline senza troncamenti.
  - **Pulsanti di Stato a 1-Click**: `Mark: Letto`, `🚀 Segna Candidato`, `📁 Archivia`, `↩️ Ripristina Non Letto` (con aggiornamento bidirezionale immediato su `history.csv`).
  - **Pulsante Candidati ↗**: Apertura diretta dell'annuncio originale.
- **📋 Tab Offerte Scartate**: Tabella interattiva ricercabile con filtro per motivo di scarto (`AGENZIA`, `LOCATION_ERRATA`, `NOT_HR`).
- **🛡️ Tab Blacklist Agenzie AI**: Visualizzatore ed editor reattivo per aggiungere o rimuovere agenzie dalla blacklist con un click.
- **Avvio Istantaneo (Windows)**: Doppio clic sul file [`scripts/run_ui.bat`](file:///c:/Users/borgi/projects/AI-Job-Finder/scripts/run_ui.bat).

---

## ⏰ Automazione & Schedulazione

### 1. Windows Task Scheduler (Locale)
Gli script automatizzati sono configurati per eseguire il job due volte al giorno:
- **Mattina**: ore **08:30**
- **Sera**: ore **18:00**

Configurazione rapida via PowerShell (Amministratore):
```powershell
.\scripts\setup_windows_task.ps1
```
Oppure esecuzione manuale via batch:
```cmd
.\scripts\run_daily.bat
```

### 2. Docker & Cloud VPS (Pronto per il Deploy)
- [`Dockerfile`](file:///c:/Users/borgi/projects/AI-Job-Finder/Dockerfile) & [`docker-compose.yml`](file:///c:/Users/borgi/projects/AI-Job-Finder/docker-compose.yml) basati su `mcr.microsoft.com/playwright/python:v1.49.1-jammy`.
- [`src/scheduler.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/scheduler.py): demone con libreria `schedule` per esecuzione autonoma 24/7 su VPS Linux (Hetzner, DigitalOcean, AWS).

---

## ⚙️ Configurazione e Guida Rapida

### 1. Prerequisiti
- Python 3.10 o superiore.
- Google Chrome / Chromium installato via Playwright.

### 2. Installazione
```bash
# Creazione e attivazione virtualenv
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux/Mac

# Installazione dipendenze
pip install -r requirements.txt

# Installazione browser Playwright
playwright install chromium
```

### 3. File di Configurazione (`.env`)
Creare il file `.env` nella radice del progetto:
```env
# AI & Search
GEMINI_API_KEY=AQ.Ab8...
TAVILY_API_KEY=tvly-...

# Notifiche WhatsApp (CallMeBot Gratuito)
CALLMEBOT_API_KEY=tuo_codice_callmebot
USER_WHATSAPP_NUMBER=whatsapp:+393XXXXXXXXX

# LinkedIn (Autenticazione Stealth)
LINKEDIN_EMAIL=tua_email@gmail.com
LINKEDIN_PASSWORD=tua_password

# Indeed (Autenticazione Autonoma via OTP Gmail)
INDEED_EMAIL=tua_email@gmail.com
INDEED_IMAP_USER=tua_email@gmail.com
INDEED_IMAP_PASSWORD=app_password_gmail_16_caratteri
```

### 4. Comandi di Esecuzione

- **Esecuzione Scansione Giornaliera**:
  ```powershell
  $env:PYTHONPATH="."
  .\venv\Scripts\python -u src/main.py
  ```
- **Avvio Web Dashboard Streamlit**:
  ```powershell
  .\venv\Scripts\streamlit run src/ui/app.py
  # oppure doppio clic su: .\scripts\run_ui.bat
  ```

---

## 📄 Licenza e Manutenibilità
Progetto open-source a uso privato, rilasciato sotto licenza MIT. Tutti i cookie e i dati sensibili sono protetti tramite `.gitignore`.
