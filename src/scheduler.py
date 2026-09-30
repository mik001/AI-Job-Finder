import os
import sys
import time
import subprocess
import signal
from datetime import datetime, timedelta

# Dual-output logger che scrive contemporaneamente su console e su data/system_run.log
LOG_FILE_PATH = os.path.join("data", "system_run.log")

class TeeLogger:
    def __init__(self, filepath, stream):
        self.stream = stream
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.file = open(filepath, "a", encoding="utf-8", buffering=1)

    def write(self, data):
        self.stream.write(data)
        try:
            self.file.write(data)
        except Exception:
            pass

    def flush(self):
        self.stream.flush()
        try:
            self.file.flush()
        except Exception:
            pass

if not isinstance(sys.stdout, TeeLogger):
    sys.stdout = TeeLogger(LOG_FILE_PATH, sys.stdout)
if not isinstance(sys.stderr, TeeLogger):
    sys.stderr = TeeLogger(LOG_FILE_PATH, sys.stderr)

# Gestione timezone con fallback difensivo
try:
    from zoneinfo import ZoneInfo
    ROME_TZ = ZoneInfo("Europe/Rome")
except Exception:
    ROME_TZ = None

from src.config_manager import ConfigManager

def get_current_time():
    """Restituisce il datetime corrente con la corretta timezone italiana."""
    if ROME_TZ:
        return datetime.now(ROME_TZ)
    return datetime.now()

def parse_time_slot(time_str: str):
    """Converte '08:30' o '8:30' in tupla (ora, minuto)."""
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]), int(parts[1])
    except Exception:
        return None

def compute_next_run(scheduled_times_list: list, enabled: bool) -> str:
    """Calcola la data e ora della prossima esecuzione programmata."""
    if not enabled or not scheduled_times_list:
        return "Disattivata"

    now = get_current_time()
    today_date = now.date()
    
    candidate_dts = []
    for t_str in scheduled_times_list:
        parsed = parse_time_slot(t_str)
        if not parsed:
            continue
        h, m = parsed
        
        # Orario oggi
        dt_today = datetime(today_date.year, today_date.month, today_date.day, h, m, tzinfo=now.tzinfo)
        if dt_today > now:
            candidate_dts.append(dt_today)
        else:
            # Orario domani
            dt_tomorrow = dt_today + timedelta(days=1)
            candidate_dts.append(dt_tomorrow)
            
    if not candidate_dts:
        return "Nessun orario valido configurato"
        
    next_dt = min(candidate_dts)
    return next_dt.strftime("%Y-%m-%d %H:%M:%S")

def run_pipeline(reason: str = "Schedulazione automatica"):
    """Esegue la pipeline di AI Job Finder tramite subprocess isolato."""
    now_str = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now_str}] 🚀 Avvio pipeline ({reason})...")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    
    python_bin = sys.executable
    start_time = time.time()
    
    ConfigManager.update_scheduler_state(
        is_running=True,
        last_status="RUNNING",
        last_run_start=now_str,
        last_message=f"Pipeline avviata ({reason})",
        current_step="Avvio processo di scraping..."
    )
    
    try:
        result = subprocess.run([python_bin, "-u", "src/main.py"], env=env)
        duration_sec = round(time.time() - start_time, 1)
        finish_str = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
        
        if result.returncode == 0:
            print(f"[{finish_str}] [+] Pipeline completata con successo in {duration_sec}s.\n")
        else:
            print(f"[{finish_str}] [-] Pipeline terminata con codice di errore {result.returncode}.\n")
            ConfigManager.update_scheduler_state(
                is_running=False,
                last_run_end=finish_str,
                last_status="ERROR",
                current_step="Terminato con errore",
                last_message=f"Processo terminato con codice {result.returncode}"
            )
    except Exception as e:
        finish_str = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[-] Errore critico avvio subprocess: {e}\n")
        ConfigManager.update_scheduler_state(
            is_running=False,
            last_run_end=finish_str,
            last_status="ERROR",
            current_step="Errore esecuzione",
            last_message=str(e)[:200]
        )

def handle_shutdown(signum, frame):
    """Gestione pulita della terminazione dello scheduler."""
    print("\n[!] Ricevuto segnale di arresto. Chiusura pulita dello schedulatore...")
    ConfigManager.update_scheduler_state(
        is_running=False,
        current_step="Schedulatore arrestato",
        last_message="Demone arrestato pulitamente"
    )
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_shutdown)

    print("="*65)
    print("⏰ AI JOB FINDER - DEMONE SCHEDULATORE CONTINUO DI PRODUZIONE")
    print("="*65)
    
    # Inizializzazione stato
    ConfigManager.update_scheduler_state(
        is_running=False,
        last_status="IDLE",
        current_step="In attesa",
        last_message="Schedulatore attivo in background"
    )
    
    executed_slots_today = set()
    last_cleaned_day = None
    
    while True:
        try:
            # 1. Carica configurazione schedulazione a caldo (hot-reloading)
            sched_cfg = ConfigManager.get_scheduling_config()
            is_enabled = sched_cfg.get("enabled", True)
            times_list = sched_cfg.get("times", ["08:30", "18:00"])
            
            # Calcola e aggiorna la prossima esecuzione per la dashboard UI
            next_run_str = compute_next_run(times_list, is_enabled)
            state = ConfigManager.load_scheduler_state()
            if state.get("next_run") != next_run_str and not state.get("is_running"):
                ConfigManager.update_scheduler_state(next_run=next_run_str)
                
            # 2. Controllo Trigger Manuale da Web UI
            if state.get("manual_trigger_requested"):
                print("[*] ⚡ Rilevata richiesta di esecuzione manuale dalla Dashboard!")
                ConfigManager.clear_manual_run()
                if not state.get("is_running"):
                    run_pipeline(reason="Trigger manuale da Dashboard Streamlit")
                    # Ricalcola next_run
                    ConfigManager.update_scheduler_state(next_run=compute_next_run(times_list, is_enabled))
                else:
                    print("[-] Scansione già in corso: richiesta manuale ignorata.")

            # 3. Controllo Schedulazione Automatica (se abilitata)
            now = get_current_time()
            today_str = now.strftime("%Y-%m-%d")
            
            # Reset giornaliero degli slot già eseguiti
            if last_cleaned_day != today_str:
                executed_slots_today.clear()
                last_cleaned_day = today_str

            if is_enabled and not state.get("is_running"):
                for t_str in times_list:
                    parsed = parse_time_slot(t_str)
                    if not parsed:
                        continue
                    sched_h, sched_m = parsed
                    slot_key = f"{today_str}_{sched_h:02d}_{sched_m:02d}"
                    
                    if now.hour == sched_h and now.minute == sched_m and slot_key not in executed_slots_today:
                        executed_slots_today.add(slot_key)
                        run_pipeline(reason=f"Slot orario programmato: {t_str}")
                        ConfigManager.update_scheduler_state(next_run=compute_next_run(times_list, is_enabled))
                        break

        except Exception as e:
            print(f"[-] Errore nel ciclo di schedulazione: {e}")

        # Polling breve (10s) per consentire reattività ai click manuali dalla UI
        time.sleep(10)

if __name__ == "__main__":
    main()
