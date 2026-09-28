import os
import json
import csv
import pandas as pd
import streamlit as st
from datetime import datetime

# Configurazione pagina
st.set_page_config(
    page_title="AI Job Finder - Dashboard",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

HISTORY_FILE = "history.csv"
LEARNED_AGENCIES_FILE = os.path.join("data", "learned_agencies.json")

def load_history() -> pd.DataFrame:
    """Carica lo storico con gestione sicura dei campi mancanti."""
    if not os.path.exists(HISTORY_FILE) or os.path.getsize(HISTORY_FILE) == 0:
        return pd.DataFrame(columns=[
            "Data", "Piattaforma", "Titolo", "Azienda", "Match", 
            "Rejection_Tag", "Stato_UI", "Content_Hash", "Reasoning", "URL", "Description"
        ])
    df = pd.read_csv(HISTORY_FILE, dtype=str)
    # Assicura la presenza di tutte le colonne previste
    expected_cols = [
        "Data", "Piattaforma", "Titolo", "Azienda", "Match", 
        "Rejection_Tag", "Stato_UI", "Content_Hash", "Reasoning", "URL", "Description"
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""
    df.fillna("", inplace=True)
    return df

def save_history(df: pd.DataFrame):
    """Salva il DataFrame su history.csv preservando l'encoding UTF-8."""
    df.to_csv(HISTORY_FILE, index=False, encoding="utf-8")

def update_status(job_url: str, new_status: str):
    """Aggiorna lo stato di lettura di un singolo annuncio identificato da URL."""
    df = load_history()
    idx = df[df["URL"] == job_url].index
    if not idx.empty:
        df.loc[idx, "Stato_UI"] = new_status
        save_history(df)
        st.toast(f"Stato aggiornato a: {new_status}", icon="✅")

def load_agencies() -> list:
    """Carica la blacklist delle agenzie apprese dall'AI."""
    if os.path.exists(LEARNED_AGENCIES_FILE):
        try:
            with open(LEARNED_AGENCIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_agencies(agencies: list):
    """Salva la blacklist delle agenzie."""
    os.makedirs("data", exist_ok=True)
    with open(LEARNED_AGENCIES_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(set(agencies))), f, indent=2, ensure_ascii=False)

# Stile personalizzato CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #0d6efd;
    }
    .badge-linkedin {
        background-color: #0077b5;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85em;
        font-weight: 600;
    }
    .badge-indeed {
        background-color: #2164f3;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85em;
        font-weight: 600;
    }
    .badge-match {
        background-color: #198754;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85em;
        font-weight: 600;
    }
    .badge-rejected {
        background-color: #dc3545;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85em;
        font-weight: 600;
    }
    .job-box {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        background-color: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }
</style>
""", unsafe_allow_html=True)

# Intestazione Principale
st.title("💼 AI Job Finder - HR Candidate Dashboard")
st.caption("Piattaforma di ricerca intelligente e screening automatico offerte HR (Bari / Full Remote)")

# Caricamento Dati
df_history = load_history()

# Metriche Principali
col1, col2, col3, col4, col5 = st.columns(5)
total_jobs = len(df_history)
total_matches = len(df_history[df_history["Match"] == "SI"])
total_rejected = len(df_history[df_history["Match"] == "NO"])
unread_matches = len(df_history[(df_history["Match"] == "SI") & (df_history["Stato_UI"].isin(["NON_LETTO", ""]))])
total_indeed = len(df_history[df_history["Piattaforma"] == "Indeed"])
total_linkedin = len(df_history[df_history["Piattaforma"] == "LinkedIn"])

with col1:
    st.metric("Totale Esaminati", total_jobs)
with col2:
    st.metric("🎯 Match Accettati", total_matches, delta=f"{unread_matches} da leggere" if unread_matches > 0 else "0 nuovi")
with col3:
    st.metric("🚫 Annunci Scartati", total_rejected)
with col4:
    st.metric("LinkedIn", total_linkedin)
with col5:
    st.metric("Indeed", total_indeed)

st.divider()

# Tab Principali
tab_matches, tab_rejected, tab_agencies, tab_runner = st.tabs([
    "🎯 Match Lavorativi", 
    "📋 Offerte Scartate", 
    "🛡️ Blacklist Agenzie AI", 
    "⚙️ Esecuzione & Schedulazione"
])

# ==========================================
# TAB 1: MATCH LAVORATIVI
# ==========================================
with tab_matches:
    matches_df = df_history[df_history["Match"] == "SI"].copy()
    
    if matches_df.empty:
        st.info("Nessun match positivo trovato al momento. Le offerte che rispettano i criteri appariranno qui.")
    else:
        # Filtri Barra Superiore
        f_col1, f_col2, f_col3 = st.columns([2, 2, 3])
        with f_col1:
            status_filter = st.selectbox(
                "Stato Lettura",
                ["Tutti", "NON_LETTO", "LETTO", "CANDIDATO", "ARCHIVIATO"],
                key="match_status_filter"
            )
        with f_col2:
            plat_filter = st.selectbox(
                "Piattaforma",
                ["Tutte", "LinkedIn", "Indeed"],
                key="match_plat_filter"
            )
        with f_col3:
            search_query = st.text_input("Cerca per titolo o azienda...", key="match_search")

        # Applicazione Filtri
        filtered_matches = matches_df
        if status_filter != "Tutti":
            if status_filter == "NON_LETTO":
                filtered_matches = filtered_matches[filtered_matches["Stato_UI"].isin(["NON_LETTO", ""])]
            else:
                filtered_matches = filtered_matches[filtered_matches["Stato_UI"] == status_filter]
                
        if plat_filter != "Tutte":
            filtered_matches = filtered_matches[filtered_matches["Piattaforma"] == plat_filter]
            
        if search_query:
            q = search_query.lower()
            filtered_matches = filtered_matches[
                filtered_matches["Titolo"].str.lower().str.contains(q) | 
                filtered_matches["Azienda"].str.lower().str.contains(q)
            ]

        st.write(f"Mostrando **{len(filtered_matches)}** offerte su {len(matches_df)} match totali:")

        # Rendering Card dei Match
        for idx, row in filtered_matches.iterrows():
            with st.container():
                plat = row["Piattaforma"]
                badge_class = "badge-linkedin" if plat == "LinkedIn" else "badge-indeed"
                status_curr = row["Stato_UI"] if row["Stato_UI"] else "NON_LETTO"
                
                # Header Card
                header_cols = st.columns([6, 2, 2])
                with header_cols[0]:
                    st.markdown(f"### {row['Titolo']}")
                    st.markdown(f"🏢 **{row['Azienda']}** &nbsp;•&nbsp; <span class='{badge_class}'>{plat}</span> &nbsp;•&nbsp; 📅 *{row['Data']}*", unsafe_allow_html=True)
                with header_cols[1]:
                    st.markdown(f"**Stato:** `{status_curr}`")
                with header_cols[2]:
                    if row["URL"]:
                        st.link_button("Candidati ↗", row["URL"], use_container_width=True)

                # Motivazione Gemini
                if row["Reasoning"]:
                    st.info(f"🤖 **Verdetto AI Gemini:**\n\n{row['Reasoning']}")

                # Descrizione Completa Espandibile
                desc = row.get("Description", "").strip()
                with st.expander("📄 Leggi la Descrizione Completa dell'Annuncio"):
                    if desc:
                        st.markdown(desc)
                    else:
                        st.caption("Descrizione non registrata per questo annuncio.")

                # Barra Azioni Stato
                act_col1, act_col2, act_col3, act_col4 = st.columns(4)
                with act_col1:
                    if st.button("Mark: Letto", key=f"btn_letto_{idx}"):
                        update_status(row["URL"], "LETTO")
                        st.rerun()
                with act_col2:
                    if st.button("🚀 Segna Candidato", key=f"btn_cand_{idx}"):
                        update_status(row["URL"], "CANDIDATO")
                        st.rerun()
                with act_col3:
                    if st.button("📁 Archivia", key=f"btn_arch_{idx}"):
                        update_status(row["URL"], "ARCHIVIATO")
                        st.rerun()
                with act_col4:
                    if st.button("↩️ Ripristina Non Letto", key=f"btn_un_{idx}"):
                        update_status(row["URL"], "NON_LETTO")
                        st.rerun()

                st.divider()

# ==========================================
# TAB 2: OFFERTE SCARTATE
# ==========================================
with tab_rejected:
    rejected_df = df_history[df_history["Match"] == "NO"].copy()
    
    col_rf1, col_rf2, col_rf3 = st.columns([2, 2, 3])
    with col_rf1:
        tag_list = ["Tutti"] + sorted(list(set(t for t in rejected_df["Rejection_Tag"].unique() if t)))
        tag_filter = st.selectbox("Motivo Scarto (Tag)", tag_list, key="rej_tag_filter")
    with col_rf2:
        rej_plat = st.selectbox("Piattaforma", ["Tutte", "LinkedIn", "Indeed"], key="rej_plat_filter")
    with col_rf3:
        rej_search = st.text_input("Cerca tra gli scartati...", key="rej_search")

    filtered_rej = rejected_df
    if tag_filter != "Tutti":
        filtered_rej = filtered_rej[filtered_rej["Rejection_Tag"] == tag_filter]
    if rej_plat != "Tutte":
        filtered_rej = filtered_rej[filtered_rej["Piattaforma"] == rej_plat]
    if rej_search:
        q_r = rej_search.lower()
        filtered_rej = filtered_rej[
            filtered_rej["Titolo"].str.lower().str.contains(q_r) | 
            filtered_rej["Azienda"].str.lower().str.contains(q_r)
        ]

    st.write(f"Mostrando **{len(filtered_rej)}** offerte scartate su {len(rejected_df)}:")

    # Tabella compatta per consultazione veloce
    display_df = filtered_rej[["Data", "Piattaforma", "Titolo", "Azienda", "Rejection_Tag", "Reasoning"]].copy()
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data": st.column_config.TextColumn("Data", width="small"),
            "Piattaforma": st.column_config.TextColumn("Piattaforma", width="small"),
            "Titolo": st.column_config.TextColumn("Titolo Ruolo", width="medium"),
            "Azienda": st.column_config.TextColumn("Azienda / Studio", width="medium"),
            "Rejection_Tag": st.column_config.TextColumn("Tag Rifiuto", width="small"),
            "Reasoning": st.column_config.TextColumn("Motivazione Scarto", width="large")
        }
    )

# ==========================================
# TAB 3: BLACKLIST AGENZIE
# ==========================================
with tab_agencies:
    st.subheader("🛡️ Gestione Blacklist Agenzie & Società di Selezione")
    st.markdown("""
    Le società in questo elenco vengono **scartate istantaneamente a zero token** senza interrogare Gemini, 
    risparmiando tempo e consumo API. L'AI aggiunge automaticamente qui le agenzie di somministrazione pura o headhunting confermate.
    """)
    
    current_agencies = load_agencies()
    st.write(f"Attualmente memorizzate: **{len(current_agencies)} agenzie**")
    
    col_ag1, col_ag2 = st.columns([3, 1])
    with col_ag1:
        new_agency = st.text_input("Aggiungi nuova agenzia / società di selezione:", placeholder="es. Randstad Professional, Michael Page, ecc.")
    with col_ag2:
        st.write("")
        st.write("")
        if st.button("➕ Aggiungi", use_container_width=True):
            if new_agency.strip():
                clean_name = new_agency.strip().lower()
                if clean_name not in current_agencies:
                    current_agencies.append(clean_name)
                    save_agencies(current_agencies)
                    st.success(f"Aggiunto '{clean_name}' alla blacklist!")
                    st.rerun()

    # Visualizzazione Tag interattivi per rimozione
    st.write("---")
    st.write("Elenco attivo (clicca per rimuovere se necessario):")
    del_cols = st.columns(4)
    for i, ag in enumerate(current_agencies):
        c_idx = i % 4
        with del_cols[c_idx]:
            if st.button(f"❌ {ag}", key=f"del_ag_{i}"):
                current_agencies.remove(ag)
                save_agencies(current_agencies)
                st.warning(f"Rimosso '{ag}' dalla blacklist.")
                st.rerun()

# ==========================================
# TAB 4: ESECUZIONE & SCHEDULAZIONE
# ==========================================
with tab_runner:
    st.subheader("⚙️ Automazione & Esecuzione")
    st.markdown("""
    ### ⏰ Schedulazione Giornaliera Attiva
    Il sistema è configurato per eseguirsi automaticamente **due volte al giorno** su Windows Task Scheduler:
    - **Mattina:** ore **08:30**
    - **Sera:** ore **18:00**
    
    Lo script esegue la deduplicazione a monte su `history.csv`, scansiona le offerte delle ultime 24 ore su LinkedIn e Indeed, 
    invia gli avvisi istantanei su **WhatsApp** (CallMeBot) per ogni nuovo match, e aggiorna questa dashboard.
    """)
    
    st.divider()
    st.markdown("### 🔔 Configurazione Notifiche WhatsApp")
    callmebot_key = os.getenv("CALLMEBOT_API_KEY", "")
    phone_dest = os.getenv("USER_WHATSAPP_NUMBER", "")
    
    if callmebot_key:
        st.success(f"✅ CallMeBot Attivo per il numero: `{phone_dest}`")
    else:
        st.warning("⚠️ CallMeBot non configurato nel file `.env`.")
        
    st.divider()
    st.markdown("### 📂 Comandi Utili da Terminale")
    st.code("streamlit run src/ui/app.py", language="bash")
    st.code(".\\scripts\\run_daily.bat", language="bash")
