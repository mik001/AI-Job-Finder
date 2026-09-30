import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join("data", "config.json")
STATE_PATH = os.path.join("data", "scheduler_state.json")

DEFAULT_CANDIDATE_PROFILE = """Candidata: 30 anni, 4 anni di esperienza nel settore HR come Recruiter (executive search in Randstad Professional e attualmente in somministrazione).
Obiettivo Principale: Fare esperienza e lavorare come HR INTERNA all'interno del team di un'azienda cliente finale.
Ruoli accettati: Recruiter interna, HR Generalist, HR Specialist, Talent Acquisition, People Operations, o altri ruoli HR.
Località e Modalità di Lavoro: 
- Accetta lavoro in sede o ibrido (es. un paio di giorni a settimana in ufficio) SOLO se a Bari o dintorni.
- Accetta Full Remote (o ibrido con presenza rarissima in sede, es. 1 volta al mese) in tutta Italia.

REGOLA FONDAMENTALE SU AGENZIE E SOMMINISTRAZIONE:
- Categoricamente NO a ruoli interni di filiale presso agenzie per il lavoro (es. fare il recruiter di filiale in Adecco/Randstad/Manpower che seleziona per conto di terzi).
- ACCETTATO CON VALUTAZIONE POSITIVA (is_match=True): Contratti di somministrazione o staff leasing (anche se emessi da Adecco, Randstad, ecc.) IN CUI LA CANDIDATA VIENE INSERITA A LAVORARE DENTRO IL TEAM HR DI UN'AZIENDA CLIENTE FINALE (es. "per conto di nostra azienda cliente cerchiamo HR Generalist/Recruiter"). Questa tipologia di lavoro in azienda terza è considerata un ottimo trampolino di lancio per fare esperienza aziendale ed è da considerare valida se rispetta la sede (Bari o Full Remote).

ALTRE REGOLE MORBIDE (NON SCARTARE):
- La seniority troppo alta (es. Senior/Manager), troppo bassa (es. Stage/Junior) o la modalità Freelance/P.IVA NON DEVONO essere un motivo di scarto. Includile nei 'cons' (warning) ma mantieni is_match=True se l'annuncio rispetta la sede e la natura del ruolo aziendale."""

DEFAULT_SEARCH_QUERIES = [
    {"keywords": "Risorse Umane", "location": "Italia", "enabled": True},
    {"keywords": "Human Resources", "location": "Italia", "enabled": True},
    {"keywords": "HR", "location": "Italia", "enabled": True},
    {"keywords": "Recruiter OR Recruiting", "location": "Italia", "enabled": True},
    {"keywords": "Talent Acquisition", "location": "Italia", "enabled": True},
    {"keywords": "HR Generalist OR HR Specialist", "location": "Italia", "enabled": True},
    {"keywords": "People Culture", "location": "Italia", "enabled": True},
    {"keywords": "People Operations", "location": "Italia", "enabled": True},
    {"keywords": "Talent Partner OR Talent Specialist", "location": "Italia", "enabled": True},
    {"keywords": "HR Business Partner OR HRBP", "location": "Italia", "enabled": True},
    {"keywords": "Selezione del Personale", "location": "Italia", "enabled": True},
    {"keywords": "Risorse Umane", "location": "Bari", "enabled": True},
    {"keywords": "HR", "location": "Puglia", "enabled": True},
    {"keywords": "Recruiter", "location": "Bari", "enabled": True},
    {"keywords": "Talent Acquisition", "location": "Puglia", "enabled": True},
    {"keywords": "Selezione del Personale", "location": "Bari", "enabled": True}
]

DEFAULT_CONFIG: Dict[str, Any] = {
    "candidate": {
        "role_title": "HR Recruiter & Specialist",
        "exclude_agencies": True,
        "profile_prompt": DEFAULT_CANDIDATE_PROFILE
    },
    "search": {
        "max_results_linkedin": 50,
        "max_results_indeed": 30,
        "queries": DEFAULT_SEARCH_QUERIES
    },
    "scheduling": {
        "enabled": True,
        "times": ["08:30", "18:00"],
        "timezone": "Europe/Rome"
    },
    "notifications": {
        "whatsapp_enabled": True,
        "channels": []
    },
    "diagnostics": {
        "enabled": True,
        "max_saved_runs": 5,
        "capture_screenshots": True
    },
    "session_check": {
        "enabled": True,
        "times": ["12:00"],
        "target_phone": "3925435261"
    }
}

class ConfigManager:
    """Gestore centralizzato e persistente della configurazione dell'applicazione."""

    @staticmethod
    def ensure_data_dir():
        os.makedirs("data", exist_ok=True)

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        """Carica la configurazione da disco. Se inesistente o corrotta, la crea con i default."""
        cls.ensure_data_dir()
        if not os.path.exists(CONFIG_PATH):
            cls.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
        
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Verifica e merge difensivo con i campi di default
            merged = DEFAULT_CONFIG.copy()
            if "candidate" in data:
                merged["candidate"].update(data["candidate"])
            if "search" in data:
                merged["search"].update(data["search"])
            if "scheduling" in data:
                merged["scheduling"].update(data["scheduling"])
            if "notifications" in data:
                merged["notifications"].update(data["notifications"])
            if "session_check" in data:
                merged["session_check"].update(data["session_check"])
            return merged
        except Exception as e:
            logger.error(f"Errore lettura configurazione da {CONFIG_PATH}: {e}. Ritorno default.")
            return DEFAULT_CONFIG.copy()

    @classmethod
    def save_config(cls, config: Dict[str, Any]) -> bool:
        """Salva la configurazione su disco."""
        cls.ensure_data_dir()
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Errore scrittura configurazione su {CONFIG_PATH}: {e}")
            return False

    @classmethod
    def get_candidate_profile(cls) -> str:
        cfg = cls.load_config()
        return cfg.get("candidate", {}).get("profile_prompt", DEFAULT_CANDIDATE_PROFILE)

    @classmethod
    def get_candidate_config(cls) -> Dict[str, Any]:
        cfg = cls.load_config()
        return cfg.get("candidate", {
            "role_title": "HR Recruiter & Specialist",
            "exclude_agencies": True,
            "profile_prompt": DEFAULT_CANDIDATE_PROFILE
        })

    @classmethod
    def get_active_search_queries(cls) -> List[Dict[str, str]]:
        """Restituisce solo le query abilitate."""
        cfg = cls.load_config()
        queries = cfg.get("search", {}).get("queries", DEFAULT_SEARCH_QUERIES)
        return [{"keywords": q["keywords"], "location": q["location"]} for q in queries if q.get("enabled", True)]

    @classmethod
    def get_all_search_queries(cls) -> List[Dict[str, Any]]:
        cfg = cls.load_config()
        return cfg.get("search", {}).get("queries", DEFAULT_SEARCH_QUERIES)

    @classmethod
    def get_scheduling_config(cls) -> Dict[str, Any]:
        cfg = cls.load_config()
        return cfg.get("scheduling", {"enabled": True, "times": ["08:30", "18:00"], "timezone": "Europe/Rome"})

    @classmethod
    def get_session_check_config(cls) -> Dict[str, Any]:
        cfg = cls.load_config()
        return cfg.get("session_check", {
            "enabled": True,
            "times": ["12:00"],
            "target_phone": "3925435261"
        })

    # --- Gestione Notifiche WhatsApp (CallMeBot Multi-Destinatario) ---
    @classmethod
    def _discover_env_whatsapp_channels(cls) -> List[Dict[str, Any]]:
        """Rileva automaticamente i numeri WhatsApp già presenti nel file .env come canali iniziali."""
        found = []
        k1 = os.getenv("CALLMEBOT_API_KEY")
        p1 = os.getenv("USER_WHATSAPP_NUMBER", "")
        if k1 and p1:
            clean_p1 = p1.replace("whatsapp:", "").strip()
            found.append({
                "id": "ch_env_1",
                "name": "Destinatario Primario (.env)",
                "phone": clean_p1,
                "apikey": k1.strip(),
                "enabled": True
            })
            
        k2 = os.getenv("CALLMEBOT_API_KEY_2")
        p2 = os.getenv("USER_WHATSAPP_NUMBER_2", "")
        if k2 and p2:
            clean_p2 = p2.replace("whatsapp:", "").strip()
            found.append({
                "id": "ch_env_2",
                "name": "Destinatario Secondario (.env)",
                "phone": clean_p2,
                "apikey": k2.strip(),
                "enabled": True
            })
            
        for i in range(3, 10):
            ki = os.getenv(f"CALLMEBOT_API_KEY_{i}")
            pi = os.getenv(f"USER_WHATSAPP_NUMBER_{i}", "")
            if ki and pi:
                clean_pi = pi.replace("whatsapp:", "").strip()
                found.append({
                    "id": f"ch_env_{i}",
                    "name": f"Destinatario {i} (.env)",
                    "phone": clean_pi,
                    "apikey": ki.strip(),
                    "enabled": True
                })
        return found

    @classmethod
    def get_whatsapp_config(cls) -> Dict[str, Any]:
        """Restituisce la configurazione WhatsApp, auto-importando canali da .env se vuota."""
        cfg = cls.load_config()
        notif = cfg.get("notifications", {})
        channels = notif.get("channels", [])
        if not channels:
            env_channels = cls._discover_env_whatsapp_channels()
            if env_channels:
                notif["channels"] = env_channels
                cfg["notifications"] = notif
                cls.save_config(cfg)
        return notif

    @classmethod
    def get_whatsapp_channels(cls) -> List[Dict[str, Any]]:
        return cls.get_whatsapp_config().get("channels", [])

    @classmethod
    def save_whatsapp_channels(cls, channels: List[Dict[str, Any]], enabled: bool = True) -> bool:
        cfg = cls.load_config()
        if "notifications" not in cfg:
            cfg["notifications"] = {}
        cfg["notifications"]["whatsapp_enabled"] = enabled
        cfg["notifications"]["channels"] = channels
        return cls.save_config(cfg)

    @classmethod
    def add_whatsapp_channel(cls, name: str, phone: str, apikey: str) -> bool:
        import uuid
        channels = cls.get_whatsapp_channels()
        clean_phone = phone.replace("whatsapp:", "").strip()
        if not clean_phone.startswith("+") and clean_phone.isdigit() and len(clean_phone) >= 10:
            clean_phone = f"+{clean_phone}"
        new_ch = {
            "id": f"ch_{uuid.uuid4().hex[:6]}",
            "name": name.strip() or f"Destinatario ({clean_phone})",
            "phone": clean_phone,
            "apikey": apikey.strip(),
            "enabled": True
        }
        channels.append(new_ch)
        cfg = cls.load_config()
        enabled = cfg.get("notifications", {}).get("whatsapp_enabled", True)
        return cls.save_whatsapp_channels(channels, enabled=enabled)

    @classmethod
    def remove_whatsapp_channel(cls, channel_id: str) -> bool:
        channels = [ch for ch in cls.get_whatsapp_channels() if ch.get("id") != channel_id]
        cfg = cls.load_config()
        enabled = cfg.get("notifications", {}).get("whatsapp_enabled", True)
        return cls.save_whatsapp_channels(channels, enabled=enabled)

    @classmethod
    def toggle_whatsapp_channel(cls, channel_id: str, enabled: bool) -> bool:
        channels = cls.get_whatsapp_channels()
        for ch in channels:
            if ch.get("id") == channel_id:
                ch["enabled"] = enabled
        cfg = cls.load_config()
        notif_enabled = cfg.get("notifications", {}).get("whatsapp_enabled", True)
        return cls.save_whatsapp_channels(channels, enabled=notif_enabled)

    @classmethod
    def set_whatsapp_enabled(cls, enabled: bool) -> bool:
        cfg = cls.load_config()
        if "notifications" not in cfg:
            cfg["notifications"] = {}
        cfg["notifications"]["whatsapp_enabled"] = enabled
        return cls.save_config(cfg)

    # --- Gestione dello Stato dello Schedulatore ---
    @classmethod
    def load_scheduler_state(cls) -> Dict[str, Any]:
        cls.ensure_data_dir()
        if not os.path.exists(STATE_PATH):
            default_state = {
                "is_running": False,
                "pid": None,
                "last_run_start": None,
                "last_run_end": None,
                "last_status": "IDLE",
                "last_message": "Schedulatore in attesa del prossimo slot programmato",
                "next_run": None,
                "manual_trigger_requested": False,
                "current_step": "",
                "total_scraped": 0,
                "total_matches": 0
            }
            cls.save_scheduler_state(default_state)
            return default_state

        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"is_running": False, "last_status": "UNKNOWN"}

    @classmethod
    def save_scheduler_state(cls, state: Dict[str, Any]) -> bool:
        cls.ensure_data_dir()
        try:
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Errore scrittura stato scheduler: {e}")
            return False

    @classmethod
    def update_scheduler_state(cls, **kwargs) -> Dict[str, Any]:
        current = cls.load_scheduler_state()
        current.update(kwargs)
        cls.save_scheduler_state(current)
        return current

    @classmethod
    def request_manual_run(cls):
        cls.update_scheduler_state(manual_trigger_requested=True)

    @classmethod
    def clear_manual_run(cls):
        cls.update_scheduler_state(manual_trigger_requested=False)

    @classmethod
    def get_diagnostics_config(cls) -> Dict[str, Any]:
        cfg = cls.load_config()
        return cfg.get("diagnostics", {
            "enabled": True,
            "max_saved_runs": 5,
            "capture_screenshots": True
        })

    @classmethod
    def save_diagnostics_config(cls, diag_config: Dict[str, Any]) -> bool:
        cfg = cls.load_config()
        cfg["diagnostics"] = diag_config
        return cls.save_config(cfg)

