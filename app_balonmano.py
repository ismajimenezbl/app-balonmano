import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

st.set_page_config(page_title="Stats Balonmano", layout="wide")

# 1. Conexión a Google Sheets
@st.cache_resource
def conectar_gsheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Carga el secreto que pusimos en Streamlit
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # ATENCIÓN: Este debe ser el nombre exacto de tu archivo de Google Sheets
    return client.open("Datos App Balonmano")

try:
    sheet = conectar_gsheets()
    ws_jugadores = sheet.worksheet("jugadores")
    ws_eventos = sheet.worksheet("eventos")
except Exception as e:
    st.error(f"Error conectando a Google Sheets. Comprueba que el documento se llama exactamente igual y que lo compartiste con el robot. Detalle: {e}")
    st.stop()

st.title("📊 Panel de Estadísticas - Balonmano (En la Nube)")

menu = st.sidebar.selectbox("Navegación", ["1. Plantilla", "2. Registro en Vivo", "3. Estadísticas"])

# Funciones auxiliares para descargar datos del Excel
def obtener_jugadores():
    records = ws_jugadores.get_all_records()
    return pd.DataFrame(records)

def obtener_eventos():
    records = ws_eventos.get_all_records()
    return pd.DataFrame(records)

# --- SECCIÓN: PLANTILLA ---
if menu == "1. Plantilla":
    st.subheader("Añadir Nuevo Jugador")
    col1, col2, col3 = st.columns(3)
    with col1: nombre = st.text_input("Nombre")
    with col2: dorsal = st.number_input("Dorsal", min_value=1, max_value=99)
    with col3: posicion = st.selectbox("Posición", ["Portero", "Extremo Izq", "Lateral Izq", "Central", "Lateral Der", "Extremo Der", "Pivote"])
    
    if st.button("Guardar Jugador"):
        df_j = obtener_jugadores()
        nuevo_id = 1 if df_j.empty else int(df_j['id'].max()) + 1
        ws_jugadores.append_row([nuevo_id, nombre, dorsal, posicion])
        st.success(f"{nombre} añadido a la plantilla en la nube.")
        st.rerun()
        
    st.subheader("Plantilla Actual")
    df_j = obtener_jugadores()
    if not df_j.empty:
        st.dataframe(df_j[['dorsal', 'nombre', 'posicion']].sort_values('dorsal'), use_container_width=True)
    else:
        st.info("No hay jugadores registrados. Añade uno arriba.")

# --- SECCIÓN: REGISTRO EN VIVO ---
elif menu == "2. Registro en Vivo":
    st.subheader("Panel del Partido")
    df_j = obtener_jugadores()
    
    if not df_j.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            nombres_display = df_j['dorsal'].astype(str) + " - " + df_j['nombre']
            jugador_sel = st.selectbox("Selecciona Jugador", nombres_display)
            minuto = st.number_input("Minuto de juego", min_value=1, max_value=60)
        with col2:
            accion = st.radio("Acción", ["Gol", "Tiro Fallado", "Asistencia", "Pérdida", "Parada (Solo Porteros)", "Exclusión 2 Min"])
        with col3:
            zona = st.selectbox("Zona del campo", ["N/A", "6 metros", "9 metros", "Extremo", "Penalti", "Contraataque"])
            
        if st.button("Registrar Evento"):
            idx = df_j[nombres_display == jugador_sel]['id'].values[0]
            df_e = obtener_eventos()
            nuevo_id_evento = 1 if df_e.empty else int(df_e['id'].max()) + 1
            
            ws_eventos.append_row([nuevo_id_evento, int(idx), accion, zona, minuto])
            st.success("¡Acción registrada correctamente y guardada en tu Excel!")
    else:
        st.warning("Ve a la sección 'Plantilla' y añade jugadores antes de iniciar el partido.")

# --- SECCIÓN: ESTADÍSTICAS ---
elif menu == "3. Estadísticas":
    st.subheader("Rendimiento del Equipo")
    df_j = obtener_jugadores()
    df_e = obtener_eventos()
    
    if not df_e.empty and not df_j.empty:
        df_merged = pd.merge(df_e, df_j, left_on='jugador_id', right_on='id', how='inner')
        
        if not df_merged.empty:
            resumen = df_merged.groupby(['dorsal', 'nombre', 'accion']).size().reset_index(name='total')
            df_pivot = resumen.pivot(index=['dorsal', 'nombre'], columns='accion', values='total').fillna(0).astype(int)
            
            if 'Gol' in df_pivot.columns and 'Tiro Fallado' in df_pivot.columns:
                total_tiros = df_pivot['Gol'] + df_pivot['Tiro Fallado']
                df_pivot['% Acierto Tiro'] = (df_pivot['Gol'] / total_tiros * 100).round(1).astype(str) + "%"
                
            st.dataframe(df_pivot, use_container_width=True)
            
            st.subheader("Goles por Zona de Tiro")
            goles_zona = df_merged[(df_merged['accion'] == 'Gol') & (df_merged['zona_tiro'] != 'N/A')]
            if not goles_zona.empty:
                conteo_zonas = goles_zona['zona_tiro'].value_counts()
                st.bar_chart(conteo_zonas)
        else:
            st.info("No hay datos cruzados aún.")
    else:
        st.info("Aún no hay estadísticas registradas.")
