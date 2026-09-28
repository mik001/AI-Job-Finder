import os
import sys
import time
import subprocess
from datetime import datetime

# Orari giornalieri programmati di default (es: 08:30 e 18:00)
SCHEDULED_HOURS = [(8, 30), (18, 0)]

def run_pipeline():
    """Esegue la pipeline di AI Job Finder."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now_str}] 🚀 Avvio esecuzione programmata AI Job Finder...")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    
    python_bin = sys.executable
    try:
        result = subprocess.run([python_bin, "-u", "src/main.py"], env=env)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [+] Pipeline completata con codice {result.returncode}.\n")
    except Exception as e:
        print(f"[-] Errore durante l'esecuzione programmata: {e}\n")

def main():
    print("="*60)
    print("⏰ AI JOB FINDER - SCHEDULATORE CONTINUO DI BACKGROUND")
    print("="*60)
    print(f"[*] Orari programmati di esecuzione: {', '.join([f'{h:02d}:{m:02d}' for h, m in SCHEDULED_HOURS])}")
    print("[*] Lo schedulatore rimarrà attivo in background. Premi CTRL+C per arrestarlo.\n")
    
    executed_today = set()
    
    while True:
        now = datetime.now()
        current_time = (now.hour, now.minute)
        today_date = now.strftime("%Y-%m-%d")
        
        for sched_h, sched_m in SCHEDULED_HOURS:
            slot_key = f"{today_date}_{sched_h}_{sched_m}"
            if now.hour == sched_h and now.minute == sched_m and slot_key not in executed_today:
                executed_today.add(slot_key)
                run_pipeline()
                
        # Pulizia slot vecchi
        if now.hour == 0 and now.minute == 0:
            executed_today = set()
            
        time.sleep(25)

if __name__ == "__main__":
    main()
