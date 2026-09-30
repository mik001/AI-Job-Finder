import os
import re
import json
import time
import shutil
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

RUNS_DIR = os.path.join("data", "runs")

class RunDiagnostics:
    """
    Gestore della diagnostica e degli snapshot storici per le run di scraping ed esecuzione.
    Salva log dedicati, screenshot di Playwright per ogni fase chiave o errore,
    e gestisce una politica di retention automatica per conservare solo le ultime N run.
    """
    def __init__(self, run_id: Optional[str] = None, max_saved_runs: int = 5, enabled: bool = True):
        self.enabled = enabled
        self.max_saved_runs = max(1, max_saved_runs)
        self.run_id = run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        self.run_dir = os.path.join(RUNS_DIR, self.run_id)
        self.screenshots_dir = os.path.join(self.run_dir, "screenshots")
        self.screenshot_counter = 0
        self.screenshots_meta = []
        self.start_time = datetime.now()
        self.start_timestamp = time.time()
        self.log_file_path = os.path.join(self.run_dir, "run.log")
        self._log_handle = None

        if self.enabled:
            os.makedirs(self.screenshots_dir, exist_ok=True)
            try:
                self._log_handle = open(self.log_file_path, "a", encoding="utf-8", buffering=1)
                self.log(f"=== INIZIO RUN {self.run_id} ===")
            except Exception as e:
                logger.error(f"Errore apertura log file di run: {e}")

    def log(self, message: str):
        """Scrive un messaggio sia nel log dedicato di run che nel logger di sistema."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        if self._log_handle and not self._log_handle.closed:
            try:
                self._log_handle.write(line)
            except Exception:
                pass

    async def capture_screenshot(self, page, name_hint: str) -> Optional[str]:
        """
        Cattura uno screenshot da Playwright con indice progressivo e nome descrittivo.
        Salva nella cartella dedicata della run per diagnostica visiva.
        """
        if not self.enabled or not page:
            return None

        try:
            if page.is_closed():
                return None
            
            self.screenshot_counter += 1
            clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name_hint).lower()[:40]
            filename = f"{self.screenshot_counter:02d}_{clean_name}.png"
            target_path = os.path.join(self.screenshots_dir, filename)

            # Breve timeout per screenshot non bloccante
            await page.screenshot(path=target_path, timeout=5000)
            
            rel_path = os.path.join("data", "runs", self.run_id, "screenshots", filename).replace("\\", "/")
            meta = {
                "index": self.screenshot_counter,
                "filename": filename,
                "relative_path": rel_path,
                "name_hint": name_hint,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "url": page.url if not page.is_closed() else ""
            }
            self.screenshots_meta.append(meta)
            self.log(f"[📸 Snapshot #{self.screenshot_counter}] Salvato: {filename} (URL: {meta['url'][:60]})")
            print(f"[📸 Snapshot #{self.screenshot_counter:02d}] Catturato screenshot diagnostico: {filename}", flush=True)
            return target_path
        except Exception as e:
            self.log(f"[-] Errore cattura screenshot '{name_hint}': {e}")
            return None

    def finish_run(self, status: str = "SUCCESS", stats: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        """Conclude la sessione di diagnostica della run, salva summary.json e pota le run vecchie."""
        if not self.enabled:
            return

        end_time = datetime.now()
        duration_sec = round(time.time() - self.start_timestamp, 1)

        summary = {
            "run_id": self.run_id,
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": duration_sec,
            "status": status,
            "error": error,
            "stats": stats or {},
            "screenshots_count": len(self.screenshots_meta),
            "screenshots": self.screenshots_meta
        }

        summary_path = os.path.join(self.run_dir, "summary.json")
        try:
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            self.log(f"=== FINE RUN {self.run_id} (Stato: {status}, Durata: {duration_sec}s, Screenshots: {len(self.screenshots_meta)}) ===")
        except Exception as e:
            logger.error(f"Errore scrittura summary.json per {self.run_id}: {e}")

        if self._log_handle and not self._log_handle.closed:
            try:
                self._log_handle.close()
            except Exception:
                pass

        # Pota automaticamente le vecchie run per non superare il limite N
        self.prune_old_runs()

    def prune_old_runs(self):
        """Mantiene solo le ultime N run sul disco, eliminando le più vecchie."""
        if not os.path.exists(RUNS_DIR):
            return

        try:
            entries = [
                d for d in os.listdir(RUNS_DIR)
                if os.path.isdir(os.path.join(RUNS_DIR, d)) and d.startswith("run_")
            ]
            entries.sort()

            excess = len(entries) - self.max_saved_runs
            if excess > 0:
                to_delete = entries[:excess]
                for old_run in to_delete:
                    old_path = os.path.join(RUNS_DIR, old_run)
                    try:
                        shutil.rmtree(old_path)
                        print(f"[🧹 Diagnostics Cleanup] Rimossa vecchia run archiviata: {old_run}", flush=True)
                    except Exception as e:
                        logger.error(f"Impossibile rimuovere {old_path}: {e}")
        except Exception as e:
            logger.error(f"Errore durante la pulizia delle vecchie run: {e}")

    @classmethod
    def get_all_runs(cls) -> List[Dict[str, Any]]:
        """Restituisce l'elenco di tutte le run salvate, ordinate dalla più recente alla più vecchia."""
        if not os.path.exists(RUNS_DIR):
            return []

        runs = []
        try:
            entries = [
                d for d in os.listdir(RUNS_DIR)
                if os.path.isdir(os.path.join(RUNS_DIR, d)) and d.startswith("run_")
            ]
            entries.sort(reverse=True)

            for d in entries:
                run_path = os.path.join(RUNS_DIR, d)
                summary_file = os.path.join(run_path, "summary.json")
                if os.path.exists(summary_file):
                    try:
                        with open(summary_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            runs.append(data)
                    except Exception:
                        runs.append({"run_id": d, "status": "UNKNOWN"})
                else:
                    runs.append({"run_id": d, "status": "INCOMPLETE"})
        except Exception as e:
            logger.error(f"Errore lettura archivio run: {e}")
            
        return runs

    @classmethod
    def get_run_details(cls, run_id: str) -> Optional[Dict[str, Any]]:
        """Restituisce i dettagli completi, i percorsi degli screenshot e il log di una run specifica."""
        run_dir = os.path.join(RUNS_DIR, run_id)
        if not os.path.exists(run_dir):
            return None

        summary_file = os.path.join(run_dir, "summary.json")
        summary_data = {}
        if os.path.exists(summary_file):
            try:
                with open(summary_file, "r", encoding="utf-8") as f:
                    summary_data = json.load(f)
            except Exception:
                pass

        log_file = os.path.join(run_dir, "run.log")
        log_content = ""
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    log_content = f.read()
            except Exception:
                pass

        screenshots_dir = os.path.join(run_dir, "screenshots")
        screenshots_list = []
        if os.path.exists(screenshots_dir):
            for sf in sorted(os.listdir(screenshots_dir)):
                if sf.endswith(".png"):
                    screenshots_list.append({
                        "filename": sf,
                        "abs_path": os.path.abspath(os.path.join(screenshots_dir, sf)),
                        "rel_path": os.path.join("data", "runs", run_id, "screenshots", sf).replace("\\", "/")
                    })

        return {
            "summary": summary_data,
            "log": log_content,
            "screenshots": screenshots_list
        }
