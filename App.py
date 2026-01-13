import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAZIONE ---
USERS = ["Spano", "Matteo", "Jozef", "Luca"]
POSIZIONI = ["Magazzino"] + USERS
PIATTAFORME = {
    "eBay": "🟡",
    "Subito": "🔴",
    "Vinted": "🟢",
    "Wallapop": "⚪",
    "FB Marketplace": "🔵",
    "A Mano": "🤝"
}

# --- FUNZIONI DI CONNESSIONE ---
def get_connection():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    else:
        # File locale per test
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    return gspread.authorize(creds)

def init_db(client, sheet_name):
    try:
        sh = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        st.error(f"File '{sheet_name}' non trovato su Google Drive. Assicurati di averlo creato e condiviso con l'email del bot.")
        st.stop()

    # Definizione delle colonne necessarie (Auto-creazione se mancano i fogli)
    needed_sheets = {
        "Magazzino": ["ID_Tag", "Categoria", "Descrizione", "Stato", "Posizione", "Canali_Raw", "Prezzo_Ipotetico", "Prezzo_Minimo", "Data_Ins"],
        "Vendite": ["ID_Tag", "Descrizione", "Piattaforma", "Lordo_Incassato", "Spese_Sped", "Netto_Finale", "Spedito", "Incassato", "Venditore", "Data_Vendita", "Data_Incasso"],
        "Spese": ["Data", "Categoria", "Descrizione", "Importo", "Pagato_Da"]
    }

    # Controllo e creazione automatica fogli mancanti
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
    st.set_page_config(page_title="Gestione Vendite Pro", page_icon="🚀", layout="wide")
    
    # CSS per stile pulito
    st.markdown("""
    <style>
    .stMetric {background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 10px;}
    .alert-box {padding: 10px; background-color: #fff3cd; color: #856404; border-radius: 5px; margin-bottom: 10px;}
    </style>
    """, unsafe_allow_html=True)

    # 1. LOGIN
    if 'user' not in st.session_state: st.session_state['user'] = USERS[0]
    
    with st.sidebar:
        st.title("🔐 Accesso Team")
        st.session_state['user'] = st.selectbox("Utente Attuale", USERS, index=USERS.index(st.session_state['user']))
        st.divider()
        menu = st.radio("Navigazione", [
            "🏠 Dashboard & Ordini", 
            "📦 Magazzino", 
            "➕ Aggiungi Articolo", 
            "💰 Registra Vendita", 
            "🔙 Gestione Resi",
            "💸 Spese & Uscite"
        ])

    # CONNESSIONE DB
    SHEET_NAME = "Gestionale_Team_V1"
    try:
        client = get_connection()
        sh = init_db(client, SHEET_NAME)
        # Accesso ai fogli (safe mode)
        ws_mag = sh.worksheet("Magazzino")
        ws_ven = sh.worksheet("Vendite")
        ws_spese = sh.worksheet("Spese")
    except Exception as e:
        st.error(f"Errore connessione: {e}")
        st.stop()

    # --- DATAFRAMES ---
    # Carichiamo i dati all'inizio per calcoli veloci
    df_ven = pd.DataFrame(ws_ven.get_all_records())
    df_spese = pd.DataFrame(ws_spese.get_all_records())
    
    # Conversione tipi numerici
    if not df_ven.empty:
        df_ven['Netto_Finale'] = pd.to_numeric(df_ven['Netto_Finale'], errors='coerce').fillna(0)
        df_ven['Spedito'] = df_ven['Spedito'].astype(str).str.upper() == 'TRUE'
        df_ven['Incassato'] = df_ven['Incassato'].astype(str).str.upper() == 'TRUE'
    
    tot_spese = 0
    if not df_spese.empty:
        df_spese['Importo'] = pd.to_numeric(df_spese['Importo'], errors='coerce').fillna(0)
        tot_spese = df_spese['Importo'].sum()

    # --- CALCOLO METRICHE FINANZIARIE ---
    cassa_reale = 0.0
    in_arrivo = 0.0
    da_spedire_count = 0

    if not df_ven.empty:
        # Cassa Reale: Solo quelli INCASSATI (meno le spese totali)
        cassa_reale = df_ven[df_ven['Incassato'] == True]['Netto_Finale'].sum() - tot_spese
        
        # In Arrivo: Venduti ma NON incassati
        in_arrivo = df_ven[df_ven['Incassato'] == False]['Netto_Finale'].sum()
        
        # Da Spedire
        da_spedire_count = len(df_ven[df_ven['Spedito'] == False])

    # --- TOP BAR (Metriche e Notifiche) ---
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("💰 Cassa Reale (Disponibile)", f"€ {cassa_reale:,.2f}", delta="Netto Incassato - Spese")
    col_kpi2.metric("⏳ Soldi in Arrivo", f"€ {in_arrivo:,.2f}", delta="Venduti ma non incassati", delta_color="off")
    col_kpi3.metric("📉 Spese Totali", f"€ {tot_spese:,.2f}", delta_color="inverse")

    # Notifica "Da Spedire"
    if da_spedire_count > 0:
        st.markdown(f"""
        <div class="alert-box">
            ⚠️ <b>ATTENZIONE:</b> Ci sono <b>{da_spedire_count}</b> ordini in attesa di spedizione! Controlla la lista qui sotto.
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()

    # --- PAGINA 1: DASHBOARD & ORDINI ---
    if menu == "🏠 Dashboard & Ordini":
        st.header("Gestione Ordini in Corso")
        
        if not df_ven.empty:
            # Ordiniamo: Prima quelli da spedire/incassare, poi i completati
            df_ven = df_ven.sort_values(by=['Incassato', 'Spedito'], ascending=[True, True])
            
            # Editor Interattivo
            edited_df = st.data_editor(
                df_ven[['ID_Tag', 'Descrizione', 'Piattaforma', 'Netto_Finale', 'Data_Vendita', 'Spedito', 'Incassato']],
                column_config={
                    "Spedito": st.column_config.CheckboxColumn("📦 Spedito", help="Spunta quando hai consegnato il pacco"),
                    "Incassato": st.column_config.CheckboxColumn("💸 Incassato", help="Spunta quando i soldi sono arrivati"),
                    "Netto_Finale": st.column_config.NumberColumn("Netto", format="€ %.2f"),
                    "Data_Vendita": st.column_config.TextColumn("Data Vendita", disabled=True),
                },
                disabled=["ID_Tag", "Descrizione", "Piattaforma", "Netto_Finale", "Data_Vendita"],
                use_container_width=True,
                hide_index=True,
                key="order_editor"
            )

            if st.button("💾 Salva Cambiamenti Ordini", type="primary"):
                # Logica aggiornamento avanzata con DATE
                # Scarichiamo di nuovo il foglio per essere sicuri
                current_data = ws_ven.get_all_records()
                
                updated_rows = []
                # Ricostruiamo la lista di dati da salvare
                for i, row in enumerate(current_data):
                    tag = row['ID_Tag']
                    # Troviamo la riga corrispondente nell'editor
                    if tag in edited_df['ID_Tag'].values:
                        edited_row = edited_df[edited_df['ID_Tag'] == tag].iloc[0]
                        
                        new_spedito = bool(edited_row['Spedito'])
                        new_incassato = bool(edited_row['Incassato'])
                        
                        # Gestione Data Incasso
                        old_incassato = str(row['Incassato']).upper() == 'TRUE'
                        data_incasso = row.get('Data_Incasso', '') # Prende valore vecchio o vuoto
                        
                        if new_incassato and not old_incassato:
                            # Se è passato da False a True ora -> Metti data oggi
                            data_incasso = datetime.now().strftime("%Y-%m-%d")
                        elif not new_incassato:
                            # Se è tornato False -> Cancella data
                            data_incasso = ""

                        # Aggiorniamo la riga in memoria
                        row['Spedito'] = new_spedito
                        row['Incassato'] = new_incassato
                        row['Data_Incasso'] = data_incasso
                    
                    updated_rows.append(list(row.values()))
                
                # Scrittura su Google Sheet (Riscriviamo tutto per sicurezza e ordine)
                if updated_rows:
                    headers = list(current_data[0].keys())
                    ws_ven.clear()
                    ws_ven.append_row(headers)
                    ws_ven.append_rows(updated_rows)
                    st.success("Stati e Date aggiornati!")
                    st.rerun()
        else:
            st.info("Nessuna vendita registrata.")

    # --- PAGINA 2: MAGAZZINO ---
    elif menu == "📦 Magazzino":
        st.subheader("Inventario Attuale")
        df_mag = pd.DataFrame(ws_mag.get_all_records())
        
        if not df_mag.empty:
            search = st.text_input("🔍 Cerca...", "")
            df_mag['Canali'] = df_mag['Canali_Raw'].apply(get_channel_dots)
            
            if search:
                mask = df_mag.astype(str).apply(lambda x: x.str.lower().str.contains(search.lower())).any(axis=1)
                df_show = df_mag[mask]
            else:
                df_show = df_mag
                
            st.dataframe(
                df_show[['ID_Tag', 'Canali', 'Posizione', 'Descrizione', 'Prezzo_Ipotetico', 'Prezzo_Minimo']],
                column_config={
                    "Prezzo_Ipotetico": st.column_config.NumberColumn("€ Ipo", format="€ %.0f"),
                    "Prezzo_Minimo": st.column_config.NumberColumn("€ Min", format="€ %.0f"),
                },
                use_container_width=True, hide_index=True
            )

    # --- PAGINA 3: NUOVO ---
    elif menu == "➕ Aggiungi Articolo":
        st.header("Carica Articolo")
        with st.form("add_form"):
            c1, c2 = st.columns([1, 2])
            id_tag = c1.text_input("# TAG (es. #F10)", placeholder="#").upper()
            pos = c2.selectbox("Posizione", POSIZIONI)
            
            st.markdown("---")
            st.write("**Prezzi Target**")
            cp1, cp2 = st.columns(2)
            p_ipo = cp1.number_input("Prezzo Ipotetico (€)", min_value=0.0)
            p_min = cp2.number_input("Prezzo Minimo (€)", min_value=0.0)
            
            st.markdown("---")
            desc = st.text_area("Descrizione (Copia e incolla dal questionario o scrivi a mano)")
            
            st.write("**Canali Attivi**")
            cols = st.columns(5)
            chans = []
            for i, p in enumerate(PIATTAFORME.keys()):
                if cols[i].checkbox(p): chans.append(p)
            
            if st.form_submit_button("Salva in Magazzino"):
                ws_mag.append_row([
                    id_tag, "GENERICO", desc, "Buono", pos, ",".join(chans), 
                    p_ipo, p_min, datetime.now().strftime("%Y-%m-%d")
                ])
                st.success("Salvato!")

    # --- PAGINA 4: VENDITA ---
    elif menu == "💰 Registra Vendita":
        st.header("Nuova Vendita")
        df_mag = pd.DataFrame(ws_mag.get_all_records())
        
        if not df_mag.empty:
            tag = st.selectbox("Seleziona Articolo", df_mag['ID_Tag'].tolist())
            item = df_mag[df_mag['ID_Tag'] == tag].iloc[0]
            st.caption(f"Descrizione: {item['Descrizione']}")
            
            with st.form("sell_form"):
                d1, d2 = st.columns(2)
                piattaforma = d1.selectbox("Piattaforma Vendita", list(PIATTAFORME.keys()))
                data_vendita = d2.date_input("Data Vendita", datetime.now())
                
                c1, c2 = st.columns(2)
                lordo = c1.number_input("Prezzo Pagato dal Cliente (€)", min_value=0.0)
                spese = c2.number_input("Spese Sped./Comm. (€)", min_value=0.0, help="Quanto ci è costato spedire/vendere?")
                
                netto = lordo - spese
                st.write(f"**Guadagno Netto:** € {netto:.2f}")
                
                if st.form_submit_button("CONFERMA VENDITA"):
                    # Salva in Vendite
                    ws_ven.append_row([
                        tag, item['Descrizione'], piattaforma, lordo, spese, netto, 
                        False, False, st.session_state['user'], str(data_vendita), ""
                    ])
                    # Cancella da Magazzino
                    cell = ws_mag.find(tag)
                    ws_mag.delete_rows(cell.row)
                    st.balloons()
                    st.success("Vendita registrata! Vai in Dashboard per gestire spedizione e incasso.")
        else:
            st.warning("Magazzino vuoto.")

    # --- PAGINA 5: RESI ---
    elif menu == "🔙 Gestione Resi":
        st.header("Gestione Resi e Annullamenti")
        st.warning("Usa questa funzione se un cliente restituisce un prodotto o se hai registrato una vendita per errore.")
        
        if not df_ven.empty:
            # Lista prodotti venduti
            # Creiamo etichette leggibili per la selectbox
            df_ven['Label'] = df_ven['ID_Tag'] + " - " + df_ven['Descrizione']
            selected_reso = st.selectbox("Seleziona Prodotto da Restituire", df_ven['Label'].tolist())
            
            # Estrai ID dal label
            tag_reso = selected_reso.split(" - ")[0]
            row_reso = df_ven[df_ven['ID_Tag'] == tag_reso].iloc[0]
            
            st.info(f"Stai per riportare **{tag_reso}** in Magazzino.")
            
            col_r1, col_r2 = st.columns(2)
            motivo = col_r1.text_input("Motivo del reso", placeholder="Es. Cliente non soddisfatto / Errore inserimento")
            nuovo_stato = col_r2.selectbox("Stato attuale oggetto", ["Come prima", "Rotto/Danneggiato", "Da Testare"])
            
            if st.button("🔄 EFFETTUA RESO (Ripristina in Magazzino)"):
                # 1. Aggiungi di nuovo a Magazzino
                ws_mag.append_row([
                    tag_reso, 
                    "Reso", 
                    row_reso['Descrizione'] + f" [RESO: {motivo}]", 
                    nuovo_stato, 
                    "Magazzino", 
                    "", 
                    0, 0, # Prezzi target resettati
                    datetime.now().strftime("%Y-%m-%d")
                ])
                
                # 2. Rimuovi da Vendite
                cell = ws_ven.find(tag_reso)
                ws_ven.delete_rows(cell.row)
                
                st.success(f"{tag_reso} è tornato in magazzino. La vendita è stata annullata.")
                st.rerun()

    # --- PAGINA 6: SPESE ---
    elif menu == "💸 Spese & Uscite":
        st.header("Registra Spesa")
        with st.form("exp"):
            d = st.text_input("Descrizione")
            imp = st.number_input("Importo (€)", min_value=0.0)
            cat = st.selectbox("Categoria", ["Materiale", "Cibo", "Affitto", "Varie"])
            if st.form_submit_button("Registra"):
                ws_spese.append_row([datetime.now().strftime("%Y-%m-%d"), cat, d, imp, st.session_state['user']])
                st.success("Spesa salvata.")
        
        st.divider()
        st.write("Ultime spese:")
        st.dataframe(df_spese.tail(10) if not df_spese.empty else pd.DataFrame(), use_container_width=True)

if __name__ == "__main__":
    main()