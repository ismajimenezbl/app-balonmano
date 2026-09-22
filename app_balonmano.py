import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import time
import altair as alt

st.set_page_config(page_title="Stats Balonmano", layout="wide")

# --- MEMORIA DEL RELOJ (Session State) ---
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
    # Calculamos el minuto (Ej: el segundo 65 es el minuto 2)
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

st.title("📊 Panel de Estadísticas Pro - Balonmano")

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
    with col1: fecha = st.date_input("Fecha del partido", datetime.today())
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
        # Selección de partido
        opciones_partidos = df_p['id'].astype(str) + " - vs " + df_p['rival']
        partido_sel = st.selectbox("📌 Partido actual:", opciones_partidos)
        id_partido_actual = int(partido_sel.split(" - ")[0])
        
        st.divider()
        
        # CONTROLES DEL RELOJ
        st.subheader("⏱️ Cronómetro del Partido")
        col_btn1, col_btn2, col_btn3, col_metric = st.columns(4)
        
        with col_btn1:
            if not st.session_state.reloj_activo:
                if st.button("▶️ Iniciar / Reanudar", use_container_width=True):
                    st.session_state.reloj_activo = True
                    st.session_state.inicio_tramo = time.time()
                    st.rerun()
            else:
                if st.button("⏸️ Tiempo Muerto (Pausar)", use_container_width=True):
                    st.session_state.reloj_activo = False
                    st.session_state.tiempo_acumulado += (time.time() - st.session_state.inicio_tramo)
                    st.rerun()
        
        with col_btn2:
            if st.button("⏹️ Fin 1ª Parte / Reset", use_container_width=True):
                st.session_state.reloj_activo = False
                st.session_state.tiempo_acumulado = 0.0
                st.rerun()

        with col_metric:
            min_actual = calcular_minuto_actual()
            estado = "EN JUEGO 🟢" if st.session_state.reloj_activo else "PAUSADO 🔴"
            st.metric(label=f"Estado: {estado}", value=f"Minuto {min_actual}")

        st.divider()
        
        # REGISTRO DE ACCIONES (El minuto se pone solo)
        col1, col2, col3 = st.columns(3)
        with col1:
            nombres_display = df_j['dorsal'].astype(str) + " - " + df_j['nombre']
            jugador_sel = st.selectbox("Jugador", nombres_display)
            # El campo minuto se rellena automáticamente con el reloj
            minuto = st.number_input("Minuto", min_value=1, max_value=120, value=min_actual)
        with col2:
            accion = st.radio("Acción", ["Gol", "Tiro Fallado", "Asistencia", "Pérdida", "Parada (Porteros)", "Exclusión 2 Min"])
        with col3:
            zona = st.selectbox("Zona", ["N/A", "6 metros", "9 metros", "Extremo", "Penalti", "Contraataque"])
            
        if st.button("Registrar Evento", type="primary"):
            idx = df_j[nombres_display == jugador_sel]['id'].values[0]
            df_e = obtener_datos(ws_eventos)
            nuevo_id_evento = 1 if df_e.empty else int(df_e['id'].max()) + 1
            ws_eventos.append_row([nuevo_id_evento, int(idx), accion, zona, minuto, id_partido_actual])
            st.success(f"¡{accion} registrado en el minuto {minuto}!")

# --- 4. ESTADÍSTICAS ---
elif menu == "4. Estadísticas":
    df_j = obtener_datos(ws_jugadores)
    df_e = obtener_datos(ws_eventos)
    df_p = obtener_datos(ws_partidos)
    
    if not df_e.empty and not df_j.empty and not df_p.empty:
        opciones_filtro = ["🏆 Acumulado (Toda la temporada)"] + list(df_p['id'].astype(str) + " - vs " + df_p['rival'])
        filtro_sel = st.selectbox("Ver estadísticas de:", opciones_filtro)
        
        if "Acumulado" not in filtro_sel:
            id_filtro = int(filtro_sel.split(" - ")[0])
            if 'id_partido' in df_e.columns:
                df_e = df_e[df_e['id_partido'] == id_filtro]
        
        if df_e.empty:
            st.info("No hay eventos registrados.")
        else:
            df_merged = pd.merge(df_e, df_j, left_on='jugador_id', right_on='id', how='inner')
            
            # --- CRONOLOGÍA DEL PARTIDO ---
            if "Acumulado" not in filtro_sel:
                st.subheader("📈 Cronología del Partido")
                
                # Filtramos solo acciones relevantes para la gráfica temporal
                df_timeline = df_merged[df_merged['accion'].isin(['Gol', 'Parada (Porteros)', 'Exclusión 2 Min'])]
                
                if not df_timeline.empty:
                    # Creamos un gráfico de dispersión con Altair
                    c = alt.Chart(df_timeline).mark_circle(size=150).encode(
                        x=alt.X('minuto:Q', title='Minuto del partido', scale=alt.Scale(domain=[0, 60])),
                        y=alt.Y('accion:N', title=''),
                        color=alt.Color('accion:N', legend=alt.Legend(title="Acción")),
                        tooltip=['minuto', 'nombre', 'accion', 'zona_tiro']
                    ).interactive().properties(height=200)
                    
                    st.altair_chart(c, use_container_width=True)

            # --- TABLA DE ESTADÍSTICAS ---
            st.subheader("Rendimiento del Equipo")
            resumen = df_merged.groupby(['dorsal', 'nombre', 'accion']).size().reset_index(name='total')
            df_pivot = resumen.pivot(index=['dorsal', 'nombre'], columns='accion', values='total').fillna(0).astype(int)
            if 'Gol' in df_pivot.columns and 'Tiro Fallado' in df_pivot.columns:
                total_tiros = df_pivot['Gol'] + df_pivot['Tiro Fallado']
                df_pivot['% Acierto'] = (df_pivot['Gol'] / total_tiros * 100).round(1).astype(str) + "%"
            st.dataframe(df_pivot, use_container_width=True)
