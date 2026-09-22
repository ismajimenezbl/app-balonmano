import streamlit as st
import sqlite3
import pandas as pd

# 1. Configuración de la Base de Datos Local
conn = sqlite3.connect('balonmano_local.db')
c = conn.cursor()

# Creación de tablas si no existen
c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
             (id INTEGER PRIMARY KEY, nombre TEXT, dorsal INTEGER, posicion TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS eventos 
             (id INTEGER PRIMARY KEY, jugador_id INTEGER, accion TEXT, zona_tiro TEXT, minuto INTEGER)''')
conn.commit()

# 2. Configuración de la Interfaz
st.set_page_config(page_title="Stats Balonmano", layout="wide")
st.title("📊 Panel de Estadísticas - Balonmano")

menu = st.sidebar.selectbox("Navegación", ["1. Plantilla", "2. Registro en Vivo", "3. Estadísticas"])

# --- SECCIÓN: PLANTILLA ---
if menu == "1. Plantilla":
    st.subheader("Añadir Nuevo Jugador")
    col1, col2, col3 = st.columns(3)
    with col1: nombre = st.text_input("Nombre")
    with col2: dorsal = st.number_input("Dorsal", min_value=1, max_value=99)
    with col3: posicion = st.selectbox("Posición", ["Portero", "Extremo Izq", "Lateral Izq", "Central", "Lateral Der", "Extremo Der", "Pivote"])
    
    if st.button("Guardar Jugador"):
        c.execute("INSERT INTO jugadores (nombre, dorsal, posicion) VALUES (?, ?, ?)", (nombre, dorsal, posicion))
        conn.commit()
        st.success(f"{nombre} añadido a la plantilla.")
        
    st.subheader("Plantilla Actual")
    df_jugadores = pd.read_sql_query("SELECT dorsal, nombre, posicion FROM jugadores ORDER BY dorsal", conn)
    st.dataframe(df_jugadores, use_container_width=True)

# --- SECCIÓN: REGISTRO EN VIVO ---
elif menu == "2. Registro en Vivo":
    st.subheader("Panel del Partido")
    jugadores = pd.read_sql_query("SELECT id, nombre, dorsal FROM jugadores", conn)
    
    if not jugadores.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            nombres_display = jugadores['dorsal'].astype(str) + " - " + jugadores['nombre']
            jugador_sel = st.selectbox("Selecciona Jugador", nombres_display)
            minuto = st.number_input("Minuto de juego", min_value=1, max_value=60)
        with col2:
            accion = st.radio("Acción", ["Gol", "Tiro Fallado", "Asistencia", "Pérdida", "Parada (Solo Porteros)", "Exclusión 2 Min"])
        with col3:
            zona = st.selectbox("Zona del campo (Opcional)", ["N/A", "6 metros", "9 metros", "Extremo", "Penalti", "Contraataque"])
            
        if st.button("Registrar Evento"):
            idx = jugadores[nombres_display == jugador_sel]['id'].values[0]
            c.execute("INSERT INTO eventos (jugador_id, accion, zona_tiro, minuto) VALUES (?, ?, ?, ?)", (int(idx), accion, zona, minuto))
            conn.commit()
            st.success("Acción registrada correctamente.")
    else:
        st.warning("Ve a la sección 'Plantilla' y añade jugadores antes de iniciar el partido.")

# --- SECCIÓN: ESTADÍSTICAS ---
elif menu == "3. Estadísticas":
    st.subheader("Rendimiento del Equipo")
    query = """
    SELECT j.dorsal, j.nombre, e.accion, COUNT(e.id) as total
    FROM eventos e
    JOIN jugadores j ON e.jugador_id = j.id
    GROUP BY j.nombre, e.accion
    """
    df = pd.read_sql_query(query, conn)
    
    if not df.empty:
        # Transformar los datos para tener las acciones en columnas
        df_pivot = df.pivot(index=['dorsal', 'nombre'], columns='accion', values='total').fillna(0).astype(int)
        
        # Calcular porcentaje de acierto si hay tiros
        if 'Gol' in df_pivot.columns and 'Tiro Fallado' in df_pivot.columns:
            total_tiros = df_pivot['Gol'] + df_pivot['Tiro Fallado']
            df_pivot['% Acierto Tiro'] = (df_pivot['Gol'] / total_tiros * 100).round(1).astype(str) + "%"
            
        st.dataframe(df_pivot, use_container_width=True)
        
        st.subheader("Goles por Zona de Tiro")
        query_zonas = "SELECT zona_tiro, COUNT(*) as Goles FROM eventos WHERE accion = 'Gol' AND zona_tiro != 'N/A' GROUP BY zona_tiro"
        df_zonas = pd.read_sql_query(query_zonas, conn)
        if not df_zonas.empty:
            st.bar_chart(df_zonas.set_index('zona_tiro'))
    else:
        st.info("Aún no hay estadísticas registradas.")