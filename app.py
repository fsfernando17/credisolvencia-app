import streamlit as st
from google import genai
from google.genai import types
import time
from datetime import datetime, timezone, timedelta
import requests
from pydantic import BaseModel, Field

st.set_page_config(page_title="Credisolvencia - Auditoría", page_icon="📊", layout="centered")

# --- ESQUEMA ESTRUCTURADO CON EXTRACCIÓN GARANTIZADA DE SUMINISTRO ---
class AuditoriaCredito(BaseModel):
    dictamen_markdown: str = Field(description="Dictamen técnico detallado en formato Markdown mostrando la evaluación objetiva de edad, buró Sentinel, validación de luz, reglas de descuento actualizadas (diario: hasta 5 últimas cuotas; semanal >= 1 mes: última cuota), monto de cuota, capacidad de pago y nivel de riesgo como comentarios analíticos.")
    dni: str = Field(description="Número de DNI extraído correctamente de los documentos (8 dígitos exactos).")
    codigo_suministro: str = Field(description="Número o código de suministro de luz extraído estrictamente de la fotografía del recibo de luz adjunta.")
    nombres: str = Field(description="Nombres completos del cliente (sin apellidos).")
    apellidos: str = Field(description="Apellidos completos del cliente (sin nombres).")
    monto: str = Field(description="Monto total del crédito solicitado con su símbolo o número.")
    interes: str = Field(description="Tasa de interés aplicada según el producto.")
    tipo_cuotas: str = Field(description="Frecuencia de pago obligatoriamente: Semanal, Mensual, Diario o Catorcenal.")
    monto_cuota: str = Field(description="Monto exacto de cada cuota a pagar según la frecuencia.")
    nivel_riesgo: int = Field(description="Puntuación de riesgo numérica exacta del 1 al 10 como métrica analítica de comentario.")
    capacidad_pago: str = Field(description="Capacidad de pago estimada mensual promedio en dinero como comentario analítico no condicionante.")
    estado_final: str = Field(description="Estrictamente uno de estos tres valores basado ÚNICAMENTE en normativas formales (edad menor a 66, reglas de descuento válidas, suministro válido y Sentinel sin moras activas graves): APROBADO, OBSERVADO o RECHAZADO.")

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
                    1. INTI: Microempresas >1 año. Tasa: 0.6% diaria / 3% semanal / 12% mensual. Frec: Semanal. Plazo: 4-8 sem. Requisito: Historial Sentinel normal/aceptable y negocio >1 año.
                    2. WARMI: Grupos 6-8 mujeres (20-65). Tasa: 4% catorcenal / 8% mensual. Frec: Catorcenal. Garantía: Solidaridad grupal.
                    3. YUNKA: Emprendedores (20-65). Tasa: 0.9% diaria / 4.5% semanal / 18% mensual. Frec: Semanal. Requisito: Buen Sentinel, negocio >6 meses, vivienda >1 año.
                    4. YAPAY: Negocios >6 meses. Tasa: 0.9% diaria / 4.5% semanal / 18% mensual. Frec: Diaria (lunes a viernes). Plazo: 22-44 días. Requisito: Permite buena o mala calificación Sentinel.
                    5. LLAMA: Grupos 4 mujeres (20-65). Tasa: 3% semanal / 12% mensual. Frec: Semanal. Garantía: 5% depósito + solidaridad grupal.

                    REGLAS CRÍTICAS Y POLÍTICAS ACTUALIZADAS DE DESCUENTO Y SUMINISTRO:
                    - **CÓDIGO DE SUMINISTRO:** Es OBLIGATORIO ubicar y extraer el número o código de suministro de luz de la fotografía del recibo cargada. Revisa bien las imágenes para capturar este número exacto.
                    - **POLÍTICA ACTUALIZADA DE DESCUENTO DE CUOTAS:**
                      1. **Crédito Diario:** Se permite descontar hasta las **5 últimas cuotas**.
                      2. **Crédito Semanal (a partir de 1 mes / >= 4 semanas de duración):** Se permite descontar la **última cuota**.
                      3. Cualquier descuento dentro de estos rangos es completamente válido y aprobado.
                    - **CAPACIDAD DE PAGO (INDICADOR NO CONDICIONANTE):** Es una métrica estadística y descriptiva de soporte analítico. **NUNCA** debe ser motivo para calificar un crédito como OBSERVADO o RECHAZADO por el hecho de que la cuota sea cercana o mayor.
                    - **BURÓ EXPERIAN/SENTINEL:** Sin moras activas graves, el cliente es apto.
                    - **EDAD:** RECHAZO AUTOMÁTICO si el titular tiene 66 años o más (>= 66 años) en individuales.
                    - **SUMINISTRO (LUZ):** Valida titularidad (familiar con coincidencia de apellidos, conviviente o alquilada).

                    Rellena todos los campos del esquema estructurado con absoluta precisión, separando nombres y apellidos, extrayendo obligatoriamente el código de suministro y aplicando los nuevos criterios de descuento.
                    """
                    contents.append(prompt_instrucciones)

                    # Sistema con Backoff Exponencial y el modelo activo gemini-3.5-flash-lite
                    max_reintentos = 5
                    response = None
                    ultimo_error = ""
                    tiempo_espera = 3

                    for intento in range(max_reintentos):
                        try:
                            response = client.models.generate_content(
                                model="gemini-3.5-flash-lite",
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

                        # Payload estructurado incluyendo el código de suministro en la posición exacta
                        payload_sheet = {
                            "fecha": fecha_peru,
                            "tipo_credito": modalidad,
                            "producto": producto,
                            "dni": resultado.dni,
                            "codigo_suministro": resultado.codigo_suministro,
                            "nombre": resultado.nombres,
                            "apellidos": resultado.apellidos,
                            "monto": resultado.monto,
                            "interes": resultado.interes,
                            "tipo_cuotas": resultado.tipo_cuotas,
                            "monto_cuota": resultado.monto_cuota,
                            "nivel_riesgo": str(resultado.nivel_riesgo),
                            "capacidad_pago": resultado.capacidad_pago,
                            "estado": f"{resultado.estado_final} [{detalle_condicion}]"
                        }

                        guardar_en_sheets(payload_sheet)
                    else:
                        st.error(f"Error al procesar la respuesta estructurada. Detalle: {ultimo_error}")

                except Exception as e:
                    st.error(f"Error al procesar la solicitud: {str(e)}")
