# 🤖 AI Job Finder & Autonomous Contact Hunter

Sistema intelligente e autonomo per il monitoraggio avanzato del mercato del lavoro, lo scraping resiliente anti-bot, la valutazione semantica dei requisiti tramite LLM (**Gemini 3.8 Flash**) e la caccia automatizzata ai contatti degli Hiring Manager tramite **LangGraph** e **Tavily Search API**.

---

## 📌 Indice dei Contenuti
1. [Obiettivo e Target del Progetto](#-obiettivo-e-target-del-progetto)
2. [Architettura Generale del Sistema](#-architettura-generale-del-sistema)
3. [Dettagli Tecnici di Scraping per Piattaforma](#-dettagli-tecnici-di-scraping-per-piattaforma)
   - [LinkedIn (Scraper Ufficiale)](#1-linkedin-scraper-profondo)
     - [Autenticazione Persistente & Stealth Anti-Bot](#a-autenticazione-persistente--stealth-anti-bot)
     - [Bypass Honeypot & Schermate A/B di Login](#b-bypass-honeypot--schermate-ab-di-login)
     - [Ciclo di Vita & Riutilizzo del Browser](#c-ciclo-di-vita--riutilizzo-del-browser)
     - [Deduplicazione Preventiva a Bassa Latenza](#d-deduplicazione-preventiva-a-bassa-latenza)
     - [Il Meccanismo di Scroll e Lazy Loading (Risolto)](#e-il-meccanismo-di-scroll-e-lazy-loading-risolto)
     - [Paginazione Multi-Pagina Infinita](#f-paginazione-multi-pagina-infinita)
     - [Estrazione Card & Dati Essenziali](#g-estrazione-card--dati-essenziali)
     - [Estrazione Descrizione Completa (Cascata di Fallback)](#h-estrazione-descrizione-completa-cascata-di-fallback)
   - [Blueprint per Altre Piattaforme (Indeed, InfoJobs, ecc.)](#2-blueprint-per-altre-piattaforme-indeed-infojobs)
4. [Valutazione Semantica con AI (Job Evaluator)](#-valutazione-semantica-con-ai-job-evaluator)
   - [Tassonomia Rigorosa dei Rifiuti (RejectionReason Enum)](#tassonomia-rigorosa-dei-rifiuti-rejectionreason-enum)
   - [Hard Limits vs Soft Warnings](#hard-limits-vs-soft-warnings)
   - [Risoluzione del Truncamento JSON (EOF Error)](#risoluzione-del-truncamento-json-eof-error)
5. [Agente LangGraph: Contact Hunter](#-agente-langgraph-contact-hunter)
6. [Sistema di Notifica (WhatsApp & Email)](#-sistema-di-notifica-whatsapp--email)
7. [Storico & Data Audit (history.csv)](#-storico--data-audit-historycsv)
8. [Configurazione e Guida all'Uso](#-configurazione-e-guida-alluso)

---

## 🎯 Obiettivo e Target del Progetto

Il progetto nasce da un'esigenza specifica e rigorosa: individuare opportunità di lavoro per una figura professionale **HR Recruiter / Specialist** (30 anni, 4 anni di esperienza maturati sia in Executive Search/Permanent che in somministrazione), con il vincolo fondamentale di **uscire dal settore della consulenza e delle agenzie interinali** per entrare come **HR interna in un'azienda finale di prodotto**.

### Requisiti Chiave della Ricerca:
- **Ruoli ammessi**: HR Generalist, HR Specialist, Talent Acquisition, People Operations, Talent Partner, HR Business Partner, Selezione e Formazione.
- **Sede e Modalità di Lavoro**:
  - In presenza o ibrido: **SOLO a Bari e provincia / Puglia**.
  - Da remoto: **Full Remote in tutta Italia** (o con presenze rarissime).
- **Esclusioni Assolute (Hard Disqualifiers)**:
  - Tutte le Agenzie per il Lavoro (APL), società di selezione terzi, consulenza HR o headhunting (es. Randstad, Adecco, Manpower, Gi Group, Hunters Group, ecc.).
  - Posizioni che richiedono presenza fisica al di fuori della provincia di Bari.
  - Corsi di formazione o master a pagamento camuffati da annunci di lavoro.
- **Eccezioni Gestite come Warning (Non Bloccanti)**:
  - Seniority alta o bassa (es. posizioni Junior/Stage o Manageriali non scartano l'annuncio se l'azienda è cliente finale nella zona consentita).
  - Contratti Freelance / P.IVA (accettati come opportunità da valutare).

---

## 🏗️ Architettura Generale del Sistema

```
[ Avvio Programma ]
        │
        ▼
[ AuthManager ] ──► Verifica Cookie / Esegue Login Stealth su LinkedIn
        │
        ▼
[ LinkedInScraper ] ──► 16 Query Strategiche (Italia Full-Remote + Focus Bari/Puglia)
        │                 ├── Navigazione multi-pagina (start=0, 25, 50, ...)
        │                 ├── Scroll dinamico del container effettivo (25 card/pag)
        │                 ├── Deduplicazione preventiva via set seen_urls
        │                 └── Download descrizione con fallback per layout React/SSR
        │
        ▼
[ JobEvaluator (Gemini 3.8 Flash via OpenRouter) ]
        │  ├── Analisi semantica della descrizione reale
        │  ├── Validazione criteri rigidi (Location, Tipo Azienda)
        │  ├── Assegnazione RejectionReason Enum (AGENZIA, LOCATION_ERRATA, ecc.)
        │  └── Scrittura progressiva in history.csv
        │
        ├── Se [SCARTATO] ──► Fine ciclo annuncio
        │
        └── Se [MATCH] ─────► [ ContactHunter Agent (LangGraph + Tavily) ]
                                    │
                                    ├── Query mirate su Hiring Manager / HR
                                    ├── Scansione profili LinkedIn reali
                                    ├── Deduzione pattern email aziendale
                                    │
                                    ▼
                             [ WhatsAppNotifier (Twilio) ]
                             (Alert immediato con link e contatti)
```

---

## 🌐 Dettagli Tecnici di Scraping per Piattaforma

### 1. LinkedIn Scraper Profondo

LinkedIn implementa tra i più aggressivi sistemi anti-scraping del web: rilevamento bot tramite TLS fingerprinting, layout React/Ember polimorfici, classi CSS oscurate/dinamiche, virtual scrolling (occlusion culling) e honeypot nascosti. Di seguito tutte le soluzioni ingegnerizzate nel modulo `src/scraper/linkedin_scraper.py`.

#### A. Autenticazione Persistente & Stealth Anti-Bot
- **Persistenza della Sessione**: I cookie e lo storage di sessione vengono serializzati su disco in `data/sessions/linkedin_session.json`. Al riavvio dello script, `AuthManager` ripristina la sessione evitando di eseguire un login interattivo a ogni run (che insospettirebbe gli algoritmi di sicurezza).
- **Stealth Evasion**: Utilizzo della classe `Stealth().apply_stealth_async(context)` (dal package `playwright-stealth` v2.0.3) che maschera le proprietà `navigator.webdriver`, normalizza i codici lingua, i parametri `chrome.runtime` e le proprietà hardware di rendering WebGL.
- **User-Agent Realistico**: Viene iniettato uno User-Agent moderno di Chromium desktop con viewport standard a 1920x1080.

#### B. Bypass Honeypot & Schermate A/B di Login
Durante i test, il login di LinkedIn falliva regolarmente a causa di due trappole architetturali:
1. **Campi Nascosti (Honeypot)**: Nel form di login sono presenti input invisibili con selettori generici `#username`. Se Playwright prova a interagire con essi, va in timeout.
   - *Soluzione*: Utilizzo rigoroso del selettore con pseudo-classe di visibilità CSS: `input[type='email']:visible`, `input[name='session_key']:visible`.
2. **Schermata A/B "Welcome Back"**: Se LinkedIn rileva un browser già visto, omette completamente il campo email e mostra solo un avatar con il campo password.
   - *Soluzione*: Il riempimento dell'email è racchiuso in un blocco `try/except` con timeout a 5 secondi; se non compare, il bot assume la presenza della schermata "Welcome Back" e procede direttamente all'immissione della password.
3. **Pulsanti di Submit Polimorfici**: Molti pulsanti non presentano l'attributo `type="submit"` o hanno classi offuscate.
   - *Soluzione*: L'invio delle credenziali avviene simulando la pressione del tasto tastiera fisico: `await page.keyboard.press("Enter")`.

#### C. Ciclo di Vita & Riutilizzo del Browser
- **Problema rilevato**: Nelle prime versioni, lo script avviava, navigava e chiudeva una nuova istanza Chromium per ciascuna query di ricerca (9-16 volte a sessione). Questo generava 10-15 secondi di overhead a query, saturazione di memoria e spam di log.
- **Soluzione applicata**: `LinkedInScraper` espone i metodi asincroni `init_browser()` e `close_browser()`. In `main.py`, il browser viene inizializzato una sola volta all'avvio, rimane attivo e riutilizza la stessa pagina web per scorrere sequenzialmente tutte le query, e viene chiuso pulitamente solo alla fine.

#### D. Deduplicazione Preventiva a Bassa Latenza
Le query ampie generano inevitabilmente annunci sovrapposti (es. "Risorse Umane Italia" vs "Recruiter Italia").
- Scaricare ogni volta la pagina di dettaglio di un annuncio duplicato richiede 2-3 secondi per ogni click.
- **Soluzione**: Il set in memoria `seen_urls` viene condiviso attraverso tutte le query e passato direttamente al metodo `scraper.run()`. Quando il bot esamina l'HTML dei risultati di ricerca, estrae l'URL della card e verifica `if job_url in seen_urls: continue` **prima** di tentare qualsiasi navigazione pesante, risparmiando minuti di esecuzione.

#### E. Il Meccanismo di Scroll e Lazy Loading (Risolto)
Questo rappresentava il collo di bottiglia più critico: *perché lo scraper trovava sempre e solo 7 o 8 annunci per pagina?*

##### L'Indagine al Livello del DOM:
1. LinkedIn su desktop per gli utenti autenticati adotta un layout a due colonne (`.scaffold-layout__list-detail`).
2. La colonna sinistra con l'elenco degli annunci ha classe container `.scaffold-layout__list`.
3. Tuttavia, analizzando gli stili computati con `window.getComputedStyle()`, abbiamo scoperto che:
   - `.scaffold-layout__list` ha `overflow-y: visible` e altezza identica allo scroll (`clientHeight == scrollHeight == 971px`).
   - L'invocazione di `scrollBy()` su di esso non produce **alcun movimento**.
4. Il vero elemento con scroll attivo è un `<div>` figlio interno che possiede:
   - `overflow-y: auto`
   - `scrollHeight: 3414px` (mentre `clientHeight` è 906px).
   - Classi CSS criptate e variabili da sessione a sessione.
5. Inoltre, LinkedIn usa l'**Occlusion Culling (Virtual Scrolling)** con classe `occludable-update`: le card al di fuori della finestra visibile non vengono caricate o vengono rimosse dal DOM.

##### La Soluzione Dinamica:
Nel metodo `run()` è stato iniettato un algoritmo Javascript che analizza l'albero DOM a runtime, individua programmaticamente il contenitore reale con `overflow-y: auto` e lo scorre progressivamente a scatti da 800px:

```javascript
await page.evaluate(`
    async () => {
        const listContainer = document.querySelector('.scaffold-layout__list') || document.body;
        const scrollable = Array.from(listContainer.querySelectorAll('*')).find(el => {
            const s = window.getComputedStyle(el);
            return (s.overflowY === 'auto' || s.overflowY === 'scroll') && el.scrollHeight > el.clientHeight;
        });
        
        if (scrollable) {
            for (let i = 0; i < 5; i++) {
                scrollable.scrollBy(0, 800);
                await new Promise(r => setTimeout(r, 500));
            }
        }
    }
`);
```
**Risultato certificato dai test**:
- Card prima dello scroll: **8**
- Step 1 (+600px): **13**
- Step 2 (+1200px): **18**
- Step 3 (+1800px): **23**
- Step 4 (+2400px): **25 card complete!**

#### F. Paginazione Multi-Pagina Infinita
- **URL Parameter**: LinkedIn struttura la paginazione incrementando il parametro `start` a blocchi di 25 elementi:
  `https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&f_TPR=r86400&sortBy=DD&start={start}`
  - Pagina 1: `start=0`
  - Pagina 2: `start=25`
  - Pagina 3: `start=50`
  - Pagina 4: `start=75`
- **Condizione di Uscita Pulita**: È stato rimosso un vecchio controllo buggato (`len(job_cards) < 10`) che interrompeva prematuramente il ciclo. Ora la paginazione continua regolarmente fino a quando `len(jobs_found) >= max_results` oppure `if not job_cards: break` (pagina priva di annunci).

#### G. Estrazione Card & Dati Essenziali
Per ciascun blocco card nel DOM, il parser `_parse_job_card()` estrae:
- **Titolo**: Ricerca nei tag `<a>` con percorso `/jobs/view/`, con fallback su tag `<h3>` o `<strong>`. Pulizia automatica dei caratteri a capo spuri.
- **Azienda**: Gestione del polimorfismo delle classi di LinkedIn per gli utenti loggati:
  1. `div.artdeco-entity-lockup__subtitle` (utilizzato nel layout moderno con classi React oscurate).
  2. `span.job-card-container__primary-description` (layout legacy).
  3. `a[class*='company']` (fallback generico).
- **URL**: Normalizzazione dell'URL con rimozione dei parametri di tracking commerciale (`?eBP=...&refId=...&trackingId=...`) per garantire link puliti e univoci.

#### H. Estrazione Descrizione Completa (Cascata di Fallback)
Quando lo scraper naviga sulla pagina singola dell'annuncio (`https://www.linkedin.com/jobs/view/{id}/`), LinkedIn può servire due layout differenti:
1. **Layout SPA Utente Autenticato**: Il testo risiede nel selettore `#job-details` o `<article>`. Spesso il testo è parzialmente nascosto da un bottone espandibile (`button.jobs-description__footer-button`), su cui il bot clicca automaticamente.
2. **Layout SSR / Guest Dinamico**: In molti casi, LinkedIn serve un DOM pre-renderizzato in cui la descrizione risiede in un contenitore con ID generato che include il Job ID numerico: `JobDetails_AboutTheJob_{job_id}`.
- **Cascata Selettori Implementata**:
  ```python
  desc_div = (
      soup.find("div", id="job-details") or
      soup.find(id=lambda x: x and "AboutTheJob" in x) or
      soup.find("article") or
      soup.find("div", class_="jobs-description__content") or
      soup.find("div", class_="description__text")
  )
  ```
- **Timeout Ottimizzato**: Attesa massima impostata a **2.5 secondi** (anziché i precedenti 5 secondi), garantendo la massima rapidità senza rischiare letture parziali.

---

### 2. Blueprint per Altre Piattaforme (Indeed, InfoJobs)

L'architettura è stata progettata in modo modulare affinché nuovi portali possano essere aggiunti ereditando l'interfaccia standard e il gestore sessioni:

| Piattaforma | Meccanismo di Paginazione | Selettore Lista Card | Selettore Descrizione | Protezioni Specifiche |
| :--- | :--- | :--- | :--- | :--- |
| **Indeed** | Parametro URL `&start=10, 20, ...` | `div.job_seen_beacon` o `td.resultContent` | `div#jobDescriptionText` | Cloudflare Turnstile, popup "Crea un avviso" |
| **InfoJobs** | Parametro URL `&page=2, 3, ...` | `li.ij-ComponentList-item` | `div.description-content` | Cookie banner bloccante, form di login tradizionale |
| **Glassdoor** | Parametro URL `&p=2, 3, ...` | `li[data-test='jobListing']` | `div.JobDetails_jobDescription__...` | Obbligo di login per visualizzare stipendi e dettagli |

---

## 🧠 Valutazione Semantica con AI (Job Evaluator)

Il modulo [src/evaluator/job_evaluator.py](file:///c:/Users/borgi/projects/AI-Job-Finder/src/evaluator/job_evaluator.py) delega l'analisi qualitativa delle descrizioni a **Gemini 3.8 Flash** tramite la piattaforma **OpenRouter**.

### Tassonomia Rigorosa dei Rifiuti (RejectionReason Enum)
Per evitare che l'AI utilizzi etichette fantasiose o incoerenti, i motivi di scarto sono vincolati a una classe `Enum` strettamente tipizzata in Pydantic:

```python
class RejectionReason(str, Enum):
    AGENZIA = "AGENZIA"                  # APL, somministrazione, consulenza o headhunting
    LOCATION_ERRATA = "LOCATION_ERRATA"  # In presenza/ibrido fuori da Bari, o non full-remote
    NOT_HR = "NOT_HR"                    # Ruolo tecnico, commerciale, operations (non HR)
    CATEGORIA_PROTETTA = "CATEGORIA_PROTETTA" # Annuncio riservato a L.68/99
    LINGUA = "LINGUA"                    # Richiesta lingua straniera vincolante (es. Tedesco)
    MANCANZA_DATI = "MANCANZA_DATI"      # Annuncio privo di dettagli sufficienti
    ALTRO = "ALTRO"                      # Motivi residuali non classificabili sopra
```

### Hard Limits vs Soft Warnings
Su indicazione strategica, il prompt di sistema distingue nettamente tra motivi di bocciatura totale e semplici avvertimenti:
- **Criteri Bloccanti (`is_match = False`)**:
  - Se l'azienda è un'agenzia o società di consulenza terzi.
  - Se la sede richiede presenza fisica a Milano, Roma o comunque fuori dall'area metropolitana di Bari e non offre il full-remote.
  - Se l'annuncio non riguarda l'ambito HR.
- **Avvisi Tollerati (`is_match = True` con annotazione in `cons`)**:
  - **Seniority Alta**: Ruoli come HR Manager o HR Director non vengono scartati, ma segnalati nei `cons`.
  - **Seniority Bassa**: Annunci di Stage o ruoli Junior non vengono eliminati a priori (potrebbero rappresentare opportunità di ingresso in prestigiosi clienti finali).
  - **Contratti Freelance / P.IVA**: Ammessi e segnalati nei warning.

### Risoluzione del Truncamento JSON (EOF Error)
- **Causa**: Durante le chiamate a modelli non-OpenAI tramite connettori LangChain/OpenRouter, il default del parametro `max_tokens` era impostato a una soglia minima (256-500 token). Nelle descrizioni articolate, Gemini raggiungeva il limite prima di chiudere le stringhe JSON, sollevando eccezioni del tipo:
  `Invalid JSON: EOF while parsing a string at line 16 column 14`.
- **Risoluzione**: Configurazione esplicita di `max_tokens=4000` sia in `JobEvaluator` che in `ContactHunter`, garantendo ampio margine per risposte strutturate e descrizioni di reasoning complete.

---

## 🕵️ Agente LangGraph: Contact Hunter

Quando un annuncio riceve esito `is_match = True`, si attiva il workflow autonomo implementato in [src/agents/contact_hunter.py](file:///c:/Users/borgi/projects/AI-Job-Finder/src/agents/contact_hunter.py). L'agente coordina un grafo di tre nodi per scoprire le figure chiave dell'azienda prima dell'invio della candidatura.

```
[generate_queries] ──► [execute_searches] ──► [extract_contacts] ──► END
```

1. **`generate_queries`**: Formula query a linguaggio naturale per identificare l'Hiring Manager o i recruiter interni (es. *"Who is the HR manager or recruiter for {job_title} at {company}? site:linkedin.com/in/"*).
2. **`execute_searches`**: Esegue ricerche web approfondite tramite **Tavily Search API** (modalità `search_depth="advanced"`, target domain `linkedin.com`).
3. **`extract_contacts`**: Gemini analizza i frammenti di testo estratti, mappa i profili LinkedIn autentici e calcolauristicamente l'indirizzo email aziendale più probabile sulla base dei pattern italiani (`nome.cognome@azienda.it` o `n.cognome@azienda.com`).

---

## 📲 Sistema di Notifica (WhatsApp & Email)

Il modulo [src/notifier/whatsapp_notifier.py](file:///c:/Users/borgi/projects/AI-Job-Finder/src/notifier/whatsapp_notifier.py) distribuisce l'alert su due canali in parallelo:
- **WhatsApp (via Twilio API)**: Messaggio formattato con emoji, azienda, titolo, fit score percentuale, link diretto all'offerta e nominativi dei recruiter rilevati con relative email dedotte.
- **Email (SMTP)**: Dispatch dell'alert all'indirizzo configurato per archiviazione e consultazione comoda da desktop.

---

## 📊 Storico & Data Audit (`history.csv`)

Ogni annuncio analizzato da Gemini viene registrato in tempo reale in [history.csv](file:///c:/Users/borgi/projects/AI-Job-Finder/history.csv), garantendo piena trasparenza sulle decisioni dell'AI:

| Data | Titolo | Azienda | Match | Rejection_Tag | Reasoning | URL |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| `2026-09-28 18:20:11` | *HR Specialist* | *Bending Spoons* | **SI** | *(null)* | Azienda di prodotto, full remote, ruolo in linea... | `https://...` |
| `2026-09-28 18:22:45` | *Recruiter* | *The Adecco Group* | **NO** | `AGENZIA` | Società di somministrazione categoricamente esclusa... | `https://...` |
| `2026-09-28 18:24:02` | *HR Generalist* | *Manifattura SPA* | **NO** | `LOCATION_ERRATA` | Richiede presenza 5 giorni su 5 a Torino... | `https://...` |

---

## ⚙️ Configurazione e Guida all'Uso

### 1. Prerequisiti
- Python 3.10 o superiore.
- Google Chrome / Chromium installato via Playwright.

### 2. Installazione delle Dipendenze
```bash
# Creazione e attivazione virtual environment
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux/Mac

# Installazione librerie
pip install -r requirements.txt

# Installazione browser Playwright con dipendenze
playwright install chromium
```

### 3. Configurazione Variabili d'Ambiente (`.env`)
Creare un file `.env` nella radice del progetto:

```env
# Credenziali LinkedIn (necessarie solo al primo avvio per generare la sessione)
LINKEDIN_EMAIL=tua_email@dominio.it
LINKEDIN_PASSWORD=tua_password_sicura

# LLM & Search API Keys
OPENROUTER_API_KEY=sk-or-v1-...
TAVILY_API_KEY=tvly-...

# Notifiche WhatsApp (Twilio - Opzionale)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
USER_WHATSAPP_NUMBER=whatsapp:+393XXXXXXXXX

# Notifiche Email (Opzionale)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=tuo_account@gmail.com
SMTP_PASSWORD=tua_app_password
ALERT_RECIPIENT_EMAIL=destinatario@dominio.it
```

### 4. Esecuzione dello Script
```powershell
$env:PYTHONPATH="."
$env:PYTHONIOENCODING="utf-8"
.\venv\Scripts\python -u src/main.py
```

### 5. Automazione Giornaliera (Pianificazione)
Per eseguire la scansione automatica ogni mattina alle ore 08:00 su Windows, configurare l'Utilità di Pianificazione (Task Scheduler):
- **Programma**: `C:\Users\...\AI-Job-Finder\venv\Scripts\python.exe`
- **Argomenti**: `-u src/main.py`
- **Inizia in**: `C:\Users\...\AI-Job-Finder`
