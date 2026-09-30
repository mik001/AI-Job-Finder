# Script PowerShell per deploy rapido su VPS Hetzner
$VPS_IP = "195.201.148.129"
$REMOTE_DIR = "/opt/ai-job-finder"

Write-Host "🚀 Sincronizzazione codice sorgente e file di configurazione verso $VPS_IP..." -ForegroundColor Cyan
scp -r -o BatchMode=yes src root@${VPS_IP}:${REMOTE_DIR}/
scp -o BatchMode=yes docker-compose.prod.yml Caddyfile Dockerfile requirements.txt root@${VPS_IP}:${REMOTE_DIR}/

Write-Host "🔄 Riavvio e build rapido dei container in produzione..." -ForegroundColor Cyan
ssh -o BatchMode=yes root@$VPS_IP "cd $REMOTE_DIR && docker compose -f docker-compose.prod.yml up -d --build"

Write-Host "✅ Deploy completato con successo!" -ForegroundColor Green
Write-Host "🌐 Web Dashboard: http://${VPS_IP}:8501" -ForegroundColor Yellow
