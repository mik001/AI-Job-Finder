import os
import sys
import json
import csv
import html
import subprocess
import pandas as pd
import streamlit as st
from datetime import datetime

from src.config_manager import ConfigManager, DEFAULT_CANDIDATE_PROFILE, DEFAULT_SEARCH_QUERIES
from src.notifier.whatsapp_notifier import WhatsAppNotifier

# Configurazione della pagina
st.set_page_config(
    page_title="AI Job Finder & Contact Hunter",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

HISTORY_FILE = "history.csv"
LEARNED_AGENCIES_FILE = os.path.join("data", "learned_agencies.json")

# Mappatura semantica degli stati interni in etichette utente accessibili
STATUS_MAP = {
    "NON_LETTO": {
        "label": "Nuova",
        "badge_class": "badge-status-new",
        "icon": "✨"
    },
    "LETTO": {
        "label": "Esaminata",
        "badge_class": "badge-status-read",
        "icon": "👀"
    },
    "CANDIDATO": {
        "label": "Candidatura Inviata",
        "badge_class": "badge-status-applied",
        "icon": "🚀"
    },
    "ARCHIVIATO": {
        "label": "Archiviata",
        "badge_class": "badge-status-archived",
        "icon": "📁"
    }
}

# Tassonomia esplicita e generalizzata dei criteri di esclusione (KO Enums)
REJECTION_LABELS = {
    "AGENZIA": "Agenzia per il Lavoro / Headhunting",
    "LOCATION_INCOMPATIBILE": "Sede o modalità non compatibile (presenza/remoto)",
    "RUOLO_NON_ATTINENTE": "Ruolo o mansione non attinente agli obiettivi",
    "SENIORITY_INCOMPATIBILE": "Seniority / Esperienza richiesta non allineata",
    "CONTRATTO_INCOMPATIBILE": "Tipologia contrattuale non ammessa (Stage/P.IVA/ecc.)",
    "COMPETENZE_MANCANTI": "Requisiti tecnici o hard skill vincolanti mancanti",
    "CATEGORIA_PROTETTA": "Offerta riservata a Categorie Protette (L. 68/99)",
    "LINGUA": "Requisito linguistico vincolante non posseduto",
    "MANCANZA_DATI": "Descrizione insufficiente o incompleta",
    "ALTRO": "Altro motivo specifico",
    # Mappature retrocompatibili per i dati storici
    "LOCATION_ERRATA": "Sede o modalità non compatibile (presenza/remoto)",
    "NOT_HR": "Ruolo o mansione non attinente agli obiettivi"
}

# Mappa di normalizzazione per filtri coerenti
CANONICAL_REJECTION_MAP = {
    "LOCATION_ERRATA": "LOCATION_INCOMPATIBILE",
    "NOT_HR": "RUOLO_NON_ATTINENTE"
}

def load_history() -> pd.DataFrame:
    """Carica lo storico con gestione difensiva di encoding, colonne mancanti e corruzione."""
    expected_cols = [
        "Data", "Piattaforma", "Titolo", "Azienda", "Match", 
        "Rejection_Tag", "Stato_UI", "Content_Hash", "Reasoning", "URL", "Description",
        "Contatti", "Fit_Score"
    ]
    if not os.path.exists(HISTORY_FILE) or os.path.getsize(HISTORY_FILE) == 0:
        return pd.DataFrame(columns=expected_cols)
        
    try:
        df = pd.read_csv(HISTORY_FILE, dtype=str, encoding="utf-8", on_bad_lines="skip")
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(HISTORY_FILE, dtype=str, encoding="latin1", on_bad_lines="skip")
        except Exception as e:
            st.error(f"Errore critico nella lettura di {HISTORY_FILE}: {e}")
            return pd.DataFrame(columns=expected_cols)
    except Exception as e:
        st.error(f"Errore nella lettura dello storico: {e}")
        return pd.DataFrame(columns=expected_cols)

    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""
    df.fillna("", inplace=True)
    return df

def save_history(df: pd.DataFrame):
    """Salva il DataFrame su history.csv preservando l'encoding UTF-8."""
    df.to_csv(HISTORY_FILE, index=False, encoding="utf-8")

def get_history(force_reload: bool = False) -> pd.DataFrame:
    """Cache in-memory di sessione per azzerare l'overhead di I/O disco sui re-render."""
    if "df_history" not in st.session_state or force_reload:
        st.session_state["df_history"] = load_history()
    return st.session_state["df_history"]

def update_status(job_url: str, new_status: str):
    """Aggiorna lo stato in memoria in tempo O(1) e flush su history.csv."""
    st.session_state[f"status_{job_url}"] = new_status
    df = get_history()
    idx = df[df["URL"] == job_url].index
    if not idx.empty:
        df.loc[idx, "Stato_UI"] = new_status
        save_history(df)
        
        status_feedback = {
            "LETTO": "Posizione contrassegnata come esaminata 👀",
            "CANDIDATO": "Candidatura registrata con successo! In bocca al lupo 🚀",
            "ARCHIVIATO": "Posizione archiviata 📁",
            "NON_LETTO": "Posizione reimpostata come nuova ✨"
        }
        feedback_msg = status_feedback.get(new_status, f"Stato aggiornato a: {new_status}")
        st.toast(feedback_msg, icon="✅")

def load_agencies() -> list:
    """Carica la blacklist delle agenzie apprese autonomamente dall'AI con caching e fallbacks."""
    if "agencies_cache" in st.session_state:
        return st.session_state["agencies_cache"]
    if os.path.exists(LEARNED_AGENCIES_FILE):
        try:
            with open(LEARNED_AGENCIES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                st.session_state["agencies_cache"] = data
                return data
        except Exception:
            try:
                with open(LEARNED_AGENCIES_FILE, "r", encoding="latin1") as f:
                    data = json.load(f)
                    st.session_state["agencies_cache"] = data
                    return data
            except Exception:
                return []
    return []

def save_agencies(agencies: list):
    """Salva la blacklist delle agenzie e aggiorna la cache in-memory."""
    os.makedirs("data", exist_ok=True)
    sorted_agencies = sorted(list(set(agencies)))
    st.session_state["agencies_cache"] = sorted_agencies
    with open(LEARNED_AGENCIES_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_agencies, f, indent=2, ensure_ascii=False)

# Stile personalizzato per contrasto, gerarchia e leggibilità (WCAG AA Compliant - Light & Dark Mode)
st.markdown("""
<style>
    /* Tipografia e Leading */
    h1, h2, h3, h4, .stMarkdown h3 {
        line-height: 1.38 !important;
        margin-bottom: 0.35rem !important;
    }
    
    .sub-header-text {
        font-size: 1.05rem;
        color: inherit;
        opacity: 0.88;
        margin-top: -8px;
        margin-bottom: 24px;
        line-height: 1.55;
        max-width: 78ch;
    }
    
    .badge-platform-linkedin {
        background-color: #0a66c2;
        color: #ffffff;
        padding: 3px 9px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .badge-platform-indeed {
        background-color: #2164f3;
        color: #ffffff;
        padding: 3px 9px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .badge-status {
        padding: 3px 9px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-status-new {
        background-color: rgba(14, 165, 233, 0.16);
        color: #0284c7;
        border: 1px solid rgba(14, 165, 233, 0.35);
    }
    .badge-status-read {
        background-color: rgba(100, 116, 139, 0.16);
        color: #64748b;
        border: 1px solid rgba(100, 116, 139, 0.35);
    }
    .badge-status-applied {
        background-color: rgba(34, 197, 94, 0.16);
        color: #16a34a;
        border: 1px solid rgba(34, 197, 94, 0.35);
    }
    .badge-status-archived {
        background-color: rgba(148, 163, 184, 0.16);
        color: #94a3b8;
        border: 1px solid rgba(148, 163, 184, 0.35);
    }
    .badge-fit-score {
        background-color: rgba(234, 179, 8, 0.16);
        color: #ca8a04;
        border: 1px solid rgba(234, 179, 8, 0.35);
        padding: 3px 9px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 700;
    }
    .contact-hunter-box {
        background-color: rgba(14, 165, 233, 0.06);
        border: 1px solid rgba(14, 165, 233, 0.22);
        border-radius: 8px;
        padding: 14px 18px;
        margin-top: 10px;
        margin-bottom: 12px;
        line-height: 1.5;
        max-width: 80ch;
    }
    .contact-hunter-header {
        font-size: 0.95rem;
        font-weight: 700;
        color: inherit;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .contact-empty-notice {
        opacity: 0.75;
        font-size: 0.88rem;
        font-style: italic;
    }
    .inbox-zero-card {
        background-color: rgba(34, 197, 94, 0.08);
        border: 1px solid rgba(34, 197, 94, 0.25);
        border-radius: 12px;
        padding: 28px 24px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .inbox-zero-title {
        color: #16a34a;
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .inbox-zero-desc {
        color: inherit;
        opacity: 0.88;
        font-size: 0.95rem;
        line-height: 1.55;
        max-width: 650px;
        margin: 0 auto;
    }
</style>
""", unsafe_allow_html=True)

# Intestazione Principale (h1)
st.title("💼 AI Job Finder & Autonomous Contact Hunter")
st.markdown("<div class='sub-header-text'>Monitoraggio intelligente del mercato del lavoro, screening semantico dei requisiti HR e identificazione autonoma dei referenti aziendali (Bari / Full Remote).</div>", unsafe_allow_html=True)

# Caricamento Dati dalla cache di sessione
df_history = get_history()

# =====================================================================
# SIDEBAR: STATO SISTEMA, SCHEDULAZIONE & DOCUMENTAZIONE
# =====================================================================
with st.sidebar:
    st.subheader("⚡ Controllo & Sincronizzazione")
    if st.button("🔄 Sincronizza Dati da Disco", use_container_width=True):
        get_history(force_reload=True)
        if "agencies_cache" in st.session_state:
            del st.session_state["agencies_cache"]
        st.toast("Dati ricaricati con successo da disco!", icon="✅")
        st.rerun()

    st.caption(f"Totale record indicizzati: **{len(df_history)}**")
    st.divider()

    st.subheader("⏰ Schedulazione")

    @st.fragment(run_every=4)
    def render_sidebar_scheduler():
        side_cfg = ConfigManager.get_scheduling_config()
        side_state = ConfigManager.load_scheduler_state()
        is_sched_enabled = side_cfg.get("enabled", True)
        side_times = side_cfg.get("times", ["08:30", "18:00"])

        if side_state.get("is_running"):
            st.warning(f"⏳ **Scansione in corso!**\n\n`{side_state.get('current_step', 'Elaborazione...')}`")
        elif is_sched_enabled:
            st.markdown(f"**Stato:** 🟢 Attiva ({len(side_times)} slot/giorno)")
            st.caption(f"Orari: {', '.join([f'**{t}**' for t in side_times])}")
            if side_state.get("next_run"):
                st.caption(f"Prossima: **{side_state.get('next_run')}**")
        else:
            st.markdown("**Stato:** ⏸️ Disattivata (solo manuale)")

    render_sidebar_scheduler()

    st.divider()

    st.subheader("🔔 Canali WhatsApp")
    notif_cfg = ConfigManager.get_whatsapp_config()
    is_wa_enabled = notif_cfg.get("whatsapp_enabled", True)
    channels_list = notif_cfg.get("channels", [])
    active_chs = [c for c in channels_list if c.get("enabled", True)]

    if not is_wa_enabled:
        st.warning("⏸️ Notifiche disattivate globalmente")
    elif active_chs:
        st.success(f"✅ **{len(active_chs)}** Canali Attivi")
        for ch in active_chs:
            st.caption(f"📱 **{ch.get('name', 'Canale')}**: `{ch.get('phone')}`")
    else:
        st.warning("⚠️ Nessun canale configurato")
    st.caption("Gestisci canali nel Tab **'⚙️ Configurazione'**.")

    st.divider()
    with st.expander("📂 Comandi Rapidi da Terminale"):
        st.caption("Avvio manuale scansione:")
        st.code(".\\scripts\\run_daily.bat", language="bash")
        st.caption("Avvio dashboard locale:")
        st.code("streamlit run src/ui/app.py", language="bash")

# Intestazione Sezione Metriche (h2: risolve WCAG 1.3.1 per gerarchia heading continua)
st.header("📊 Riepilogo Attività & Avanzamento Candidature", divider="gray")

total_jobs = len(df_history)
total_matches = len(df_history[df_history["Match"] == "SI"])
total_rejected = len(df_history[df_history["Match"] == "NO"])
unread_matches = len(df_history[(df_history["Match"] == "SI") & (df_history["Stato_UI"].isin(["NON_LETTO", ""]))])
total_indeed = len(df_history[df_history["Piattaforma"] == "Indeed"])
total_linkedin = len(df_history[df_history["Piattaforma"] == "LinkedIn"])

m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
with m_col1:
    st.metric("Annunci Esaminati", total_jobs)
with m_col2:
    delta_str = f"{unread_matches} da valutare" if unread_matches > 0 else "Nessuna nuova"
    st.metric("🎯 Opportunità Valide", total_matches, delta=delta_str)
with m_col3:
    st.metric("🚫 Non Idonei / Scartati", total_rejected)
with m_col4:
    st.metric("Fonte: LinkedIn", total_linkedin)
with m_col5:
    st.metric("Fonte: Indeed", total_indeed)

st.divider()

# Schede di Navigazione Focalizzate sul Workflow Operativo
tab_matches, tab_rejected, tab_agencies, tab_config, tab_logs = st.tabs([
    "🎯 Opportunità Valide", 
    "📋 Archivio Scartati", 
    "🛡️ Regole & Blacklist Agenzie",
    "⚙️ Configurazione & Schedulazione",
    "📜 Log & Diagnostica Live"
])

# =====================================================================
# COMPONENTE ISOLATO: FRAGMENT CARD MATCH (CONTAINER CON BORDI & AZIONI CONTESTUALI)
# =====================================================================
@st.fragment
def render_job_card(row: dict, idx: int):
    """
    Rappresenta una singola offerta racchiusa in un container con bordo dedicato.
    Include sanitizzazione sicura delle stringhe HTML per prevenire rendering anomali.
    """
    url = str(row.get("URL", "")).strip()
    current_status = st.session_state.get(f"status_{url}", row.get("Stato_UI", "") or "NON_LETTO")
    status_info = STATUS_MAP.get(current_status, STATUS_MAP["NON_LETTO"])
    
    clean_title = html.escape(str(row.get("Titolo", "Senza Titolo")))
    clean_company = html.escape(str(row.get("Azienda", "Azienda Non Specificata")))
    clean_date = html.escape(str(row.get("Data", "")))

    with st.container(border=True):
        plat = row.get("Piattaforma", "LinkedIn")
        plat_badge_class = "badge-platform-linkedin" if plat == "LinkedIn" else "badge-platform-indeed"
        status_badge = f"<span class='badge-status {status_info['badge_class']}'>{status_info['icon']} {status_info['label']}</span>"
        
        fit_score_val = str(row.get("Fit_Score", "")).strip()
        fit_score_badge = f"<span class='badge-fit-score'>🎯 Fit Score: {html.escape(fit_score_val)}/100</span>" if fit_score_val and fit_score_val != "nan" else ""

        # Riga Intestazione Card: Titolo (h3), Badge e CTA Esterna
        header_cols = st.columns([7, 3])
        with header_cols[0]:
            st.markdown(f"### {clean_title}")
            st.markdown(
                f"🏢 **{clean_company}** &nbsp;•&nbsp; "
                f"<span class='{plat_badge_class}'>{plat}</span> &nbsp;•&nbsp; "
                f"{status_badge} "
                f"{('&nbsp;•&nbsp; ' + fit_score_badge) if fit_score_badge else ''} &nbsp;•&nbsp; "
                f"📅 <span style='color: #4b5563; font-size: 0.88rem;'>Rilevato il {clean_date}</span>", 
                unsafe_allow_html=True
            )
        with header_cols[1]:
            if url:
                st.link_button(f"Apri su {plat} ↗", url, type="primary", use_container_width=True)

        # Analisi di Idoneità AI (Gemini)
        reasoning = row.get("Reasoning", "")
        if reasoning and str(reasoning) != "nan":
            st.info(f"🤖 **Valutazione di Idoneità AI (Gemini):**\n\n{reasoning}")

        # Sezione Contact Hunter: Referenti e Contatti Hiring Manager
        contacts_raw = str(row.get("Contatti", "")).strip()
        st.markdown("<div class='contact-hunter-box'>", unsafe_allow_html=True)
        st.markdown("<div class='contact-hunter-header'>👥 Referenti & Contatti Hiring Manager (LangGraph + Tavily)</div>", unsafe_allow_html=True)
        if contacts_raw and contacts_raw != "nan":
            st.markdown(contacts_raw)
        else:
            st.markdown("<div class='contact-empty-notice'>Nessun referente aziendale estratto o ricerca contatti non ancora eseguita per questa posizione.</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Descrizione Completa Consultabile Offline
        desc = str(row.get("Description", "")).strip()
        with st.expander("📄 Testo Integrale dell'Annuncio (Consultabile Offline)"):
            if desc and desc != "nan":
                st.markdown(desc)
            else:
                st.caption("Il testo completo dell'annuncio non è stato archiviato durante la scansione.")

        # Barra Azioni Triage: Azione Primaria Dinamica + Menu Popover per Azioni Secondarie
        act_col1, act_col2, act_col3 = st.columns([3, 2, 5])
        
        with act_col1:
            if current_status == "NON_LETTO":
                if st.button("👀 Segna come Esaminata", key=f"p_letto_{idx}", use_container_width=True):
                    update_status(url, "LETTO")
                    st.rerun(scope="fragment")
            elif current_status == "LETTO":
                if st.button("🚀 Candidatura Inviata", key=f"p_cand_{idx}", type="primary", use_container_width=True):
                    update_status(url, "CANDIDATO")
                    st.rerun(scope="fragment")
            elif current_status == "CANDIDATO":
                if st.button("📁 Sposta in Archivio", key=f"p_arch_{idx}", use_container_width=True):
                    update_status(url, "ARCHIVIATO")
                    st.rerun(scope="fragment")
            elif current_status == "ARCHIVIATO":
                if st.button("↩️ Riapri come Nuova", key=f"p_un_{idx}", use_container_width=True):
                    update_status(url, "NON_LETTO")
                    st.rerun(scope="fragment")

        with act_col2:
            with st.popover("⚙️ Altro Stato", use_container_width=True):
                st.caption("Imposta stato manualmente:")
                if st.button("✨ Nuova da valutare", key=f"pop_new_{idx}", use_container_width=True):
                    update_status(url, "NON_LETTO")
                    st.rerun(scope="fragment")
                if st.button("👀 Già esaminata", key=f"pop_read_{idx}", use_container_width=True):
                    update_status(url, "LETTO")
                    st.rerun(scope="fragment")
                if st.button("🚀 Candidatura inviata", key=f"pop_app_{idx}", use_container_width=True):
                    update_status(url, "CANDIDATO")
                    st.rerun(scope="fragment")
                if st.button("📁 Archivia posizione", key=f"pop_arc_{idx}", use_container_width=True):
                    update_status(url, "ARCHIVIATO")
                    st.rerun(scope="fragment")

        with act_col3:
            pass

# =====================================================================
# TAB 1: OPPORTUNITÀ VALIDE (MATCH POSITIVI)
# =====================================================================
with tab_matches:
    st.header("🎯 Posizioni Aperte Corrispondenti al Profilo", divider="gray")
    matches_df = df_history[df_history["Match"] == "SI"].copy()
    
    if matches_df.empty:
        st.info("Nessuna opportunità idonea rilevata al momento. Le offerte che soddisfano i vincoli di ruolo e sede appariranno qui.")
    else:
        # Filtri di Triage
        f_col1, f_col2, f_col3 = st.columns([3, 2, 4])
        with f_col1:
            status_filter_options = [
                "Tutti gli stati", 
                "✨ Nuove da valutare", 
                "👀 Già esaminate", 
                "🚀 Candidature inviate", 
                "📁 Archiviate"
            ]
            selected_status_filter = st.selectbox(
                "Stato di Lavorazione",
                status_filter_options,
                key="match_status_filter"
            )
        with f_col2:
            plat_filter = st.selectbox(
                "Piattaforma di Origine",
                ["Tutte le fonti", "LinkedIn", "Indeed"],
                key="match_plat_filter"
            )
        with f_col3:
            search_query = st.text_input(
                "Ricerca rapida...", 
                placeholder="Filtra per titolo, ruolo o nome azienda...",
                key="match_search"
            )

        # Applicazione Filtri
        filtered_matches = matches_df
        if selected_status_filter != "Tutti gli stati":
            if selected_status_filter == "✨ Nuove da valutare":
                filtered_matches = filtered_matches[filtered_matches["Stato_UI"].isin(["NON_LETTO", ""])]
            elif selected_status_filter == "👀 Già esaminate":
                filtered_matches = filtered_matches[filtered_matches["Stato_UI"] == "LETTO"]
            elif selected_status_filter == "🚀 Candidature inviate":
                filtered_matches = filtered_matches[filtered_matches["Stato_UI"] == "CANDIDATO"]
            elif selected_status_filter == "📁 Archiviate":
                filtered_matches = filtered_matches[filtered_matches["Stato_UI"] == "ARCHIVIATO"]
                
        if plat_filter != "Tutte le fonti":
            filtered_matches = filtered_matches[filtered_matches["Piattaforma"] == plat_filter]
            
        if search_query.strip():
            q = search_query.strip().lower()
            filtered_matches = filtered_matches[
                filtered_matches["Titolo"].str.lower().str.contains(q) | 
                filtered_matches["Azienda"].str.lower().str.contains(q)
            ]

        # Riscontro numerico e gestione stati vuoti / Inbox Zero
        if filtered_matches.empty:
            if selected_status_filter == "✨ Nuove da valutare" and not search_query.strip() and plat_filter == "Tutte le fonti":
                st.markdown("""
                <div class="inbox-zero-card">
                    <div style="font-size: 2.2rem; margin-bottom: 6px;">🎉</div>
                    <div class="inbox-zero-title">Inbox Zero! Tutte le nuove opportunità sono state esaminate</div>
                    <div class="inbox-zero-desc">
                        Non ci sono nuove offerte da valutare. Il sistema eseguirà le prossime scansioni automatiche alle <strong>08:30</strong> e alle <strong>18:00</strong>.<br>
                        Puoi consultare le posizioni archiviate o le candidature già inviate selezionando gli altri stati di lavorazione.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("💡 Nessuna offerta corrisponde ai filtri impostati. Prova a selezionare 'Tutti gli stati' o a cancellare la ricerca testuale.")
        else:
            st.caption(f"Mostrando **{len(filtered_matches)}** opportunità su {len(matches_df)} totali:")

            # Rendering delle card incapsulate in container con bordi
            for idx, row in filtered_matches.iterrows():
                render_job_card(row.to_dict(), idx)

# =====================================================================
# TAB 2: ARCHIVIO SCARTATI (AUDIT LOG DEI RIFIUTI)
# =====================================================================
with tab_rejected:
    st.header("📋 Archivio Offerte Scartate e Motivi di Esclusione", divider="gray")
    rejected_df = df_history[df_history["Match"] == "NO"].copy()
    rejected_df["Canonical_Tag"] = rejected_df["Rejection_Tag"].apply(lambda t: CANONICAL_REJECTION_MAP.get(t, t))
    
    col_rf1, col_rf2, col_rf3 = st.columns([3, 2, 4])
    with col_rf1:
        canonical_tags = sorted(list(set(t for t in rejected_df["Canonical_Tag"].unique() if t and t != "nan")))
        tag_options = ["Tutti i criteri"] + [f"{REJECTION_LABELS.get(t, t)} ({t})" for t in canonical_tags]
        selected_tag_label = st.selectbox("Criterio di Esclusione", tag_options, key="rej_tag_filter")
    with col_rf2:
        rej_plat = st.selectbox("Piattaforma di Origine", ["Tutte le fonti", "LinkedIn", "Indeed"], key="rej_plat_filter")
    with col_rf3:
        rej_search = st.text_input("Cerca tra gli annunci scartati...", placeholder="Filtra per azienda, ruolo o parole chiave...", key="rej_search")

    filtered_rej = rejected_df
    if selected_tag_label != "Tutti i criteri":
        chosen_tag = selected_tag_label.split("(")[-1].replace(")", "").strip()
        legacy_matches = [k for k, v in CANONICAL_REJECTION_MAP.items() if v == chosen_tag] + [chosen_tag]
        filtered_rej = filtered_rej[filtered_rej["Rejection_Tag"].isin(legacy_matches) | (filtered_rej["Canonical_Tag"] == chosen_tag)]
    if rej_plat != "Tutte le fonti":
        filtered_rej = filtered_rej[filtered_rej["Piattaforma"] == rej_plat]
    if rej_search.strip():
        q_r = rej_search.strip().lower()
        filtered_rej = filtered_rej[
            filtered_rej["Titolo"].str.lower().str.contains(q_r) | 
            filtered_rej["Azienda"].str.lower().str.contains(q_r) |
            filtered_rej["Reasoning"].str.lower().str.contains(q_r)
        ]

    st.caption(f"Mostrando **{len(filtered_rej)}** offerte scartate su {len(rejected_df)} totali:")

    # Creazione vista formattata per la consultazione
    display_df = filtered_rej[["Data", "Piattaforma", "Titolo", "Azienda", "Rejection_Tag", "Reasoning"]].copy()
    display_df["Criterio di Esclusione"] = display_df["Rejection_Tag"].apply(lambda t: REJECTION_LABELS.get(CANONICAL_REJECTION_MAP.get(t, t), REJECTION_LABELS.get(t, t)))
    display_view = display_df[["Data", "Piattaforma", "Titolo", "Azienda", "Criterio di Esclusione", "Reasoning"]]

    st.dataframe(
        display_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data": st.column_config.TextColumn("Data Rilevazione", width="small"),
            "Piattaforma": st.column_config.TextColumn("Fonte", width="small"),
            "Titolo": st.column_config.TextColumn("Titolo Ruolo", width="medium"),
            "Azienda": st.column_config.TextColumn("Azienda Pubblicante", width="medium"),
            "Criterio di Esclusione": st.column_config.TextColumn("Criterio di Esclusione", width="medium"),
            "Reasoning": st.column_config.TextColumn("Motivazione Analitica AI", width="large")
        }
    )

# =====================================================================
# TAB 3: BLACKLIST AGENZIE (TABELLA INTERATTIVA E RIMOZIONE PROTETTA)
# =====================================================================
with tab_agencies:
    st.header("🛡️ Gestione Blacklist Agenzie e Società di Selezione", divider="gray")
    
    cand_cfg = ConfigManager.get_candidate_config()
    is_agency_filter_active = cand_cfg.get("exclude_agencies", True)
    
    if is_agency_filter_active:
        st.info("🟢 **Filtro Agenzie ATTIVO**: Le società registrate in questa blacklist vengono scartate istantaneamente a monte a zero token. Inoltre, Gemini inserisce automaticamente qui le nuove agenzie per il lavoro e società di headhunting che identifica durante lo screening. Puoi disattivarlo dalla Tab *'⚙️ Configurazione & Schedulazione'*.")
    else:
        st.warning("⚪ **Filtro Agenzie DISATTIVATO**: Le agenzie per il lavoro e le società di selezione sono attualmente ammesse per questo profilo. La blacklist a monte a zero token è in pausa e l'AI non apprende automaticamente nuove agenzie. Puoi riattivare il filtro in qualsiasi momento dalla Tab *'⚙️ Configurazione & Schedulazione'*.")
    
    current_agencies = load_agencies()
    st.markdown(f"Società attualmente memorizzate nella blacklist: **{len(current_agencies)}**")
    
    # 1. Modulo Aggiunta Controllata
    with st.container(border=True):
        st.subheader("➕ Aggiunta Nuova Società")
        col_ag1, col_ag2 = st.columns([3, 1])
        with col_ag1:
            new_agency = st.text_input(
                "Nome agenzia o società di selezione da escludere:", 
                placeholder="es. Randstad, Michael Page, Adecco, Hunters Group...",
                key="new_agency_input"
            )
        with col_ag2:
            st.write("")
            st.write("")
            if st.button("➕ Aggiungi alla Blacklist", use_container_width=True):
                clean_name = new_agency.strip().lower()
                if not clean_name:
                    st.warning("⚠️ Inserisci una denominazione valida.")
                elif clean_name in current_agencies:
                    st.info(f"ℹ️ '{clean_name}' è già presente nella blacklist.")
                else:
                    current_agencies.append(clean_name)
                    save_agencies(current_agencies)
                    st.success(f"Azienda '{clean_name}' aggiunta con successo alla blacklist!")
                    st.rerun()

    st.divider()

    # 2. Consultazione e Ricerca Blacklist
    c_hdr1, c_hdr2 = st.columns([3, 2])
    with c_hdr1:
        st.subheader("📋 Elenco Società Escluse")
    with c_hdr2:
        agency_search = st.text_input("Filtra elenco blacklist...", placeholder="Cerca azienda...", key="agency_search_input")

    filtered_agencies = current_agencies
    if agency_search.strip():
        q_a = agency_search.strip().lower()
        filtered_agencies = [a for a in current_agencies if q_a in a]

    if not filtered_agencies:
        st.info("Nessuna società corrisponde ai criteri di ricerca impostati.")
    else:
        df_agencies = pd.DataFrame({
            "Denominazione Azienda / Agenzia": [a.title() for a in filtered_agencies],
            "Identificativo Normalizzato": filtered_agencies
        })
        st.dataframe(
            df_agencies,
            use_container_width=True,
            hide_index=True
        )

        # 3. Rimozione Protetta con Conferma (Previene cancellazioni accidentali a 1-click)
        with st.expander("🗑️ Gestione Rimozione dalla Blacklist"):
            st.caption("Seleziona una o più società da riabilitare (rimuovere dalla blacklist):")
            agencies_to_remove = st.multiselect(
                "Seleziona aziende da rimuovere:",
                options=filtered_agencies,
                format_func=lambda x: x.title(),
                key="agencies_removal_multiselect"
            )
            if agencies_to_remove:
                if st.button(f"⚠️ Conferma Rimozione di {len(agencies_to_remove)} Società", type="primary"):
                    for a in agencies_to_remove:
                        if a in current_agencies:
                            current_agencies.remove(a)
                    save_agencies(current_agencies)
                    st.success(f"Rimosse {len(agencies_to_remove)} società dalla blacklist.")
                    st.rerun()

# =====================================================================
# TAB 4: CONFIGURAZIONE & SCHEDULAZIONE
# =====================================================================
with tab_config:
    st.header("⚙️ Configurazione Sistema, Profilo & Schedulazione", divider="gray")
    st.markdown("<div class='sub-header-text'>Personalizza in tempo reale il profilo e le regole di screening del candidato, gestisci gli orari di schedulazione automatica e configura le query di ricerca per LinkedIn e Indeed.</div>", unsafe_allow_html=True)

    cfg_data = ConfigManager.load_config()

    # 1. Stato Schedulatore & Scansione Live (con Fragment & Auto-Refresh)
    def _render_monitor_ui():
        cfg_d = ConfigManager.load_config()
        st_state = ConfigManager.load_scheduler_state()

        with st.container(border=True):
            col_t_title, col_t_switch = st.columns([6, 4])
            with col_t_title:
                st.subheader("⚡ Monitor Schedulatore & Scansione Live")
            with col_t_switch:
                is_auto_on = st.toggle(
                    "🔄 Auto-aggiornamento live (4s)",
                    value=st.session_state.get("sched_auto_refresh_on", True),
                    key="sched_auto_refresh_toggle_input",
                    help="Se attivo, aggiorna automaticamente lo stato del demone e la fase di scraping ogni 4 secondi senza ricaricare l'intera pagina."
                )
                if is_auto_on != st.session_state.get("sched_auto_refresh_on", True):
                    st.session_state["sched_auto_refresh_on"] = is_auto_on
                    st.rerun()

            col_st1, col_st2 = st.columns([7, 3])
            with col_st1:
                if st_state.get("is_running"):
                    st.markdown("### ⏳ **Scansione Attiva in Corso**")
                    step_msg = st_state.get('current_step', 'Elaborazione...')
                    start_msg = st_state.get('last_run_start', 'N/D')
                    st.info(f"**Fase Attuale:** {step_msg}\n\n**Avviata:** {start_msg}")
                else:
                    is_on = cfg_d.get("scheduling", {}).get("enabled", True)
                    status_icon = "🟢" if is_on else "⏸️"
                    status_text = "Schedulatore Programmato Attivo" if is_on else "Schedulazione Automatica Disattivata"
                    st.markdown(f"### {status_icon} **{status_text}**")
                    
                    info_cols = st.columns(2)
                    with info_cols[0]:
                        next_run_val = st_state.get("next_run") or "Non programmata"
                        st.markdown(f"📅 **Prossima esecuzione:** `{next_run_val}`")
                    with info_cols[1]:
                        last_run_val = st_state.get("last_run_end") or "Nessuna recente"
                        last_status_val = st_state.get("last_status") or "IDLE"
                        st.markdown(f"🏁 **Ultima esecuzione:** `{last_run_val}` ({last_status_val})")
                        
                    msg_val = st_state.get("last_message")
                    if msg_val:
                        st.caption(f"💬 Ultimo messaggio di stato: *{msg_val}*")
                        
            with col_st2:
                st.write("")
                if st_state.get("is_running"):
                    st.button("⏳ Scansione in corso...", disabled=True, use_container_width=True)
                else:
                    if st.button("🚀 Avvia Scansione Adesso", type="primary", use_container_width=True):
                        ConfigManager.request_manual_run()
                        st.toast("Richiesta inviata al demone! Avvio scansione...", icon="🚀")
                        st.rerun(scope="fragment")

                if st.button("🔄 Aggiorna Adesso", use_container_width=True):
                    st.rerun(scope="fragment")

    @st.fragment(run_every=4)
    def render_monitor_live():
        _render_monitor_ui()

    @st.fragment()
    def render_monitor_static():
        _render_monitor_ui()

    if st.session_state.get("sched_auto_refresh_on", True):
        render_monitor_live()
    else:
        render_monitor_static()

    st.divider()

    # 2. Configurazione Schedulazione Automatica
    with st.container(border=True):
        st.subheader("⏰ Orari e Frequenza di Scansione Automatica")
        sched_conf = cfg_data.get("scheduling", {})
        
        c_sch1, c_sch2 = st.columns([3, 2])
        with c_sch1:
            auto_enabled = st.toggle(
                "Abilita schedulazione automatica continua di background", 
                value=sched_conf.get("enabled", True),
                key="auto_sched_toggle"
            )
        with c_sch2:
            st.caption(f"Fuso orario di riferimento: **{sched_conf.get('timezone', 'Europe/Rome')}**")
            
        current_times = sched_conf.get("times", ["08:30", "18:00"])
        st.markdown(f"Orari di esecuzione attuali: {', '.join([f'`{t}`' for t in current_times])}")
        
        col_t1, col_t2 = st.columns([3, 2])
        with col_t1:
            new_time_input = st.text_input("Aggiungi nuovo orario di scansione (formato HH:MM, es. 13:00):", key="new_time_slot_input")
        with col_t2:
            st.write("")
            st.write("")
            if st.button("➕ Aggiungi Orario", use_container_width=True):
                val = new_time_input.strip()
                import re
                if re.match(r"^(?:[01]?\d|2[0-3]):[0-5]\d$", val):
                    parts = val.split(":")
                    norm_val = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
                    if norm_val not in current_times:
                        current_times.append(norm_val)
                        current_times.sort()
                        sched_conf["times"] = current_times
                        cfg_data["scheduling"] = sched_conf
                        ConfigManager.save_config(cfg_data)
                        st.toast(f"Orario {norm_val} aggiunto con successo!", icon="✅")
                        st.rerun()
                    else:
                        st.info(f"L'orario {norm_val} è già presente.")
                else:
                    st.warning("⚠️ Inserisci un orario valido in formato 24h (es. 08:30, 14:00, 21:15).")

        if len(current_times) > 1:
            with st.expander("🗑️ Rimuovi uno slot orario esistente"):
                slot_to_remove = st.selectbox("Seleziona slot da eliminare:", options=current_times, key="remove_time_slot_select")
                if st.button("Elimina Orario Selezionato", type="secondary"):
                    current_times.remove(slot_to_remove)
                    sched_conf["times"] = current_times
                    cfg_data["scheduling"] = sched_conf
                    ConfigManager.save_config(cfg_data)
                    st.toast(f"Orario {slot_to_remove} eliminato!", icon="🗑️")
                    st.rerun()

        if auto_enabled != sched_conf.get("enabled", True):
            sched_conf["enabled"] = auto_enabled
            cfg_data["scheduling"] = sched_conf
            ConfigManager.save_config(cfg_data)
            st.toast("Impostazione schedulazione aggiornata!", icon="✅")
            st.rerun()

    st.divider()

    # 3. Canali di Notifica WhatsApp Multi-Destinatario (CallMeBot)
    with st.container(border=True):
        st.subheader("🔔 Canali di Notifica WhatsApp (CallMeBot Multi-Destinatario)")
        st.markdown(
            "Configura uno o più canali WhatsApp con **API Key individuali** per ricevere gli alert istantanei "
            "quando l'AI identifica una nuova opportunità lavorativa idonea con i contatti dei recruiter."
        )

        notif_cfg = ConfigManager.get_whatsapp_config()
        current_wa_enabled = notif_cfg.get("whatsapp_enabled", True)
        
        wa_toggle_col1, wa_toggle_col2 = st.columns([3, 2])
        with wa_toggle_col1:
            new_wa_enabled = st.toggle(
                "Abilita invio notifiche WhatsApp per i nuovi match",
                value=current_wa_enabled,
                key="global_wa_enabled_toggle"
            )
            if new_wa_enabled != current_wa_enabled:
                ConfigManager.set_whatsapp_enabled(new_wa_enabled)
                st.toast("Preferenza notifiche WhatsApp salvata!", icon="✅")
                st.rerun()

        # Guida all'attivazione rapida
        with st.expander("📖 Guida Rapida: Come attivare gratis CallMeBot su ciascun numero (richiede 30 secondi)", expanded=False):
            st.markdown("""
            **CallMeBot** è un servizio gratuito per l'invio di messaggi WhatsApp personali.
            Per ragioni di privacy e anti-spam di WhatsApp, **ogni destinatario deve autorizzare il bot dal proprio smartphone** per generare la propria API Key personale:

            1. Salva nei contatti dello smartphone il numero ufficiale di CallMeBot: **`+34 644 44 49 64`**  
               *(oppure clicca direttamente su questo link da cellulare o WhatsApp Web: [wa.me/34644444964](https://api.whatsapp.com/send?phone=34644444964&text=I%20allow%20callmebot%20to%20send%20me%20messages))*
            2. Invia questo identico messaggio al bot:  
               `I allow callmebot to send me messages`
            3. Il bot risponderà istantaneamente con un messaggio:  
               `API Key: XXXXXX` (es. 4407379)
            4. Inserisci il tuo **Nome**, **Numero** (con prefisso internazionale, es. `+39333...`) e la **API Key** nel modulo sottostante e clicca su **Salva Canale WhatsApp**!
            """)

        # Canali attuali
        channels = ConfigManager.get_whatsapp_channels()
        st.markdown(f"Canali configurati: **{len(channels)}**")

        if channels:
            for idx, ch in enumerate(channels):
                ch_id = ch.get("id", f"ch_{idx}")
                ch_name = ch.get("name", "Destinatario")
                ch_phone = ch.get("phone", "")
                ch_key = str(ch.get("apikey", ""))
                ch_enabled = ch.get("enabled", True)

                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 3])
                    with c1:
                        icon_st = "🟢" if ch_enabled else "⏸️"
                        st.markdown(f"**{icon_st} {ch_name}**")
                        st.caption(f"ID: `{ch_id}`")
                    with c2:
                        st.markdown(f"📱 `{ch_phone}`")
                    with c3:
                        masked_key = (ch_key[:2] + "••••" + ch_key[-2:]) if len(ch_key) > 4 else "••••"
                        st.markdown(f"🔑 API Key: `{masked_key}`")
                    with c4:
                        act_b1, act_b2, act_b3 = st.columns([2, 1, 1])
                        with act_b1:
                            if st.button("🧪 Test", key=f"btn_test_{ch_id}_{idx}", use_container_width=True, help="Invia subito una notifica WhatsApp di test"):
                                with st.spinner(f"Invio notifica di prova a {ch_phone}..."):
                                    ok, res_msg = WhatsAppNotifier.send_test_alert(ch_phone, ch_key, ch_name)
                                    if ok:
                                        st.toast(f"Test recapitato con successo a {ch_name}!", icon="✅")
                                        st.success(f"✅ Notifica inviata a `{ch_phone}`: {res_msg}")
                                    else:
                                        st.toast(f"Errore invio a {ch_name}", icon="❌")
                                        st.error(f"❌ Errore CallMeBot per `{ch_phone}`: {res_msg}")
                        with act_b2:
                            toggle_icon = "⏸️" if ch_enabled else "▶️"
                            toggle_help = "Disattiva temporaneamente questo canale" if ch_enabled else "Riattiva questo canale"
                            if st.button(toggle_icon, key=f"btn_tog_{ch_id}_{idx}", help=toggle_help):
                                ConfigManager.toggle_whatsapp_channel(ch_id, not ch_enabled)
                                st.toast(f"Canale {ch_name} {'disattivato' if ch_enabled else 'attivato'}!", icon="ℹ️")
                                st.rerun()
                        with act_b3:
                            if st.button("🗑️", key=f"btn_del_{ch_id}_{idx}", help=f"Elimina definitivamente il canale {ch_name}"):
                                ConfigManager.remove_whatsapp_channel(ch_id)
                                st.toast(f"Canale {ch_name} rimosso!", icon="🗑️")
                                st.rerun()
        else:
            st.info("Nessun canale WhatsApp configurato. Aggiungi il primo canale qui sotto.")

        # Modulo per aggiungere un nuovo canale
        with st.expander("➕ Aggiungi Nuovo Canale WhatsApp", expanded=(len(channels) == 0)):
            col_add1, col_add2, col_add3 = st.columns([3, 3, 2])
            with col_add1:
                new_ch_name = st.text_input(
                    "Nome o Ruolo Destinatario:",
                    placeholder="es. Bartoli HR, Michele (Personale)",
                    key="input_new_ch_name"
                )
            with col_add2:
                new_ch_phone = st.text_input(
                    "Numero WhatsApp (con prefisso int., es. +39334...):",
                    placeholder="+393348652594",
                    key="input_new_ch_phone"
                )
            with col_add3:
                new_ch_key = st.text_input(
                    "API Key CallMeBot:",
                    placeholder="es. 4407379",
                    key="input_new_ch_key"
                )

            col_submit1, col_submit2 = st.columns([3, 2])
            with col_submit1:
                send_test_on_add = st.checkbox("Invia automaticamente una notifica WhatsApp di test al salvataggio", value=True, key="cb_test_on_add")
            with col_submit2:
                if st.button("➕ Salva Canale WhatsApp", type="primary", use_container_width=True):
                    val_name = new_ch_name.strip()
                    val_phone = new_ch_phone.strip()
                    val_key = new_ch_key.strip()

                    if not val_phone or not val_key:
                        st.warning("⚠️ Compila sia il Numero WhatsApp che l'API Key CallMeBot.")
                    else:
                        clean_p = WhatsAppNotifier.normalize_phone(val_phone)
                        if not clean_p.startswith("+") and clean_p.isdigit():
                            clean_p = f"+{clean_p}"
                        
                        if send_test_on_add:
                            with st.spinner(f"Verifica connessione CallMeBot per {clean_p}..."):
                                ok, res_msg = WhatsAppNotifier.send_test_alert(clean_p, val_key, val_name)
                                if ok:
                                    ConfigManager.add_whatsapp_channel(val_name, clean_p, val_key)
                                    st.toast(f"Canale {val_name} aggiunto e verificato con successo!", icon="✅")
                                    st.success(f"✅ Messaggio di test recapitato con successo su WhatsApp a `{clean_p}`!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Impossibile verificare il canale: {res_msg}. Verifica che il destinatario abbia inviato il messaggio di autorizzazione a CallMeBot prima di riprovare.")
                        else:
                            ConfigManager.add_whatsapp_channel(val_name, clean_p, val_key)
                            st.toast(f"Canale {val_name} salvato!", icon="✅")
                            st.rerun()

    st.divider()

    # 4. Profilo del Candidato & Regole Semantiche (Gemini 3.8 Flash)
    with st.container(border=True):
        st.subheader("🎯 Profilo Target & Criteri di Screening AI")
        st.markdown("""
        Questo profilo viene inviato direttamente a **Gemini 3.8 Flash** per valutare ogni singola offerta trovata.
        Puoi personalizzare ruoli ammessi, vincoli geografici, seniority, e regole contrattuali (es. somministrazione vs filiale).
        """)
        
        cand_conf = cfg_data.get("candidate", {})
        col_c1, col_c2 = st.columns([3, 2])
        with col_c1:
            role_title_input = st.text_input(
                "Etichetta / Ruolo Target Principale:", 
                value=cand_conf.get("role_title", "HR Recruiter & Talent Specialist"),
                key="cand_role_title_input"
            )
        with col_c2:
            st.write("")
            exclude_agencies_input = st.toggle(
                "🛡️ Escludi Agenzie ed Headhunting",
                value=cand_conf.get("exclude_agencies", True),
                help="Se ATTIVO: l'AI scarta le agenzie di selezione e usa la blacklist a monte a zero token. Se DISATTIVATO: le offerte di agenzie di selezione e somministrazione vengono ammesse (ideale per profili IT, Marketing, Finanza o Consulenza).",
                key="cand_exclude_agencies_toggle"
            )
        
        prompt_input = st.text_area(
            "Prompt di Profilo e Vincoli del Candidato (utilizzato per la valutazione AI):",
            value=cand_conf.get("profile_prompt", DEFAULT_CANDIDATE_PROFILE),
            height=320,
            key="cand_profile_prompt_input"
        )
        
        col_p1, col_p2 = st.columns([3, 2])
        with col_p1:
            if st.button("💾 Salva Modifiche Profilo", type="primary", use_container_width=True):
                clean_title = role_title_input.strip() or "Candidato"
                clean_prompt = prompt_input.strip()
                if not clean_prompt:
                    st.error("Il prompt del profilo non può essere vuoto!")
                else:
                    cand_conf["role_title"] = clean_title
                    cand_conf["exclude_agencies"] = exclude_agencies_input
                    cand_conf["profile_prompt"] = clean_prompt
                    cfg_data["candidate"] = cand_conf
                    ConfigManager.save_config(cfg_data)
                    st.toast("Profilo salvato con successo! Le prossime scansioni useranno questi criteri.", icon="✅")
                    st.rerun()
        with col_p2:
            if st.button("🔄 Ripristina Profilo HR Predefinito", use_container_width=True):
                cand_conf["profile_prompt"] = DEFAULT_CANDIDATE_PROFILE
                cand_conf["role_title"] = "HR Recruiter & Specialist"
                cand_conf["exclude_agencies"] = True
                cfg_data["candidate"] = cand_conf
                ConfigManager.save_config(cfg_data)
                st.toast("Profilo predefinito ripristinato!", icon="🔄")
                st.rerun()

    st.divider()

    # 4. Parametri di Ricerca & Query Scraper
    with st.container(border=True):
        st.subheader("🔍 Query di Ricerca (LinkedIn & Indeed Italia)")
        st.markdown("Definisci le query che gli scraper eseguono su LinkedIn e Indeed. Puoi abilitare/disabilitare query o aggiungerne di nuove.")
        
        search_conf = cfg_data.get("search", {})
        col_lim1, col_lim2 = st.columns(2)
        with col_lim1:
            max_li = st.number_input(
                "Max risultati LinkedIn per singola query:",
                min_value=10, max_value=100,
                value=int(search_conf.get("max_results_linkedin", 50)),
                step=5,
                key="max_li_input"
            )
        with col_lim2:
            max_ind = st.number_input(
                "Max risultati Indeed per singola query:",
                min_value=10, max_value=60,
                value=int(search_conf.get("max_results_indeed", 30)),
                step=5,
                key="max_ind_input"
            )

        if max_li != search_conf.get("max_results_linkedin", 50) or max_ind != search_conf.get("max_results_indeed", 30):
            search_conf["max_results_linkedin"] = int(max_li)
            search_conf["max_results_indeed"] = int(max_ind)
            cfg_data["search"] = search_conf
            ConfigManager.save_config(cfg_data)
            st.toast("Profondità di scraping aggiornata!", icon="✅")

        # Lista interattiva query
        queries_list = search_conf.get("queries", DEFAULT_SEARCH_QUERIES)
        
        st.markdown(f"Query configurate: **{len(queries_list)}** (Attive: **{len([q for q in queries_list if q.get('enabled', True)])}**)")
        
        # Aggiunta nuova query
        with st.expander("➕ Aggiungi Nuova Query di Ricerca"):
            col_q1, col_q2, col_q3 = st.columns([3, 2, 2])
            with col_q1:
                new_kw = st.text_input("Parole chiave / Ruolo:", placeholder="es. HR Business Partner, People Specialist...", key="new_query_kw")
            with col_q2:
                new_loc = st.text_input("Località:", placeholder="es. Italia, Bari, Puglia, Remoto...", key="new_query_loc")
            with col_q3:
                st.write("")
                st.write("")
                if st.button("➕ Aggiungi Query", use_container_width=True):
                    if new_kw.strip() and new_loc.strip():
                        queries_list.append({"keywords": new_kw.strip(), "location": new_loc.strip(), "enabled": True})
                        search_conf["queries"] = queries_list
                        cfg_data["search"] = search_conf
                        ConfigManager.save_config(cfg_data)
                        st.toast(f"Query '{new_kw}' in '{new_loc}' aggiunta!", icon="✅")
                        st.rerun()
                    else:
                        st.warning("Compila sia parole chiave che località.")

        # Tabella visuale delle query
        df_queries = pd.DataFrame(queries_list)
        if not df_queries.empty:
            df_queries["Stato"] = df_queries["enabled"].apply(lambda e: "✅ Attiva" if e else "⏸️ Disabilitata")
            st.dataframe(
                df_queries[["Stato", "keywords", "location"]].rename(columns={
                    "keywords": "Parole Chiave",
                    "location": "Località"
                }),
                use_container_width=True,
                hide_index=True
            )

        # Gestione eliminazione query
        with st.expander("🗑️ Gestisci ed Elimina Query"):
            query_labels = [f"{q['keywords']} ({q['location']})" for q in queries_list]
            selected_to_delete = st.multiselect("Seleziona una o più query da rimuovere:", options=query_labels, key="queries_to_delete_select")
            if selected_to_delete:
                if st.button(f"⚠️ Conferma Eliminazione di {len(selected_to_delete)} Query", type="primary"):
                    search_conf["queries"] = [q for q in queries_list if f"{q['keywords']} ({q['location']})" not in selected_to_delete]
                    cfg_data["search"] = search_conf
                    ConfigManager.save_config(cfg_data)
                    st.toast(f"Eliminate {len(selected_to_delete)} query.", icon="🗑️")
                    st.rerun()

    st.divider()

    # 5. Tassonomia Criteri di Esclusione (KO Enums)
    with st.container(border=True):
        st.subheader("🚫 Tassonomia Criteri di Rifiuto (KO Enums)")
        st.markdown("""
        Di seguito la tassonomia dei motivi di esclusione utilizzata da Gemini e le statistiche storiche di scarto.
        Questa architettura consente al sistema di adattarsi a qualsiasi tipologia professionale garantendo retrocompatibilità con i dati pregressi.
        """)
        
        # Conteggio scarti per ciascun motivo
        rej_counts = {}
        if not df_history.empty:
            for _, r in df_history[df_history["Match"] == "NO"].iterrows():
                tag = str(r.get("Rejection_Tag", "")).strip()
                canonical = CANONICAL_REJECTION_MAP.get(tag, tag)
                if canonical:
                    rej_counts[canonical] = rej_counts.get(canonical, 0) + 1
                    
        ko_items = [
            ("AGENZIA", "Agenzia per il Lavoro / Headhunting", "Società interinali, agenzie o intermediari non graditi (es. filiale che seleziona per conto terzi)."),
            ("LOCATION_INCOMPATIBILE", "Sede o Modalità Incompatibile", "Lavoro in presenza o ibrido fuori dalle città autorizzate, oppure mancato full-remote richiesto."),
            ("RUOLO_NON_ATTINENTE", "Ruolo Non Attinente", "Mansioni o mansione non coerenti con gli obiettivi professionali cercati dal candidato."),
            ("SENIORITY_INCOMPATIBILE", "Seniority Incompatibile", "Esperienza richiesta non coerente (es. profilo C-level / 10+ anni quando scartato dal candidato)."),
            ("CONTRATTO_INCOMPATIBILE", "Contratto Incompatibile", "Tipologia contrattuale non ammessa (es. stage non retribuito o P.IVA quando si cerca assunzione)."),
            ("COMPETENZE_MANCANTI", "Competenze Mancanti", "Mancanza di requisiti tecnici, linguistici o certificazioni vincolanti e non negoziabili."),
            ("CATEGORIA_PROTETTA", "Categorie Protette (L. 68/99)", "Offerta riservata a personale iscritto alle liste delle Categorie Protette."),
            ("LINGUA", "Requisito Linguistico", "Richiesta vincolante di lingua straniera non posseduta dal candidato."),
            ("MANCANZA_DATI", "Mancanza Dati", "Testo dell'annuncio incompleto, vuoto o insufficiente per una valutazione attendibile."),
            ("ALTRO", "Altro Motivo Specifico", "Altra motivazione specifica dettagliata nell'analisi analitica di Gemini.")
        ]
        
        ko_table_data = []
        for code, label, desc in ko_items:
            count = rej_counts.get(code, 0)
            ko_table_data.append({
                "Codice Enum": code,
                "Etichetta Utente": label,
                "Frequenza nello Storico": count,
                "Definizione Criterio": desc
            })
            
        st.dataframe(
            pd.DataFrame(ko_table_data),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Codice Enum": st.column_config.TextColumn("Codice Enum", width="medium"),
                "Etichetta Utente": st.column_config.TextColumn("Etichetta Utente", width="medium"),
                "Frequenza nello Storico": st.column_config.NumberColumn("Annunci Scartati", width="small"),
                "Definizione Criterio": st.column_config.TextColumn("Definizione & Regola di Scarto", width="large")
            }
        )

    # =====================================================================
    # TAB 5: LOG DI SISTEMA & DIAGNOSTICA OPERATIVA LIVE
    # =====================================================================
    with tab_logs:
        st.subheader("📜 Log di Sistema & Diagnostica Live")
        st.markdown(
            "<div class='sub-header-text'>Monitoraggio trasparente e granulare in tempo reale: "
            "stato degli scraper (LinkedIn / Indeed), analisi semantica Gemini 3.8 Flash, contact hunting e notifiche WhatsApp.</div>",
            unsafe_allow_html=True
        )

        LOG_PATH = os.path.join("data", "system_run.log")

        def load_system_logs() -> list:
            """Carica le righe del log di sistema in modo sicuro e performante."""
            if not os.path.exists(LOG_PATH):
                return []
            try:
                with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                    return f.readlines()
            except Exception as e:
                return [f"[-] Errore apertura file di log: {e}\n"]

        # Rendering isolato con fragment per aggiornamento automatico
        def render_logs_view():
            all_lines = load_system_logs()
            st_state = ConfigManager.load_scheduler_state()
            is_running = st_state.get("is_running", False)

            # Conteggi analitici su tutto il log
            count_total = len(all_lines)
            count_linkedin = sum(1 for line in all_lines if "[LinkedIn]" in line or "LinkedIn" in line)
            count_indeed = sum(1 for line in all_lines if "[Indeed]" in line or "Indeed" in line)
            count_sec_check = sum(1 for line in all_lines if "Security Check" in line or "bloccata da verifica" in line)
            count_gemini = sum(1 for line in all_lines if "Gemini" in line or "[SCARTATO]" in line or "Fit Score" in line or "Analisi:" in line)
            count_matches = sum(1 for line in all_lines if "Nuovo Match" in line or "is_match=True" in line)
            count_wa = sum(1 for line in all_lines if "CallMeBot" in line or "WhatsApp" in line)

            # KPI Cards in cima
            kpi_c1, kpi_c2, kpi_c3, kpi_c4, kpi_c5 = st.columns(5)
            with kpi_c1:
                st_icon = "🟢" if is_running else "🏁"
                st_label = "In Esecuzione" if is_running else "In Attesa / Idle"
                st.metric("Stato Pipeline", f"{st_icon} {st_label}")
                if is_running:
                    st.caption(f"Fase: `{st_state.get('current_step', 'Elaborazione...')[:35]}`")
                else:
                    st.caption(f"Ultimo stato: `{st_state.get('last_status', 'IDLE')}`")
            with kpi_c2:
                st.metric("Eventi LinkedIn", count_linkedin)
                st.caption("Scraping & estrazioni descrizioni")
            with kpi_c3:
                indeed_delta = f"⚠️ {count_sec_check} blocchi" if count_sec_check > 0 else "OK"
                st.metric("Eventi Indeed", count_indeed, delta=indeed_delta, delta_color="inverse" if count_sec_check > 0 else "normal")
                st.caption("Security Check / Cloudflare rilevati")
            with kpi_c4:
                st.metric("Valutazioni AI Gemini", count_gemini)
                st.caption(f"Match trovati nel log: {count_matches}")
            with kpi_c5:
                st.metric("Righe Totali Log", count_total)
                st.caption(f"Alert WhatsApp: {count_wa}")

            st.divider()

            # Controlli di filtraggio e ricerca
            f_col1, f_col2, f_col3, f_col4 = st.columns([3, 3, 2, 2])
            with f_col1:
                category_filter = st.selectbox(
                    "Filtra per modulo/argomento:",
                    options=[
                        "Tutti i log (Completo)",
                        "🤖 Valutazioni AI Gemini & Fit Score",
                        "💼 Scraping LinkedIn",
                        "🔍 Scraping Indeed & Security Checks",
                        "👥 Contact Hunter (Referenti)",
                        "🔔 Notifiche WhatsApp (CallMeBot)",
                        "⚠️ Errori & Security Checks"
                    ],
                    key="log_category_filter_select"
                )
            with f_col2:
                search_query = st.text_input(
                    "Cerca parola chiave nel testo:",
                    placeholder="es. Adecco, Bari, Security, SCARTATO, 4407379...",
                    key="log_search_query_input"
                )
            with f_col3:
                sort_order = st.selectbox(
                    "Ordinamento cronologico:",
                    options=["Più recenti in alto (Inverso)", "Cronologico classico (Dal primo)"],
                    key="log_sort_order_select"
                )
            with f_col4:
                limit_lines = st.selectbox(
                    "Righe da mostrare:",
                    options=[100, 250, 500, 1000, 2000, "Tutte"],
                    index=1,
                    key="log_limit_select"
                )

            # Applicazione filtri
            filtered_lines = []
            q_lower = search_query.strip().lower()

            for line in all_lines:
                line_lower = line.lower()
                
                # Filtro Categoria
                if category_filter == "🤖 Valutazioni AI Gemini & Fit Score":
                    if not any(k in line_lower for k in ["gemini", "fit score", "scartato", "match", "analisi:", "valutazione"]):
                        continue
                elif category_filter == "💼 Scraping LinkedIn":
                    if "linkedin" not in line_lower:
                        continue
                elif category_filter == "🔍 Scraping Indeed & Security Checks":
                    if "indeed" not in line_lower and "security check" not in line_lower:
                        continue
                elif category_filter == "👥 Contact Hunter (Referenti)":
                    if not any(k in line_lower for k in ["tavily", "contatti", "recruiter", "hiring manager", "referent"]):
                        continue
                elif category_filter == "🔔 Notifiche WhatsApp (CallMeBot)":
                    if not any(k in line_lower for k in ["whatsapp", "callmebot"]):
                        continue
                elif category_filter == "⚠️ Errori & Security Checks":
                    if not any(k in line_lower for k in ["error", "security check", "bloccata da verifica", "[-]"]):
                        continue

                # Filtro Ricerca Testuale
                if q_lower and q_lower not in line_lower:
                    continue

                filtered_lines.append(line)

            # Ordinamento
            if sort_order == "Più recenti in alto (Inverso)":
                display_lines = list(reversed(filtered_lines))
            else:
                display_lines = filtered_lines

            # Limitazione
            if limit_lines != "Tutte":
                display_lines = display_lines[:int(limit_lines)]

            st.caption(f"Mostrate **{len(display_lines)}** righe filtrate su **{count_total}** totali nel file.")

            # Rendering Terminale ad alto contrasto (Dark Monospace con Syntax Highlighting)
            if not display_lines:
                st.info("Nessuna riga di log corrispondente ai filtri impostati.")
            else:
                formatted_html = []
                for l in display_lines:
                    safe_l = html.escape(l.rstrip("\r\n"))
                    if not safe_l.strip():
                        formatted_html.append("<div style='height: 8px;'></div>")
                        continue

                    # Color coding intelligente
                    if "[+]" in safe_l or "inviata con successo" in safe_l or "Nuovo Match" in safe_l:
                        line_html = f"<span style='color: #4ade80; font-weight: 600;'>{safe_l}</span>"
                    elif "[-]" in safe_l or "[SCARTATO]" in safe_l or "Errore" in safe_l or "Exception" in safe_l:
                        line_html = f"<span style='color: #f87171; font-weight: 500;'>{safe_l}</span>"
                    elif "Security Check" in safe_l or "bloccata da verifica" in safe_l:
                        line_html = f"<span style='background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; padding: 2px 6px; border-radius: 4px; font-weight: 700;'>🛡️ {safe_l}</span>"
                    elif "[*]" in safe_l or "[LinkedIn]" in safe_l or "[Indeed]" in safe_l:
                        line_html = f"<span style='color: #38bdf8;'>{safe_l}</span>"
                    elif "🤖" in safe_l or "Gemini" in safe_l or "Fit Score" in safe_l or "AI-Learned" in safe_l:
                        line_html = f"<span style='color: #c084fc; font-weight: 500;'>{safe_l}</span>"
                    elif "[!]" in safe_l or "Salto" in safe_l or "Warning" in safe_l:
                        line_html = f"<span style='color: #fbbf24;'>{safe_l}</span>"
                    else:
                        line_html = f"<span style='color: #e2e8f0;'>{safe_l}</span>"

                    formatted_html.append(f"<div style='margin-bottom: 2px;'>{line_html}</div>")

                terminal_content = "".join(formatted_html)
                st.markdown(
                    f"""
                    <div style="
                        background-color: #0b0f19;
                        border: 1px solid #1e293b;
                        border-radius: 10px;
                        padding: 16px 20px;
                        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                        font-size: 0.84rem;
                        line-height: 1.55;
                        max-height: 650px;
                        overflow-y: auto;
                        box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
                    ">
                        {terminal_content}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # Azioni: Download e Gestione
            st.write("")
            act_col1, act_col2 = st.columns([3, 2])
            with act_col1:
                raw_full_text = "".join(all_lines)
                st.download_button(
                    "📥 Scarica Log Completo (.txt)",
                    data=raw_full_text,
                    file_name=f"ai_job_finder_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
                    mime="text/plain",
                    use_container_width=True
                )
            with act_col2:
                if st.button("🔄 Forza Ricaricamento Log", use_container_width=True):
                    st.rerun()

        # Fragment per auto-refresh
        @st.fragment(run_every=3)
        def render_live_logs_fragment():
            render_logs_view()

        @st.fragment()
        def render_static_logs_fragment():
            render_logs_view()

        col_ref1, col_ref2 = st.columns([4, 2])
        with col_ref1:
            auto_ref = st.toggle("🔄 Auto-aggiornamento live streaming (ogni 3 secondi)", value=True, key="log_auto_streaming_toggle")
        with col_ref2:
            st.caption("Mostra le novità senza ricaricare la pagina")

        if auto_ref:
            render_live_logs_fragment()
        else:
            render_static_logs_fragment()


