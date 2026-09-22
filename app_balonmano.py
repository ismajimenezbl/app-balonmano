import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

st.set_page_config(page_title="Stats Balonmano", layout="wide")

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
    ws_partidos = sheet.worksheet("partidos") # Nueva pestaña
except Exception as e:
    st.error(f"Error conectando a Google Sheets: {e}")
    st.stop()

st.title("📊 Panel de Estadísticas Pro - Balonmano")

menu = st.sidebar.selectbox("Navegación", ["1. Plantilla", "2. Partidos", "3. Registro en Vivo", "4. Estadísticas"])

# --- FUNCIONES AUXILIARES ---
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

# --- 2. PARTIDOS (NUEVA SECCIÓN) ---
elif menu == "2. Partidos":
    st.subheader("Crear Nuevo Partido")
    col1, col2 = st.columns(2)
    with col1: fecha = st.date_input("Fecha del partido", datetime.today())
    with col2: rival = st.text_input("Equipo Rival")
    
    if st.button("Crear Partido"):
        if rival:
            df_p = obtener_datos(ws_partidos)
            nuevo_id_p = 1 if df_p.empty else int(df_p['id'].max()) + 1
            ws_partidos.append_row([nuevo_id_p, str(fecha), rival])
            st.success(f"Partido contra {rival} creado correctamente.")
            st.rerun()
        else:
            st.warning("Escribe el nombre del rival.")
            
    st.subheader("Historial de Partidos")
    df_p = obtener_datos(ws_partidos)
    if not df_p.empty:
        st.dataframe(df_p, use_container_width=True)
    else:
        st.info("No has creado ningún partido aún.")

# --- 3. REGISTRO EN VIVO (ACTUALIZADO) ---
elif menu == "3. Registro en Vivo":
    st.subheader("Panel del Partido")
    df_j = obtener_datos(ws_jugadores)
    df_p = obtener_datos(ws_partidos)
    
    if df_j.empty or df_p.empty:
        st.warning("Asegúrate de tener al menos 1 jugador en la plantilla y 1 partido creado.")
    else:
        # Selector de partido
        opciones_partidos = df_p['id'].astype(str) + " - vs " + df_p['rival'] + " (" + df_p['fecha'] + ")"
        partido_sel = st.selectbox("📌 Selecciona el partido actual:", opciones_partidos)
        id_partido_actual = int(partido_sel.split(" - ")[0])
        
        st.divider()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            nombres_display = df_j['dorsal'].astype(str) + " - " + df_j['nombre']
            jugador_sel = st.selectbox("Jugador", nombres_display)
            minuto = st.number_input("Minuto", min_value=1, max_value=60)
        with col2:
            accion = st.radio("Acción", ["Gol", "Tiro Fallado", "Asistencia", "Pérdida", "Parada (Porteros)", "Exclusión 2 Min"])
        with col3:
            zona = st.selectbox("Zona", ["N/A", "6 metros", "9 metros", "Extremo", "Penalti", "Contraataque"])
            
        if st.button("Registrar Evento"):
            idx = df_j[nombres_display == jugador_sel]['id'].values[0]
            df_e = obtener_datos(ws_eventos)
            nuevo_id_evento = 1 if df_e.empty else int(df_e['id'].max()) + 1
            
            # Guardamos el evento con el id del partido al final
            ws_eventos.append_row([nuevo_id_evento, int(idx), accion, zona, minuto, id_partido_actual])
            st.success("¡Acción registrada en el partido seleccionado!")

# --- 4. ESTADÍSTICAS (ACTUALIZADO) ---
elif menu == "4. Estadísticas":
    df_j = obtener_datos(ws_jugadores)
    df_e = obtener_datos(ws_eventos)
    df_p = obtener_datos(ws_partidos)
    
    if not df_e.empty and not df_j.empty and not df_p.empty:
        # Filtro Global o Por Partido
        opciones_filtro = ["🏆 Acumulado (Toda la temporada)"] + list(df_p['id'].astype(str) + " - vs " + df_p['rival'])
        filtro_sel = st.selectbox("Ver estadísticas de:", opciones_filtro)
        
        # Aplicar el filtro si no es "Acumulado"
        if "Acumulado" not in filtro_sel:
            id_filtro = int(filtro_sel.split(" - ")[0])
            # Comprobamos si la columna id_partido existe por si hay eventos viejos sin ella
            if 'id_partido' in df_e.columns:
                df_e = df_e[df_e['id_partido'] == id_filtro]
        
        if df_e.empty:
            st.info("No hay eventos registrados para este filtro.")
        else:
            st.subheader("Rendimiento del Equipo")
            df_merged = pd.merge(df_e, df_j, left_on='jugador_id', right_on='id', how='inner')
            resumen = df_merged.groupby(['dorsal', 'nombre', 'accion']).size().reset_index(name='total')
            df_pivot = resumen.pivot(index=['dorsal', 'nombre'], columns='accion', values='total').fillna(0).astype(int)
            
            if 'Gol' in df_pivot.columns and 'Tiro Fallado' in df_pivot.columns:
                total_tiros = df_pivot['Gol'] + df_pivot['Tiro Fallado']
                df_pivot['% Acierto'] = (df_pivot['Gol'] / total_tiros * 100).round(1).astype(str) + "%"
                
            st.dataframe(df_pivot, use_container_width=True)
    else:
        st.info("Aún faltan datos (jugadores, partidos o eventos) para mostrar estadísticas.")
