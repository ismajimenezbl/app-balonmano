import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import time
from streamlit_image_coordinates import streamlit_image_coordinates

# Configuración inicial
st.set_page_config(page_title="Stats Balonmano", layout="wide", initial_sidebar_state="collapsed")

# --- CSS PARA FORZAR VISTA MÓVIL (ESTILO STEAZZI) ---
st.markdown("""
<style>
    /* Forzar que las columnas no se rompan en móviles */
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            display: flex !important;
            flex-wrap: nowrap !important;
        }
        /* Ajustar el ancho: Columna izquierda (Dorsales) 20%, Derecha (Pista) 80% */
        div[data-testid="column"]:nth-of-type(1) {
            width: 20% !important;
            flex: 1 1 20% !important;
            min-width: 20% !important;
            padding-right: 5px !important;
        }
        div[data-testid="column"]:nth-of-type(2) {
            width: 80% !important;
            flex: 1 1 80% !important;
            min-width: 80% !important;
        }
    }
    
    /* Reducir márgenes y espacios muertos para que quepa todo */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    button {
        padding: 0.2rem !important;
        min-height: 2.5rem !important;
    }
</style>
""", unsafe_allow_html=True)

# --- MEMORIA (SESSION STATE) ---
if 'reloj_activo' not in st.session_state: st.session_state.reloj_activo = False
if 'inicio_tramo' not in st.session_state: st.session_state.inicio_tramo = None
if 'tiempo_acumulado' not in st.session_state: st.session_state.tiempo_acumulado = 0.0
if 'jugador_activo' not in st.session_state: st.session_state.jugador_activo = None
if 'tmp_pista' not in st.session_state: st.session_state.tmp_pista = ""
if 'tmp_porteria' not in st.session_state: st.session_state.tmp_porteria = ""

def calcular_minuto_actual():
    if st.session_state.reloj_activo:
        total_segundos = st.session_state.tiempo_acumulado + (time.time() - st.session_state.inicio_tramo)
    else:
        total_segundos = st.session_state.tiempo_acumulado
    return int(total_segundos // 60) + 1

# --- CONEXIÓN Y CACHÉ ---
@st.cache_resource
def conectar_gsheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds).open("Datos App Balonmano")

try: sheet = conectar_gsheets()
except Exception as e: st.stop()

@st.cache_data(ttl=300)
def obtener_datos(nombre_hoja):
    return pd.DataFrame(sheet.worksheet(nombre_hoja).get_all_records())

def registrar_accion_agil(accion, id_partido, zona="N/A"):
    if not st.session_state.jugador_activo:
        st.toast("⚠️ Selecciona un jugador", icon="⚠️")
        return
    idx = st.session_state.jugador_activo['id']
    minuto = calcular_minuto_actual()
    df_e = obtener_datos("eventos")
    nuevo_id_e = 1 if df_e.empty else int(df_e['id'].max()) + 1
    
    sheet.worksheet("eventos").append_row([
        nuevo_id_e, int(idx), accion, zona, minuto, id_partido, 
        st.session_state.tmp_pista, st.session_state.tmp_porteria
    ])
    st.cache_data.clear()
    st.session_state.jugador_activo = None
    st.session_state.tmp_pista = ""
    st.session_state.tmp_porteria = ""
    st.toast(f"✅ Guardado: {accion}", icon="✅")

# POP-UPS
@st.dialog("Sanciones")
def menu_sanciones(id_partido):
    c1, c2, c3 = st.columns(3)
    if c1.button("🟨", use_container_width=True): registrar_accion_agil("Amarilla", id_partido); st.rerun()
    if c2.button("✌️", use_container_width=True): registrar_accion_agil("Exclusión 2 Min", id_partido); st.rerun()
    if c3.button("🟥", type="primary", use_container_width=True): registrar_accion_agil("Tarjeta Roja", id_partido); st.rerun()

@st.dialog("Ataque")
def menu_ataque(id_partido):
    for acc in ["Pasos", "Doble regate", "Falta en ataque", "Pérdida", "Tiro bloqueado", "7m provocado"]:
        if st.button(acc, use_container_width=True): registrar_accion_agil(acc, id_partido); st.rerun()

@st.dialog("Defensa")
def menu_defensa(id_partido):
    for acc in ["7m en contra", "Duelo perdido", "Falta", "Intercepción"]:
        if st.button(acc, use_container_width=True): registrar_accion_agil(acc, id_partido); st.rerun()

menu = st.sidebar.selectbox("Nav", ["1. Partido", "2. Ajustes"])

if menu == "1. Partido":
    df_j = obtener_datos("jugadores")
    df_p = obtener_datos("partidos")
    if not df_j.empty and not df_p.empty:
        id_partido_actual = int(df_p['id'].iloc[-1]) # Selecciona el último partido por defecto para ahorrar espacio
        
        # Reloj compacto superior
        c_r1, c_r2 = st.columns(2)
        with c_r1:
            if not st.session_state.reloj_activo:
                if st.button("▶️", use_container_width=True): st.session_state.reloj_activo = True; st.session_state.inicio_tramo = time.time(); st.rerun()
            else:
                if st.button("⏸️", use_container_width=True): st.session_state.reloj_activo = False; st.session_state.tiempo_acumulado += (time.time() - st.session_state.inicio_tramo); st.rerun()
        with c_r2:
            st.markdown(f"<h3 style='text-align: center; margin:0;'>{calcular_minuto_actual()}'</h3>", unsafe_allow_html=True)

        st.markdown("---")

        # MAQUETACIÓN LADO A LADO FORZADA
        col_dorsal, col_centro = st.columns([1, 4])
        
        with col_dorsal:
            for _, row in df_j.sort_values('dorsal').iterrows():
                es_activo = (st.session_state.jugador_activo is not None and st.session_state.jugador_activo.get('id') == row['id'])
                if st.button(f"{row['dorsal']}", key=f"dor_{row['id']}", use_container_width=True, type="primary" if es_activo else "secondary"):
                    st.session_state.jugador_activo = row.to_dict()
                    st.rerun()
                    
        with col_centro:
            # Fila de Pulgares
            c_mal, c_bien = st.columns(2)
            with c_mal:
                if st.button("👎", use_container_width=True):
                    if st.session_state.jugador_activo:
                        registrar_accion_agil("Gol Encajado" if st.session_state.jugador_activo['posicion']=='Portero' else "Tiro Fallado", id_partido_actual)
                        st.rerun()
            with c_bien:
                if st.button("👍", use_container_width=True):
                    if st.session_state.jugador_activo:
                        registrar_accion_agil("Parada" if st.session_state.jugador_activo['posicion']=='Portero' else "Gol", id_partido_actual)
                        st.rerun()
            
            # Imagen Pista
            try:
                click = streamlit_image_coordinates("plantilla.jpg", key="mapa", use_column_width=True)
                if click:
                    if click['y'] < 400: st.session_state.tmp_porteria = f"{click['x']},{click['y']}"
                    else: st.session_state.tmp_pista = f"{click['x']},{click['y']}"
            except: st.warning("Falta imagen")
            
            # Botones Pop-up debajo
            cb1, cb2, cb3 = st.columns(3)
            with cb1: 
                if st.button("Sanc", use_container_width=True): menu_sanciones(id_partido_actual)
            with cb2: 
                if st.button("Atq", use_container_width=True): menu_ataque(id_partido_actual)
            with cb3: 
                if st.button("Def", use_container_width=True): menu_defensa(id_partido_actual)
