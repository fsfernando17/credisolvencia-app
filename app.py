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
        # 1. Selector de Modalidad Principal
        modalidad = st.selectbox("Tipo de Crédito:", ["Individual", "Grupal"])
        
        # 2. Selector de Producto (Se oculta si es Grupal)
        producto = ""
        if modalidad == "Individual":
            producto = st.selectbox("Seleccione el Producto Individual:", ["INTI", "WARMI", "YUNKA", "YAPAY", "LLAMA"])
            
        # 3. Selector de Condición del Cliente
        condicion_cliente = st.selectbox("Condición del Crédito / Cliente:", ["Nuevo", "Renovado", "Recuperado", "Promotor"])
        
        detalle_condicion = condicion_cliente
        if condicion_cliente == "Renovado":
            sub_renovacion = st.selectbox("Tipo de Renovación:", ["Adelantada", "Atrasada"])
            detalle_condicion = f"Renovado ({sub_renovacion})"

        # Generación del título para Google Sheets
        if modalidad == "Individual":
            tipo_credito_completo = f"{modalidad} - {producto} [{detalle_condicion}]"
        else:
            tipo_credito_completo = f"{modalidad} [{detalle_condicion}]"

        ficha_texto = st.text_area("Ficha de Datos del Asesor (Texto enviado por chat):", height=150)
        sentinel_pdf = st.file_uploader("Cargar Reporte Sentinel / Experian (PDF)", type=["pdf"])
        fotos_requisitos = st.file_uploader("Cargar Fotos (DNI, Caja de Luz, Vivienda, Negocio)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        
        btn_evaluar = st.form_submit_button("🚀 Auditar Expediente")

    if btn_evaluar:
        if not sentinel_pdf or not fotos_requisitos:
            st.error("⚠️ Es obligatorio adjuntar el PDF de Sentinel y las fotografías de los requisitos.")
        else:
            with st.spinner("Analizando expediente y evaluando políticas de Credisolvencia..."):
                try:
                    contents = []
                    pdf_bytes = sentinel_pdf.read()
                    contents.append(types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))
                    
                    for foto in fotos_requisitos:
                        img_bytes = foto.read()
                        contents.append(types.Part.from_bytes(data=img_bytes, mime_type=foto.type))
                    
                    # Construcción dinámica de la instrucción para la IA
                    instruccion_producto = f"- **Producto Seleccionado:** {producto}" if producto else "- **Producto:** Crédito Grupal Estándar"
                    
                    prompt_instrucciones = f"""
                    Actúa como Analista Senior de Riesgos y Cumplimiento para Credisolvencia. Audita la solicitud evaluando las reglas y la condición específica del cliente:
                    - **Modalidad:** {modalidad}
                    {instruccion_producto}
                    - **Condición de la Operación:** {detalle_condicion}
                    - **Ficha de Datos:** {ficha_texto}

                    POLÍTICAS OFICIALES POR PRODUCTO:
                    1. **INTI (Individual):** Microempresas > 1 año. Tasa: 0.6% diaria / 3% semanal / 12% mensual. Frecuencia: Semanal. Plazos: 4 a 8 semanas. Requisito: Buen historial Sentinel y negocio > 1 año.
                    2. **YUNKA (Individual):** Emprendedores (20-65 años) con negocio propio. Tasa: 0.9% diaria / 4.5% semanal / 18% mensual. Frecuencia: Semanal. Requisito: Buen historial Sentinel, negocio > 6 meses y vivienda > 1 año.
                    3. **YAPAY (Individual):** Negocios > 6 meses. Tasa: 0.9% diaria / 4.5% semanal / 18% mensual. Frecuencia: Diaria. Plazos: 22 a 44 días útiles. Requisito: Permite buena o mala calificación en Sentinel.
                    4. **WARMI (Grupal):** Grupos de 6 a 8 mujeres (20-65 años). Tasa: 4% catorcenal. Garantía: Solidaridad grupal.
                    5. **LLAMA (Grupal):** Grupos de 4 mujeres (20-65 años). Tasa: 3% semanal. Garantía: 5% depósito + solidaridad grupal.
                    *(Si la modalidad es Grupal y no se especificó producto, evaluar que se cumplan las garantías solidarias y el perfil grupal emprendedor).*

                    CRITERIOS ESPECÍFICOS SEGÚN CONDICIÓN ({detalle_condicion}):
                    - **Nuevo:** Validación rigurosa inicial de negocio, vivienda y buró según el producto.
                    - **Renovado (Adelantada):** Cliente con excelente comportamiento; evaluar si califica para aprobación rápida.
                    - **Renovado (Atrasada):** Cliente con historial de retrasos; analizar estrictamente si el riesgo de mora persiste.
                    - **Recuperado:** Revisar estabilidad actual del negocio y mitigación de su comportamiento pasado.
                    - **Promotor:** Aplicar condiciones de fomento verificando que cumpla los mínimos de seguridad.

                    REGLAS OBLIGATORIAS (CAPACIDAD DE PAGO, LUZ Y COHERENCIA):
                    1. **EDAD:** RECHAZO AUTOMÁTICO si tiene 66 años o más (>= 66 años) en créditos individuales.
                    2. **CAPACIDAD DE PAGO:** Estimar financieramente la viabilidad del cliente basándote en las fotos del negocio/vivienda y Sentinel.
                    3. **SUMINISTRO (LUZ):** Validar estrictamente la titularidad del recibo de luz (si es familiar, exigir coincidencia de apellidos; si es conviviente o alquilada, validarlo y mencionarlo).
                    4. **COHERENCIA:** Si los datos no coinciden con las políticas del producto solicitado, detectarlo como error y observar/rechazar.

                    Emite el dictamen final estructurado detallando: ESTADO (APROBADO / OBSERVADO / RECHAZADO), VALIDACIÓN DEL PRODUCTO Y CONDICIÓN ({tipo_credito_completo}), CAPACIDAD DE PAGO ESTIMADA, VALIDACIÓN DEL SUMINISTRO y JUSTIFICACIÓN.
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
                        
                        # Extracción y registro automático a Google Sheets (Mantenido intacto)
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

                        guardar_en_sheets(tipo_credito_completo, dni_ext, nombre_ext, suministro_ext, estado_ext, ficha_texto, texto_respuesta)
                    else:
                        st.error(f"Error de conexión tras {max_reintentos} intentos. Detalle: {ultimo_error}")

                except Exception as e:
                    st.error(f"Error al procesar la solicitud: {str(e)}")
