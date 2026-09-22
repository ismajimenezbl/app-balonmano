import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import time
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="Stats Balonmano", layout="wide", initial_sidebar_state="collapsed")

# --- CSS DEFINITIVO: LAYOUT ESTILO STEAZZI EN MÓVIL ---
st.markdown("""
<style>
    /* Ocultar elementos sobrantes de Streamlit y reducir padding */
    header { visibility: hidden !important; }
    footer { display: none !important; }
    .block-container {
        padding: 0.1rem 0.2rem 0.5rem 0.2rem !important;
        max-width: 100vw !important;
        overflow-x: hidden !important;
    }

    /* Contenedor principal de 2 columnas: Bloqueado horizontalmente sin salto de línea */
    div[data-testid="stHorizontalBlock"]:has(.col-dorsales-scroll) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 6px !important;
        width: 100% !important;
    }

    /* Columna 1: Dorsales con scroll vertical independiente */
    .col-dorsales-scroll {
        width: 48px !important;
        min-width: 48px !important;
        max-width: 48px !important;
        max-height: 80vh !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 3px !important;
        padding-right: 2px !important;
    }

    .col-dorsales-scroll button {
        width: 100% !important;
        min-height: 36px !important;
        height: 36px !important;
        padding: 0px !important;
        font-size: 15px !important;
        font-weight: bold !important;
        border-radius: 6px !important;
    }

    /* Columna 2: Panel de juego FIJO (Pulgares + Imagen + Botones) */
    .col-panel-juego {
        flex: 1 1 auto !important;
        width: calc(100% - 54px) !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
    }

    /* Fila de 2 pulgares arriba de la imagen */
    div[data-testid="stHorizontalBlock"]:has(.btn-pulgar) {
        display: grid !important;
        grid-template-columns: 1fr 1fr !important;
        gap: 6px !important;
        width: 100% !important;
        margin-bottom: 4px !important;
    }

    .btn-pulgar button {
        height: 44px !important;
        min-height: 44px !important;
        font-size: 22px !important;
        border-radius: 8px !important;
    }

    /* Fila de 3 botones abajo de la imagen */
    div[data-testid="stHorizontalBlock"]:has(.btn-accion-inferior) {
        display: grid !important;
        grid-template-columns: 1fr 1fr 1fr !important;
        gap: 4px !important;
        width: 100% !important;
        margin-top: 4px !important;
    }

    .btn-accion-inferior button {
        height: 36px !important;
        min-height: 36px !important;
        font-size: 13px !important;
        padding: 0px !important;
        border-radius: 6px !important;
    }

    /* Ajuste de la imagen para que encaje al ancho exacto del panel */
    .col-panel-juego iframe, .col-panel-juego img {
        max-width: 100% !important;
        border-radius: 8px !important;
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

# --- MENÚ PRINCIPAL ---
menu = st.sidebar.selectbox("Navegación", ["1. Registro en Vivo", "2. Partidos", "3. Plantilla", "4. Estadísticas"])

if menu == "1. Registro en Vivo":
    df_j = obtener_datos("jugadores")
    df_p = obtener_datos("partidos")
    
    if df_j.empty or df_p.empty:
        st.warning("⚠️ Añade jugadores y un partido en el menú lateral.")
    else:
        # Marcador y Reloj superior
        col_sup1, col_sup2, col_sup3 = st.columns([3, 1, 1])
        with col_sup1:
            opciones_partidos = df_p['id'].astype(str) + " - vs " + df_p['rival']
            partido_sel = st.selectbox("Partido:", opciones_partidos, label_visibility="collapsed")
            id_partido_actual = int(partido_sel.split(" - ")[0])
        with col_sup2:
            if not st.session_state.reloj_activo:
                if st.button("▶️", use_container_width=True): 
                    st.session_state.reloj_activo = True; st.session_state.inicio_tramo = time.time(); st.rerun()
            else:
                if st.button("⏸️", use_container_width=True): 
                    st.session_state.reloj_activo = False; st.session_state.tiempo_acumulado += (time.time() - st.session_state.inicio_tramo); st.rerun()
        with col_sup3:
            st.markdown(f"<div style='font-size: 18px; font-weight: bold; text-align: center; line-height: 38px;'>{calcular_minuto_actual()}'</div>", unsafe_allow_html=True)

        st.markdown("<hr style='margin: 2px 0 6px 0;'>", unsafe_allow_html=True)

        # DISTRIBUCIÓN HORIZONTAL ESTRICTA (Dorsales izq con scroll + Panel der fijo)
        col_izq, col_der = st.columns([1, 5])
        
        with col_izq:
            st.markdown('<div class="col-dorsales-scroll">', unsafe_allow_html=True)
            for _, row in df_j.sort_values('dorsal').iterrows():
                es_activo = (st.session_state.jugador_activo is not None and st.session_state.jugador_activo.get('id') == row['id'])
                if st.button(f"{row['dorsal']}", key=f"dor_{row['id']}", type="primary" if es_activo else "secondary"):
                    st.session_state.jugador_activo = row.to_dict()
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
                    
        with col_der:
            st.markdown('<div class="col-panel-juego">', unsafe_allow_html=True)
            
            # Nombre del jugador seleccionado
            if st.session_state.jugador_activo:
                jug = st.session_state.jugador_activo
                st.markdown(f"<div style='font-size:13px; font-weight:bold; margin-bottom:3px;'>#{jug['dorsal']} {jug['nombre']}</div>", unsafe_allow_html=True)
                es_portero = (jug['posicion'] == 'Portero')
            else:
                st.markdown("<div style='font-size:12px; color:#888; margin-bottom:3px;'>👈 Toca un dorsal</div>", unsafe_allow_html=True)
                es_portero = False

            # Fila de 2 Pulgares justo encima de la imagen
            st.markdown('<div class="btn-pulgar">', unsafe_allow_html=True)
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
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Imagen de Pista/Portería
            try:
                click = streamlit_image_coordinates("plantilla.jpg", key="mapa_movil", width=290)
                if click:
                    if click['y'] < 350: st.session_state.tmp_porteria = f"{click['x']},{click['y']}"
                    else: st.session_state.tmp_pista = f"{click['x']},{click['y']}"
            except:
                st.warning("Falta plantilla.jpg")
                
            # Fila de 3 Acciones justo debajo de la imagen
            st.markdown('<div class="btn-accion-inferior">', unsafe_allow_html=True)
            cb1, cb2, cb3 = st.columns(3)
            with cb1: 
                if st.button("Sanc.", use_container_width=True): menu_sanciones(id_partido_actual)
            with cb2: 
                if st.button("Ataq.", use_container_width=True): menu_ataque(id_partido_actual)
            with cb3: 
                if st.button("Def.", use_container_width=True): menu_defensa(id_partido_actual)
            st.markdown('</div>', unsafe_allow_html=True)
                
            st.markdown('</div>', unsafe_allow_html=True)

# --- 2. PARTIDOS ---
elif menu == "2. Partidos":
    st.subheader("Gestión de Partidos")
    c_p1, c_p2 = st.columns(2)
    with c_p1: fecha = st.date_input("Fecha", datetime.today())
    with c_p2: rival = st.text_input("Rival")
    if st.button("Crear Partido", type="primary"):
        if rival:
            df_p = obtener_datos("partidos")
            nuevo_id_p = 1 if df_p.empty else int(df_p['id'].max()) + 1
            sheet.worksheet("partidos").append_row([nuevo_id_p, str(fecha), rival])
            st.cache_data.clear()
            st.success(f"Partido vs {rival} creado.")
            st.rerun()
    st.divider()
    df_p = obtener_datos("partidos")
    if not df_p.empty: st.dataframe(df_p, use_container_width=True)

# --- 3. PLANTILLA ---
elif menu == "3. Plantilla":
    st.subheader("Gestión de Plantilla")
    c1, c2, c3 = st.columns(3)
    with c1: nombre = st.text_input("Nombre")
    with c2: dorsal = st.number_input("Dorsal", min_value=1, max_value=99)
    with c3: posicion = st.selectbox("Posición", ["Portero", "Extremo Izq", "Lateral Izq", "Central", "Lateral Der", "Extremo Der", "Pivote"])
    if st.button("Guardar Jugador", type="primary"):
        df_j = obtener_datos("jugadores")
        nuevo_id = 1 if df_j.empty else int(df_j['id'].max()) + 1
        sheet.worksheet("jugadores").append_row([nuevo_id, nombre, dorsal, posicion])
        st.cache_data.clear()
        st.success("Jugador añadido.")
        st.rerun()
    df_j = obtener_datos("jugadores")
    if not df_j.empty: st.dataframe(df_j[['dorsal', 'nombre', 'posicion']].sort_values('dorsal'), use_container_width=True)

# --- 4. ESTADÍSTICAS ---
elif menu == "4. Estadísticas":
    df_j = obtener_datos("jugadores")
    df_e = obtener_datos("eventos")
    df_p = obtener_datos("partidos")
    if not df_e.empty and not df_j.empty and not df_p.empty:
        filtro_sel = st.selectbox("Ver:", ["🏆 Acumulado"] + list(df_p['id'].astype(str) + " - vs " + df_p['rival']))
        if "Acumulado" not in filtro_sel:
            df_e = df_e[df_e['id_partido'] == int(filtro_sel.split(" - ")[0])]
        if not df_e.empty:
            df_merged = pd.merge(df_e, df_j, left_on='jugador_id', right_on='id')
            resumen = df_merged.groupby(['dorsal', 'nombre', 'accion']).size().reset_index(name='total')
            st.dataframe(resumen.pivot(index=['dorsal', 'nombre'], columns='accion', values='total').fillna(0).astype(int), use_container_width=True)
