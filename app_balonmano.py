import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import time
from streamlit_image_coordinates import streamlit_image_coordinates
from PIL import Image, ImageDraw

st.set_page_config(page_title="Stats Balonmano", layout="wide")

# --- MEMORIA (SESSION STATE) ---
if 'reloj_activo' not in st.session_state: st.session_state.reloj_activo = False
if 'inicio_tramo' not in st.session_state: st.session_state.inicio_tramo = None
if 'tiempo_acumulado' not in st.session_state: st.session_state.tiempo_acumulado = 0.0

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

st.title("📊 Panel de Estadísticas Pro - Modo Ágil")
menu = st.sidebar.selectbox("Navegación", ["1. Plantilla", "2. Partidos", "3. Registro en Vivo", "4. Estadísticas"])

def registrar_accion_agil(accion, id_partido, zona="N/A"):
    idx = st.session_state.jugador_activo['id']
    minuto = calcular_minuto_actual()
    df_e = obtener_datos("eventos")
    nuevo_id_e = 1 if df_e.empty else int(df_e['id'].max()) + 1
    
    ws_eventos = sheet.worksheet("eventos")
    ws_eventos.append_row([
        nuevo_id_e, int(idx), accion, zona, minuto, id_partido, 
        st.session_state.tmp_pista, st.session_state.tmp_porteria
    ])
    
    st.cache_data.clear()
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
        df_j = obtener_datos("jugadores")
        nuevo_id = 1 if df_j.empty else int(df_j['id'].max()) + 1
        sheet.worksheet("jugadores").append_row([nuevo_id, nombre, dorsal, posicion])
        st.cache_data.clear()
        st.success("Jugador guardado.")
        st.rerun()
    df_j = obtener_datos("jugadores")
    if not df_j.empty: st.dataframe(df_j[['dorsal', 'nombre', 'posicion']].sort_values('dorsal'), use_container_width=True)

# --- 2. PARTIDOS ---
elif menu == "2. Partidos":
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

# --- 3. REGISTRO EN VIVO ---
elif menu == "3. Registro en Vivo":
    df_j = obtener_datos("jugadores")
    df_p = obtener_datos("partidos")
    
    if df_j.empty or df_p.empty:
        st.warning("Faltan jugadores o crear un partido.")
    else:
        opciones_partidos = df_p['id'].astype(str) + " - vs " + df_p['rival']
        id_partido_actual = int(st.selectbox("📌 Partido actual:", opciones_partidos).split(" - ")[0])
        
        # RELOJ
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

        # PANTALLA PRINCIPAL
        col_dorsales, col_accion = st.columns([1, 4])
        
        with col_dorsales:
            st.markdown("### Jug.")
            for _, row in df_j.sort_values('dorsal').iterrows():
                tipo_btn = "primary" if st.session_state.jugador_activo is dict and st.session_state.jugador_activo.get('id') == row['id'] else "secondary"
                if st.button(f"{row['dorsal']} - {row['nombre'][:3]}", key=f"btn_{row['id']}", use_container_width=True, type=tipo_btn):
                    st.session_state.jugador_activo = row.to_dict()
                    st.session_state.tmp_pista = ""
                    st.session_state.tmp_porteria = ""
                    st.rerun()

        with col_accion:
            if st.session_state.jugador_activo is None:
                st.info("👈 Selecciona un jugador en el panel izquierdo.")
            else:
                jugador = st.session_state.jugador_activo
                es_portero = jugador['posicion'] == 'Portero'
                
                st.markdown(f"#### Acción para: **{jugador['dorsal']} - {jugador['nombre']}**")
                tab_tiro, tab_ataque, tab_def, tab_sanc = st.tabs(["🎯 Tiro/Portería", "⚔️ Ataque", "🛡️ Defensa", "🟥 Sanciones"])
                
                with tab_tiro:
                    col_mapa, col_botones = st.columns([2, 1])
                    with col_mapa:
                        try:
                            # --- NUEVA LÓGICA DE COLOR DE SELECCIÓN ---
                            # Abrimos la imagen original
                            img_base = Image.open("plantilla.jpg").convert("RGBA")
                            # Creamos una capa transparente del mismo tamaño
                            capa_color = Image.new('RGBA', img_base.size, (255, 255, 255, 0))
                            draw_color = ImageDraw.Draw(capa_color)
                            
                            # Si hay clics guardados, dibujamos un resaltado amarillo
                            radio = 35 # Tamaño de la zona coloreada
                            color_resalte = (255, 215, 0, 160) # Amarillo Steazzi transparente
                            
                            if st.session_state.tmp_pista:
                                xp, yp = map(int, st.session_state.tmp_pista.split(','))
                                draw_color.ellipse((xp-radio, yp-radio, xp+radio, yp+radio), fill=color_resalte)
                            if st.session_state.tmp_porteria:
                                xg, yg = map(int, st.session_state.tmp_porteria.split(','))
                                draw_color.ellipse((xg-radio, yg-radio, xg+radio, yg+radio), fill=color_resalte)
                                
                            # Mezclamos la imagen original con la capa de colores
                            img_final = Image.alpha_composite(img_base, capa_color)
                            
                            # Mostramos la imagen interactiva que acabamos de colorear
                            click = streamlit_image_coordinates(img_final, key="mapa_agil", width=350)
                            
                            # Procesamos el nuevo clic
                            if click and click != st.session_state.ultimo_click:
                                st.session_state.ultimo_click = click
                                # Si toca por debajo de Y=400 es pista, si toca por encima es portería.
                                # (Ajusta este 400 si la mitad de tu foto está más arriba o abajo)
                                if click['y'] > 400: 
                                    st.session_state.tmp_pista = f"{click['x']},{click['y']}"
                                else:
                                    st.session_state.tmp_porteria = f"{click['x']},{click['y']}"
                                st.rerun()
                                
                        except FileNotFoundError:
                            st.warning("Falta 'plantilla.jpg'")
                    
                    with col_botones:
                        st.write("Resultado:")
                        if es_portero:
                            if st.button("👍 Parada", type="primary", use_container_width=True): registrar_accion_agil("Parada", id_partido_actual)
                            if st.button("👎 Gol Encajado", use_container_width=True): registrar_accion_agil("Gol Encajado", id_partido_actual)
                        else:
                            if st.button("👍 GOL", type="primary", use_container_width=True): registrar_accion_agil("Gol", id_partido_actual)
                            if st.button("👎 Fallo / Guardado", use_container_width=True): registrar_accion_agil("Tiro Fallado", id_partido_actual)

                # Resto de pestañas...
                with tab_ataque:
                    cols_a = st.columns(3)
                    for i, acc in enumerate(["Pasos", "Doble regate", "Falta en ataque", "Pérdida de balón", "Falta", "Tiro bloqueado", "2 mins provocados", "7m provocado", "Duelo ganado"]):
                        if cols_a[i % 3].button(acc, key=f"ataque_{i}", use_container_width=True): registrar_accion_agil(acc, id_partido_actual)

                with tab_def:
                    cols_d = st.columns(3)
                    for i, acc in enumerate(["7m en contra", "Duelo perdido", "Falta", "Tiro bloqueado", "Falta en ataque", "Intercepción"]):
                        if cols_d[i % 3].button(acc, key=f"def_{i}", use_container_width=True): registrar_accion_agil(acc, id_partido_actual)

                with tab_sanc:
                    col_s1, col_s2, col_s3 = st.columns(3)
                    if col_s1.button("🟨 Amarilla", use_container_width=True): registrar_accion_agil("Amarilla", id_partido_actual)
                    if col_s2.button("✌️ 2 Min", use_container_width=True): registrar_accion_agil("Exclusión 2 Min", id_partido_actual)
                    if col_s3.button("🟥 Roja", type="primary", use_container_width=True): registrar_accion_agil("Tarjeta Roja", id_partido_actual)

# --- 4. ESTADÍSTICAS ---
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
