#!/usr/bin/env bash
# ==============================================================================
# AI JOB FINDER - SCRIPT DI DEPLOY AUTOMATIZZATO PER VPS LINUX (UBUNTU / DEBIAN)
# Hetzner Cloud / DigitalOcean / AWS Lightsail / Linode
# ==============================================================================

set -e

echo "================================================================="
echo "🚀 AVVIO INSTALLAZIONE E DEPLOY DI PRODUZIONE: AI JOB FINDER"
echo "================================================================="

# 1. Verifica permessi di root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Esegui questo script come root o con 'sudo bash setup_vps.sh'"
  exit 1
fi

# 2. Aggiornamento pacchetti di sistema
echo "[*] Aggiornamento repository di sistema..."
apt-get update -y
apt-get install -y apt-transport-https ca-certificates curl software-properties-common gnupg lsb-release ufw

# 3. Configurazione SWAP (2GB) se non presente (previene Out-Of-Memory con Chromium)
if [ ! -f /swapfile ]; then
    echo "[*] Creazione file di SWAP da 2GB per ottimizzare le risorse di Playwright..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "[+] SWAP attivato con successo."
fi

# 4. Installazione Docker & Docker Compose
if ! command -v docker &> /dev/null; then
    echo "[*] Installazione Docker Engine..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    systemctl enable docker
    systemctl start docker
    echo "[+] Docker installato con successo."
else
    echo "[+] Docker è già presente sul sistema."
fi

# 5. Configurazione Firewall UFW
echo "[*] Configurazione porte del firewall (SSH 22, HTTP 80, HTTPS 443, UI 8501)..."
ufw allow 22/tcp || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
ufw allow 8501/tcp || true
ufw --force enable || true

# 6. Verifica file di configurazione .env
if [ ! -f .env ]; then
    echo "[-] File .env non trovato. Creazione da .env.example..."
    cp .env.example .env
    echo "[!] Modifica il file .env con le tue chiavi API prima di avviare il servizio:"
    echo "    nano .env"
    exit 0
fi

# 7. Creazione cartella data se mancante
mkdir -p data

# 8. Build e Avvio dei Container di Produzione
echo "[*] Compilazione immagini e avvio dello stack Docker di produzione (UI + Scheduler + SSL Caddy)..."
docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "================================================================="
echo "✅ DEPLOY COMPLETATO CON SUCCESSO!"
echo "================================================================="
echo "I servizi sono ora attivi in background:"
echo "- 💼 Web Dashboard (Streamlit): Accessibile via browser su HTTP/HTTPS"
echo "- ⏰ Schedulatore Continuo: In esecuzione 24/7 (08:30 / 18:00)"
echo "- 🔒 Caddy SSL Proxy: Certificati HTTPS Let's Encrypt automatici"
echo ""
echo "Comandi utili per la gestione:"
echo "- Visualizza log scheduler: docker compose -f docker-compose.prod.yml logs -f ai-job-finder-scheduler"
echo "- Visualizza log web UI:    docker compose -f docker-compose.prod.yml logs -f ai-job-finder-ui"
echo "- Riavvia stack:            docker compose -f docker-compose.prod.yml restart"
echo "- Arresta stack:            docker compose -f docker-compose.prod.yml down"
echo "================================================================="
