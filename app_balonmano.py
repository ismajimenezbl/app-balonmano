import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import time
from streamlit_image_coordinates import streamlit_image_coordinates
from PIL import Image, ImageDraw

# Configuración para móvil
st.set_page_config(page_title="Stats Balonmano", layout="wide", initial_sidebar_state="collapsed")

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

try:
    sheet = conectar_gsheets()
except Exception as e:
    st.error(f"Error conectando a Google Sheets: {e}")
    st.stop()

@st.cache_data(ttl=300)
def obtener_datos(nombre_hoja):
    ws = sheet.worksheet(nombre_hoja)
    return pd.DataFrame(ws.get_all_records())

# Función para guardar datos limpia y rápida
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
    st.toast(f"✅ {accion} guardado", icon="✅")

# --- MENÚS POP-UP (FLOTANTES) ---
@st.dialog("Sanciones")
def menu_sanciones(id_partido):
    c1, c2, c3 = st.columns(3)
    if c1.button("🟨 Amarilla", use_container_width=True): 
        registrar_accion_agil("Amarilla", id_partido)
        st.rerun()
    if c2.button("✌️ 2 Minutos", use_container_width=True): 
        registrar_accion_agil("Exclusión 2 Min", id_partido)
        st.rerun()
    if c3.button("🟥 Roja", type="primary", use_container_width=True): 
        registrar_accion_agil("Tarjeta Roja", id_partido)
        st.rerun()

@st.dialog("Ataque")
def menu_ataque(id_partido):
    acciones = ["Pasos", "Doble regate", "Falta en ataque", "Pérdida de balón", "Falta", "Tiro bloqueado", "2 mins provocados", "7m provocado", "Duelo ganado"]
    cols = st.columns(3)
    for i, acc in enumerate(acciones):
        if cols[i % 3].button(acc, use_container_width=True):
            registrar_accion_agil(acc, id_partido)
            st.rerun()

@st.dialog("Defensa")
def menu_defensa(id_partido):
    acciones = ["7m en contra", "Duelo perdido", "Falta", "Tiro bloqueado", "Falta en ataque", "Intercepción"]
    cols = st.columns(3)
    for i, acc in enumerate(acciones):
        if cols[i % 3].button(acc, use_container_width=True):
            registrar_accion_agil(acc, id_partido)
            st.rerun()

# --- NAVEGACIÓN ---
menu = st.sidebar.selectbox("Navegación", ["1. Registro en Vivo", "2. Plantilla", "3. Partidos", "4. Estadísticas"])

# --- 1. REGISTRO EN VIVO (LA PANTALLA PRINCIPAL) ---
if menu == "1. Registro en Vivo":
    df_j = obtener_datos("jugadores")
    df_p = obtener_datos("partidos")
    
    if df_j.empty or df_p.empty:
        st.warning("Ve al menú lateral para añadir jugadores o crear un partido.")
    else:
        # Reloj y Partido Superior
        col_r1, col_r2, col_r3 = st.columns([3, 1, 1])
        with col_r1:
            opciones_partidos = df_p['id'].astype(str) + " - vs " + df_p['rival']
            id_partido_actual = int(st.selectbox("Partido:", opciones_partidos, label_visibility="collapsed").split(" - ")[0])
        with col_r2:
            if not st.session_state.reloj_activo:
                if st.button("▶️", use_container_width=True):
                    st.session_state.reloj_activo = True
                    st.session_state.inicio_tramo = time.time()
                    st.rerun()
            else:
                if st.button("⏸️", use_container_width=True):
                    st.session_state.reloj_activo = False
                    st.session_state.tiempo_acumulado += (time.time() - st.session_state.inicio_tramo)
                    st.rerun()
        with col_r3:
            st.markdown(f"### {calcular_minuto_actual()}'")

        # Layout estilo Steazzi: Lateral izquierdo (Dorsales), Resto (Acción)
        col_dorsal, col_centro = st.columns([1, 4])
        
        with col_dorsal:
            # Lista vertical de solo números
            for _, row in df_j.sort_values('dorsal').iterrows():
                es_activo = (st.session_state.jugador_activo is not None and st.session_state.jugador_activo.get('id') == row['id'])
                if st.button(f"{row['dorsal']}", key=f"dorsal_{row['id']}", use_container_width=True, type="primary" if es_activo else "secondary"):
                    st.session_state.jugador_activo = row.to_dict()
                    st.session_state.tmp_pista = ""
                    st.session_state.tmp_porteria = ""
                    st.rerun()
                    
        with col_centro:
            # Info del jugador activo
            if st.session_state.jugador_activo:
                jug = st.session_state.jugador_activo
                st.markdown(f"**{jug['dorsal']} - {jug['nombre']}** ({jug['posicion']})")
                es_portero = jug['posicion'] == 'Portero'
            else:
                st.markdown("**Selecciona un dorsal 👈**")
                es_portero = False

            # Fila de los Pulgares (GOL / FALLO)
            col_fallo, col_gol = st.columns(2)
            with col_fallo:
                if st.button("👎", use_container_width=True):
                    registrar_accion_agil("Gol Encajado" if es_portero else "Tiro Fallado", id_partido_actual)
                    st.rerun()
            with col_gol:
                if st.button("👍", use_container_width=True):
                    registrar_accion_agil("Parada" if es_portero else "Gol", id_partido_actual)
                    st.rerun()
            
            # IMAGEN CENTRAL (Rapidísima, sin redibujado de PIL)
            try:
                # Usamos la imagen original directamente para velocidad máxima
                click = streamlit_image_coordinates("plantilla.jpg", key="mapa_rapido", use_column_width=True)
                
                # Detectar clics en la imagen de forma inteligente
                if click:
                    # El valor Y define si tocó arriba (portería) o abajo (pista)
                    # Si tu imagen mide 800px de alto, la mitad es 400. Ajusta este número si hace falta.
                    if click['y'] < 400:
                        st.session_state.tmp_porteria = f"{click['x']},{click['y']}"
                    else:
                        st.session_state.tmp_pista = f"{click['x']},{click['y']}"
            except FileNotFoundError:
                st.warning("⚠️ Falta 'plantilla.jpg'")

            # Indicadores de selección textuales para no ralentizar la imagen
            texto_pista = "🟢" if st.session_state.tmp_pista else "⚪"
            texto_port = "🟢" if st.session_state.tmp_porteria else "⚪"
            st.caption(f"{texto_pista} Pista seleccionada | {texto_port} Portería seleccionada")

            # Botones Pop-Up inferiores
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                if st.button("Sanciones", use_container_width=True): menu_sanciones(id_partido_actual)
            with col_b2:
                if st.button("Ataque", use_container_width=True): menu_ataque(id_partido_actual)
            with col_b3:
                if st.button("Defensa", use_container_width=True): menu_defensa(id_partido_actual)


# --- (Se mantienen las secciones de Plantilla, Partidos y Estadísticas ocultas en el menú lateral) ---

elif menu == "2. Plantilla":
    st.subheader("Añadir Nuevo Jugador")
    col1, col2, col3 = st.columns(3)
    with col1: nombre = st.text_input("Nombre")
    with col2: dorsal = st.number_input("Dorsal", min_value=1, max_value=99)
    with col3: posicion = st.selectbox("Posición", ["Portero", "Extremo Izq", "Lateral Izq", "Central", "Lateral Der", "Extremo Der", "Pivote"])
    if st.button("Guardar Jugador"):
        df_j = obtener_datos("jugadores")
        nuevo_id = 1 if df_j.empty else int(df_j['id'].max()) + 1
        sheet.worksheet("jugadores").append_row([nuevo_id, nombre, dorsal, posicion])
        st.cache_data.clear()
        st.success("Jugador guardado.")
        st.rerun()
    df_j = obtener_datos("jugadores")
    if not df_j.empty: st.dataframe(df_j[['dorsal', 'nombre', 'posicion']].sort_values('dorsal'), use_container_width=True)

elif menu == "3. Partidos":
    st.subheader("Crear Nuevo Partido")
    col1, col2 = st.columns(2)
    with col1: fecha = st.date_input("Fecha", datetime.today())
    with col2: rival = st.text_input("Equipo Rival")
    if st.button("Crear Partido"):
        if rival:
            df_p = obtener_datos("partidos")
            nuevo_id_p = 1 if df_p.empty else int(df_p['id'].max()) + 1
            sheet.worksheet("partidos").append_row([nuevo_id_p, str(fecha), rival])
            st.cache_data.clear()
            st.success("Partido creado.")
            st.rerun()
    df_p = obtener_datos("partidos")
    if not df_p.empty: st.dataframe(df_p, use_container_width=True)

elif menu == "4. Estadísticas":
    df_j = obtener_datos("jugadores")
    df_e = obtener_datos("eventos")
    df_p = obtener_datos("partidos")
    
    if not df_e.empty and not df_j.empty and not df_p.empty:
        filtro_sel = st.selectbox("Ver estadísticas de:", ["🏆 Acumulado"] + list(df_p['id'].astype(str) + " - vs " + df_p['rival']))
        if "Acumulado" not in filtro_sel:
            df_e = df_e[df_e['id_partido'] == int(filtro_sel.split(" - ")[0])]
        
        if not df_e.empty:
            df_merged = pd.merge(df_e, df_j, left_on='jugador_id', right_on='id', how='inner')
            st.subheader("🗺️ Mapa de Tiro Unificado")
            try:
                img_unificada = Image.open("plantilla.jpg").convert("RGBA")
                draw = ImageDraw.Draw(img_unificada)
                for _, row in df_merged.iterrows():
                    color = "red" if row['accion'] == 'Gol' else "blue" if row['accion'] in ['Tiro Fallado', 'Parada'] else None
                    if color:
                        if pd.notna(row.get('coord_pista')) and str(row.get('coord_pista')).strip():
                            x_p, y_p = map(int, str(row['coord_pista']).split(','))
                            draw.ellipse((x_p-12, y_p-12, x_p+12, y_p+12), fill=color, outline="white")
                        if pd.notna(row.get('coord_porteria')) and str(row.get('coord_porteria')).strip():
                            x_g, y_g = map(int, str(row['coord_porteria']).split(','))
                            draw.ellipse((x_g-12, y_g-12, x_g+12, y_g+12), fill=color, outline="black")
                st.image(img_unificada, use_container_width=True)
            except: pass

            st.subheader("Rendimiento del Equipo")
            resumen = df_merged.groupby(['dorsal', 'nombre', 'accion']).size().reset_index(name='total')
            st.dataframe(resumen.pivot(index=['dorsal', 'nombre'], columns='accion', values='total').fillna(0).astype(int), use_container_width=True)
