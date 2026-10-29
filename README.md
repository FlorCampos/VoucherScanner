# 📸 Voucher Scanner

Aplicación en Streamlit que captura o sube una foto de un voucher/ticket, extrae sus datos con **Gemini 2.5 Flash** (visión + structured outputs) y los registra automáticamente en una hoja de **Google Sheets**.

## Arquitectura (Fase 1)

```
Imagen (cámara / upload)
        │
        ▼
Gemini 2.5 Flash  ──  response_schema = Voucher (Pydantic)
        │
        ▼
Voucher (objeto validado)
        │
        ▼
Google Sheets (gspread + google-auth)
```

- **OCR/Extracción**: `google-genai`, modelo `gemini-2.5-flash`, con `response_mime_type="application/json"` y `response_schema=Voucher`. El modelo está forzado a devolver un JSON que cumple el esquema Pydantic `Voucher`; si no lo cumple, `response.parsed` es `None` y la app lo trata como un error explícito (no se parsea texto a mano).
- **Persistencia**: `gspread.service_account_from_dict(...)`, autenticado con `google-auth` (no `oauth2client`, que está deprecado).
- **Secretos**: gestionados exclusivamente vía `st.secrets` (Streamlit secrets), nunca archivos en disco.

## Setup local

1. Crear y activar un entorno virtual:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   # para correr tests:
   pip install -r requirements-dev.txt
   ```
3. Crear `.streamlit/secrets.toml` (este archivo está en `.gitignore`, nunca se commitea):
   ```toml
   GEMINI_KEY = "tu-api-key-de-gemini"
   GOOGLE_CREDENTIALS = '''{"type": "service_account", "project_id": "...", ...}'''
   ```
   - `GEMINI_KEY`: API key de [Google AI Studio](https://aistudio.google.com/).
   - `GOOGLE_CREDENTIALS`: el JSON completo de una service account de Google Cloud (como string), con acceso de **Editor** a la hoja de cálculo destino (compartir la hoja con el `client_email` de la service account).
4. Ejecutar la app:
   ```bash
   streamlit run app.py
   ```

## Tests

```bash
pytest tests/ -v
```

Cubren el esquema `Voucher` (validación de campos requeridos/tipos) y la función `extraer_datos_voucher` (mockeando el cliente de Gemini, sin llamadas reales a la API).

## Seguridad

- Ningún secreto vive en el repositorio. `credentials.json` y `.streamlit/secrets.toml` están excluidos vía `.gitignore`.
- Si una clave de service account llega a exponerse en disco o en un commit, **rotarla de inmediato** desde Google Cloud Console (IAM → Service Accounts → Keys), sin esperar confirmación de que haya sido filtrada.

## Roadmap (próximas fases)

- **Fase 2 — Robustez**: reintentos con backoff ante errores transitorios de la API de Gemini; límite de tamaño/validación de imágenes antes de enviarlas al modelo; manejo de rate limiting.
- **Fase 3 — Observabilidad**: logging estructurado (JSON) enviado a un sistema externo (p. ej. Cloud Logging) en vez de solo `st.error`; métricas de tasa de éxito de extracción.
- **Fase 4 — Escalabilidad de datos**: migrar de Google Sheets a una base de datos (Postgres/SQLite) detrás de una capa de servicio, manteniendo Sheets como vista/export opcional.
- **Fase 5 — Multiusuario**: autenticación de usuarios en la app y separación de hojas/registros por usuario.
