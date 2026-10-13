import re
import time
from google import genai
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# --- CONFIGURACIÓN DE PÁGINA FINTECH PROFESIONAL ---
st.set_page_config(
    page_title="Asistente Inteligente de Inversiones Bursátiles",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos CSS Personalizados de Grado Terminal Financiera
st.markdown(
    """
    <style>
    /* Estilo General Dark Mode */
    .stApp {
        background-color: #0b0f17;
        color: #e5e7eb;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Contraste en etiquetas de formulario */
    label, [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label, .stWidgetLabel p {
        color: #f3f4f6 !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }
    
    /* Cajas de entrada e inputs */
    div[data-baseweb="select"] > div, input {
        background-color: #1f2937 !important;
        color: #ffffff !important;
        border-color: #374151 !important;
        border-radius: 8px !important;
    }

    /* Módulos de informe estratégico */
    .report-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 10px;
        padding: 24px;
        margin-top: 10px;
        margin-bottom: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        line-height: 1.6;
    }

    /* Badges de Veredicto Dinámico */
    .verdict-badge-comprar {
        background-color: rgba(16, 185, 129, 0.15);
        border: 1px solid #10b981;
        color: #34d399;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 800;
        display: inline-block;
        font-size: 1.1rem;
        letter-spacing: 0.05em;
    }
    
    .verdict-badge-desestimar {
        background-color: rgba(239, 68, 68, 0.15);
        border: 1px solid #ef4444;
        color: #f87171;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 800;
        display: inline-block;
        font-size: 1.1rem;
        letter-spacing: 0.05em;
    }

    .verdict-badge-observacion {
        background-color: rgba(245, 158, 11, 0.15);
        border: 1px solid #f59e0b;
        color: #fbbf24;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 800;
        display: inline-block;
        font-size: 1.1rem;
        letter-spacing: 0.05em;
    }

    /* Títulos y Métricas */
    h1 { color: #ffffff !important; font-weight: 800 !important; }
    h2, h3 { color: #38bdf8 !important; font-weight: 700 !important; }
    
    [data-testid="stMetric"] {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 10px;
        padding: 14px 18px;
    }
    [data-testid="stMetricLabel"] { color: #9ca3af !important; font-size: 0.88rem !important; font-weight: 600; }
    [data-testid="stMetricValue"] { color: #38bdf8 !important; font-size: 1.45rem !important; font-weight: 700; }

    /* Botón Principal */
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        color: #ffffff;
        font-weight: 700;
        font-size: 17px;
        border-radius: 10px;
        border: none;
        padding: 14px 28px;
        box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.5);
    }

    /* Descargo Legal */
    .disclaimer-box {
        background-color: #17120a;
        border-left: 4px solid #f59e0b;
        border-radius: 8px;
        color: #f3f4f6;
        padding: 16px 20px;
        font-size: 0.88rem;
        margin-top: 20px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Carga transparente de la API Key
api_key_oculta = st.secrets.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=api_key_oculta) if api_key_oculta else None


# SISTEMA DE CONEXIÓN ULTRARRÁPIDO CON MODELOS OFICIALES (gemini-3.8-flash -> gemini-3.7-flash -> gemini-3.6-flash)
def generar_respuesta_ia_rapida(client, prompt):
  modelos_validos = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"]
  ultimo_error = None

  for modelo in modelos_validos:
    for intento in range(2):
      try:
        response = client.models.generate_content(
            model=modelo, contents=prompt
        )
        if response and response.text:
          return response.text
      except Exception as e:
        ultimo_error = e
        err_str = str(e)
        if (
            "503" in err_str
            or "UNAVAILABLE" in err_str
            or "429" in err_str
            or "RESOURCE_EXHAUSTED" in err_str
        ):
          time.sleep(0.5 * (intento + 1))
        else:
          break

  raise Exception(f"Detalle de servicio API: {str(ultimo_error)}")


# --- DICCIONARIOS Y TASAS DE CONVERSIÓN ---
TASAS_CAMBIO_USD = {
    "USD ($)": 1.0,
    "PEN (S/.)": 3.75,
    "CLP ($)": 950.0,
    "BRL (R$)": 5.50,
    "MXN ($)": 19.50,
}

SIMBOLOS_MONEDA = {
    "USD ($)": "$",
    "PEN (S/.)": "S/.",
    "CLP ($)": "$ CLP",
    "BRL (R$)": "R$",
    "MXN ($)": "$ MXN",
}

MINIMOS_MONEDA = {
    "USD ($)": 20.0,
    "PEN (S/.)": 75.0,
    "CLP ($)": 19000.0,
    "BRL (R$)": 110.0,
    "MXN ($)": 390.0,
}

MERCADOS = {
    "NYSE / NASDAQ (Estados Unidos)": {
        "AAPL": "Apple Inc.",
        "TSLA": "Tesla Inc.",
        "MSFT": "Microsoft Corp.",
        "NVDA": "NVIDIA Corp.",
        "AMZN": "Amazon.com Inc.",
        "GOOGL": "Alphabet Inc.",
        "META": "Meta Platforms",
        "NFLX": "Netflix Inc.",
        "AMD": "Advanced Micro Devices",
        "INTC": "Intel Corp.",
        "SCCO": "Southern Copper Corp. (NYSE - USD)",
        "🔍 Buscar otro Ticker manualmente": "CUSTOM",
    },
    "Bolsa de Valores de Lima (BVL - Perú)": {
        "SPCCPI1.LM": "Southern Copper Corp. (Acc. Inversión BVL - PEN)",
        "BAP": "Credicorp Ltd. (USD)",
        "SCCO": "Southern Copper Corp. (NYSE ADR - USD)",
        "IFS": "Intercorp Financial Services (USD)",
        "BVN": "Compañía de Minas Buenaventura (USD)",
        "CPACEN1.LM": "Cementos Pacasmayo (PEN)",
        "VOLCABC1.LM": "Volcan Compañía Minera (PEN)",
        "ALICORC1.LM": "Alicorp S.A.A. (PEN)",
        "FERREYC1.LM": "Ferreycorp S.A.A. (PEN)",
        "🔍 Buscar otro Ticker manualmente": "CUSTOM",
    },
    "B3 (Bolsa de Brasil)": {
        "PETR4.SA": "Petrobras (BRL)",
        "VALE3.SA": "Vale S.A. (BRL)",
        "ITUB4.SA": "Itaú Unibanco (BRL)",
        "BBDC4.SA": "Banco Bradesco (BRL)",
        "ABEV3.SA": "Ambev S.A. (BRL)",
        "WEGE3.SA": "WEG S.A. (BRL)",
        "🔍 Buscar otro Ticker manualmente": "CUSTOM",
    },
}


# NORMALIZACIÓN DINÁMICA DE DIVISA BASE A DIVISA DESTINO
def obtener_factor_conversion(moneda_base_asset, moneda_destino_key):
  tasa_destino = TASAS_CAMBIO_USD[moneda_destino_key]

  base_upper = str(moneda_base_asset).upper()
  if "PEN" in base_upper or "SOL" in base_upper:
    tasa_base_usd = TASAS_CAMBIO_USD["PEN (S/.)"]
  elif "BRL" in base_upper:
    tasa_base_usd = TASAS_CAMBIO_USD["BRL (R$)"]
  elif "CLP" in base_upper:
    tasa_base_usd = TASAS_CAMBIO_USD["CLP ($)"]
  elif "MXN" in base_upper:
    tasa_base_usd = TASAS_CAMBIO_USD["MXN ($)"]
  else:
    tasa_base_usd = 1.0  # Por defecto USD

  return (1.0 / tasa_base_usd) * tasa_destino


# --- ENCABEZADO PRINCIPAL ---
st.title("📈 Asistente Inteligente de Inversiones Bursátiles")
st.markdown(
    "<p style='color: #9ca3af; font-size: 1.05rem; margin-bottom:"
    " 25px;'>Terminal cuantitativa, fundamental y econométrica para la"
    " evaluación estratégica de activos financieros globales.</p>",
    unsafe_allow_html=True,
)

# --- PANEL DE CONFIGURACIÓN ---
with st.container(border=True):
  st.subheader("⚙️ Parámetros Operativos de Inversión")

  col1, col2, col3 = st.columns(3)

  with col1:
    mercado_sel = st.selectbox("🌍 Mercado de Origen:", list(MERCADOS.keys()))

  dic_acciones = MERCADOS[mercado_sel]

  with col2:
    opcion_accion = st.selectbox(
        "📊 Selección de Acción / Ticker:",
        list(dic_acciones.keys()),
        format_func=lambda x: (
            f"{x} - {dic_acciones[x] if x != '🔍 Buscar otro Ticker manualmente' else 'Escribir Ticker'}"
        ),
    )

    if opcion_accion == "🔍 Buscar otro Ticker manualmente":
      ticker_final = st.text_input(
          "Ingrese Ticker oficial de Yahoo Finance (ej: AMD, MELI, PBR):",
          value="NVDA",
      ).upper()
      nombre_empresa = ticker_final
    else:
      ticker_final = opcion_accion
      nombre_empresa = dic_acciones[opcion_accion]

  with col3:
    moneda_sel = st.selectbox("💵 Moneda de Operación:", list(TASAS_CAMBIO_USD.keys()))

  simb = SIMBOLOS_MONEDA[moneda_sel]
  monto_min = MINIMOS_MONEDA[moneda_sel]

  col4, col5, col6 = st.columns(3)

  with col4:
    capital_input = st.number_input(
        f"💰 Capital Disponible ({simb}):",
        min_value=monto_min,
        value=monto_min * 10,
        step=monto_min,
    )

  with col5:
    horizonte = st.selectbox(
        "⏱️ Horizonte Temporal:",
        [
            "Corto Plazo (1 a 3 meses)",
            "Mediano Plazo (6 meses a 1 año)",
            "Largo Plazo (1 año a más)",
        ],
    )

  with col6:
    perfil_riesgo = st.selectbox(
        "🛡️ Perfil del Inversor:", ["Conservador", "Moderado", "Agresivo"]
    )

st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

# --- BOTÓN PRINCIPAL DE EJECUCIÓN ---
if st.button(
    "🚀 Ejecutar Análisis Multidimensional y Proyección",
    use_container_width=True,
):
  if not api_key_oculta or not client:
    st.error(
        "⚠️ El servicio de Inteligencia Artificial no está configurado en el"
        " servidor (Falta la clave GEMINI_API_KEY en Secrets)."
    )
  else:
    # 1. PASO BURSÁTIL Y CUANTITATIVO (INMEDIATO)
    datos_cargados = False
    try:
      stock = yf.Ticker(ticker_final)
      df = stock.history(period="1y")
      info = stock.info

      if df.empty:
        st.error(
            "⚠️ No se encontraron registros financieros para el símbolo"
            f" '{ticker_final}'. Verifique el ticker en Yahoo Finance."
        )
      else:
        datos_cargados = True
        currency_base = info.get("currency", "USD")
        factor_conv = obtener_factor_conversion(currency_base, moneda_sel)

        precio_actual_raw = df["Close"].iloc[-1]
        precio_actual = precio_actual_raw * factor_conv
        df["Close_Moneda"] = df["Close"] * factor_conv

        # Datos fundamentales
        market_cap = (
            info.get("marketCap", 0) * factor_conv
            if info.get("marketCap")
            else 0
        )
        pe_ratio_raw = info.get("trailingPE", "N/A")
        pe_ratio = (
            f"{pe_ratio_raw:.2f}"
            if isinstance(pe_ratio_raw, (int, float))
            else str(pe_ratio_raw)
        )

        pb_ratio_raw = info.get("priceToBook", "N/A")
        pb_ratio = (
            f"{pb_ratio_raw:.2f}"
            if isinstance(pb_ratio_raw, (int, float))
            else str(pb_ratio_raw)
        )

        dividend_yield = info.get("dividendYield", 0)
        dividend_str = (
            f"{dividend_yield*100:.2f}%" if dividend_yield else "0.00%"
        )
        profit_margin = info.get("profitMargins", 0)
        margin_str = (
            f"{profit_margin*100:.2f}%" if profit_margin else "N/A"
        )
        sector = info.get("sector", "General / No especificado")

        # Métricas Cuantitativas
        df["Retorno_Diario"] = df["Close"].pct_change()
        volatilidad_anual = df["Retorno_Diario"].std() * np.sqrt(252)
        retorno_medio_diario = df["Retorno_Diario"].mean()
        var_95 = np.percentile(df["Retorno_Diario"].dropna(), 5)

        sma_50 = df["Close_Moneda"].rolling(window=50).mean().iloc[-1]
        sma_200 = (
            df["Close_Moneda"].rolling(window=200).mean().iloc[-1]
            if len(df) >= 200
            else sma_50
        )

        # --- MOSTRAR PANEL DE KPIS DE INMEDIATO ---
        st.markdown("### 📊 Panel de Indicadores Clave & Fundamentos")

        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        c_m1.metric(
            f"Precio Actual ({simb})", f"{simb} {precio_actual:,.2f}"
        )
        c_m2.metric("PER (Price / Earnings)", f"{pe_ratio}")
        c_m3.metric("Volatilidad Anualizada", f"{volatilidad_anual:.2%}")
        c_m4.metric("Margen Beneficio Neto", f"{margin_str}")

        c_m5, c_m6, c_m7, c_m8 = st.columns(4)
        c_m5.metric(
            f"Cap. de Mercado ({simb})",
            f"{simb} {market_cap:,.0f}" if market_cap else "N/A",
        )
        c_m6.metric("Ratio P/B", f"{pb_ratio}")
        c_m7.metric("Rendimiento Dividendo", f"{dividend_str}")
        c_m8.metric("VaR 95% (Pérdida Máx. Diaria)", f"{var_95:.2%}")

        st.markdown("---")

        # --- MOSTRAR GRÁFICO PLOTLY DE INMEDIATO ---
        st.markdown(
            "### 📈 Comportamiento Histórico & Proyección Econométrica"
            f" ({horizonte})"
        )

        dias_proy = (
            60
            if "1 a 3 meses" in horizonte
            else (180 if "6 meses a 1 año" in horizonte else 365)
        )

        np.random.seed(42)
        cambios_simulados = np.random.normal(
            retorno_medio_diario, df["Retorno_Diario"].std(), dias_proy
        )
        precios_futuros = [precio_actual]
        for cambio in cambios_simulados:
          precios_futuros.append(precios_futuros[-1] * (1 + cambio))

        fechas_hist = df.index[-90:]
        precios_hist = df["Close_Moneda"].tail(90)
        fechas_futuras = pd.date_range(
            start=df.index[-1], periods=dias_proy + 1, freq="B"
        )

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=fechas_hist,
                y=precios_hist,
                mode="lines",
                name="Histórico Reciente (Real)",
                line=dict(color="#00e676", width=2.5),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=fechas_futuras,
                y=precios_futuros,
                mode="lines",
                name="Proyección Econométrica",
                line=dict(color="#e040fb", width=2.5, dash="dash"),
            )
        )

        fig.update_layout(
            title=dict(
                text=f"Trayectoria de Cotización Estimada - {ticker_final}",
                font=dict(size=16, color="#f9fafb"),
            ),
            xaxis=dict(
                title="Fecha / Periodo de Proyección", gridcolor="#1f2937"
            ),
            yaxis=dict(title=f"Precio del Activo ({simb})", gridcolor="#1f2937"),
            template="plotly_dark",
            paper_bgcolor="#111827",
            plot_bgcolor="#111827",
            height=480,
            hovermode="x unified",
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(17,24,39,0.8)",
            ),
        )

        st.plotly_chart(fig, use_container_width=True)

        # --- AVISO LEGAL DEBAJO DEL GRÁFICO ---
        st.markdown(
            """
            <div class="disclaimer-box">
                <strong>⚠️ Aviso Legal / Descargo de Responsabilidad:</strong> 
                Este modelo genera pronósticos estadísticos basándose strictly en datos pasados y condiciones actuales de mercado. 
                No es 100% exacto y está expuesto a la volatilidad implícita, eventos macroeconómicos imprevistos y riesgos sistémicos. 
                Las proyecciones no constituyen una garantía de rendimiento ni una recomendación directa de compra o venta.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

    except Exception as e:
      st.error(f"Error procesando métricas financieras: {str(e)}")

    # 2. PASO DE INTELIGENCIA ARTIFICIAL CON SPINNER DEDICADO
    if datos_cargados:
      st.markdown(
          "## 📋 Dictamen Estratégico de Inversión", unsafe_allow_html=True
      )

      paquete_analisis = f"""
      Activo: {ticker_final} ({nombre_empresa}) | Sector: {sector}
      Precio Actual: {simb} {precio_actual:,.2f}
      Capital disponible: {simb} {capital_input:,.2f}
      Moneda: {moneda_sel} | Horizonte: {horizonte} | Perfil: {perfil_riesgo}
      
      MÉTRICAS FUNDAMENTALES:
      - PER: {pe_ratio} | P/B: {pb_ratio} | Dividend Yield: {dividend_str} | Margen Beneficio: {margin_str}
      
      MÉTRICAS DE RIESGO:
      - Volatilidad Anualizada: {volatilidad_anual:.2%}
      - VaR 95%: {var_95:.2%}
      - Media Móvil 50d: {simb} {sma_50:,.2f} | Media Móvil 200d: {simb} {sma_200:,.2f}
      """

      prompt_ia = f"""
      Actúa como un Director de Análisis Cuantitativo y Gestor de Portafolios Financieros.
      Redacta un dictamen ejecutivo profesional utilizando el siguiente formato exacto:

      {paquete_analisis}

      INSTRUCCIONES DE FORMATO:
      Proporciona el análisis dividido estrictamente en estas 4 secciones numeradas:

      ### 1. Diagnóstico Fundamental y Técnico
      [Análisis conciso de valoración y Medias Móviles]

      ### 2. Viabilidad del Capital y Horizonte
      [Análisis técnico sobre la suficiencia del capital {simb} {capital_input:,.2f} y la alineación del perfil]

      ### 3. Factores de Riesgo Macro
      [Tres puntos ejecutivos concretos]

      ### 4. Veredicto Estratégico
      Recomendación: [Escribe exactamente COMPRAR, DESESTIMAR o MANTENER EN OBSERVACIÓN]
      Fundamento: [Justificación corta]
      """

      with st.spinner("🤖 Generando dictamen estratégico con Inteligencia Artificial (Gemini)..."):
        try:
          informe_raw = generar_respuesta_ia_rapida(client, prompt_ia)

          # Badge dinámico según veredicto
          badge_html = ""
          informe_upper = informe_raw.upper()
          if "COMPRAR" in informe_upper and "DESESTIMAR" not in informe_upper:
            badge_html = "<div class='verdict-badge-comprar'>🟢 RECOMENDACIÓN: COMPRAR</div>"
          elif "DESESTIMAR" in informe_upper:
            badge_html = "<div class='verdict-badge-desestimar'>🔴 RECOMENDACIÓN: DESESTIMAR</div>"
          else:
            badge_html = "<div class='verdict-badge-observacion'>🟡 RECOMENDACIÓN: MANTENER EN OBSERVACIÓN</div>"

          st.markdown(
              f"<div style='margin-bottom: 15px;'>{badge_html}</div>",
              unsafe_allow_html=True,
          )

          st.markdown(
              f"<div class='report-card'>{informe_raw}</div>",
              unsafe_allow_html=True,
          )

        except Exception as e_ia:
          st.error(f"Error al generar el dictamen de IA: {str(e_ia)}")
