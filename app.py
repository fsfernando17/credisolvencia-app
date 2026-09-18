import streamlit as st
from google import genai
from google.genai import types
import time
from datetime import datetime, timezone, timedelta
import requests
from pydantic import BaseModel, Field

st.set_page_config(page_title="Credisolvencia - Auditoría", page_icon="📊", layout="centered")

# --- ESQUEMA ESTRUCTURADO PARA EXTRACCIÓN CERO ERRORES ---
class AuditoriaCredito(BaseModel):
    dictamen_markdown: str = Field(description="Dictamen técnico detallado en formato Markdown mostrando la evaluación de edad, buró Sentinel, validación de luz, regla de cuotas de descuento y justificación.")
    dni: str = Field(description="Número de DNI extraído correctamente de los documentos (8 dígitos exactos).")
    nombres: str = Field(description="Nombres completos del cliente.")
    apellidos: str = Field(description="Apellidos completos del cliente.")
    monto: str = Field(description="Monto del crédito solicitado con su símbolo o número.")
    interes: str = Field(description="Tasa de interés aplicada según el producto.")
    tipo_cuotas: str = Field(description="Frecuencia de pago obligatoriamente: Semanal, Mensual, Diario o Catorcenal.")
    nivel_riesgo: int = Field(description="Puntuación de riesgo numérica exacta del 1 al 10 (1 menor riesgo, 10 máximo riesgo).")
    capacidad_pago: str = Field(description="Capacidad de pago estimada mensual promedio en dinero.")
    estado_final: str = Field(description="Estrictamente uno de estos tres valores: APROBADO, OBSERVADO o RECHAZADO.")

# --- FUNCIÓN PARA GUARDAR EN GOOGLE SHEETS ---
def guardar_en_sheets(datos_dict):
    try:
        url_script = st.secrets.get("GOOGLE_SHEET_URL", "")
        if not url_script:
            st.warning("⚠️ Falta configurar la URL de Google Sheets en los Secretos.")
            return
            
        respuesta = requests.post(url_script, json=datos_dict, timeout=10)
        if respuesta.status_code == 200:
            st.success("✅ Expediente registrado limpiamente en Google Sheets.")
        else:
            st.warning(f"⚠️ El servidor de Google respondió con código: {respuesta.status_code}")
    except Exception as e:
        st.warning(f"No se pudo guardar en el registro online: {str(e)}")

st.title("📋 Evaluador de Crédito - Credisolvencia")
st.write("Sube la ficha, fotos y el PDF de Sentinel para emitir el dictamen automático.")

# Seguridad de acceso
clave_correcta = st.secrets.get("CLAVE_TRABAJADORES", "")
api_key_oculta = st.secrets.get("GEMINI_API_KEY", "")

clave_ingresada = st.sidebar.text_input("Clave de Subadministrador / Asesor:", type="password")

if clave_ingresada != clave_correcta or not clave_correcta:
    st.warning("⚠️ Ingresa la clave de acceso autorizada para habilitar la auditoría.")
else:
    client = genai.Client(api_key=api_key_oculta)

    # 1. Selector de Modalidad Principal (Dinámico sin form)
    modalidad = st.selectbox("Tipo de Crédito:", ["Individual", "Grupal"], key="select_modalidad")
    
    # 2. Selector Dinámico de Productos según Modalidad
    if modalidad == "Individual":
        producto = st.selectbox("Seleccione el Producto Individual:", ["INTI", "YUNKA", "YAPAY"], key="select_prod_ind")
    else:
        producto = st.selectbox("Seleccione el Producto Grupal:", ["WARMI", "LLAMA"], key="select_prod_grp")
        
    # 3. Selector de Condición del Cliente
    condicion_cliente = st.selectbox("Condición del Cliente:", ["Nuevo", "Renovado", "Recuperado", "Promotor"], key="select_condicion")
    
    # Subcategoría que aparece al instante solo si es Renovado
    detalle_condicion = condicion_cliente
    if condicion_cliente == "Renovado":
        sub_renovacion = st.selectbox("Tipo de Renovación:", ["Adelantada", "Atrasada"], key="select_sub_renovacion")
        detalle_condicion = f"Renovado ({sub_renovacion})"

    ficha_texto = st.text_area("Ficha de Datos del Asesor:", height=150, key="input_ficha")
    sentinel_pdf = st.file_uploader("Cargar Sentinel (PDF)", type=["pdf"], key="file_sentinel")
    fotos_requisitos = st.file_uploader("Cargar Fotos (DNI, Luz, Vivienda, Negocio)", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key="file_fotos")
    
    btn_evaluar = st.button("🚀 Auditar Expediente", key="btn_submit")

    if btn_evaluar:
        if not sentinel_pdf or not fotos_requisitos:
            st.error("⚠️ Es obligatorio adjuntar el PDF de Sentinel y las fotografías.")
        else:
            with st.spinner("Analizando expediente y aplicando normativas de Credisolvencia..."):
                try:
                    contents = []
                    pdf_bytes = sentinel_pdf.read()
                    contents.append(types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))
                    
                    for foto in fotos_requisitos:
                        img_bytes = foto.read()
                        contents.append(types.Part.from_bytes(data=img_bytes, mime_type=foto.type))
                    
                    prompt_instrucciones = f"""
                    Actúa como Analista Senior de Riesgos y Cumplimiento para Credisolvencia. Audita rigurosamente la solicitud:
                    Modalidad: {modalidad} | Producto Seleccionado: {producto} | Condición: {detalle_condicion}
                    Ficha del Asesor: {ficha_texto}

                    POLÍTICAS OFICIALES POR PRODUCTO:
                    1. INTI: Microempresas >1 año. Tasa: 0.6% diaria / 3% semanal / 12% mensual. Frec: Semanal. Plazo: 4-8 sem. Requisito: Buen Sentinel, negocio >1 año.
                    2. WARMI: Grupos 6-8 mujeres (20-65). Tasa: 4% catorcenal / 8% mensual. Frec: Catorcenal. Garantía: Solidaridad grupal.
                    3. YUNKA: Emprendedores (20-65). Tasa: 0.9% diaria / 4.5% semanal / 18% mensual. Frec: Semanal. Requisito: Buen Sentinel, negocio >6 meses, vivienda >1 año.
                    4. YAPAY: Negocios >6 meses. Tasa: 0.9% diaria / 4.5% semanal / 18% mensual. Frec: Diaria (lunes a viernes). Plazo: 22-44 días. Requisito: Permite buena o mala calificación Sentinel.
                    5. LLAMA: Grupos 4 mujeres (20-65). Tasa: 3% semanal / 12% mensual. Frec: Semanal. Garantía: 5% depósito + solidaridad grupal.

                    NORMATIVAS Y REGLAS CRÍTICAS DE CUMPLIMIENTO:
                    1. EDAD: RECHAZO AUTOMÁTICO si el titular tiene 66 años o más (>= 66 años) en créditos individuales.
                    2. LÍMITE DE CUOTAS DE DESCUENTO: El máximo de cuotas permitidas a descontar es de 3 cuotas como máximo. Si se indica un descuento mayor a 3 cuotas, constituye un motivo estricto de OBSERVACIÓN / RECHAZADO.
                    3. CAPACIDAD DE PAGO: Analiza las fotos del negocio/vivienda y Sentinel para estimar un promedio de pago mensual viable en dinero.
                    4. SUMINISTRO (LUZ): Valida estrictamente la titularidad (si es familiar, exige coincidencia de apellidos; indica claramente si es conviviente o alquilada).
                    5. COHERENCIA DE PRODUCTO: Verifica que la antigüedad y condiciones coincidan exactamente con las reglas del producto seleccionado ({producto}).

                    Rellena todos los campos del esquema estructurado con absoluta precisión, extrayendo los datos reales de los archivos adjuntos y del texto.
                    """
                    contents.append(prompt_instrucciones)

                    # Sistema con Backoff Exponencial y el modelo gemini-2.5-flash-lite activo
                    max_reintentos = 5
                    response = None
                    ultimo_error = ""
                    tiempo_espera = 3

                    for intento in range(max_reintentos):
                        try:
                            response = client.models.generate_content(
                                model="gemini-2.5-flash-lite",
                                contents=contents,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    response_schema=AuditoriaCredito,
                                ),
                            )
                            if response and response.parsed:
                                break
                        except Exception as err:
                            ultimo_error = str(err)
                            if "503" in ultimo_error or "UNAVAILABLE" in ultimo_error or "429" in ultimo_error:
                                time.sleep(tiempo_espera)
                                tiempo_espera *= 2
                                continue
                            else:
                                break

                    if response and response.parsed:
                        resultado = response.parsed
                        
                        st.success("Auditoría completada:")
                        st.markdown("---")
                        st.markdown(resultado.dictamen_markdown)
                        
                        # Hora exacta de Perú (UTC-5)
                        zona_peru = timezone(timedelta(hours=-5))
                        fecha_peru = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")

                        # Payload estructurado para las 12 columnas exactas del Google Sheet
                        payload_sheet = {
                            "fecha": fecha_peru,
                            "tipo_credito": modalidad,
                            "producto": producto,
                            "dni": resultado.dni,
                            "nombre": resultado.nombres,
                            "apellidos": resultado.apellidos,
                            "monto": resultado.monto,
                            "interes": resultado.interes,
                            "tipo_cuotas": resultado.tipo_cuotas,
                            "nivel_riesgo": str(resultado.nivel_riesgo),
                            "capacidad_pago": resultado.capacidad_pago,
                            "estado": f"{resultado.estado_final} [{detalle_condicion}]"
                        }

                        guardar_en_sheets(payload_sheet)
                    else:
                        st.error(f"Error al procesar la respuesta estructurada. Detalle: {ultimo_error}")

                except Exception as e:
                    st.error(f"Error al procesar la solicitud: {str(e)}")
