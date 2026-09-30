# 🚀 Guida Ufficiale di Hosting in Produzione: AI Job Finder

Questa guida documenta l'architettura di produzione attiva di **AI Job Finder** ospitata su **Hetzner Cloud VPS**, con certificato SSL **HTTPS Let's Encrypt**, dominio **DuckDNS**, autenticazione multi-utente crittografata con **Bcrypt** e schedulatore continuo 24/7.

---

## 📌 Indice dei Contenuti
1. [Infrastruttura Attiva in Produzione](#-infrastruttura-attiva-in-produzione)
2. [Analisi dei Costi Reali Hetzner](#-analisi-dei-costi-reali-hetzner)
3. [Architettura di Rete & Sicurezza](#-architettura-di-rete--sicurezza)
4. [Dominio DuckDNS & Certificati SSL (Caddy)](#-dominio-duckdns--certificati-ssl-caddy)
5. [Gestione Utenti & Autenticazione Bcrypt](#-gestione-utenti--autenticazione-bcrypt)
6. [Demone Schedulatore & Auto-Refresh](#-demone-schedulatore--auto-refresh)
7. [Deploy Rapido & Comandi di Gestione](#-deploy-rapido--comandi-di-gestione)
8. [Procedure di Backup & Ripristino Dati](#-procedure-di-backup--ripristino-dati)

---

## 🏆 Infrastruttura Attiva in Produzione

L'istanza è ospitata nel datacenter europeo di Norimberga (`nbg1`):

| Parametro | Valore Reale in Produzione |
| :--- | :--- |
| **Provider** | Hetzner Cloud |
| **Server Name** | `ai-job-finder-vps` (ID: `168070554`) |
| **Tipo Istanza** | `cx23` (x86_64) |
| **CPU & RAM** | 2 vCPU dedicate/shared, 4 GB RAM DDR4 |
| **Memoria Swap** | 2 GB Swap file attivo (`/swapfile`) |
| **Disco** | 40 GB NVMe SSD |
| **Indirizzo IPv4** | `195.201.148.129` |
| **Sistema Operativo** | Ubuntu 24.04 LTS x86_64 |
| **Dominio Pubblico** | **`https://my-job-finder.duckdns.org`** |

---

## 💰 Analisi dei Costi Reali Hetzner

La fatturazione di Hetzner Cloud avviene al secondo di utilizzo:

* **Tariffa Oraria**: `0,0088 € / ora` netti (`~0,0107 € / ora` con IVA).
* **Tetto Mensile Massimo**: **`5,49 € / mese`** netti (**`~6,70 € / mese`** con IVA).
* **Traffico Incluso**: **20 TB al mese** a 1 Gbps (nessun costo nascosto di banda).
* **Chiamate AI (Gemini 3.8 Flash)**: Circa `$0.075` per 1.000.000 di token, quantificabile in pochi centesimi al mese grazie al pre-filtro a zero token e alla deduplicazione a monte.

Puoi monitorare la spesa accumulata al centesimo direttamente dalla console:
👉 [https://console.hetzner.cloud/](https://console.hetzner.cloud/) -> Sezione **Usage / Invoices**.

---

## 🛡️ Architettura di Rete & Sicurezza (Defense in Depth)

```
                            INTERNET
                               │
                      Porte 80 (HTTP) e 443 (HTTPS)
                               ▼
        ┌──────────────────────────────────────────────┐
        │        HETZNER CLOUD HARDWARE FIREWALL       │
        │        - Inbound: 22 (SSH), 80 (HTTP), 443   │
        │        - Porta 8501: TOTALMENTE BLOCCATA     │
        └──────────────────────┬───────────────────────┘
                               ▼
        ┌──────────────────────────────────────────────┐
        │              CADDY REVERSE PROXY             │
        │        - Certificato Let's Encrypt TLS 1.3   │
        │        - HTTP Basic Auth (Bcrypt Cifrato)    │
        │        - Utenti: admin, bartoli              │
        └──────────────────────┬───────────────────────┘
                               │ Bridge Docker Privato (jobfinder-net)
                               ▼
                 ┌─────────────────────────────┐
                 │    ai_job_finder_ui         │
                 │    (Streamlit Porta 8501)   │
                 └─────────────────────────────┘
```

1. **Firewall a Livello Router**: La porta 8501 di Streamlit è rimossa dal firewall hardware (`ai-job-finder-fw`, ID: `11708486`). Eventuali pacchetti diretti a `195.201.148.129:8501` vengono scartati all'ingresso.
2. **Isolamento Container**: Nel file `docker-compose.prod.yml`, la direttiva `ports: - "8501:8501"` è stata eliminata in favore di `expose: - "8501"`. L'applicazione risponde unicamente a Caddy all'interno del bridge privato.
3. **Protezione Anti-Bot / Anti-Scanner**: Caddy risponde con `401 Unauthorized` a monte per qualsiasi tentativo non autenticato, azzerando il consumo di CPU e proteggendo il backend da vulnerabilità applicative.

---

## 🦆 Dominio DuckDNS & Certificati SSL (Caddy)

Il puntamento DNS è gestito gratuitamente tramite **DuckDNS**:
* **Hostname**: `my-job-finder.duckdns.org`
* **Record A**: Punta direttamente a `195.201.148.129`.
* **Caddyfile di Produzione**:
  ```caddy
  my-job-finder.duckdns.org {
      basicauth * {
          admin $2a$14$/tl4FSBteH27nVdHAr1BuukF1W53d3bckNqHZ3vDm3AVRhscJpayK
          bartoli $2a$14$2WJnApYbHDWRVAAZnhaqTOGxnxRxx6OvrG7FEKuJOVngG.035k.8C
      }

      reverse_proxy ai-job-finder-ui:8501 {
          header_up Host {host}
          header_up X-Real-IP {remote_host}
          header_up X-Forwarded-For {remote_host}
          header_up X-Forwarded-Proto {scheme}
      }
  }
  ```
* **Rinnovo Automatico**: Caddy negozia e rinnova autonomamente i certificati Let's Encrypt tramite protocollo ACME ogni 60 giorni.

---

## 🔑 Gestione Utenti & Autenticazione Bcrypt

Le password sul server non sono mai memorizzate in chiaro, ma protette con algoritmo crittografico ad alto costo computazionale (**Bcrypt**).

### Utenti Attualmente Configurati:
* `admin`
* `bartoli`

### Come Aggiungere o Modificare un Utente in Futuro:
1. Connettiti via SSH al server:
   ```bash
   ssh root@195.201.148.129
   ```
2. Genera l'hash Bcrypt per la nuova password:
   ```bash
   docker run --rm caddy:2.8-alpine caddy hash-password --plaintext "NuovaPassword123!"
   ```
3. Modifica `/opt/ai-job-finder/Caddyfile` e aggiungi la riga nel blocco `basicauth *`:
   ```caddy
   nuovoutente $2a$14$HashGeneratoNelPassaggioPrecedente...
   ```
4. Riavvia Caddy istantaneamente:
   ```bash
   docker compose -f /opt/ai-job-finder/docker-compose.prod.yml restart caddy
   ```

---

## ⏰ Demone Schedulatore & Auto-Refresh

* **Container Dedicato**: `ai_job_finder_scheduler` esegue `src/scheduler.py` in background 24/7.
* **Separazione dei Processi**: Il demone e la Web UI operano in container distinti. Eventuali riavvii o reload dell'interfaccia grafica **non interrompono** mai una scansione in corso.
* **Auto-Aggiornamento con Streamlit Fragment**:
  Nella Tab 4 ("⚙️ Configurazione & Schedulazione"), il monitor è racchiuso nel decoratore nativo `@st.fragment(run_every=4)`:
  - Aggiorna in tempo reale la fase e il progresso ogni 4 secondi.
  - È attivo **solo quando l'utente si trova in quella scheda**, spegnendosi quando si naviga in altre sezioni.
  - È provvisto di uno switch per disattivare o riattivare il polling continuo a piacere.

---

## 🚀 Deploy Rapido & Comandi di Gestione

### 1. Deploy da PC Locale con Singolo Comando (PowerShell)
Dal tuo terminale Windows, esegui:
```powershell
.\deploy\deploy_to_vps.ps1
```
Lo script:
1. Sincronizza la cartella `src/` e i file di configurazione via SSH/SCP.
2. Esegue il build incrementale Docker (con caching delle librerie).
3. Riavvia i container in produzione in meno di 10 secondi.

### 2. Comandi Operativi sul Server (SSH)
```bash
# Accesso rapido
ssh root@195.201.148.129

# Ispezione dello stato dei container
docker compose -f /opt/ai-job-finder/docker-compose.prod.yml ps

# Seguire i log in tempo reale dello schedulatore
docker compose -f /opt/ai-job-finder/docker-compose.prod.yml logs -f ai-job-finder-scheduler

# Seguire i log della Web UI Streamlit
docker compose -f /opt/ai-job-finder/docker-compose.prod.yml logs -f ai-job-finder-ui

# Riavviare l'intero stack
docker compose -f /opt/ai-job-finder/docker-compose.prod.yml restart
```

---

## 💾 Procedure di Backup & Ripristino Dati

Tutti i dati persistenti risiedono nei volumi montati su disco permanente:
* `/opt/ai-job-finder/history.csv`: archivio completo di tutti gli annunci esaminati con testi integrali.
* `/opt/ai-job-finder/data/`:
  - `config.json`: impostazioni profilo, query e schedulazione.
  - `learned_agencies.json`: blacklist persistente delle società interinali/headhunting.
  - `scheduler_state.json`: stato live di esecuzione.
* `/opt/ai-job-finder/linkedin_session.json` e `indeed_session.json`: cookie di autenticazione stealth.

### Download Backup su PC Locale (da PowerShell):
```powershell
# Esegui da locale per salvare lo storico e i dati sul tuo PC:
scp root@195.201.148.129:/opt/ai-job-finder/history.csv ./history_backup.csv
scp -r root@195.201.148.129:/opt/ai-job-finder/data ./data_backup/
```
