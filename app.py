import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Credisolvencia - Auditoría", page_icon="📊", layout="centered")

st.title("📋 Evaluador de Crédito - Credisolvencia")
st.write("Sube la ficha del asesor, las fotos de los requisitos y el PDF de Sentinel para emitir el dictamen automático.")

api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else st.sidebar.text_input("Ingresa tu Gemini API Key:", type="password")

if not api_key:
    st.info("Por favor ingresa tu Gemini API Key en la barra lateral para continuar.")
else:
    genai.configure(api_key=api_key)

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
                    
                    # Preparar PDF
                    pdf_bytes = sentinel_pdf.read()
                    contents.append({
                        "mime_type": "application/pdf",
                        "data": pdf_bytes
                    })
                    
                    # Preparar Fotografías
                    for foto in fotos_requisitos:
                        img_bytes = foto.read()
                        contents.append({
                            "mime_type": foto.type,
                            "data": img_bytes
                        })
                    
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

                    # Instanciar el modelo con la librería genai directa
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(contents)
                    
                    st.success("Auditoría completada:")
                    st.markdown("---")
                    st.markdown(response.text)

                except Exception as e:
                    st.error(f"Ocurrió un error al procesar la solicitud: {str(e)}")
