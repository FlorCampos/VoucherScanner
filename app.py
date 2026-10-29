import json
import logging

import gspread
import streamlit as st
from PIL import Image
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from gspread.exceptions import APIError as GspreadAPIError
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voucher_scanner")

GEMINI_MODEL = "gemini-2.5-flash"
SHEET_NAME = "2.- MONTHLY BUDGET"
WORKSHEET_NAME = "Micro-expenses-2026"
SHEETS_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

PROMPT = (
    "Analiza esta imagen de un voucher/ticket de compra y extrae la "
    "información solicitada en el esquema. Si un campo no aparece en la "
    "imagen, usa tu mejor estimación o un valor por defecto razonable."
)


class Voucher(BaseModel):
    comercio: str = Field(description="Nombre del comercio o establecimiento")
    fecha: str = Field(description="Fecha del voucher en formato DD/MM/AAAA")
    mes_texto: str = Field(description="Nombre del mes en inglés, ej: January")
    monto_total: float = Field(description="Monto total pagado")
    iva: float = Field(default=0.0, description="Monto de IVA/impuesto, si aplica")
    categoria_sugerida: str = Field(
        description="Categoría de gasto sugerida, ej: Comida, Transporte, Otros"
    )


def get_gemini_client() -> genai.Client:
    return genai.Client(api_key=st.secrets["GEMINI_KEY"])


def get_sheets_client() -> gspread.Client:
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    return gspread.service_account_from_dict(creds_dict, scopes=SHEETS_SCOPES)


def extraer_datos_voucher(client: genai.Client, img: Image.Image) -> Voucher:
    """Llama a Gemini pidiendo un structured output validado contra el esquema Voucher."""
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[PROMPT, img],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Voucher,
        ),
    )
    if response.parsed is None:
        raise ValueError("La IA no devolvió un JSON válido según el esquema esperado.")
    return response.parsed


def guardar_en_google_sheets(gc: gspread.Client, voucher: Voucher) -> None:
    sh = gc.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
    fila = [
        voucher.comercio,
        voucher.fecha,
        voucher.mes_texto,
        voucher.monto_total,
        voucher.iva,
        voucher.categoria_sugerida,
    ]
    sh.append_row(fila)


def main() -> None:
    st.set_page_config(page_title="Scanner de Vouchers Pro", page_icon="📸")
    st.title("📸 Scanner de Vouchers Pro")
    st.write("Captura o sube tu voucher para guardarlo en tu presupuesto.")

    if "contador_escaneo" not in st.session_state:
        st.session_state.contador_escaneo = 0

    tab1, tab2 = st.tabs(["📸 Cámara", "📁 Subir Archivo"])
    with tab1:
        foto_camara = st.camera_input(
            "Toma la foto", key=f"camara_{st.session_state.contador_escaneo}"
        )
    with tab2:
        foto_archivo = st.file_uploader("Selecciona una imagen", type=["jpg", "jpeg", "png"])

    foto = foto_camara or foto_archivo
    if not foto:
        return

    img = Image.open(foto)
    st.image(img, caption="Imagen lista para procesar", use_container_width=True)

    if not st.button("🚀 Procesar y Guardar"):
        return

    with st.spinner("La IA está leyendo el voucher..."):
        try:
            gemini_client = get_gemini_client()
            voucher = extraer_datos_voucher(gemini_client, img)
        except genai_errors.APIError as exc:
            logger.exception("Fallo en la llamada a la API de Gemini")
            st.error(f"⚠️ Error al comunicarse con Gemini: {exc}")
            return
        except ValueError as exc:
            logger.exception("Respuesta de Gemini fuera de esquema")
            st.error(f"⚠️ {exc} Intenta con una foto más clara o nítida.")
            return

        st.json(voucher.model_dump())

        try:
            sheets_client = get_sheets_client()
            guardar_en_google_sheets(sheets_client, voucher)
        except SpreadsheetNotFound:
            logger.exception("Spreadsheet no encontrado")
            st.error(
                f"⚠️ No se encontró la hoja '{SHEET_NAME}'. Verifica el nombre "
                "y que el service account tenga acceso."
            )
            return
        except WorksheetNotFound:
            logger.exception("Worksheet no encontrado")
            st.error(f"⚠️ No se encontró la pestaña '{WORKSHEET_NAME}' dentro de '{SHEET_NAME}'.")
            return
        except GspreadAPIError as exc:
            logger.exception("Fallo en la API de Google Sheets")
            st.error(f"⚠️ Error al guardar en Google Sheets: {exc}")
            return
        except (json.JSONDecodeError, KeyError):
            logger.exception("Credenciales de Google mal configuradas en st.secrets")
            st.error(
                "⚠️ Las credenciales de Google Sheets no están configuradas "
                "correctamente en los secretos de la app."
            )
            return

        st.success("✅ ¡Datos guardados correctamente en Google Sheets!")
        st.balloons()
        if st.button("🔄 Escanear otro voucher"):
            st.session_state.contador_escaneo += 1
            st.rerun()


if __name__ == "__main__":
    main()
