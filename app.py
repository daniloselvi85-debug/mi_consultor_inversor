"""
Dashboard Financiero de Inversión
----------------------------------
Requisitos (instalar con pip):
    pip install streamlit yfinance pandas numpy plotly

Ejecutar con:
    streamlit run dashboard_financiero.py
"""

import os
import json
from datetime import datetime, date

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================
st.set_page_config(
    page_title="Dashboard Financiero",
    page_icon="📈",
    layout="wide",
)

DECISIONS_FILE = "decisiones_historicas.csv"

# =========================================================
# UTILIDADES DE DATOS
# =========================================================

@st.cache_data(ttl=300, show_spinner=False)
def cargar_datos(ticker: str, periodo: str, intervalo: str) -> pd.DataFrame:
    """Descarga datos históricos desde yfinance."""
    df = yf.download(ticker, period=periodo, interval=intervalo, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna()
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def obtener_info_empresa(ticker: str) -> dict:
    """Obtiene información básica de la empresa."""
    try:
        info = yf.Ticker(ticker).info
        return info
    except Exception:
        return {}


def calcular_rsi(serie_precios: pd.Series, periodo: int = 14) -> pd.Series:
    """Calcula el RSI (Relative Strength Index)."""
    delta = serie_precios.diff()
    ganancia = delta.where(delta > 0, 0.0)
    perdida = -delta.where(delta < 0, 0.0)

    media_ganancia = ganancia.rolling(window=periodo, min_periods=periodo).mean()
    media_perdida = perdida.rolling(window=periodo, min_periods=periodo).mean()

    rs = media_ganancia / media_perdida.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)  # valor neutro donde no hay datos suficientes
    return rsi


def calcular_indicadores(df: pd.DataFrame, sma_corta: int = 20, sma_larga: int = 50) -> pd.DataFrame:
    """Agrega SMA cortas/largas y RSI al DataFrame."""
    df = df.copy()
    df["SMA_corta"] = df["Close"].rolling(window=sma_corta).mean()
    df["SMA_larga"] = df["Close"].rolling(window=sma_larga).mean()
    df["RSI"] = calcular_rsi(df["Close"], 14)
    return df


def calcular_confianza(df: pd.DataFrame) -> dict:
    """
    Heurística simple para estimar un puntaje de 'confianza/probabilidad de éxito'
    (0 a 100) combinando RSI, cruce de medias móviles y tendencia de precio.

    IMPORTANTE: esto es un indicador técnico orientativo, no una predicción
    garantizada ni asesoramiento financiero.
    """
    if df.empty or df["RSI"].isna().all() or df["SMA_larga"].isna().all():
        return {"score": 50, "señal": "Datos insuficientes", "detalle": []}

    ultimo = df.iloc[-1]
    detalle = []
    score = 50  # punto neutro

    # --- Componente RSI ---
    rsi_valor = ultimo["RSI"]
    if rsi_valor < 30:
        score += 15
        detalle.append(f"RSI en sobreventa ({rsi_valor:.1f}) → señal alcista")
    elif rsi_valor > 70:
        score -= 15
        detalle.append(f"RSI en sobrecompra ({rsi_valor:.1f}) → señal bajista")
    else:
        detalle.append(f"RSI neutro ({rsi_valor:.1f})")

    # --- Componente cruce de medias móviles ---
    if pd.notna(ultimo["SMA_corta"]) and pd.notna(ultimo["SMA_larga"]):
        if ultimo["SMA_corta"] > ultimo["SMA_larga"]:
            score += 15
            detalle.append("Media corta por encima de la larga (tendencia alcista)")
        else:
            score -= 15
            detalle.append("Media corta por debajo de la larga (tendencia bajista)")

        # cruce reciente (golden/death cross en los últimos 5 periodos)
        if len(df) > 5:
            cruce_reciente = (
                df["SMA_corta"].iloc[-5:-1] - df["SMA_larga"].iloc[-5:-1]
            )
            if (cruce_reciente.iloc[0] < 0) and (ultimo["SMA_corta"] > ultimo["SMA_larga"]):
                score += 10
                detalle.append("Cruce dorado reciente detectado")
            elif (cruce_reciente.iloc[0] > 0) and (ultimo["SMA_corta"] < ultimo["SMA_larga"]):
                score -= 10
                detalle.append("Cruce de la muerte reciente detectado")

    # --- Componente tendencia de precio (últimos 10 periodos) ---
    if len(df) > 10:
        variacion = (df["Close"].iloc[-1] / df["Close"].iloc[-10] - 1) * 100
        if variacion > 3:
            score += 10
            detalle.append(f"Precio subió {variacion:.1f}% en los últimos 10 periodos")
        elif variacion < -3:
            score -= 10
            detalle.append(f"Precio bajó {variacion:.1f}% en los últimos 10 periodos")

    score = int(max(0, min(100, score)))

    if score >= 70:
        señal = "Confianza alta (alcista)"
    elif score >= 55:
        señal = "Confianza moderada-alta"
    elif score >= 45:
        señal = "Neutral"
    elif score >= 30:
        señal = "Confianza moderada-baja"
    else:
        señal = "Confianza baja (bajista)"

    return {"score": score, "señal": señal, "detalle": detalle}


# =========================================================
# REGISTRO DE DECISIONES HISTÓRICAS
# =========================================================

def cargar_decisiones() -> pd.DataFrame:
    columnas = ["Fecha", "Ticker", "Acción", "Precio", "Cantidad", "Confianza", "Notas"]
    if os.path.exists(DECISIONS_FILE):
        try:
            return pd.read_csv(DECISIONS_FILE)
        except Exception:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)


def guardar_decision(nueva_fila: dict):
    df = cargar_decisiones()
    df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
    df.to_csv(DECISIONS_FILE, index=False)


# =========================================================
# INTERFAZ - SIDEBAR
# =========================================================

st.sidebar.title("⚙️ Configuración")

ticker_input = st.sidebar.text_input(
    "🔍 Buscar acción (ticker)", value="AAPL", help="Ej: AAPL, MSFT, TSLA, GOOGL, AMZN"
).upper().strip()

periodo = st.sidebar.selectbox(
    "Periodo histórico",
    ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
    index=3,
)

intervalo = st.sidebar.selectbox(
    "Intervalo",
    ["1d", "1wk", "1mo"],
    index=0,
)

sma_corta = st.sidebar.slider("Media móvil corta (periodos)", 5, 50, 20)
sma_larga = st.sidebar.slider("Media móvil larga (periodos)", 20, 200, 50)

st.sidebar.markdown("---")
st.sidebar.caption(
    "⚠️ Este panel es una herramienta de análisis técnico educativo. "
    "No constituye asesoramiento financiero."
)

# =========================================================
# CUERPO PRINCIPAL
# =========================================================

st.title("📈 Dashboard Financiero de Inversión")

if not ticker_input:
    st.info("Ingresa un ticker en la barra lateral para comenzar.")
    st.stop()

with st.spinner(f"Cargando datos de {ticker_input}..."):
    df = cargar_datos(ticker_input, periodo, intervalo)
    info = obtener_info_empresa(ticker_input)

if df.empty:
    st.error(f"No se encontraron datos para el ticker '{ticker_input}'. Verifica que sea correcto.")
    st.stop()

df = calcular_indicadores(df, sma_corta, sma_larga)
confianza = calcular_confianza(df)

# --- Encabezado con info de la empresa ---
nombre_empresa = info.get("longName", ticker_input)
moneda = info.get("currency", "")
precio_actual = df["Close"].iloc[-1]
variacion_dia = df["Close"].iloc[-1] - df["Close"].iloc[-2] if len(df) > 1 else 0
variacion_pct = (variacion_dia / df["Close"].iloc[-2] * 100) if len(df) > 1 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Empresa", nombre_empresa)
col2.metric(
    f"Precio actual ({moneda})",
    f"{precio_actual:,.2f}",
    f"{variacion_dia:+.2f} ({variacion_pct:+.2f}%)",
)
col3.metric("RSI actual", f"{df['RSI'].iloc[-1]:.1f}")
col4.metric("Confianza técnica", f"{confianza['score']} / 100", confianza["señal"])

st.markdown("---")

# --- Gráfico de precios con velas + medias móviles ---
st.subheader("Gráfico de precios")

fig_precio = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
    row_heights=[0.7, 0.3],
    subplot_titles=("Precio y medias móviles", "RSI (14 periodos)"),
)

fig_precio.add_trace(
    go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Precio",
    ),
    row=1, col=1,
)
fig_precio.add_trace(
    go.Scatter(x=df.index, y=df["SMA_corta"], name=f"SMA {sma_corta}", line=dict(width=1.5)),
    row=1, col=1,
)
fig_precio.add_trace(
    go.Scatter(x=df.index, y=df["SMA_larga"], name=f"SMA {sma_larga}", line=dict(width=1.5)),
    row=1, col=1,
)

# RSI
fig_precio.add_trace(
    go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="purple")),
    row=2, col=1,
)
fig_precio.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
fig_precio.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

fig_precio.update_layout(
    height=700,
    xaxis_rangeslider_visible=False,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
fig_precio.update_yaxes(title_text="Precio", row=1, col=1)
fig_precio.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)

st.plotly_chart(fig_precio, use_container_width=True)

# --- Indicador de confianza (gauge) ---
st.subheader("Indicador de confianza / probabilidad de éxito")

col_gauge, col_detalle = st.columns([1, 1.2])

with col_gauge:
    fig_gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=confianza["score"],
            title={"text": confianza["señal"]},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "black"},
                "steps": [
                    {"range": [0, 30], "color": "#e74c3c"},
                    {"range": [30, 45], "color": "#f39c12"},
                    {"range": [45, 55], "color": "#f1c40f"},
                    {"range": [55, 70], "color": "#a3e635"},
                    {"range": [70, 100], "color": "#2ecc71"},
                ],
            },
        )
    )
    fig_gauge.update_layout(height=320, margin=dict(t=40, b=10))
    st.plotly_chart(fig_gauge, use_container_width=True)

with col_detalle:
    st.markdown("**Factores considerados:**")
    for punto in confianza["detalle"]:
        st.write(f"- {punto}")
    st.caption(
        "Este puntaje combina RSI, cruces de medias móviles y tendencia reciente de "
        "precio. Es un indicador técnico orientativo, no una garantía de resultados."
    )

st.markdown("---")

# =========================================================
# REGISTRO DE DECISIONES HISTÓRICAS
# =========================================================

st.subheader("📝 Registro de decisiones de inversión")

with st.form("form_decision", clear_on_submit=True):
    fc1, fc2, fc3 = st.columns(3)
    fecha_decision = fc1.date_input("Fecha", value=date.today())
    accion = fc2.selectbox("Acción", ["Comprar", "Vender", "Mantener"])
    cantidad = fc3.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0)

    fc4, fc5 = st.columns(2)
    precio_decision = fc4.number_input(
        "Precio de referencia", min_value=0.0, value=float(round(precio_actual, 2)), step=0.01
    )
    notas = fc5.text_input("Notas (opcional)")

    enviado = st.form_submit_button("Guardar decisión")
    if enviado:
        guardar_decision({
            "Fecha": fecha_decision.isoformat(),
            "Ticker": ticker_input,
            "Acción": accion,
            "Precio": precio_decision,
            "Cantidad": cantidad,
            "Confianza": confianza["score"],
            "Notas": notas,
        })
        st.success("Decisión guardada correctamente.")

df_decisiones = cargar_decisiones()

if not df_decisiones.empty:
    filtrar_ticker_actual = st.checkbox(f"Mostrar solo decisiones de {ticker_input}", value=False)
    tabla_mostrar = (
        df_decisiones[df_decisiones["Ticker"] == ticker_input]
        if filtrar_ticker_actual else df_decisiones
    )
    st.dataframe(
        tabla_mostrar.sort_values("Fecha", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    csv_bytes = df_decisiones.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Descargar historial completo (CSV)",
        data=csv_bytes,
        file_name="decisiones_historicas.csv",
        mime="text/csv",
    )
else:
    st.info("Aún no hay decisiones registradas. Usa el formulario de arriba para agregar la primera.")
