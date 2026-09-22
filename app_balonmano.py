import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import time
import altair as alt
from streamlit_image_coordinates import streamlit_image_coordinates
from PIL import Image, ImageDraw

st.set_page_config(page_title="Stats Balonmano", layout="wide")

# --- MEMORIA (SESSION STATE) ---
if 'reloj_activo' not in st.session_state: st.session_state.reloj_activo = False
if 'inicio_tramo' not in st.session_state: st.session_state.inicio_tramo = None
if 'tiempo_acumulado' not in st.session_state: st.session_state.tiempo_acumulado = 0.0

# Nuevas variables para el flujo ágil tipo Steazzi
if 'jugador_activo' not in st.session_state: st.session_state.jugador_activo = None
if 'tmp_pista' not in st.session_state: st.session_state.tmp_pista = ""
if 'tmp_porteria' not in st.session_state: st.session_state.tmp_porteria = ""
if 'ultimo_click' not in st.session_state: st.session_state.ultimo_click = None

def calcular_minuto_actual():
    if st.session_state.reloj_activo:
        total_segundos = st.session_state.tiempo_acumulado + (time.time() - st.session_state.inicio_tramo)
    else:
        total_segundos = st.session_state.tiempo_acumulado
    return int(total_segundos // 60) + 1

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_gsheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds).open("Datos App Balonmano")

try:
    sheet = conectar_gsheets()
    ws_jugadores = sheet.worksheet("jugadores")
    ws_eventos = sheet.worksheet("eventos")
    ws_partidos = sheet.worksheet("partidos")
except Exception as e:
    st.error(f"Error conectando a Google Sheets: {e}")
    st.stop()

st.title("📊 Panel de Estadísticas Pro - Modo Ágil")
menu = st.sidebar.selectbox("Navegación", ["1. Plantilla", "2. Partidos", "3. Registro en Vivo", "4. Estadísticas"])

def obtener_datos(worksheet):
    return pd.DataFrame(worksheet.get_all_records())

def registrar_accion_agil(accion, id_partido, df_j, zona="N/A"):
    idx = st.session_state.jugador_activo['id']
    minuto = calcular_minuto_actual()
    df_e = obtener_datos(ws_eventos)
    nuevo_id_e = 1 if df_e.empty else int(df_e['id'].max()) + 1
    
    ws_eventos.append_row([
        nuevo_id_e, int(idx), accion, zona, minuto, id_partido, 
        st.session_state.tmp_pista, st.session_state.tmp_porteria
    ])
    
    # Limpiamos el estado tras guardar para estar listos para la siguiente jugada
    st.session_state.jugador_activo = None
    st.session_state.tmp_pista = ""
    st.session_state.tmp_porteria = ""
    st.session_state.ultimo_click = None
    st.toast(f"✅ {accion} registrada con éxito", icon="✅")

# --- 1. PLANTILLA ---
if menu == "1. Plantilla":
    st.subheader("Añadir Nuevo Jugador")
    col1, col2, col3 = st.columns(3)
    with col1: nombre = st.text_input("Nombre")
    with col2: dorsal = st.number_input("Dorsal", min_value=1, max_value=99)
    with col3: posicion = st.selectbox("Posición", ["Portero", "Extremo Izq", "Lateral Izq", "Central", "Lateral Der", "Extremo Der", "Pivote"])
    if st.button("Guardar Jugador"):
        df_j = obtener_datos(ws_jugadores)
        nuevo_id = 1 if df_j.empty else int(df_j['id'].max()) + 1
        ws_jugadores.append_row([nuevo_id, nombre, dorsal, posicion])
        st.success("Jugador guardado.")
        st.rerun()
    df_j = obtener_datos(ws_jugadores)
    if not df_j.empty:
        st.dataframe(df_j[['dorsal', 'nombre', 'posicion']].sort_values('dorsal'), use_container_width=True)

# --- 2. PARTIDOS ---
elif menu == "2. Partidos":
    st.subheader("Crear Nuevo Partido")
    col1, col2 = st.columns(2)
    with col1: fecha = st.date_input("Fecha", datetime.today())
    with col2: rival = st.text_input("Equipo Rival")
    if st.button("Crear Partido"):
        if rival:
            df_p = obtener_datos(ws_partidos)
            nuevo_id_p = 1 if df_p.empty else int(df_p['id'].max()) + 1
            ws_partidos.append_row([nuevo_id_p, str(fecha), rival])
            st.success("Partido creado.")
            st.rerun()
    df_p = obtener_datos(ws_partidos)
    if not df_p.empty: st.dataframe(df_p, use_container_width=True)

# --- 3. REGISTRO EN VIVO (MODO ÁGIL TIPO STEAZZI) ---
elif menu == "3. Registro en Vivo":
    df_j = obtener_datos(ws_jugadores)
    df_p = obtener_datos(ws_partidos)
    
    if df_j.empty or df_p.empty:
        st.warning("Faltan jugadores o crear un partido.")
    else:
        opciones_partidos = df_p['id'].astype(str) + " - vs " + df_p['rival']
        id_partido_actual = int(st.selectbox("📌 Partido actual:", opciones_partidos).split(" - ")[0])
        
        # Panel Superior: Reloj
        col_reloj1, col_reloj2, col_reloj3 = st.columns([1,1,2])
        with col_reloj1:
            if not st.session_state.reloj_activo:
                if st.button("▶️ Iniciar", use_container_width=True):
                    st.session_state.reloj_activo = True
                    st.session_state.inicio_tramo = time.time()
                    st.rerun()
            else:
                if st.button("⏸️ Pausar", use_container_width=True):
                    st.session_state.reloj_activo = False
                    st.session_state.tiempo_acumulado += (time.time() - st.session_state.inicio_tramo)
                    st.rerun()
        with col_reloj2:
            st.metric("Minuto", calcular_minuto_actual())

        st.divider()

        # Maquetación principal: Dorsales a la izquierda, Acción a la derecha
        col_dorsales, col_accion = st.columns([1, 4])
        
        # COLUMNA IZQUIERDA: DORSALES
        with col_dorsales:
            st.markdown("### Jug.")
            # Ordenamos por dorsal para que sea fácil de encontrar
            df_j_sorted = df_j.sort_values('dorsal')
            for _, row in df_j_sorted.iterrows():
                # Resaltar el botón si es el jugador activo
                tipo_btn = "primary" if st.session_state.jugador_activo is dict and st.session_state.jugador_activo.get('id') == row['id'] else "secondary"
                if st.button(f"{row['dorsal']} - {row['nombre'][:3]}", key=f"btn_{row['id']}", use_container_width=True, type=tipo_btn):
                    st.session_state.jugador_activo = row.to_dict()
                    st.session_state.tmp_pista = ""
                    st.session_state.tmp_porteria = ""
                    st.rerun()

        # COLUMNA DERECHA: PANTALLA DE ACCIÓN
        with col_accion:
            if st.session_state.jugador_activo is None:
                st.info("👈 Selecciona un jugador en el panel izquierdo para registrar una acción.")
            else:
                jugador = st.session_state.jugador_activo
                es_portero = jugador['posicion'] == 'Portero'
                
                st.markdown(f"#### Acción para: **{jugador['dorsal']} - {jugador['nombre']}** ({jugador['posicion']})")
                
                # Pestañas de categorías de acción
                tab_tiro, tab_ataque, tab_def, tab_sanc = st.tabs(["🎯 Tiro/Portería", "⚔️ Ataque", "🛡️ Defensa", "🟥 Sanciones"])
                
                # --- PESTAÑA TIROS E IMAGEN ---
                with tab_tiro:
                    col_mapa, col_botones = st.columns([2, 1])
                    
                    with col_mapa:
                        try:
                            # Al hacer clic en la imagen, el componente devuelve las coordenadas X,Y
                            click = streamlit_image_coordinates("plantilla.jpg", key="mapa_agil", width=350)
                            
                            # Lógica para detectar si ha tocado arriba (portería) o abajo (pista)
                            # Suponiendo que la imagen se divide por la mitad (ej. Y=400px en una img de 800px)
                            if click and click != st.session_state.ultimo_click:
                                st.session_state.ultimo_click = click
                                # Si el clic es en la mitad superior, es portería. Si es inferior, es pista.
                                # Ajusta el número 400 según la altura real de tu imagen (la mitad)
                                if click['y'] > 400: 
                                    st.session_state.tmp_pista = f"{click['x']},{click['y']}"
                                else:
                                    st.session_state.tmp_porteria = f"{click['x']},{click['y']}"
                                st.rerun()
                                
                            # Mostrar feedback de lo que ha tocado
                            if st.session_state.tmp_pista: st.caption("📍 Pista marcada")
                            if st.session_state.tmp_porteria: st.caption("🥅 Portería marcada")
                                
                        except FileNotFoundError:
                            st.warning("Falta 'plantilla.jpg'")
                    
                    with col_botones:
                        st.write("Resultado:")
                        # Si es portero, los botones cambian a Parada o Gol Encajado
                        if es_portero:
                            if st.button("👍 Parada", type="primary", use_container_width=True):
                                registrar_accion_agil("Parada", id_partido_actual, df_j)
                                st.rerun()
                            if st.button("👎 Gol Encajado", use_container_width=True):
                                registrar_accion_agil("Gol Encajado", id_partido_actual, df_j)
                                st.rerun()
                        else:
                            if st.button("👍 GOL", type="primary", use_container_width=True):
                                registrar_accion_agil("Gol", id_partido_actual, df_j)
                                st.rerun()
                            if st.button("👎 Fallo / Guardado", use_container_width=True):
                                registrar_accion_agil("Tiro Fallado", id_partido_actual, df_j)
                                st.rerun()

                # --- PESTAÑA ATAQUE ---
                with tab_ataque:
                    acciones_ataque = ["Pasos", "Doble regate", "Falta en ataque", "Pérdida de balón", "Falta", "Tiro bloqueado", "2 mins provocados", "7m provocado", "Duelo ganado"]
                    cols_a = st.columns(3)
                    for i, acc in enumerate(acciones_ataque):
                        if cols_a[i % 3].button(acc, key=f"ataque_{i}", use_container_width=True):
                            registrar_accion_agil(acc, id_partido_actual, df_j)
                            st.rerun()

                # --- PESTAÑA DEFENSA ---
                with tab_def:
                    acciones_def = ["7m en contra", "Duelo perdido", "Falta", "Tiro bloqueado", "Falta en ataque (Forzada)", "Intercepción"]
                    cols_d = st.columns(3)
                    for i, acc in enumerate(acciones_def):
                        if cols_d[i % 3].button(acc, key=f"def_{i}", use_container_width=True):
                            registrar_accion_agil(acc, id_partido_actual, df_j)
                            st.rerun()

                # --- PESTAÑA SANCIONES ---
                with tab_sanc:
                    col_s1, col_s2, col_s3 = st.columns(3)
                    if col_s1.button("🟨 Amarilla", use_container_width=True):
                        registrar_accion_agil("Amarilla", id_partido_actual, df_j)
                        st.rerun()
                    if col_s2.button("✌️ 2 Minutos", use_container_width=True):
                        registrar_accion_agil("Exclusión 2 Min", id_partido_actual, df_j)
                        st.rerun()
                    if col_s3.button("🟥 Roja", type="primary", use_container_width=True):
                        registrar_accion_agil("Tarjeta Roja", id_partido_actual, df_j)
                        st.rerun()

# --- 4. ESTADÍSTICAS ---
elif menu == "4. Estadísticas":
    df_j = obtener_datos(ws_jugadores)
    df_e = obtener_datos(ws_eventos)
    df_p = obtener_datos(ws_partidos)
    
    if not df_e.empty and not df_j.empty and not df_p.empty:
        filtro_sel = st.selectbox("Ver estadísticas de:", ["🏆 Acumulado (Toda la temporada)"] + list(df_p['id'].astype(str) + " - vs " + df_p['rival']))
        if "Acumulado" not in filtro_sel:
            id_filtro = int(filtro_sel.split(" - ")[0])
            if 'id_partido' in df_e.columns: df_e = df_e[df_e['id_partido'] == id_filtro]
        
        if not df_e.empty:
            df_merged = pd.merge(df_e, df_j, left_on='jugador_id', right_on='id', how='inner')
            
            st.subheader("🗺️ Mapa de Tiro Unificado")
            try:
                img_unificada = Image.open("plantilla.jpg").convert("RGBA")
                draw = ImageDraw.Draw(img_unificada)
                for index, row in df_merged.iterrows():
                    color = "red" if row['accion'] == 'Gol' else "blue" if row['accion'] in ['Tiro Fallado', 'Parada'] else None
                    if color:
                        if pd.notna(row.get('coord_pista')) and str(row.get('coord_pista')).strip() != "":
                            x_p, y_p = map(int, str(row['coord_pista']).split(','))
                            draw.ellipse((x_p-12, y_p-12, x_p+12, y_p+12), fill=color, outline="white")
                        if pd.notna(row.get('coord_porteria')) and str(row.get('coord_porteria')).strip() != "":
                            x_g, y_g = map(int, str(row['coord_porteria']).split(','))
                            draw.ellipse((x_g-12, y_g-12, x_g+12, y_g+12), fill=color, outline="black")
                st.image(img_unificada, use_container_width=True)
            except: pass

            st.subheader("Rendimiento del Equipo")
            resumen = df_merged.groupby(['dorsal', 'nombre', 'accion']).size().reset_index(name='total')
            df_pivot = resumen.pivot(index=['dorsal', 'nombre'], columns='accion', values='total').fillna(0).astype(int)
            st.dataframe(df_pivot, use_container_width=True)
