import os
import json
import csv
import html
import pandas as pd
import streamlit as st
from datetime import datetime

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

# Tassonomia esplicita dei criteri di esclusione in linguaggio chiaro
REJECTION_LABELS = {
    "AGENZIA": "Agenzia per il Lavoro / Headhunting",
    "LOCATION_ERRATA": "Sede incompatibile (richiesta presenza fuori Bari/Puglia)",
    "NOT_HR": "Ruolo non attinente all'area Risorse Umane",
    "CATEGORIA_PROTETTA": "Offerta riservata a Categorie Protette (L. 68/99)",
    "LINGUA": "Requisito linguistico vincolante non posseduto",
    "MANCANZA_DATI": "Descrizione insufficiente o incompleta"
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

    st.subheader("⏰ Schedulazione Automatica")
    st.markdown("""
    Scansioni giornaliere attive:
    - **Sessione Mattutina:** ore **08:30**
    - **Sessione Pomeridiana:** ore **18:00**
    
    Il motore esegue la deduplicazione preventiva su `history.csv`, scansiona le offerte delle ultime 24h, attiva l'AI di screening e notifica via WhatsApp.
    """)
    st.divider()

    st.subheader("🔔 Canale WhatsApp")
    callmebot_key = os.getenv("CALLMEBOT_API_KEY", "")
    phone_dest = os.getenv("USER_WHATSAPP_NUMBER", "")
    if callmebot_key:
        st.success(f"✅ CallMeBot Attivo\n\n`{phone_dest}`")
    else:
        st.warning("⚠️ CallMeBot non impostato nel file `.env`.")

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
tab_matches, tab_rejected, tab_agencies = st.tabs([
    "🎯 Opportunità Valide", 
    "📋 Archivio Scartati", 
    "🛡️ Regole & Blacklist Agenzie"
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
    
    col_rf1, col_rf2, col_rf3 = st.columns([3, 2, 4])
    with col_rf1:
        raw_tags = sorted(list(set(t for t in rejected_df["Rejection_Tag"].unique() if t and t != "nan")))
        tag_options = ["Tutti i criteri"] + [f"{REJECTION_LABELS.get(t, t)} ({t})" for t in raw_tags]
        selected_tag_label = st.selectbox("Criterio di Esclusione", tag_options, key="rej_tag_filter")
    with col_rf2:
        rej_plat = st.selectbox("Piattaforma di Origine", ["Tutte le fonti", "LinkedIn", "Indeed"], key="rej_plat_filter")
    with col_rf3:
        rej_search = st.text_input("Cerca tra gli annunci scartati...", placeholder="Filtra per azienda, ruolo o parole chiave...", key="rej_search")

    filtered_rej = rejected_df
    if selected_tag_label != "Tutti i criteri":
        chosen_tag = selected_tag_label.split("(")[-1].replace(")", "").strip()
        filtered_rej = filtered_rej[filtered_rej["Rejection_Tag"] == chosen_tag]
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
    display_df["Criterio di Esclusione"] = display_df["Rejection_Tag"].apply(lambda t: REJECTION_LABELS.get(t, t))
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
    st.markdown("""
    Le società registrate in questa blacklist vengono **scartate istantaneamente a monte a zero token**, 
    senza consumare chiamate API e velocizzando l'esecuzione quotidiana. 
    L'AI inserisce automaticamente qui le agenzie per il lavoro e le società di headhunting verificate.
    """)
    
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
