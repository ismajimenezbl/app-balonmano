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

# --- MEMORIA DEL RELOJ ---
if 'reloj_activo' not in st.session_state:
    st.session_state.reloj_activo = False
if 'inicio_tramo' not in st.session_state:
    st.session_state.inicio_tramo = None
if 'tiempo_acumulado' not in st.session_state:
    st.session_state.tiempo_acumulado = 0.0

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

st.title("📊 Panel de Estadísticas Pro - Mapas de Tiro")
menu = st.sidebar.selectbox("Navegación", ["1. Plantilla", "2. Partidos", "3. Registro en Vivo", "4. Estadísticas"])

def obtener_datos(worksheet):
    records = worksheet.get_all_records()
    return pd.DataFrame(records)

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
    if not df_p.empty:
        st.dataframe(df_p, use_container_width=True)

# --- 3. REGISTRO EN VIVO ---
elif menu == "3. Registro en Vivo":
    df_j = obtener_datos(ws_jugadores)
    df_p = obtener_datos(ws_partidos)
    
    if df_j.empty or df_p.empty:
        st.warning("Faltan jugadores o crear un partido.")
    else:
        opciones_partidos = df_p['id'].astype(str) + " - vs " + df_p['rival']
        partido_sel = st.selectbox("📌 Partido actual:", opciones_partidos)
        id_partido_actual = int(partido_sel.split(" - ")[0])
        st.divider()
        
        col_btn1, col_btn2, col_btn3, col_metric = st.columns(4)
        with col_btn1:
            if not st.session_state.reloj_activo:
                if st.button("▶️ Iniciar / Reanudar", use_container_width=True):
                    st.session_state.reloj_activo = True
                    st.session_state.inicio_tramo = time.time()
                    st.rerun()
            else:
                if st.button("⏸️ Pausar", use_container_width=True):
                    st.session_state.reloj_activo = False
                    st.session_state.tiempo_acumulado += (time.time() - st.session_state.inicio_tramo)
                    st.rerun()
        with col_btn2:
            if st.button("⏹️ Reset Reloj", use_container_width=True):
                st.session_state.reloj_activo = False
                st.session_state.tiempo_acumulado = 0.0
                st.rerun()
        with col_metric:
            min_actual = calcular_minuto_actual()
            st.metric(label="Minuto", value=f"{min_actual}")

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            nombres_display = df_j['dorsal'].astype(str) + " - " + df_j['nombre']
            jugador_sel = st.selectbox("Jugador", nombres_display)
            accion = st.radio("Acción", ["Gol", "Tiro Fallado", "Asistencia", "Pérdida", "Parada (Porteros)", "Exclusión"])
            minuto = st.number_input("Minuto", min_value=1, max_value=120, value=min_actual)
            zona = "N/A" # Lo dejamos por defecto
            
        coord_pista_str, coord_porteria_str = "", ""
        
        if accion in ["Gol", "Tiro Fallado"]:
            st.write("---")
            st.write("📍 **Toca en las imágenes:**")
            col_img1, col_img2 = st.columns(2)
            
            try:
                with col_img1:
                    st.write("1️⃣ ¿Desde dónde tira? (Pista)")
                    coord_p = streamlit_image_coordinates("plantilla.jpg", key="pista", width=350)
                    if coord_p:
                        coord_pista_str = f"{coord_p['x']},{coord_p['y']}"
                        st.caption(f"Pista guardada")
                
                with col_img2:
                    st.write("2️⃣ ¿A dónde va? (Portería)")
                    coord_g = streamlit_image_coordinates("plantilla.jpg", key="porteria", width=350)
                    if coord_g:
                        coord_porteria_str = f"{coord_g['x']},{coord_g['y']}"
                        st.caption(f"Portería guardada")
            except FileNotFoundError:
                st.warning("⚠️ No se encontró la imagen 'plantilla.jpg' en GitHub.")

        if st.button("💾 Registrar Evento", type="primary", use_container_width=True):
            idx = df_j[nombres_display == jugador_sel]['id'].values[0]
            df_e = obtener_datos(ws_eventos)
            nuevo_id_e = 1 if df_e.empty else int(df_e['id'].max()) + 1
            ws_eventos.append_row([nuevo_id_e, int(idx), accion, zona, minuto, id_partido_actual, coord_pista_str, coord_porteria_str])
            st.success("¡Guardado correctamente!")

# --- 4. ESTADÍSTICAS ---
elif menu == "4. Estadísticas":
    df_j = obtener_datos(ws_jugadores)
    df_e = obtener_datos(ws_eventos)
    df_p = obtener_datos(ws_partidos)
    
    if not df_e.empty and not df_j.empty and not df_p.empty:
        filtro_sel = st.selectbox("Ver estadísticas de:", ["🏆 Acumulado (Toda la temporada)"] + list(df_p['id'].astype(str) + " - vs " + df_p['rival']))
        if "Acumulado" not in filtro_sel:
            id_filtro = int(filtro_sel.split(" - ")[0])
            if 'id_partido' in df_e.columns:
                df_e = df_e[df_e['id_partido'] == id_filtro]
        
        if not df_e.empty:
            df_merged = pd.merge(df_e, df_j, left_on='jugador_id', right_on='id', how='inner')
            
            # --- MAPA DE TIRO UNIFICADO ---
            st.subheader("🗺️ Mapa de Tiro Unificado")
            st.write("🔴 = Goles | 🔵 = Tiros Fallados")
            
            try:
                # Cargamos la imagen una sola vez
                img_unificada = Image.open("plantilla.jpg").convert("RGBA")
                draw = ImageDraw.Draw(img_unificada)
                
                for index, row in df_merged.iterrows():
                    color = "red" if row['accion'] == 'Gol' else "blue" if row['accion'] == 'Tiro Fallado' else None
                    
                    if color:
                        # Dibujar punto de la pista (origen)
                        if pd.notna(row.get('coord_pista')) and str(row.get('coord_pista')).strip() != "":
                            x_p, y_p = map(int, str(row['coord_pista']).split(','))
                            draw.ellipse((x_p-12, y_p-12, x_p+12, y_p+12), fill=color, outline="white")
                            
                        # Dibujar punto de la portería (destino)
                        if pd.notna(row.get('coord_porteria')) and str(row.get('coord_porteria')).strip() != "":
                            x_g, y_g = map(int, str(row['coord_porteria']).split(','))
                            draw.ellipse((x_g-12, y_g-12, x_g+12, y_g+12), fill=color, outline="black")
                
                # Mostramos la imagen gigante con todos los puntos
                st.image(img_unificada, caption="Heatmap de Tiros (Origen y Destino)", use_container_width=True)
            except FileNotFoundError:
                st.info("Sube plantilla.jpg para ver el mapa unificado.")

            # --- TABLA ESTADÍSTICAS ---
            st.subheader("Rendimiento del Equipo")
            resumen = df_merged.groupby(['dorsal', 'nombre', 'accion']).size().reset_index(name='total')
            df_pivot = resumen.pivot(index=['dorsal', 'nombre'], columns='accion', values='total').fillna(0).astype(int)
            if 'Gol' in df_pivot.columns and 'Tiro Fallado' in df_pivot.columns:
                total_tiros = df_pivot['Gol'] + df_pivot['Tiro Fallado']
                df_pivot['% Acierto'] = (df_pivot['Gol'] / total_tiros * 100).round(1).astype(str) + "%"
            st.dataframe(df_pivot, use_container_width=True)
