# =========================================================================
# Setup Windows Scheduled Task per AI Job Finder
# =========================================================================

$ProjectDir = Split-Path -Parent $PSScriptRoot
$BatPath = Join-Path $PSScriptRoot "run_daily.bat"
$TaskName = "AI-Job-Finder"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "🤖 CONFIGURAZIONE SCHEDULATORE AUTOMATICO WINDOWS" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Azione: esecuzione dello script batch
$Action = New-ScheduledTaskAction -Execute $BatPath -WorkingDirectory $ProjectDir

# Trigger: Esecuzione due volte al giorno (ore 08:30 e ore 18:00)
$TriggerMorning = New-ScheduledTaskTrigger -Daily -At "08:30"
$TriggerEvening = New-ScheduledTaskTrigger -Daily -At "18:00"

# Impostazioni task: esegui appena possibile se un avvio viene mancato
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# Registrazione Task
try {
    # Rimuovi task precedente se già presente
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($TriggerMorning, $TriggerEvening) -Settings $Settings -Description "Esecuzione autonoma di AI Job Finder (LinkedIn + Indeed)"
    
    Write-Host "`n[+] Task '$TaskName' registrato con successo in Windows Task Scheduler!" -ForegroundColor Green
    Write-Host "    - Orari di esecuzione: 08:30 e 18:00 ogni giorno" -ForegroundColor Green
    Write-Host "    - Script avviato: $BatPath" -ForegroundColor Green
    Write-Host "    - Log salvati in: $ProjectDir\data\scheduler.log`n" -ForegroundColor Green
} catch {
    Write-Host "`n[-] Errore durante la registrazione: $_" -ForegroundColor Red
    Write-Host "[!] Assicurati di eseguire PowerShell come Amministratore se richiesto dai permessi di sistema." -ForegroundColor Yellow
}
