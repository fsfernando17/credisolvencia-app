import streamlit as st
from google import genai
from google.genai import types
import time
from datetime import datetime
import requests
import json

st.set_page_config(page_title="Credisolvencia - Auditoría", page_icon="📊", layout="centered")

# --- FUNCIÓN PARA GUARDAR EN GOOGLE SHEETS CON DATOS EXTRAÍDOS ---
def guardar_en_sheets(tipo_credito, dni, nombre, suministro, estado, ficha, dictamen):
    try:
        url_script = st.secrets.get("GOOGLE_SHEET_URL", "")
        if not url_script:
            return
            
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "fecha": fecha_actual,
            "tipo_credito": tipo_credito,
            "dni": dni,
            "nombre": nombre,
            "suministro": suministro,
            "estado": estado,
            "ficha_resumen": ficha[:150],
            "dictamen": dictamen[:400]
        }
        requests.post(url_script, json=payload, timeout=5)
    except Exception as e:
        st.warning(f"No se pudo guardar en el registro online: {str(e)}")

st.title("📋 Evaluador de Crédito - Credisolvencia")
st.write("Sube la ficha del asesor, las fotos de los requisitos y el PDF de Sentinel para emitir el dictamen automático.")

# Seguridad de acceso
clave_correcta = st.secrets.get("CLAVE_TRABAJADORES", "")
api_key_oculta = st.secrets.get("GEMINI_API_KEY", "")

clave_ingresada = st.sidebar.text_input("Clave de Subadministrador / Asesor:", type="password")

if clave_ingresada != clave_correcta or not clave_correcta:
    st.warning("⚠️ Por favor, ingresa la clave de acceso autorizada en la barra lateral para habilitar la auditoría.")
else:
    client = genai.Client(api_key=api_key_oculta)

    with st.form("form_credito"):
        tipo_credito = st.selectbox("Tipo de Crédito", ["Individual", "Grupal"])
        ficha_texto = st.text_area("Ficha de Datos del Asesor (Texto enviado por chat):", height=150)
        sentinel_pdf = st.file_uploader("Cargar Reporte Sentinel / Experian (PDF)", type=["pdf"])
        fotos_requisitos = st.file_uploader("Cargar Fotos (DNI, Caja de Luz, Vivienda, Negocio)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        
        btn_evaluar = st.form_submit_button("🚀 Auditar Expediente")

    if btn_evaluar:
        if not sentinel_pdf or not fotos_requisitos:
            st.error("⚠️ Es obligatorio adjuntar el PDF de Sentinel y las fotografías de los requisitos.")
        else:
            with st.spinner("Analizando expediente y aplicando reglas de riesgo..."):
                try:
                    contents = []
                    pdf_bytes = sentinel_pdf.read()
                    contents.append(types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))
                    
                    for foto in fotos_requisitos:
                        img_bytes = foto.read()
                        contents.append(types.Part.from_bytes(data=img_bytes, mime_type=foto.type))
                    
                    prompt_instrucciones = f"""
                    Actúa como Analista Experto en Riesgo Crediticio para Credisolvencia. Audita la solicitud enviada:
                    - Tipo de Crédito: {tipo_credito}
                    - Ficha de Datos: {ficha_texto}

                    REGLAS OBLIGATORIAS DE NEGOCIO:
                    1. EDAD: RECHAZO AUTOMÁTICO si el cliente tiene 66 años cumplidos o más (>= 66 años).
                    2. BURÓ (SENTINEL): En Crédito Individual rechazar si está en CPP, DEF, DUD o PER (con Días Venc. <= 365 días). Si está en PER con > 365 días o NOR, es APTO. En Crédito Grupal se permite flexibilidad sujeto a aval.
                    3. REQUISITOS (IMÁGENES): Validar presencia de DNI/C4 vigente, Caja de Luz/Suministro, Foto Vivienda y Foto Negocio.

                    Además del dictamen, DEBES incluir al inicio de tu respuesta un bloque en formato JSON estricto con los siguientes datos extraídos de los documentos:
                    {{
                      "dni": "número de DNI encontrado o 'No encontrado'",
                      "nombre": "nombre completo del cliente o 'No encontrado'",
                      "suministro": "número de suministro de la caja de luz o 'No encontrado'",
                      "estado": "APROBADO o OBSERVADO o RECHAZADO o DOCUMENTACIÓN_FALTANTE"
                    }}

                    Emite el dictamen final detallado después del JSON.
                    """
                    contents.append(prompt_instrucciones)

                    # Sistema de reintentos automáticos
                    max_reintentos = 5
                    response = None
                    ultimo_error = ""

                    for intento in range(max_reintentos):
                        try:
                            response = client.models.generate_content(
                                model="gemini-3.6-flash",
                                contents=contents
                            )
                            if response:
                                break
                        except Exception as err:
                            ultimo_error = str(err)
                            if "503" in ultimo_error or "UNAVAILABLE" in ultimo_error or "429" in ultimo_error:
                                time.sleep(5)
                                continue
                            else:
                                break

                  if response:
                        st.success("Auditoría completada:")
                        st.markdown("---")
                        st.markdown(response.text)
                        
                        # Extracción segura y directa garantizada
                        texto_respuesta = response.text
                        dni_ext = "No especificado"
                        nombre_ext = "No especificado"
                        suministro_ext = "No especificado"
                        estado_ext = "APROBADO" if "APROBADO" in texto_respuesta.upper() else ("RECHAZADO" if "RECHAZADO" in texto_respuesta.upper() else "OBSERVADO")
                        
                        try:
                            # Búsqueda manual de datos clave por texto si el JSON falla
                            for linea in texto_respuesta.split("\n"):
                                if "dni" in linea.lower():
                                    dni_ext = ''.join(filter(str.isdigit, linea)) or "No especificado"
                                if "nombre" in linea.lower():
                                    nombre_ext = linea.split(":")[-1].replace('"', '').replace(',', '').strip()
                                if "suministro" in linea.lower():
                                    suministro_ext = ''.join(filter(str.isdigit, linea)) or "No especificado"
                        except:
                            pass

                        # Envío inmediato y seguro a tu Google Sheet
                        guardar_en_sheets(tipo_credito, dni_ext, nombre_ext, suministro_ext, estado_ext, ficha_texto, texto_respuesta)
                    else:
                        st.error(f"Error de conexión tras {max_reintentos} intentos. Detalle: {ultimo_error}")

                except Exception as e:
                    st.error(f"Error al procesar la solicitud: {str(e)}")
