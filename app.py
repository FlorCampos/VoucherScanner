import streamlit as st
from google import genai
from PIL import Image
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. CONFIGURACIÓN DE ESTADO (SESSION STATE) ---
# Esto sirve para que la cámara se limpie correctamente
if 'contador_escaneo' not in st.session_state:
    st.session_state.contador_escaneo = 0
if 'mostrar_camara' not in st.session_state:
    st.session_state.mostrar_camara = True

# --- 1. CONFIGURACIÓN DE LA IA (GEMINI) ---
#SECRETS1
# Reemplaza con tu API Key real
API_KEY = st.secrets["GEMINI_KEY"]
client = genai.Client(api_key=API_KEY)

# --- 2. FUNCIÓN PARA GUARDAR EN GOOGLE SHEETS ---
def guardar_en_google_sheets(datos_json):
    try:
        # Definir el alcance y cargar credenciales
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        #SECRETS2
        creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        gc = gspread.authorize(creds)
        
        # Abrir el archivo y la primera pestaña (índice 0)
        # Asegúrate de que el nombre coincida con tu Google Drive
        # sh = gc.open("2.- MONTHLY BUDGET").get_worksheet(1) 
        sh = gc.open("2.- MONTHLY BUDGET").worksheet("Micro-expenses-2026")
        
        # Preparamos la fila usando las llaves exactas que pediremos a la IA
        fila = [
            str(datos_json.get("comercio", "N/A")),
            str(datos_json.get("fecha", "N/A")),
            float(datos_json.get("monto_total", 0)),
            float(datos_json.get("iva", 0)),
            str(datos_json.get("categoria_sugerida", "Otros"))
        ]
        
        sh.append_row(fila)
        return True
    except Exception as e:
        st.error(f"Error al guardar en Sheets: {e}")
        return False

# --- 3. INTERFAZ DE USUARIO (STREAMLIT) ---
st.set_page_config(page_title="Scanner de Vouchers Pro", page_icon="📸")
st.title("📸 Scanner de Vouchers Pro")
st.write("Captura o sube tu voucher para guardarlo en tu presupuesto.")

# Pestañas para elegir método de entrada
tab1, tab2 = st.tabs(["📸 Cámara", "📁 Subir Archivo"])

with tab1:
    placeholder_camara = st.empty()
    if st.session_state.mostrar_camara:
        # La 'key' cambia con cada escaneo para forzar la limpieza
        foto_camara = placeholder_camara.camera_input(
            "Toma la foto", 
            key=f"camara_{st.session_state.contador_escaneo}"
        )
    else:
        foto_camara = None
with tab2:
    foto_archivo = st.file_uploader("Selecciona una imagen", type=['jpg', 'jpeg', 'png'])

# Unificamos la entrada de imagen
foto = foto_camara if foto_camara else foto_archivo

# --- 4. LÓGICA DE PROCESAMIENTO ---
if foto:
    img = Image.open(foto)
    st.image(img, caption="Imagen lista para procesar", use_container_width=True)
    
    if st.button("🚀 Procesar y Guardar"):
        with st.spinner("La IA está leyendo el voucher..."):
            # Prompt estricto para que la IA no invente nombres de etiquetas
            prompt = """
            Analiza esta imagen de un voucher/ticket y extrae la información.
            Responde ÚNICAMENTE en formato JSON puro con estas llaves:
            {
              "comercio": "nombre del lugar",
              "fecha": "DD/MM/AAAA",
              "monto_total": 0.0,
              "iva": 0.0,
              "categoria_sugerida": "ej: Comida, Transporte, etc."
            }
            """
            
            try:
                # Llamada a Gemini 2.5 Flash
                response = client.models.generate_content(
                    model="gemini-2.5-flash", 
                    contents=[prompt, img]
                )
                
                # Limpiar la respuesta y convertir a diccionario
                texto_json = response.text.replace('```json', '').replace('```', '').strip()
                datos = json.loads(texto_json)
                
                # Mostrar resultado en pantalla
                st.json(datos)
                
                # Intentar guardar en Google Sheets
                if guardar_en_google_sheets(datos):
                    st.success("✅ ¡Datos guardados correctamente en Google Sheets!")
                    st.balloons()
                # Botón para limpiar todo y empezar de nuevo
                    if st.button("🔄 Escanear otro voucher"):
                        st.session_state.contador_escaneo += 1
                        st.rerun()
                    
            except Exception as e:
                st.error(f"Error procesando el voucher: {e}")