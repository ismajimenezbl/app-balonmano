import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import time
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="Stats Balonmano", layout="wide", initial_sidebar_state="collapsed")

# --- CSS EXACTO PARA MÓVILES (ESTILO STEAZZI) ---
st.markdown("""
<style>
    /* 1. Evitar márgenes sobrantes en móviles */
    .block-container {
        padding: 0.5rem 0.2rem 1rem 0.2rem !important;
        max-width: 100% !important;
    }
    
    /* 2. Forzar que las dos columnas principales se mantengan una al lado de la otra */
    div[data-testid="stHorizontalBlock"]:has(div.col-dorsales) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 4px !important;
    }
    
    /* 3. Columna izquierda (Dorsales estrechos) */
    div.col-dorsales {
        width: 48px !important;
        min-width: 48px !important;
        max-width: 55px !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 2px !important;
    }
    
    /* Botones de dorsal pequeños y cuadrados */
    div.col-dorsales button {
        width: 100% !important;
        min-height: 38px !important;
        height: 38px !important;
        padding: 0px !important;
        font-weight: bold !important;
        font-size: 16px !important;
        border-radius: 6px !important;
    }
    
    /* 4. Columna derecha (Acción y Pista) */
    div.col-pista {
        flex: 1 1 auto !important;
        width: calc(100% - 55px) !important;
        overflow: hidden !important;
    }

    /* Pulgares más grandes y compactos */
    div.col-pista button {
        min-height: 42px !important;
        font-size: 20px !important;
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
        st.toast("⚠️ Selecciona un jugador primero", icon="⚠️")
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

# --- POP-UPS NATIVOS ---
@st.dialog("Sanciones")
def menu_sanciones(id_partido):
    c1, c2, c3 = st.columns(3)
    if c1.button("🟨", use_container_width=True): registrar_accion_agil("Amarilla", id_partido); st.rerun()
    if c2.button("✌️ 2'", use_container_width=True): registrar_accion_agil("Exclusión 2 Min", id_partido); st.rerun()
    if c3.button("🟥", type="primary", use_container_width=True): registrar_accion_agil("Tarjeta Roja", id_partido); st.rerun()

@st.dialog("Ataque")
def menu_ataque(id_partido):
    for acc in ["Pasos", "Doble regate", "Falta en ataque", "Pérdida", "Tiro bloqueado", "7m provocado"]:
        if st.button(acc, use_container_width=True): registrar_accion_agil(acc, id_partido); st.rerun()

@st.dialog("Defensa")
def menu_defensa(id_partido):
    for acc in ["7m en contra", "Duelo perdido", "Falta", "Intercepción"]:
        if st.button(acc, use_container_width=True): registrar_accion_agil(acc, id_partido); st.rerun()

# --- PANTALLA PRINCIPAL ---
menu = st.sidebar.selectbox("Nav", ["1. Partido", "2. Plantilla", "3. Estadísticas"])

if menu == "1. Partido":
    df_j = obtener_datos("jugadores")
    df_p = obtener_datos("partidos")
    
    if not df_j.empty and not df_p.empty:
        id_partido_actual = int(df_p['id'].iloc[-1])
        
        # Barra superior con marcador/reloj
        c_r1, c_r2 = st.columns([1, 2])
        with c_r1:
            if not st.session_state.reloj_activo:
                if st.button("▶️ Iniciar", use_container_width=True): 
                    st.session_state.reloj_activo = True; st.session_state.inicio_tramo = time.time(); st.rerun()
            else:
                if st.button("⏸️ Pausa", use_container_width=True): 
                    st.session_state.reloj_activo = False; st.session_state.tiempo_acumulado += (time.time() - st.session_state.inicio_tramo); st.rerun()
        with c_r2:
            st.markdown(f"<div style='text-align: right; font-size: 20px; font-weight: bold;'>⏱️ Minuto: {calcular_minuto_actual()}'</div>", unsafe_allow_html=True)

        st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)

        # DISTRIBUCIÓN HORIZONTAL BLOQUEADA
        col_izq, col_der = st.columns([1, 6])
        
        with col_izq:
            st.markdown('<div class="col-dorsales">', unsafe_allow_html=True)
            for _, row in df_j.sort_values('dorsal').iterrows():
                es_activo = (st.session_state.jugador_activo is not None and st.session_state.jugador_activo.get('id') == row['id'])
                if st.button(f"{row['dorsal']}", key=f"dor_{row['id']}", type="primary" if es_activo else "secondary"):
                    st.session_state.jugador_activo = row.to_dict()
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
                    
        with col_der:
            st.markdown('<div class="col-pista">', unsafe_allow_html=True)
            
            # Nombre del jugador seleccionado
            if st.session_state.jugador_activo:
                jug = st.session_state.jugador_activo
                st.markdown(f"<div style='font-size:14px; margin-bottom:4px;'>👤 <b>#{jug['dorsal']} {jug['nombre']}</b> ({jug['posicion']})</div>", unsafe_allow_html=True)
                es_portero = jug['posicion'] == 'Portero'
            else:
                st.markdown("<div style='font-size:13px; color:#aaa; margin-bottom:4px;'>👈 Pulsa un dorsal</div>", unsafe_allow_html=True)
                es_portero = False

            # Botones de Gol / Fallo (Pulgares)
            c_mal, c_bien = st.columns(2)
            with c_mal:
                if st.button("👎", use_container_width=True):
                    if st.session_state.jugador_activo:
                        registrar_accion_agil("Gol Encajado" if es_portero else "Tiro Fallado", id_partido_actual)
                        st.rerun()
            with c_bien:
                if st.button("👍", use_container_width=True):
                    if st.session_state.jugador_activo:
                        registrar_accion_agil("Parada" if es_portero else "Gol", id_partido_actual)
                        st.rerun()
            
            # Imagen de la Pista (ocupando el ancho disponible)
            try:
                click = streamlit_image_coordinates("plantilla.jpg", key="mapa_movil", use_column_width=True)
                if click:
                    if click['y'] < 400: st.session_state.tmp_porteria = f"{click['x']},{click['y']}"
                    else: st.session_state.tmp_pista = f"{click['x']},{click['y']}"
            except:
                st.warning("Falta plantilla.jpg")
                
            # Acciones Rápidas (Pop-ups inferiores)
            cb1, cb2, cb3 = st.columns(3)
            with cb1: 
                if st.button("Sanc.", use_container_width=True): menu_sanciones(id_partido_actual)
            with cb2: 
                if st.button("Ataq.", use_container_width=True): menu_ataque(id_partido_actual)
            with cb3: 
                if st.button("Def.", use_container_width=True): menu_defensa(id_partido_actual)
                
            st.markdown('</div>', unsafe_allow_html=True)

# Pestañas de soporte
elif menu == "2. Plantilla":
    st.subheader("Añadir Jugador")
    nombre = st.text_input("Nombre")
    dorsal = st.number_input("Dorsal", min_value=1, max_value=99)
    posicion = st.selectbox("Posición", ["Portero", "Extremo Izq", "Lateral Izq", "Central", "Lateral Der", "Extremo Der", "Pivote"])
    if st.button("Guardar"):
        df_j = obtener_datos("jugadores")
        nuevo_id = 1 if df_j.empty else int(df_j['id'].max()) + 1
        sheet.worksheet("jugadores").append_row([nuevo_id, nombre, dorsal, posicion])
        st.cache_data.clear()
        st.success("Guardado")
        st.rerun()

elif menu == "3. Estadísticas":
    df_j = obtener_datos("jugadores")
    df_e = obtener_datos("eventos")
    if not df_e.empty and not df_j.empty:
        df_merged = pd.merge(df_e, df_j, left_on='jugador_id', right_on='id')
        resumen = df_merged.groupby(['dorsal', 'nombre', 'accion']).size().reset_index(name='total')
        st.dataframe(resumen.pivot(index=['dorsal', 'nombre'], columns='accion', values='total').fillna(0).astype(int), use_container_width=True)
