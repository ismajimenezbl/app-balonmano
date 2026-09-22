import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import time
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="Stats Balonmano", layout="wide", initial_sidebar_state="collapsed")

# Anchos matemáticos para entrar en el 100% de pantallas móviles sin scroll horizontal
ANCHO_IMG = 245
ANCHO_DORSAL = 52
UMBRAL_PORTERIA_Y = 320

CSS = """
<style>
    /* Ocultar barra superior nativa y pie de página */
    header { display: none !important; }
    footer { display: none !important; }

    /* Ajustar márgenes globales de la pantalla al mínimo */
    .block-container {
        padding: 0.2rem 0.2rem 0.4rem 0.2rem !important;
        max-width: 100vw !important;
        overflow-x: hidden !important;
    }

    /* Contenedor principal sin desbordamiento */
    .st-key-registro {
        max-width: 100vw !important;
        margin: 0 auto !important;
        overflow-x: hidden !important;
    }

    /* Filas horizontales fijas: prohíbe que el móvil apile las columnas */
    .st-key-registro [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 6px !important;
        align-items: flex-start !important;
    }

    /* Columna de dorsales (izquierda) */
    .st-key-registro > div[data-testid="stHorizontalBlock"] > div:first-child {
        flex: 0 0 __DORSAL__px !important;
        min-width: __DORSAL__px !important;
        max-width: __DORSAL__px !important;
        width: __DORSAL__px !important;
    }

    /* Columna del campo y controles (derecha) */
    .st-key-registro > div[data-testid="stHorizontalBlock"] > div:last-child {
        flex: 0 0 __IMG__px !important;
        min-width: __IMG__px !important;
        max-width: __IMG__px !important;
        width: __IMG__px !important;
    }

    /* Barra de cabecera superior */
    .cabecera-top [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        gap: 4px !important;
        align-items: center !important;
    }

    /* Lista vertical de dorsales con scroll */
    .st-key-dorsales {
        max-height: 80vh !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 4px !important;
    }

    .st-key-dorsales button {
        width: 100% !important;
        height: 38px !important;
        min-height: 38px !important;
        padding: 0 !important;
        font-weight: bold !important;
        font-size: 16px !important;
        border-radius: 6px !important;
    }

    /* ESTILO AMARILLO PARA PORTEROS */
    div[class*="st-key-portero_"] button {
        background-color: #facc15 !important;
        color: #000000 !important;
        font-weight: 900 !important;
        border: 2px solid #ca8a04 !important;
    }

    /* Banner informativo del jugador */
    .banner-jugador {
        width: 100%;
        text-align: center;
        font-size: 12px;
        font-weight: bold;
        padding: 5px 4px;
        margin-bottom: 4px;
        border-radius: 6px;
        box-sizing: border-box;
    }
    .banner-jugador.activo {
        background-color: #1e3a8a;
        color: #ffffff;
        border: 1px solid #3b82f6;
    }
    .banner-jugador.inactivo {
        background-color: #1f2937;
        color: #9ca3af;
        border: 1px dashed #374151;
    }

    /* Pulgares: 2 columnas fijas en fila */
    .st-key-pulgares [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        gap: 6px !important;
        width: 100% !important;
        margin-bottom: 4px !important;
    }
    .st-key-pulgares [data-testid="stColumn"],
    .st-key-pulgares [data-testid="column"] {
        flex: 1 1 50% !important;
        width: 50% !important;
        min-width: 0 !important;
    }
    .st-key-pulgares button {
        width: 100% !important;
        height: 44px !important;
        min-height: 44px !important;
        font-size: 22px !important;
        padding: 0 !important;
    }

    /* Acciones: 3 columnas fijas en fila */
    .st-key-acciones [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        gap: 4px !important;
        width: 100% !important;
        margin-top: 4px !important;
    }
    .st-key-acciones [data-testid="stColumn"],
    .st-key-acciones [data-testid="column"] {
        flex: 1 1 33.33% !important;
        width: 33.33% !important;
        min-width: 0 !important;
    }
    .st-key-acciones button {
        width: 100% !important;
        height: 38px !important;
        min-height: 38px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 0 !important;
    }

    /* Iframe de la imagen del campo */
    .st-key-campo iframe {
        border-radius: 8px !important;
        display: block !important;
        width: __IMG__px !important;
        max-width: 100% !important;
    }
</style>
"""

st.markdown(CSS.replace("__IMG__", str(ANCHO_IMG)).replace("__DORSAL__", str(ANCHO_DORSAL)), unsafe_allow_html=True)

# --- ESTADO (SESSION STATE) ---
if 'seccion_actual' not in st.session_state: st.session_state.seccion_actual = "1. Registro en Vivo"
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

# --- CONEXIÓN GOOGLE SHEETS ---
@st.cache_resource
def conectar_gsheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds).open("Datos App Balonmano")

try: sheet = conectar_gsheets()
except Exception: st.stop()

@st.cache_data(ttl=300)
def obtener_datos(nombre_hoja):
    return pd.DataFrame(sheet.worksheet(nombre_hoja).get_all_records())

def registrar_accion_agil(accion, id_partido):
    if not st.session_state.jugador_activo:
        st.toast("⚠️ Selecciona dorsal primero", icon="⚠️")
        return
    idx = st.session_state.jugador_activo['id']
    minuto = calcular_minuto_actual()
    df_e = obtener_datos("eventos")
    nuevo_id_e = 1 if df_e.empty else int(df_e['id'].max()) + 1

    sheet.worksheet("eventos").append_row([
        nuevo_id_e, int(idx), accion, "N/A", minuto, id_partido,
        st.session_state.tmp_pista, st.session_state.tmp_porteria
    ])
    st.cache_data.clear()
    st.session_state.jugador_activo = None
    st.session_state.tmp_pista = ""
    st.session_state.tmp_porteria = ""
    st.toast(f"✅ Guardado: {accion}", icon="✅")

# --- MENÚ DE NAVEGACIÓN HAMBURGUESA (POP-UP) ---
@st.dialog("Navegación")
def abrir_menu_navegacion():
    opciones = [
        ("🔴 Registro en Vivo", "1. Registro en Vivo"),
        ("📅 Partidos", "2. Partidos"),
        ("👥 Plantilla", "3. Plantilla"),
        ("📊 Estadísticas", "4. Estadísticas")
    ]
    for texto, seccion in opciones:
        if st.button(texto, use_container_width=True, type="primary" if st.session_state.seccion_actual == seccion else "secondary"):
            st.session_state.seccion_actual = seccion
            st.rerun()

# --- POP-UPS NATIVOS DE ACCIONES ---
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

# --- SECCIÓN: 1. REGISTRO EN VIVO ---
if st.session_state.seccion_actual == "1. Registro en Vivo":
    df_j = obtener_datos("jugadores")
    df_p = obtener_datos("partidos")

    if df_j.empty or df_p.empty:
        st.warning("⚠️ Añade plantilla y partidos primero.")
        if st.button("Ir al menú de opciones"):
            abrir_menu_navegacion()
    else:
        with st.container(key="registro"):
            # Cabecera superior: Selector de partido | Play/Pausa | Minuto | Menú Hamburguesa
            st.markdown('<div class="cabecera-top">', unsafe_allow_html=True)
            c_sup1, c_sup2, c_sup3, c_sup4 = st.columns([4, 1.2, 1.2, 1.2])
            with c_sup1:
                id_partido_actual = int(st.selectbox(
                    "P:", df_p['id'].astype(str) + " - " + df_p['rival'],
                    label_visibility="collapsed").split(" - ")[0])
            with c_sup2:
                if not st.session_state.reloj_activo:
                    if st.button("▶️", use_container_width=True):
                        st.session_state.reloj_activo = True; st.session_state.inicio_tramo = time.time(); st.rerun()
                else:
                    if st.button("⏸️", use_container_width=True):
                        st.session_state.reloj_activo = False
                        st.session_state.tiempo_acumulado += (time.time() - st.session_state.inicio_tramo)
                        st.rerun()
            with c_sup3:
                st.markdown(f"<div style='font-size:15px; font-weight:bold; line-height:36px; text-align:center;'>{calcular_minuto_actual()}'</div>", unsafe_allow_html=True)
            with c_sup4:
                # Botón de menú hamburguesa
                if st.button("☰", use_container_width=True):
                    abrir_menu_navegacion()
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("<hr style='margin: 2px 0 4px 0;'>", unsafe_allow_html=True)

            # Bloque principal de juego: Dorsales | Campo y botones
            c_izq, c_der = st.columns([1, 5])

            with c_izq:
                with st.container(key="dorsales"):
                    for _, row in df_j.sort_values('dorsal').iterrows():
                        es_activo = (st.session_state.jugador_activo and
                                     st.session_state.jugador_activo.get('id') == row['id'])
                        es_portero = (row['posicion'] == 'Portero')
                        
                        prefijo = "portero" if es_portero else "jugador"
                        with st.container(key=f"{prefijo}_{row['id']}"):
                            if st.button(f"{row['dorsal']}", key=f"d_{row['id']}",
                                         type="primary" if es_activo else "secondary"):
                                st.session_state.jugador_activo = row.to_dict()
                                st.rerun()

            with c_der:
                with st.container(key="campo"):
                    if st.session_state.jugador_activo:
                        j = st.session_state.jugador_activo
                        es_portero_activo = (j['posicion'] == 'Portero')
                        st.markdown(f'<div class="banner-jugador activo">#{j["dorsal"]} {j["nombre"]} ({j["posicion"]})</div>', unsafe_allow_html=True)
                    else:
                        es_portero_activo = False
                        st.markdown('<div class="banner-jugador inactivo">👈 Elige un dorsal</div>', unsafe_allow_html=True)

                    with st.container(key="pulgares"):
                        cp1, cp2 = st.columns(2)
                        with cp1:
                            if st.button("👎", use_container_width=True):
                                if st.session_state.jugador_activo:
                                    registrar_accion_agil("Gol Encajado" if es_portero_activo else "Tiro Fallado", id_partido_actual)
                                    st.rerun()
                        with cp2:
                            if st.button("👍", use_container_width=True):
                                if st.session_state.jugador_activo:
                                    registrar_accion_agil("Parada" if es_portero_activo else "Gol", id_partido_actual)
                                    st.rerun()

                    try:
                        click = streamlit_image_coordinates("plantilla.jpg", key="mapa_click", width=ANCHO_IMG)
                        if click:
                            if click['y'] < UMBRAL_PORTERIA_Y:
                                st.session_state.tmp_porteria = f"{click['x']},{click['y']}"
                            else:
                                st.session_state.tmp_pista = f"{click['x']},{click['y']}"
                    except Exception:
                        st.warning("Falta plantilla.jpg")

                    with st.container(key="acciones"):
                        ca1, ca2, ca3 = st.columns(3)
                        with ca1:
                            if st.button("Sanc.", use_container_width=True): menu_sanciones(id_partido_actual)
                        with ca2:
                            if st.button("Ataq.", use_container_width=True): menu_ataque(id_partido_actual)
                        with ca3:
                            if st.button("Def.", use_container_width=True): menu_defensa(id_partido_actual)

# --- SECCIÓN: 2. PARTIDOS ---
elif st.session_state.seccion_actual == "2. Partidos":
    col_t, col_b = st.columns([5, 1])
    with col_t: st.subheader("Gestión de Partidos")
    with col_b:
        if st.button("☰", use_container_width=True): abrir_menu_navegacion()
        
    c1, c2 = st.columns(2)
    with c1: fecha = st.date_input("Fecha", datetime.today())
    with c2: rival = st.text_input("Rival")
    if st.button("Crear Partido", type="primary"):
        if rival:
            df_p = obtener_datos("partidos")
            nuevo_id_p = 1 if df_p.empty else int(df_p['id'].max()) + 1
            sheet.worksheet("partidos").append_row([nuevo_id_p, str(fecha), rival])
            st.cache_data.clear()
            st.success("Partido creado.")
            st.rerun()
    st.divider()
    df_p = obtener_datos("partidos")
    if not df_p.empty: st.dataframe(df_p, use_container_width=True)

# --- SECCIÓN: 3. PLANTILLA ---
elif st.session_state.seccion_actual == "3. Plantilla":
    col_t, col_b = st.columns([5, 1])
    with col_t: st.subheader("Gestión de Plantilla")
    with col_b:
        if st.button("☰", use_container_width=True): abrir_menu_navegacion()
        
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

# --- SECCIÓN: 4. ESTADÍSTICAS ---
elif st.session_state.seccion_actual == "4. Estadísticas":
    col_t, col_b = st.columns([5, 1])
    with col_t: st.subheader("Estadísticas del Equipo")
    with col_b:
        if st.button("☰", use_container_width=True): abrir_menu_navegacion()
        
    df_j = obtener_datos("jugadores")
    df_e = obtener_datos("eventos")
    df_p = obtener_datos("partidos")
    if not df_e.empty and not df_j.empty and not df_p.empty:
        filtro = st.selectbox("Filtro:", ["🏆 Acumulado"] + list(df_p['id'].astype(str) + " - " + df_p['rival']))
        if "Acumulado" not in filtro:
            df_e = df_e[df_e['id_partido'] == int(filtro.split(" - ")[0])]
        if not df_e.empty:
            df_m = pd.merge(df_e, df_j, left_on='jugador_id', right_on='id')
            res = df_m.groupby(['dorsal', 'nombre', 'accion']).size().reset_index(name='total')
            st.dataframe(res.pivot(index=['dorsal', 'nombre'], columns='accion', values='total').fillna(0).astype(int), use_container_width=True)
    else:
        st.info("Aún no hay datos registrados.")
