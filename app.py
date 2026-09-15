import streamlit as st
from google import genai
from google.genai import types
import time

st.set_page_config(page_title="Credisolvencia - Auditoría", page_icon="📊", layout="centered")

st.title("📋 Evaluador de Crédito - Credisolvencia")
st.write("Sube la ficha del asesor, las fotos de los requisitos y el PDF de Sentinel para emitir el dictamen automático.")

api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else st.sidebar.text_input("Ingresa tu Gemini API Key:", type="password")

if not api_key:
    st.info("Por favor ingresa tu Gemini API Key en la barra lateral para continuar.")
else:
    client = genai.Client(api_key=api_key)

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

                    Emite el dictamen final siguiendo la estructura estándar con ESTADO (APROBADO / OBSERVADO / RECHAZADO / DOCUMENTACIÓN_FALTANTE) y JUSTIFICACIÓN.
                    """
                    contents.append(prompt_instrucciones)

                    # Sistema de persistencia agresiva frente a saturación
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
                    else:
                        st.error(f"Error de conexión tras {max_reintentos} intentos. Detalle: {ultimo_error}")

                except Exception as e:
                    st.error(f"Error al procesar la solicitud: {str(e)}")
