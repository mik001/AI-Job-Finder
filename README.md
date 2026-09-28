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
8. [Roadmap & Specifiche Interfaccia Utente (UI)](#-roadmap--specifiche-interfaccia-utente-ui)
9. [Configurazione e Guida all'Uso](#-configurazione-e-guida-alluso)

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

---

### 2. Indeed Italia Scraper (Zero Login, Click-to-Load Ultra-Fast)

Indeed rappresenta la seconda piattaforma cardine per volumi in Italia e l'accesso privilegiato alle PMI e aziende finali del Sud che evitano i costi elevati degli annunci LinkedIn. Il modulo [src/scraper/indeed_scraper.py](file:///c:/Users/borgi/projects/AI-Job-Finder/src/scraper/indeed_scraper.py) è stato sviluppato per massimizzare la velocità attraverso un'architettura **Click-to-Load Single-Page**.

#### A. Zero Registrazione / Nessun Account Richiesto
- **Vantaggio Ingegneristico**: A differenza di LinkedIn, Indeed permette l'accesso incondizionato alla ricerca, alle schede lavoro e all'intero corpo della descrizione **senza obbligo di login**.
- **Benefici**: Zero rischio di ban account, nessuna credenziale o sessione cookie da rinnovare su disco, avvio del browser istantaneo.

#### B. Evasione Anti-Bot & Gestione Popup
- **Playwright Stealth**: Mascheramento delle firme di automazione (`navigator.webdriver`, viewport a 1920x1080, User-Agent desktop Chromium 122+). La richiesta iniziale restituisce regolarmente `Status 200 OK` senza sfide Cloudflare Turnstile.
- **Accettazione Cookie**: Il banner OneTrust (`button#onetrust-accept-btn-handler`) viene intercettato e accettato automaticamente alla prima esecuzione.
- **Dismissal Modali con Tasto Escape**: Su Indeed, dopo aver cliccato 2 o 3 offerte consecutive, compare spesso una finestra modale sovrimpressa che invita a creare un avviso email o a registrarsi. Nel nostro scraper, prima di ogni interazione viene inviato l'evento `await page.keyboard.press("Escape")`, neutralizzando qualsiasi overlay senza bloccare il thread.

#### C. L'Architettura "Click-to-Load" Single-Page (0.4s per annuncio)
- Su Indeed non è necessario eseguire `page.goto()` sull'URL di ciascun annuncio (operazione lenta che richiede il rendering di un'intera nuova pagina).
- **Meccanismo a Pannello Laterale**: Nella schermata dei risultati di ricerca, ogni card appartiene alla classe `.cardOutline`. Cliccando programmaticamente sul link del titolo (`h2.jobTitle a, a.jcs-JobTitle`), Indeed aggiorna istantaneamente il pannello laterale destro (`#jobsearch-ViewjobPaneWrapper`) via AJAX in meno di 500ms.
- **Estrazione Descrizione Completa**: Il testo integrale della descrizione viene prelevato dal div `#jobDescriptionText` direttamente dal DOM del pannello laterale, insieme ai metadati di stipendio/RAL (es. `32.000 € - 38.000 € al mese`) e tipo di contratto (`Tempo indeterminato`).

#### D. Estrazione URL Canonici Puliti (`data-jk`)
- **Problema dei Link Sponsorizzati**: Cliccando sui link standard di Indeed, gli URL puntano a percorsi di reindirizzamento e tracciamento commerciale (`/pagead/clk?mo=...`) che contengono centinaia di caratteri di query string.
- **Soluzione Applicata**: Il parser estrae l'attributo univoco `data-jk` (Job Key, es. `92903ae8871c23cf`) presente nel tag della card e sintetizza l'URL canonico permanente e pulito:
  `https://it.indeed.com/viewjob?jk={jk}`.

#### E. Paginazione & Filtro Temporale Giornaliero (24 Ore)
- **Filtro Ultime 24 Ore**: Utilizzo della query string nativa `&fromage=1&sort=date`. Il parametro `fromage=1` istruisce Indeed a mostrare rigorosamente le offerte pubblicate nell'ultimo giorno, mentre `sort=date` le ordina cronologicamente.
- **Paginazione**: Incremento del parametro URL `&start=0`, `&start=10`, `&start=20`, `&start=30`... fino al raggiungimento di `max_results` o all'esaurimento delle card presenti sulla pagina.

---

### 3. Blueprint per Future Piattaforme (InfoJobs, Glassdoor)

L'architettura è aperta all'estensione verso ulteriori board di settore:

| Piattaforma | Meccanismo di Paginazione | Selettore Lista Card | Selettore Descrizione | Protezioni Specifiche |
| :--- | :--- | :--- | :--- | :--- |
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

Ogni annuncio analizzato viene registrato e memorizzato in tempo reale in [history.csv](file:///c:/Users/borgi/projects/AI-Job-Finder/history.csv), garantendo piena trasparenza sulle decisioni dell'AI e persistenza dello stato:

### Rilevamento Repost & Deduplicazione Cross-Platform a Due Stadi (Two-Stage Pipeline)
1. **Livello 1: SHA-256 Esatto (Stesso identico annuncio)**:
   - Calcola l'hash `Content_Hash = SHA256(norm(Azienda) + norm(Titolo) + norm(Descrizione))`. Se coincide, copia il verdetto a 0 token.
2. **Livello 2: Fuzzy Token Matching Locale (Stage 1 - Zero Cost)**:
   - Riconosce variazioni nominali dell'azienda (es. *"Magna International"* vs *"Magna Powertrain"* o *"Bending Spoons"* vs *"Bending Spoons S.p.A."*) e titoli con varianti (es. *"HR Specialist"* vs *"HR Specialist Talent Acquisition"*).
   - Se azienda, titolo e vocabolario della descrizione (Jaccard Index $\ge 35\%$) convergono, il job viene marcato come **Candidato Duplicato Cross-Platform**.
3. **Livello 3: Verifica Flash con Gemini (Stage 2 - Ultra-Low Cost)**:
   - Gemini riceve una query binaria lampo per confermare se i due testi descrivono la stessa posizione. Se confermato (`confidence >= 70%`), copia il risultato precedente senza rifare la valutazione complessa dei requisiti!

| Data | Piattaforma | Titolo | Azienda | Match | Rejection_Tag | Stato_UI | Content_Hash | Reasoning | URL |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- | :--- | :--- |
| `2026-09-28 18:20:11` | `LinkedIn` | *HR Specialist* | *Bending Spoons* | **SI** | *(null)* | `NON_LETTO` | `a3f5...` | Azienda di prodotto, full remote, ruolo in linea... | `https://...` |
| `2026-09-28 18:22:45` | `LinkedIn` | *Recruiter* | *The Adecco Group* | **NO** | `AGENZIA` | `NON_LETTO` | `8c12...` | Società di somministrazione categoricamente esclusa... | `https://...` |
| `2026-09-28 18:24:02` | `Indeed` | *HR Generalist* | *Manifattura SPA* | **NO** | `LOCATION_ERRATA` | `NON_LETTO` | `f94b...` | Richiede presenza 5 giorni su 5 a Torino... | `https://...` |

## 🖥️ Roadmap & Specifiche Interfaccia Utente (UI)

È pianificata un'interfaccia grafica moderna (collocata nel modulo [src/ui/](file:///c:/Users/borgi/projects/AI-Job-Finder/src/ui/)). Di seguito i requisiti funzionali cardine approvati che la UI implementerà:

### 1. Gestione e Modifica della Blacklist Aziende Escluse
- **Consultazione Trasparente (`data/learned_agencies.json`)**: La UI offrirà un pannello di controllo dedicato con l'elenco completo di tutte le aziende che l'Intelligenza Artificiale ha categorizzato e memorizzato come Agenzie per il Lavoro / Somministrazione / Consulenza.
- **Modifica ed Override Manuale**:
  - **Eliminazione Azienda**: L'utente potrà rimuovere con un singolo click un'azienda dalla blacklist (es. in caso di falso positivo di Gemini o se l'utente intende riaprire le porte a quella specifica realtà).
  - **Aggiunta Manuale**: Possibilità di inserire direttamente da interfaccia il nome di un'azienda da escludere a priori.
- **Sincronizzazione Bidirezionale con il Backend**: Ogni modifica apportata sulla UI si riflette istantaneamente nel file [data/learned_agencies.json](file:///c:/Users/borgi/projects/AI-Job-Finder/data/learned_agencies.json), garantendo che i successivi cicli di scraping recepiano immediatamente le nuove direttive.

### 2. Inbox Opportunità & Gestione Stato (`Stato_UI`)
- **Feed delle Candidature Valide (`is_match = True`)**: Visualizzazione a card delle posizioni promosse da Gemini con indicazione di Titolo, Azienda, Piattaforma (LinkedIn / Indeed), Fit Score %, e la scheda dei contatti dell'Hiring Manager/Recruiter dedotta da LangGraph.
- **Azioni Interattive**:
  - `Segna come Letto`: aggiorna lo `Stato_UI` da `NON_LETTO` a `LETTO` in [history.csv](file:///c:/Users/borgi/projects/AI-Job-Finder/history.csv).
  - `Scarta dalla UI`: archivia l'annuncio impostando `Stato_UI = SCARTATO`.
  - `Candidati`: link diretto all'annuncio originale per l'invio della candidatura.

### 3. Analytics e Distribuzione di Mercato
- Visualizzazione interattiva dei dati registrati in [history.csv](file:///c:/Users/borgi/projects/AI-Job-Finder/history.csv): volume annunci LinkedIn vs Indeed, percentuali di scarto per categoria (`RejectionReason`) e mappa delle opportunità su Bari/Puglia vs Full Remote.

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
