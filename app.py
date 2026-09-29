import streamlit as st
from google import genai
from google.genai import types
import time
from datetime import datetime, timezone, timedelta
import requests
from pydantic import BaseModel, Field
from PIL import Image
import io

st.set_page_config(page_title="Credisolvencia - Auditoría", page_icon="📊", layout="centered")

# --- ESQUEMA ESTRUCTURADO PERFECTAMENTE ALINEADO ---
class AuditoriaCredito(BaseModel):
    dictamen_markdown: str = Field(description="Dictamen técnico detallado en formato Markdown mostrando la evaluación objetiva de edad, buró Sentinel (aplicando regla de rechazo para CPP/DEF/DUD y Pérdida <365 días, aceptando Pérdida >365 días), validación de luz, cotejo de direcciones, pagos históricos antes de las 12 m. para renovaciones, titularidad, foto del cliente, capacidad de pago y conclusión.")
    dni: str = Field(description="Número de DNI extraído correctamente de los documentos (8 dígitos exactos).")
    codigo_suministro: str = Field(description="Número o código de suministro de luz extraído estrictamente de la fotografía del recibo de luz adjunta.")
    nombres: str = Field(description="Nombres completos del cliente (sin apellidos).")
    apellidos: str = Field(description="Apellidos completos del cliente (sin nombres).")
    monto: str = Field(description="Monto total del crédito solicitado con su símbolo o número.")
    aumento: str = Field(description="Indicar estrictamente 'Sí' o 'No' si el crédito representa un aumento respecto al anterior.")
    porcentaje: str = Field(description="Porcentaje exacto de la tasa de interés (ej. 15% o 18%).")
    tipo: str = Field(description="Frecuencia de pago obligatoriamente: Semanal, Mensual, Diario o Catorcenal.")
    monto_cuota: str = Field(description="Monto exacto de cada cuota a pagar según la frecuencia.")
    num_cuotas: str = Field(description="Número total de cuotas o semanas del cronograma del crédito (ej. 4).")
    nivel_riesgo: int = Field(description="Puntuación de riesgo numérica exacta del 1 al 10 como métrica analítica.")
    capacidad_pago: str = Field(description="Capacidad de pago estimada mensual promedio en dinero.")
    estado_final: str = Field(description="Estrictamente uno de estos tres valores: APROBADO, OBSERVADO o RECHAZADO.")
    observacion_subsanar: str = Field(description="Detalle específico de las observaciones o motivo de rechazo (ej. 'Registra calificación CPP en Sentinel - Rechazado por política de riesgo' o 'Ninguna').")

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

# --- FUNCIÓN PARA BORRAR ÚNICAMENTE EL CONTENIDO ---
def limpiar_contenido():
    st.session_state["input_ficha"] = ""
    st.session_state["file_sentinel"] = None
    st.session_state["file_fotos"] = None

st.title("📋 Evaluador de Crédito - Credisolvencia")
st.write("Sube la ficha, tus fotos y el PDF de Sentinel para emitir el dictamen automático.")

# Seguridad de acceso
clave_correcta = st.secrets.get("CLAVE_TRABAJADORES", "")
api_key_oculta = st.secrets.get("GEMINI_API_KEY", "")

clave_ingresada = st.sidebar.text_input("Clave de Subadministrador / Asesor:", type="password")

if clave_ingresada != clave_correcta or not clave_correcta:
    st.warning("⚠️ Ingresa la clave de acceso autorizada para habilitar la auditoría.")
else:
    client = genai.Client(api_key=api_key_oculta)

    # 1. Selector de Modalidad Principal
    modalidad = st.selectbox("Tipo de Crédito:", ["Individual", "Grupal"], key="select_modalidad")
    
    # 2. Selector Dinámico de Productos según Modalidad
    if modalidad == "Individual":
        producto = st.selectbox("Seleccione el Producto Individual:", ["INTI", "YUNKA", "YAPAY"], key="select_prod_ind")
    else:
        producto = st.selectbox("Seleccione el Producto Grupal:", ["WARMI", "LLAMA"], key="select_prod_grp")
        
    # 3. Selector de Condición del Cliente
    condicion_cliente = st.selectbox("Condición del Cliente:", ["Nuevo", "Renovado", "Recuperado", "Promotor"], key="select_condicion")
    
    # Subcategoría con las 3 opciones exactas para Renovado
    detalle_condicion = condicion_cliente
    if condicion_cliente == "Renovado":
        sub_renovacion = st.selectbox("Tipo de Renovación:", ["Adelantada", "Atrasada", "En fecha"], key="select_sub_renovacion")
        detalle_condicion = f"Renovado ({sub_renovacion})"

    ficha_texto = st.text_area("Ficha de Datos del Asesor:", height=150, key="input_ficha")
    sentinel_pdf = st.file_uploader("Cargar Sentinel (PDF)", type=["pdf"], key="file_sentinel")
    fotos_requisitos = st.file_uploader("Cargar Fotos (DNI, Luz, Vivienda, Negocio)", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key="file_fotos")
    
    # Botones organizados
    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        btn_evaluar = st.button("🚀 Auditar Expediente", key="btn_submit", use_container_width=True)
    with col_btn2:
        btn_limpiar = st.button("🔄 Borrar Todo", key="btn_clear", use_container_width=True, on_click=limpiar_contenido)

    if btn_evaluar:
        if not sentinel_pdf or not fotos_requisitos:
            st.error("⚠️ Es obligatorio adjuntar el PDF de Sentinel y las fotografías.")
        else:
            with st.spinner("Analizando expediente con políticas de riesgo de Credisolvencia..."):
                try:
                    contents = []
                    pdf_bytes = sentinel_pdf.read()
                    contents.append(types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))
                    
                    # Compresión ligera para asegurar fluidez
                    for foto in fotos_requisitos:
                        img = Image.open(foto)
                        img.thumbnail((600, 600))
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=55)
                        img_bytes = buf.getvalue()
                        contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
                    
                    prompt_instrucciones = f"""
                    Actúa como Analista Senior de Riesgos y Cumplimiento para Credisolvencia. Audita rigurosamente la solicitud evaluando cada documento y fotografía adjunta bajo los siguientes criterios inquebrantables:

                    Modalidad: {modalidad} | Producto Seleccionado: {producto} | Condición: {detalle_condicion}
                    Ficha del Asesor: {ficha_texto}

                    PARÁMETROS Y POLÍTICAS ESTRICTAS DE EVALUACIÓN:
                    1. **Buró Sentinel (REGLA DE CALIFICACIÓN Y EXCEPCIÓN)**: 
                       - **NO SE ACEPTA** calificación en CPP (Con Problemas Potenciales), DEF ni DUD. Tampoco se aceptan deudas en categoría de Pérdida (PER) menores a 365 días.
                       - **EXCEPCIÓN VÁLIDA:** Si el reporte muestra una deuda en categoría de **Pérdida (PER) mayor a 365 días, SÍ SE ACEPTA** y no es motivo de rechazo por sí sola.
                       - Si el reporte presenta CPP, DEF, DUD o Pérdida <365 días, el crédito se **RECHAZA DIRECTAMENTE**. Si solo tiene Normal (NOR) o Pérdida >365 días, puede continuar con la evaluación.
                    2. **Validación para Clientes Renovados (`{detalle_condicion}`)**: 
                       - Al tratarse de una renovación, **se debe exigir e indicar que Riesgos revise rigurosamente el historial de pagos**, verificando que los pagos anteriores se hayan efectuado estrictamente **antes de las 12:00 del mediodía**.
                    3. **Cotejo de Direcciones**: Validar y contrastar explícitamente si la dirección del suministro de luz coincide con la dirección del DNI y la ubicación del negocio/vivienda.
                    4. **Titularidad de Boletas/Recibos**: Verificar si los recibos de servicios están a nombre del titular o de un familiar directo (ej. cónyuge).
                    5. **Fotografía del Cliente**: Analiza objetivamente la foto del rostro del cliente adjunta. **Si la foto es visible y clara, NO generes ninguna observación por foto borrosa**. Solo márcala si realmente está ausente o ilegible.
                    6. **Conclusión y Estado Final**: Si el Sentinel tiene CPP u otra deuda irregular no permitida, el estado final es `RECHAZADO`. Solo se aprueba si cumple satisfactoriamente todos los filtros.

                    POLÍTICAS OFICIALES POR PRODUCTO:
                    1. INTI: Microempresas >1 año. Tasa: 0.6% diaria / 3% semanal / 12% mensual. Frec: Semanal. Plazo: 4-8 sem.
                    2. WARMI: Grupos 6-8 mujeres (20-65). Tasa: 4% catorcenal / 8% mensual. Frec: Catorcenal.
                    3. YUNKA: Emprendedores (20-65). Tasa: 0.9% diaria / 4.5% semanal / 18% mensual. Frec: Semanal.
                    4. YAPAY: Negocios >6 meses. Tasa: 0.9% diaria / 4.5% semanal / 18% mensual. Plazo: 22-44 días.
                    5. LLAMA: Grupos 4 mujeres (20-65). Tasa: 3% semanal / 12% mensual. Frec: Semanal.

                    REGLAS CRÍTICAS Y ORDEN ESTRICTO DE CAMPOS PARA GOOGLE SHEETS:
                    - **TIPO:** Debe registrar obligatoriamente la frecuencia exacta (Ej: Semanal, Diario, Mensual o Catorcenal). Jamás dejar vacío.
                    - **INTERÉS:** La columna de interés monetario se omite por completo (se envía vacía). El porcentaje va exclusivamente en el campo `%`.
                    - **¿AUMENTO?:** Registrar estrictamente 'Sí' o 'No'.
                    - **CONDICIÓN:** Registrar exactamente '{detalle_condicion}'.
                    - **ESTADO Y OBSERVACIÓN:** 
                      * Estado final: `APROBADO`, `OBSERVADO` o `RECHAZADO`.
                      * Si el Sentinel tiene CPP u otra deuda irregular prohibida, el estado es `RECHAZADO` y la observación indica el motivo exacto.
                    - **CÓDIGO DE SUMINISTRO:** Extraer obligatoriamente de la fotografía del recibo de luz.
                    - **POLÍTICA DE DESCUENTO Y CAPACIDAD DE PAGO:** Crédito diario hasta las 5 últimas cuotas; semanal a partir de 1 mes (>= 4 semanas) permite la última cuota. La capacidad de pago no es condicionante.

                    Rellena todos los campos del esquema estructurado manteniendo el orden perfecto de las columnas.
                    """
                    contents.append(prompt_instrucciones)

                    # Modelos con cuota libre y disponible
                    modelos_libres = ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
                    response = None
                    ultimo_error = ""
                    exito = False

                    for modelo in modelos_libres:
                        try:
                            response = client.models.generate_content(
                                model=modelo,
                                contents=contents,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    response_schema=AuditoriaCredito,
                                ),
                            )
                            if response and response.parsed:
                                exito = True
                                break
                        except Exception as err:
                            ultimo_error = str(err)
                            continue

                    if exito and response and response.parsed:
                        resultado = response.parsed
                        
                        st.success("Auditoría completada:")
                        st.markdown("---")
                        st.markdown(resultado.dictamen_markdown)
                        
                        zona_peru = timezone(timedelta(hours=-5))
                        fecha_peru = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")

                        payload_sheet = {
                            "fecha": fecha_peru,
                            "tipo_credito": modalidad,
                            "condicion": detalle_condicion,
                            "producto": producto,
                            "dni": resultado.dni,
                            "codigo_suministro": resultado.codigo_suministro,
                            "nombre": resultado.nombres,
                            "apellidos": resultado.apellidos,
                            "monto": resultado.monto,
                            "aumento": resultado.aumento,
                            "porcentaje": resultado.porcentaje,
                            "interes": "",  # Vacío
                            "tipo": resultado.tipo or "Semanal",
                            "monto_cuota": resultado.monto_cuota,
                            "num_cuotas": resultado.num_cuotas,
                            "capacidad_pago": resultado.capacidad_pago,
                            "estado": resultado.estado_final,
                            "observacion": resultado.observacion_subsanar
                        }

                        guardar_en_sheets(payload_sheet)
                    else:
                        st.error(f"⚠️ Error al procesar: {ultimo_error}")

                except Exception as e:
                    st.error(f"Error crítico al procesar la solicitud: {str(e)}")
