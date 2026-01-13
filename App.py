import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAZIONE UTENTI & COLORI ---
USERS = ["Spano", "Matteo", "Jozef", "Luca"]
POSIZIONI = ["Magazzino"] + USERS
PIATTAFORME = {
    "eBay": "🟡", "Subito": "🔴", "Vinted": "🟢", 
    "Wallapop": "⚪", "FB Marketplace": "🔵", "A Mano": "🤝"
}

# --- CSS PERSONALIZZATO (DARK MODE ELEGANT) ---
def local_css():
    st.markdown("""
    <style>
    /* Sfondo e Testo Principale */
    .stApp {
        background-color: #121212;
        color: #E0E0E0;
    }
    
    /* Input Fields (Text area, number input) */
    .stTextInput input, .stNumberInput input, .stSelectbox, .stDateInput {
        background-color: #1E1E1E !important;
        color: #ffffff !important;
        border: 1px solid #333 !important;
        border-radius: 8px;
    }
    
    /* Tabelle (DataFrame) */
    div[data-testid="stDataFrame"] {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 5px;
    }
    
    /* Pulsanti */
    .stButton>button {
        background-color: #2C2C2C;
        color: #ffffff;
        border: 1px solid #444;
        border-radius: 8px;
        width: 100%;
        font-weight: 500;
    }
    .stButton>button:hover {
        border-color: #E0E0E0;
        color: #ffffff;
    }
    
    /* Metrica Cassa in alto */
    div[data-testid="stMetric"] {
        background-color: #1E1E1E;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
    }
    label[data-testid="stMetricLabel"] {
        color: #888;
        font-size: 0.8rem;
    }
    div[data-testid="stMetricValue"] {
        color: #fff;
        font-size: 1.2rem;
    }
    
    /* Rimuovi spazi bianchi inutili su mobile */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* Alert Box */
    .alert-box {
        background-color: #262626;
        border-left: 5px solid #ffcc00;
        color: #fff;
        padding: 10px;
        margin-bottom: 15px;
        border-radius: 4px;
        font-size: 0.9rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONNESSIONE DATABASE ---
def get_connection():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    return gspread.authorize(creds)

def init_db(client, sheet_name):
    try:
        sh = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        st.error(f"File '{sheet_name}' non trovato.")
        st.stop()

    needed_sheets = {
        "Magazzino": ["ID_Tag", "Categoria", "Descrizione", "Stato", "Posizione", "Canali_Raw", "Prezzo_Ipotetico", "Prezzo_Minimo", "Data_Ins"],
        "Vendite": ["ID_Tag", "Descrizione", "Piattaforma", "Lordo_Incassato", "Spese_Sped", "Netto_Finale", "Spedito", "Incassato", "Venditore", "Data_Vendita", "Data_Incasso"],
        "Spese": ["Data", "Categoria", "Descrizione", "Importo", "Pagato_Da"]
    }

    for s_name, cols in needed_sheets.items():
        try:
            ws = sh.worksheet(s_name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(s_name, rows=100, cols=15)
            ws.append_row(cols)     
    return sh

# --- UTILS ---
def get_channel_dots(channel_string):
    if not isinstance(channel_string, str): return ""
    dots = ""
    for k, v in PIATTAFORME.items():
        if k in channel_string: dots += v
    return dots

# --- MAIN APP ---
def main():
    st.set_page_config(page_title="Gestione Dark", page_icon="⚫", layout="centered") # Layout centered è meglio per mobile
    local_css()

    # 1. INIT SESSION
    if 'user' not in st.session_state: st.session_state['user'] = USERS[0]
    if 'page' not in st.session_state: st.session_state['page'] = "Dashboard"

    # 2. CONNESSIONE DATI
    try:
        client = get_connection()
        sh = init_db(client, "Gestionale_Team_V1")
        ws_mag = sh.worksheet("Magazzino")
        ws_ven = sh.worksheet("Vendite")
        ws_spese = sh.worksheet("Spese")
        
        # Caricamento Dataframes
        df_ven = pd.DataFrame(ws_ven.get_all_records())
        df_spese = pd.DataFrame(ws_spese.get_all_records())
        df_mag = pd.DataFrame(ws_mag.get_all_records())

        # Pulizia dati numerici
        if not df_ven.empty:
            df_ven['Netto_Finale'] = pd.to_numeric(df_ven['Netto_Finale'], errors='coerce').fillna(0)
            df_ven['Spedito'] = df_ven['Spedito'].astype(str).str.upper() == 'TRUE'
            df_ven['Incassato'] = df_ven['Incassato'].astype(str).str.upper() == 'TRUE'
        
        tot_spese = 0
        if not df_spese.empty:
            df_spese['Importo'] = pd.to_numeric(df_spese['Importo'], errors='coerce').fillna(0)
            tot_spese = df_spese['Importo'].sum()

        # Calcolo Cassa Reale
        cassa_reale = 0.0
        in_arrivo = 0.0
        da_spedire = 0
        if not df_ven.empty:
            cassa_reale = df_ven[df_ven['Incassato'] == True]['Netto_Finale'].sum() - tot_spese
            in_arrivo = df_ven[df_ven['Incassato'] == False]['Netto_Finale'].sum()
            da_spedire = len(df_ven[df_ven['Spedito'] == False])

    except Exception as e:
        st.error("Errore di connessione. Ricarica la pagina.")
        st.stop()

    # 3. HEADER MINIMAL (CASSA CLICCABILE)
    # Creiamo due colonne: Bottone Menu a sinistra (Sidebar nativa) e Cassa a destra
    # Streamlit mette il menu hamburger in alto a sinistra. Noi mettiamo la cassa in alto.
    
    col_head1, col_head2 = st.columns([2, 1])
    with col_head1:
        if st.button(f"🏛️ Cassa: € {cassa_reale:,.0f}", help="Clicca per dettagli finanze"):
            st.session_state['page'] = "Finanze"
            st.rerun()
    with col_head2:
        st.caption(f"Utente: {st.session_state['user']}")

    # Notifica discreta
    if da_spedire > 0:
        st.markdown(f'<div class="alert-box">📦 <b>{da_spedire}</b> ordini da spedire!</div>', unsafe_allow_html=True)

    # 4. SIDEBAR NAVIGATION
    with st.sidebar:
        st.title("Menu")
        st.session_state['user'] = st.selectbox("👤 Utente", USERS, index=USERS.index(st.session_state['user']))
        st.markdown("---")
        
        # Menu selezione pagina
        selection = st.radio("Vai a:", 
            ["Dashboard Ordini", "Magazzino", "Nuovo Prodotto", "Vendi", "Resi", "Finanze"],
            index=["Dashboard Ordini", "Magazzino", "Nuovo Prodotto", "Vendi", "Resi", "Finanze"].index(st.session_state.get('page', "Dashboard Ordini"))
        )
        # Aggiorna stato se cambiato da sidebar
        if selection != st.session_state['page']:
            st.session_state['page'] = selection
            st.rerun()

    # --- LOGICA PAGINE ---
    page = st.session_state['page']

    # === PAGINA FINANZE (Dettaglio Cassa) ===
    if page == "Finanze":
        st.subheader("📊 Situazione Finanziaria")
        
        # Card riassuntive
        c1, c2 = st.columns(2)
        c1.metric("Cassa Reale", f"€ {cassa_reale:,.2f}")
        c2.metric("In Arrivo", f"€ {in_arrivo:,.2f}")
        
        st.metric("Spese Totali", f"€ {tot_spese:,.2f}")
        
        st.markdown("### 📝 Ultime Spese")
        with st.form("quick_spesa"):
            sc1, sc2 = st.columns([2, 1])
            desc_spesa = sc1.text_input("Descrizione spesa")
            imp_spesa = sc2.number_input("€", min_value=0.0)
            if st.form_submit_button("Aggiungi Spesa"):
                ws_spese.append_row([datetime.now().strftime("%Y-%m-%d"), "Varie", desc_spesa, imp_spesa, st.session_state['user']])
                st.success("Salvato")
                st.rerun()
                
        if not df_spese.empty:
            st.dataframe(df_spese.tail(10)[['Data', 'Descrizione', 'Importo', 'Pagato_Da']], use_container_width=True, hide_index=True)

    # === PAGINA DASHBOARD (Gestione Spedizioni) ===
    elif page == "Dashboard Ordini":
        st.subheader("📦 Gestione Ordini")
        if df_ven.empty:
            st.info("Nessun ordine attivo.")
        else:
            # Ordina per non spediti
            df_ven = df_ven.sort_values(by=['Incassato', 'Spedito'], ascending=[True, True])
            
            # Tabella Mobile Friendly: Nascondiamo colonne inutili
            edited_df = st.data_editor(
                df_ven[['ID_Tag', 'Descrizione', 'Spedito', 'Incassato']],
                column_config={
                    "Descrizione": st.column_config.TextColumn("Prodotto", width="medium"),
                    "Spedito": st.column_config.CheckboxColumn("📦", width="small"),
                    "Incassato": st.column_config.CheckboxColumn("💸", width="small"),
                },
                disabled=["ID_Tag", "Descrizione"],
                use_container_width=True,
                hide_index=True,
                key="dash_editor"
            )
            
            if st.button("💾 Salva Stati", type="primary"):
                # Aggiornamento logica (identica a V4 ma riadattata)
                current_data = ws_ven.get_all_records()
                updated_rows = []
                for row in current_data:
                    tag = row['ID_Tag']
                    # Cerca nel df modificato
                    match = edited_df[edited_df['ID_Tag'] == tag]
                    if not match.empty:
                        r = match.iloc[0]
                        # Aggiorna logica
                        row['Spedito'] = bool(r['Spedito'])
                        
                        old_inc = str(row['Incassato']).upper() == 'TRUE'
                        new_inc = bool(r['Incassato'])
                        row['Incassato'] = new_inc
                        
                        if new_inc and not old_inc:
                            row['Data_Incasso'] = datetime.now().strftime("%Y-%m-%d")
                        elif not new_inc:
                            row['Data_Incasso'] = ""
                            
                    updated_rows.append(list(row.values()))
                
                if updated_rows:
                    ws_ven.clear()
                    ws_ven.append_row(list(current_data[0].keys()))
                    ws_ven.append_rows(updated_rows)
                    st.success("Aggiornato!")
                    st.rerun()

    # === PAGINA MAGAZZINO ===
    elif page == "Magazzino":
        st.subheader("🔍 Inventario")
        search = st.text_input("Cerca...", placeholder="Es. #F1, 8GB...")
        
        if not df_mag.empty:
            df_mag['Canali'] = df_mag['Canali_Raw'].apply(get_channel_dots)
            
            if search:
                mask = df_mag.astype(str).apply(lambda x: x.str.lower().str.contains(search.lower())).any(axis=1)
                df_show = df_mag[mask]
            else:
                df_show = df_mag
            
            # Vista Mobile: Solo info essenziali
            st.dataframe(
                df_show[['ID_Tag', 'Canali', 'Descrizione', 'Prezzo_Minimo']],
                column_config={
                    "ID_Tag": st.column_config.TextColumn("ID", width="small"),
                    "Prezzo_Minimo": st.column_config.NumberColumn("€ Min", format="%d"),
                    "Canali": st.column_config.TextColumn("Siti"),
                },
                use_container_width=True,
                hide_index=True
            )

    # === PAGINA VENDI ===
    elif page == "Vendi":
        st.subheader("💰 Registra Vendita")
        if df_mag.empty:
            st.warning("Magazzino vuoto")
        else:
            # Dropdown intelligente: ID + Descrizione breve
            options = df_mag.apply(lambda x: f"{x['ID_Tag']} - {x['Descrizione'][:20]}...", axis=1).tolist()
            sel = st.selectbox("Prodotto", options)
            tag_sel = sel.split(" - ")[0]
            
            item = df_mag[df_mag['ID_Tag'] == tag_sel].iloc[0]
            st.caption(item['Descrizione'])
            
            with st.form("vendi_mobile"):
                piat = st.selectbox("Dove?", list(PIATTAFORME.keys()))
                lordo = st.number_input("Prezzo Cliente €", step=5.0)
                spese = st.number_input("Costi Sped/Comm €", step=1.0)
                
                if st.form_submit_button("CONFERMA VENDITA"):
                    netto = lordo - spese
                    ws_ven.append_row([
                        tag_sel, item['Descrizione'], piat, lordo, spese, netto, 
                        False, False, st.session_state['user'], datetime.now().strftime("%Y-%m-%d"), ""
                    ])
                    # Cancella da magazzino
                    cell = ws_mag.find(tag_sel)
                    ws_mag.delete_rows(cell.row)
                    st.success("Venduto!")
                    st.rerun()

    # === PAGINA NUOVO PRODOTTO ===
    elif page == "Nuovo Prodotto":
        st.subheader("➕ Aggiungi")
        
        with st.form("new_prod"):
            c1, c2 = st.columns([1,2])
            tag = c1.text_input("TAG (#F..)", placeholder="#").upper()
            pos = c2.selectbox("Chi?", POSIZIONI)
            
            desc = st.text_area("Descrizione", height=80)
            
            c3, c4 = st.columns(2)
            p_ipo = c3.number_input("€ Ipotetico", step=10.0)
            p_min = c4.number_input("€ Minimo", step=10.0)
            
            st.write("Canali:")
            cols = st.columns(4)
            chans = []
            for i, p in enumerate(["eBay", "Subito", "Vinted", "Wallapop"]):
                if cols[i].checkbox(p[0]): chans.append(p) # Usa solo l'iniziale per spazio
            
            if st.form_submit_button("Salva"):
                ws_mag.append_row([
                    tag, "GENERICO", desc, "Buono", pos, ",".join(chans), 
                    p_ipo, p_min, datetime.now().strftime("%Y-%m-%d")
                ])
                st.success("Salvato")

    # === PAGINA RESI ===
    elif page == "Resi":
        st.subheader("🔙 Resi")
        if not df_ven.empty:
            sel_reso = st.selectbox("Cosa torna?", df_ven['ID_Tag'] + " - " + df_ven['Descrizione'])
            tag_reso = sel_reso.split(" - ")[0]
            
            if st.button("Conferma Reso"):
                row = df_ven[df_ven['ID_Tag'] == tag_reso].iloc[0]
                ws_mag.append_row([
                    tag_reso, "RESO", row['Descrizione'] + " [RESO]", "Usato", "Magazzino", "", 0, 0, datetime.now().strftime("%Y-%m-%d")
                ])
                cell = ws_ven.find(tag_reso)
                ws_ven.delete_rows(cell.row)
                st.success("Reso effettuato")
                st.rerun()

if __name__ == "__main__":
    main()