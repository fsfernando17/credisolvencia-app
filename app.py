import streamlit as st
from google import genai
from google.genai import types
import time
from datetime import datetime
import requests

st.set_page_config(page_title="Credisolvencia - Auditoría", page_icon="📊", layout="centered")

# --- FUNCIÓN PARA GUARDAR EN GOOGLE SHEETS ---
def guardar_en_sheets(tipo_credito, dni, nombre, suministro, estado, ficha, dictamen):
    try:
        url_script = st.secrets.get("GOOGLE_SHEET_URL", "")
        if not url_script:
            st.warning("⚠️ Falta configurar la URL de Google Sheets en los Secretos de Streamlit.")
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
        respuesta = requests.post(url_script, json=payload, timeout=10)
        if respuesta.status_code == 200:
            st.success("✅ ¡Expediente registrado correctamente en Google Sheets!")
        else:
            st.warning(f"⚠️ El servidor de Google respondió con código: {respuesta.status_code}")
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
        tipo_credito = st.selectbox("Seleccione el Producto Crediticio:", ["INTI", "WARMI", "YUNKA", "YAPAY", "LLAMA"])
        ficha_texto = st.text_area("Ficha de Datos del Asesor (Texto enviado por chat):", height=150)
        sentinel_pdf = st.file_uploader("Cargar Reporte Sentinel / Experian (PDF)", type=["pdf"])
        fotos_requisitos = st.file_uploader("Cargar Fotos (DNI, Caja de Luz, Vivienda, Negocio)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        
        btn_evaluar = st.form_submit_button("🚀 Auditar Expediente")

    if btn_evaluar:
        if not sentinel_pdf or not fotos_requisitos:
            st.error("⚠️ Es obligatorio adjuntar el PDF de Sentinel y las fotografías de los requisitos.")
        else:
            with st.spinner("Analizando expediente y validando políticas del producto..."):
                try:
                    contents = []
                    pdf_bytes = sentinel_pdf.read()
                    contents.append(types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))
                    
                    for foto in fotos_requisitos:
                        img_bytes = foto.read()
                        contents.append(types.Part.from_bytes(data=img_bytes, mime_type=foto.type))
                    
                    prompt_instrucciones = f"""
                    Actúa como Analista Senior de Riesgos y Cumplimiento para Credisolvencia. Audita la solicitud evaluando estrictamente si cumple con las reglas del producto seleccionado:
                    - **Producto Seleccionado por el Asesor:** {tipo_credito}
                    - **Ficha de Datos:** {ficha_texto}

                    POLÍTICAS OFICIALES POR PRODUCTO (VALIDACIÓN CRUZADA OBLIGATORIA):
                    1. **INTI:** Dirigido a microempresas con más de 1 año de funcionamiento. Requisito clave: Buen historial en Sentinel y negocio propio > 1 año de antigüedad. Frecuencia: Semanal. Plazos: 4 a 8 semanas.
                    2. **WARMI:** Grupos de 6 a 8 mujeres emprendedoras (20 a 65 años) que se agrupan voluntariamente. Frecuencia: Catorcenal. Garantía: Solidaridad grupal. Requisito clave: Grupo de mujeres con negocios/emprendimientos.
                    3. **YUNKA:** Emprendedores (20 a 65 años) con negocio propio. Frecuencia: Semanal. Requisito clave: Estar bien calificado en Sentinel, negocio propio > 6 meses y vivienda propia > 1 año.
                    4. **YAPAY:** Negocios con al menos 6 meses de antigüedad. Frecuencia: Diaria (lunes a viernes). Requisito clave: Permite clientes con buena o mala calificación en Sentinel. Negocio propio > 6 meses y vivienda propia > 1 año.
                    5. **LLAMA:** Grupos de 4 mujeres emprendedoras (20 a 65 años) con negocio propio. Frecuencia: Semanal. Garantía: Depósito de garantía del 5% + solidaridad grupal. Requisito clave: No apto para clientes mal calificados en 3 entidades o con pérdidas en créditos grupales.

                    REGLAS GENERALES Y VALIDACIÓN DE ERRORES:
                    - **EDAD:** RECHAZO AUTOMÁTICO si el cliente tiene 66 años o más (>= 66 años) en productos individuales.
                    - **COHERENCIA DE PRODUCTO:** Si los datos enviados por el asesor (antigüedad de negocio, calificación en Sentinel, tipo de garantía, género o estructura de grupo) **NO CORRESPONDEN** a lo exigido por el producto `{tipo_credito}`, la IA debe detectarlo obligatoriamente como un **ERROR DE SOLICITUD / NO CUMPLE** y rechazar/observar el expediente indicando la discrepancia exacta.
                    - **SUMINISTRO Y VIVIENDA:** Validar el nombre del titular del recibo de luz frente a lo declarado (si es familiar, verificar apellidos; si es conviviente o alquilada, indicarlo).

                    Emite el dictamen final estructurado detallando: ESTADO (APROBADO / OBSERVADO / RECHAZADO), VALIDACIÓN DEL PRODUCTO ({tipo_credito}), CAPACIDAD DE PAGO y JUSTIFICACIÓN.
                    """
                    contents.append(prompt_instrucciones)

                    # Sistema automático de reintentos
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
                        
                        # Extracción y registro automático seguro
                        texto_respuesta = response.text
                        dni_ext = "No especificado"
                        nombre_ext = "No especificado"
                        suministro_ext = "No especificado"
                        estado_ext = "APROBADO" if "APROBADO" in texto_respuesta.upper() else ("RECHAZADO" if "RECHAZADO" in texto_respuesta.upper() else "OBSERVADO")
                        
                        try:
                            for linea in texto_respuesta.split("\n"):
                                if "dni" in linea.lower():
                                    dni_ext = ''.join(filter(str.isdigit, linea)) or "No especificado"
                                if "nombre" in linea.lower():
                                    nombre_ext = linea.split(":")[-1].replace('"', '').replace(',', '').strip()
                                if "suministro" in linea.lower():
                                    suministro_ext = ''.join(filter(str.isdigit, linea)) or "No especificado"
                        except:
                            pass

                        guardar_en_sheets(tipo_credito, dni_ext, nombre_ext, suministro_ext, estado_ext, ficha_texto, texto_respuesta)
                    else:
                        st.error(f"Error de conexión tras {max_reintentos} intentos. Detalle: {ultimo_error}")

                except Exception as e:
                    st.error(f"Error al procesar la solicitud: {str(e)}")
