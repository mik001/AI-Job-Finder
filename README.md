# 🤖 AI Job Finder & Autonomous Contact Hunter

Sistema enterprise e autonomo per il monitoraggio avanzato del mercato del lavoro, lo scraping resiliente anti-bot (**LinkedIn** + **Indeed Italia**), la valutazione semantica dei requisiti tramite LLM (**Gemini 3.8 Flash**), la caccia automatizzata agli Hiring Manager tramite **LangGraph** & **Tavily**, notifiche istantanee gratuite via **WhatsApp (CallMeBot)**, dashboard web interattiva in **Streamlit** e infrastruttura cloud di produzione containerizzata (**Hetzner Cloud VPS + Caddy HTTPS + DuckDNS**).

---

## 📌 Indice dei Contenuti
1. [Obiettivo e Profilo Candidata](#-obiettivo-e-profilo-candidata)
2. [Architettura Generale del Sistema](#-architettura-generale-del-sistema)
3. [Infrastruttura Cloud & Produzione (Hetzner + Caddy + DuckDNS)](#-infrastruttura-cloud--produzione)
4. [Tecnologie e Moduli Chiave](#-tecnologie-e-moduli-chiave)
5. [Dettagli di Scraping: LinkedIn](#-scraping-linkedin-profondo)
6. [Dettagli di Scraping: Indeed Italia](#-scraping-indeed-italia-multi-pagina--zero-stalli)
7. [Valutazione Semantica con AI & Tassonomia Universale](#-valutazione-semantica-con-ai--tassonomia-universale)
8. [Deduplicazione Multi-Livello & Scalabilità](#-deduplicazione-multi-livello--scalabilit)
9. [Agente LangGraph: Contact Hunter](#-agente-langgraph-contact-hunter)
10. [Notifiche WhatsApp Gratuite (CallMeBot)](#-notifiche-whatsapp-callmebot)
11. [Web Dashboard Interattiva v2.0 (Streamlit)](#-web-dashboard-interattiva-v20-streamlit)
12. [Automazione & Schedulazione Continua](#-automazione--schedulazione-continua)
13. [Configurazione, Deploy Rapido e Manutenzione](#-configurazione-deploy-rapido-e-manutenzione)

---

## 🎯 Obiettivo e Profilo Candidata

Il sistema è calibrato per monitorare quotidianamente il mercato e individuare opportunità mirate per una figura **HR Recruiter / Specialist** (30 anni, 4 anni di esperienza tra Executive Search/Permanent in agenzia e somministrazione), con l'obiettivo strategico di **lavorare come HR interna nel team di un'azienda cliente finale**.

Grazie al **nuovo sistema di configurazione dinamica (`data/config.json`)**, il profilo, i vincoli geografici, i criteri contrattuali e il filtro per le agenzie possono essere **modificati in tempo reale** direttamente dall'interfaccia web per adattare il tool a qualsiasi figura professionale (IT, Marketing, Finanza, Ingegneria, ecc.).

### Requisiti Predefiniti della Candidata:
- **Ruoli Accettati**: Recruiter interna, HR Generalist, HR Specialist, Talent Acquisition, People Operations, Talent Partner, HR Business Partner.
- **Sede e Modalità di Lavoro**:
  - In presenza o ibrido: **SOLO a Bari e provincia / Puglia**.
  - Da remoto: **Full Remote in tutta Italia** (o ibrido con presenza rarissima in sede).
- **Regola Fondamentale su Agenzie e Somministrazione**:
  - ❌ **Categoricamente NO**: Ruoli interni di filiale presso agenzie per il lavoro (es. recruiter di filiale in Adecco, Randstad, Manpower, Gi Group che seleziona per terzi).
  - ✅ **ACCETTATO CON VALUTAZIONE POSITIVA (`is_match = True`)**: Contratti di somministrazione o staff leasing in cui la candidata viene inserita **a lavorare dentro il team HR di un'azienda cliente finale** (trampolino per fare esperienza aziendale interna).
- **Filtro Agenzie Configurabile**: Toggle attivabile/disattivabile per consentire o bloccare le agenzie/headhunter in base alle preferenze.
- **Warning Tollerati (Non Scartano l'Annuncio)**:
  - Seniority alta (HR Manager) o bassa (Stage/Junior).
  - Contratti Freelance / P.IVA.

---

## 🏗️ Architettura Generale del Sistema

```
                        [ Web Dashboard Streamlit o Orario Schedulato ]
                                               │
                                               ▼
                        [ Demone Schedulatore Continuo 24/7 (src/scheduler.py) ]
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
                              ├── Pre-filtro Blacklist Agenzie a monte (se abilitato)
                              ├── Valutazione semantica con Tassonomia Universale (10 Enum)
                              ├── Auto-apprendimento dinamico in data/learned_agencies.json
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

## ☁️ Infrastruttura Cloud & Produzione

L'applicazione è ospitata su infrastruttura cloud dedicata ad alte prestazioni:

```
                            INTERNET (Utenti & Browser)
                                         │
                               HTTPS (Porta 443) / HTTP (Porta 80)
                                         ▼
                      ┌─────────────────────────────────────┐
                      │    HETZNER CLOUD HARDWARE FIREWALL  │
                      │    Porte ammesse: 22, 80, 443       │
                      │    Porta 8501: TOTALMENTE BLOCCATA   │
                      └──────────────────┬──────────────────┘
                                         ▼
                      ┌─────────────────────────────────────┐
                      │        CADDY REVERSE PROXY          │
                      │  - Certificato SSL Let's Encrypt    │
                      │  - Dominio: my-job-finder.duckdns.org│
                      │  - HTTP Basic Auth (Bcrypt Cifrato) │
                      │  - Utenti: admin, bartoli           │
                      └──────────────────┬──────────────────┘
                                         │ Rete interna Docker privata (jobfinder-net)
                                         ▼
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
┌──────────────────────────────┐                   ┌──────────────────────────────┐
│  ai_job_finder_ui            │                   │  ai_job_finder_scheduler     │
│  - Web Dashboard Streamlit   │                   │  - Demone Continuo 24/7      │
│  - Fragment Live Auto-Refresh│                   │  - Timezone Europe/Rome      │
│  - Porta 8501 (Solo interna) │                   │  - Hot-Reloading Config      │
└──────────────┬───────────────┘                   └──────────────┬───────────────┘
               │                                                  │
               └───────────────────────┬──────────────────────────┘
                                       │ Volume Persistente Condiviso
                                       ▼
                       ┌──────────────────────────────┐
                       │    PERSISTENT STORAGE        │
                       │    - history.csv             │
                       │    - data/config.json        │
                       │    - data/scheduler_state.json│
                       │    - data/learned_agencies.json
                       │    - linkedin_session.json   │
                       │    - indeed_session.json     │
                       └──────────────────────────────┘
```

### Specifiche Tecniche del Server:
* **Provider**: Hetzner Cloud (Datacenter Norimberga `nbg1`).
* **Hardware**: Server `cx23` (2 vCPU x86_64, 4 GB RAM, 40 GB NVMe SSD, 2 GB Swap attivo).
* **Traffico**: 20 TB/mese inclusi a banda 1 Gbps.
* **Costo**: Solo **0,0088 €/ora** (massimo **~6,70 €/mese con IVA**).
* **Dominio Pubblico**: `https://my-job-finder.duckdns.org` con rinnovo automatico certificati TLS 1.3 Let's Encrypt.
* **Sicurezza "Defense in Depth"**:
  1. **Firewall Hardware**: porta 8501 rimossa dall'esterno per impedire bypass del proxy.
  2. **Isolamento Docker**: il container Streamlit è esposto solo all'interno del bridge privato `jobfinder-net`.
  3. **Bcrypt Authentication**: Caddy intercetta qualsiasi tentativo non autorizzato con `401 Unauthorized` a monte, proteggendo il backend da bot, crawler e scanner di rete.

---

## 🌐 Tecnologie e Moduli Chiave

- **Linguaggio**: Python 3.10+ (Playwright Jammy base image).
- **Browser Automation**: Playwright + `playwright-stealth` (Chromium anti-detection, headless shell v1243).
- **AI & LLM**: Google Gemini 3.8 Flash (`gemini-2.5-flash` tramite OpenRouter e API nativa).
- **Orchestrazione Agenti**: LangGraph + LangChain Core + LangChain OpenAI.
- **Search Engine API**: Tavily Search API.
- **Notifiche**: CallMeBot WhatsApp API (100% gratuito e senza vincoli sandbox).
- **Frontend Dashboard**: Streamlit v1.64+ (componenti reattivi, `@st.fragment` e custom CSS).
- **Web Server & Reverse Proxy**: Caddy 2.8 Alpine con ACME Let's Encrypt automatico e Bcrypt Basic Auth.
- **Orchestrazione Container**: Docker Engine + Docker Compose v2.

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
  1. **Parsing Statico Immediato**: Tutte le 16 card della pagina vengono lette via BeautifulSoup in **0.05 secondi**.
  2. **Deduplicazione a Zero Latenza**: Se l'URL o il `data-jk` è già nello storico, viene saltato all'istante senza toccare il browser.
  3. **Apertura Pannello Sicura**: Apertura tramite `MouseEvent` con bubbling sintetico sull'intestazione (senza navigare via dall'URL di ricerca).
  4. **Timeout Rigido a 800ms con Fallback**: Se il pannello destro `#jobsearch-ViewjobPaneWrapper` non carica entro 800ms, il testo dell'annuncio viene recuperato direttamente dalla card HTML.
- **Paginazione Multi-Pagina Fluida**: Scansiona `start=0`, `start=10`, `start=20` con tab isolati per prevenire sfide Cloudflare Turnstile.
- **Descrizioni Integrali Preservate**: Estrazione del testo completo da `.simple-job-description-html` e `#jobDescriptionText` (fino a 6.900+ caratteri).

---

## 🧠 Valutazione Semantica con AI & Tassonomia Universale

Modulo: [`src/evaluator/job_evaluator.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/evaluator/job_evaluator.py)

- **Modello**: Google **Gemini 3.8 Flash** (`google/gemini-3.8-flash`).
- **Tassonomia dei Rifiuti Generalizzata (`RejectionReason` Enum)**:
  - `RUOLO_NON_ATTINENTE`: Ruolo o mansioni non compatibili con il profilo (sostituisce e generalizza `NOT_HR`).
  - `LOCATION_INCOMPATIBILE`: Sede non raggiungibile o assenza di smart working/remoto richiesto (retrocompatibile con `LOCATION_ERRATA`).
  - `AGENZIA`: Agenzie per il lavoro, società di somministrazione o headhunting escluse dai vincoli.
  - `SENIORITY_INCOMPATIBILE`: Livello di esperienza/seniority non allineato (se il profilo lo impone come vincolo).
  - `CONTRATTO_INCOMPATIBILE`: Tipologia contrattuale non conforme (es. stage non retribuito o P.IVA se rifiutati).
  - `COMPETENZE_MANCANTI`: Mancanza di requisiti tecnici o certificazioni essenziali e bloccanti.
  - `CATEGORIA_PROTETTA`: Offerte riservate a Categorie Protette (L. 68/99).
  - `LINGUA`: Richiesta fluente di lingue non possedute.
  - `MANCANZA_DATI`: Descrizione troppo generica o priva di dettagli essenziali.
  - `ALTRO`: Qualsiasi altra motivazione specifica spiegata nel reasoning.
- **Filtro Agenzie Configurabile (`exclude_agencies`)**:
  - Quando **ATTIVO**: il system prompt include la regola per scartare le agenzie, attiva il pre-filtro a monte a zero token e memorizza le nuove società scartate in `learned_agencies.json`.
  - Quando **DISATTIVATO**: il prompt omette completamente la regola agenzie, consentendo la valutazione neutra di offerte da intermediari, società di consulenza o headhunter.

---

## ⚡ Deduplicazione Multi-Livello & Scalabilità

1. **Deduplicazione URL $O(1)$**: Ricerca istantanea su `set()` in memoria degli URL già processati.
2. **Fingerprint SHA-256 (`Content_Hash`)**:
   $$Content\_Hash = \text{SHA256}(\text{Azienda} + \text{Titolo} + \text{Testo})$$
   Identifica ripubblicazioni e repost con nuovi ID a 0 chiamate API.
3. **Fuzzy Cross-Platform Matching (LinkedIn vs Indeed)**:
   - *Fase 1 (Locale)*: Jaccard similarity su parole chiave di azienda, titolo e vocabolario annuncio.
   - *Fase 2 (Verifica Gemini)*: Mini-query binaria lampo per confermare se due annunci cross-platform rappresentano la stessa posizione lavorativa.
4. **Scalabilità dello Storico**:
   - Con centinaia di record già memorizzati, la lettura di `history.csv` richiede meno di **0.02 secondi**.

---

## 🕵️ Agente LangGraph: Contact Hunter

Modulo: [`src/agents/contact_hunter.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/agents/contact_hunter.py)

Attivato esclusivamente per le offerte con esito `is_match = True`:
```
[generate_queries] ──► [execute_searches (Tavily)] ──► [extract_contacts (Gemini)] ──► END
```
- Formula query mirate per individuare l'Hiring Manager o il Talent Acquisition Lead dell'azienda.
- Esegue ricerche sul web tramite Tavily filtrando su `linkedin.com/in/`.
- Deduce e mappa il profilo del referente e il pattern email aziendale più probabile (es. `nome.cognome@azienda.it`).

---

## 📱 Notifiche WhatsApp Multi-Destinatario (CallMeBot)

Modulo: [`src/notifier/whatsapp_notifier.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/notifier/whatsapp_notifier.py)

- **100% Gratuito, Diretto e Illimitato**: Utilizza l'API di CallMeBot collegata ai numeri WhatsApp personali senza limiti di sandbox o scadenze di 24 ore.
- **Supporto Multi-Destinatario / Multi-API-Key**: Ogni membro del team o candidato può configurare il proprio numero WhatsApp con la propria API Key CallMeBot personale generata via chat.
- **Configurazione da Web UI**: Gestione completa direttamente dalla Tab 4 della dashboard (Aggiungi, Attiva/Disattiva, Rimuovi, Invia Notifica di Test 1-click).
- **Auto-Discovery da `.env`**: Rilevamento e migrazione automatica trasparente delle variabili `CALLMEBOT_API_KEY`, `USER_WHATSAPP_NUMBER`, `CALLMEBOT_API_KEY_2`, ecc. in `data/config.json`.
- **Formato Notifica**:
  ```text
  🚀 *Nuovo Match Lavorativo!*

  💼 *Ruolo:* HR Generalist
  🏢 *Azienda:* Azienda Esempio S.p.A.
  🎯 *Fit Score:* 95/100

  👥 *Contatti Trovati:*
  - Mario Rossi (Head of HR): m.rossi@azienda.it

  🔗 *Link Annuncio:* https://www.linkedin.com/jobs/view/...
  ```

---

## 💻 Web Dashboard Interattiva v2.0 (Streamlit)

Modulo: [`src/ui/app.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/ui/app.py)

Interfaccia reattiva moderna conforme ai principi **Impeccable** (gerarchia visiva pulita, contrasto AAA, zero layout-shift):

1. **Tab 1: 🎯 Opportunità Lavorative Valide**:
   - Schede incapsulate con badge colorati per piattaforma, data e fit score.
   - Accordion con descrizione integrale dell'annuncio per lettura offline.
   - Azioni 1-click: `Mark: Letto`, `🚀 Segna Candidato`, `📁 Archivia`, `↩️ Ripristina`.
2. **Tab 2: 📋 Archivio Offerte Scartate**:
   - Tabella interattiva per l'audit dei motivi di esclusione con filtri per tag canonico, piattaforma e ricerca testuale.
3. **Tab 3: 🛡️ Gestione Blacklist Agenzie**:
   - Banner dinamico sullo stato del filtro (`ATTIVO` o `DISATTIVATO`).
   - Aggiunta manuale e rimozione protetta delle aziende in blacklist.
4. **Tab 4: ⚙️ Configurazione & Schedulazione**:
   - **Monitor Live con `@st.fragment(run_every=4)`**: aggiornamento automatico dello stato e della fase di scansione ogni 4 secondi senza ricaricare la pagina.
   - **Pulsante "🚀 Avvia Scansione Adesso"**: trigger manuale istantaneo delegato al demone di background.
   - **Editor Orari**: gestione flessibile degli slot giornalieri con validazione `HH:MM`.
   - **Canali WhatsApp (CallMeBot)**: gestione completa dei destinatari, test istantaneo di recapito e toggle globale on/off.
   - **Editor Profilo Candidato**: textarea per personalizzare le istruzioni AI e toggle `🛡️ Escludi Agenzie ed Headhunting`.
   - **Editor Query di Ricerca**: configurazione parole chiave e località per LinkedIn e Indeed.
   - **Guida Tassonomia Rifiuti**: tabella esplicativa dei 10 codici di scarto.
5. **Tab 5: 📜 Log & Diagnostica Live**:
   - **Live Streaming (`@st.fragment(run_every=3)`)**: console ad alto contrasto con aggiornamento in tempo reale riga per riga.
   - **Filtri di Categoria**: visualizzazione isolata per *AI Gemini*, *LinkedIn*, *Indeed (Security Checks)*, *Contact Hunter* o *WhatsApp*.
   - **Ricerca Testuale**: full-text search immediato nei log per individuare errori, aziende o motivi di scarto.
   - **Metriche Real-Time**: conteggio eventi, blocchi Cloudflare e match calcolati live.
   - **Esportazione 1-Click**: download del file `.log` completo per archiviazione e audit.

---

## ⏰ Automazione & Schedulazione Continua

Modulo: [`src/scheduler.py`](file:///c:/Users/borgi/projects/AI-Job-Finder/src/scheduler.py)

- **Demone Continuo 24/7**: Esegue in background come container dedicato con policy `restart: unless-stopped`.
- **Timezone**: Sincronizzato con il fuso orario italiano (`Europe/Rome`).
- **Hot-Reloading**: Ricarica a caldo le modifiche orarie e i criteri di ricerca salvati in `data/config.json` senza bisogno di riavviare il servizio.
- **Esecuzione Isolata**: Lancia `src/main.py` in un sottoprocesso separato con `PYTHONUNBUFFERED=1`, garantendo la massima resilienza e aggiornando costantemente `data/scheduler_state.json`.

---

## 🚀 Configurazione, Deploy Rapido e Manutenzione

### 1. File di Configurazione (`.env`)
```env
# AI & LLM (OpenRouter / Gemini)
OPENROUTER_API_KEY=sk-or-v1-...
GEMINI_API_KEY=AQ.Ab8...
TAVILY_API_KEY=tvly-...

# Notifiche WhatsApp
CALLMEBOT_API_KEY=tuo_codice_callmebot
USER_WHATSAPP_NUMBER=whatsapp:+393XXXXXXXXX

# LinkedIn (Cookie Stealth)
LINKEDIN_EMAIL=tua_email@gmail.com
LINKEDIN_PASSWORD=tua_password

# Indeed (OTP via Gmail IMAP)
INDEED_EMAIL=tua_email@gmail.com
INDEED_IMAP_USER=tua_email@gmail.com
INDEED_IMAP_PASSWORD=app_password_16_caratteri
```

### 2. Deploy Rapido su VPS con 1 Comando (PowerShell)
Dal tuo PC locale Windows:
```powershell
.\deploy\deploy_to_vps.ps1
```
Lo script sincronizza automaticamente `src/`, file di configurazione, aggiorna l'immagine Docker e riavvia i container sul server Hetzner.

### 3. Comandi di Gestione da Remoto (SSH)
```bash
# Connessione al server
ssh root@195.201.148.129

# Stato dei container
docker compose -f /opt/ai-job-finder/docker-compose.prod.yml ps

# Seguire i log in diretta dello schedulatore
docker compose -f /opt/ai-job-finder/docker-compose.prod.yml logs -f ai-job-finder-scheduler

# Seguire i log della Web UI
docker compose -f /opt/ai-job-finder/docker-compose.prod.yml logs -f ai-job-finder-ui

# Riavvio stack completo
docker compose -f /opt/ai-job-finder/docker-compose.prod.yml restart
```

---

## 📄 Licenza e Manutenibilità
Progetto open-source a uso privato, rilasciato sotto licenza MIT. Tutti i cookie, le credenziali e i dati personali sono protetti tramite `.gitignore`.
