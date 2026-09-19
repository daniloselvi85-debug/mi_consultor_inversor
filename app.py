import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Configuración de la página
st.set_page_config(page_title="Consultor de Inversión IA", layout="wide")

st.title("📊 Consultor de Inversión con Buscador e IA")
st.write("Analiza empresas del mercado en tiempo real y consulta los motivos de la recomendación.")

# 1. Buscador de Empresas personalizable
st.sidebar.header("🔍 Buscador de Activos")
ticker_busqueda = st.sidebar.text_input("Introduce un Ticker (Ej: AAPL, TSLA, AMD, BABA):", value="").upper().strip()

TICKERS_BASE = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "TSLA", "META"]

if ticker_busqueda and ticker_busqueda not in TICKERS_BASE:
    TICKERS_LISTA = [ticker_busqueda] + TICKERS_BASE
else:
    TICKERS_LISTA = TICKERS_BASE

@st.cache_data(ttl=1800)
def analizar_empresa(symbol):
    try:
        ticker_obj = yf.Ticker(symbol)
        df = ticker_obj.history(period="1y", interval="1d")
        
        if df.empty or len(df) < 50:
            return None
        
        # Aplanar columnas si yfinance devuelve MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Indicadores técnicos
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        precio_actual = float(df['Close'].iloc[-1])
        rsi_actual = float(df['RSI'].iloc[-1])
        sma20 = float(df['SMA_20'].iloc[-1])
        sma50 = float(df['SMA_50'].iloc[-1])
        
        # Algoritmo de Confianza y Generación de Motivos
        confianza = 50
        motivos = []
        
        if rsi_actual < 30:
            confianza += 25
            motivos.append(f"🟢 **Sobrevendida (RSI {rsi_actual:.1f}):** El activo está en niveles muy bajos, lo que suele preceder un rebot a la alza.")
        elif rsi_actual > 70:
            confianza -= 20
            motivos.append(f"🔴 **Sobrecomprada (RSI {rsi_actual:.1f}):** El precio ha subido demasiado rápido y podría corregir a corto plazo.")
        else:
            motivos.append(f"🟡 **RSI Neutro ({rsi_actual:.1f}):** Muestra estabilidad sin presión extrema de compra o venta.")
            
        if precio_actual > sma20:
            confianza += 15
            motivos.append("🟢 **Tendencia Corto Plazo:** Cotiza por encima de la media móvil de 20 días (fuerza compradora).")
        else:
            motivos.append("🔴 **Debilidad Corto Plazo:** Cotiza por debajo de la media móvil de 20 días.")

        if sma20 > sma50:
            confianza += 10
            motivos.append("🟢 **Cruce Alcista:** La tendencia de medio plazo es positiva (Media 20 > Media 50).")
            
        confianza = max(10, min(99, confianza))
        
        # Horizonte de inversión
        volatilidad = float(df['Close'].pct_change().std() * 100)
        horizonte = "Corto Plazo (Trading)" if volatilidad > 2.2 else "Largo Plazo (Inversión)"
        
        # Precios Ideales
        precio_compra_ideal = precio_actual * 0.98
        precio_venta_ideal = precio_actual * (1.12 if horizonte.startswith("Largo") else 1.05)
        
        return {
            "Symbol": symbol,
            "Precio Actual": round(precio_actual, 2),
            "Confianza IA (%)": confianza,
            "Horizonte": horizonte,
            "Precio Compra Ideal": round(precio_compra_ideal, 2),
            "Precio Venta Objetivo": round(precio_venta_ideal, 2),
            "Motivos": motivos,
            "DF": df
        }
    except Exception:
        return None

# Procesar análisis
resultados = []
datos_empresas = {}

for ticker in TICKERS_LISTA:
    res = analizar_empresa(ticker)
    if res:
        datos_empresas[ticker] = res
        resultados.append({
            "Empresa": res["Symbol"],
            "Precio ($)": res["Precio Actual"],
            "Confianza IA": f"{res['Confianza IA (%)']}%",
            "Horizonte": res["Horizonte"],
            "Compra Ideal ($)": res["Precio Compra Ideal"],
            "Objetivo Venta ($)": res["Precio Venta Objetivo"]
        })

df_resumen = pd.DataFrame(resultados)

# --- VISTA 1: TABLA GENERAL DE EMPRESAS ---
st.subheader("💡 Oportunidades del Mercado")
st.dataframe(df_resumen, use_container_width=True)

st.markdown("---")

# --- VISTA 2: DETALLE Y DICTAMEN DE LA EMPRESA SELECCIONADA ---
st.subheader("🔍 Análisis Detallado y Motivos de la Opinión")

empresa_seleccionada = st.selectbox(
    "Selecciona una empresa para analizar a fondo:",
    options=[r["Empresa"] for r in resultados],
    index=0 if ticker_busqueda == "" else 0
)

if empresa_seleccionada and empresa_seleccionada in datos_empresas:
    info = datos_empresas[empresa_seleccionada]
    df_empresa = info["DF"]
    
    # Métricas destacadas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Precio Actual", f"${info['Precio Actual']}")
    col2.metric("Confianza IA", f"{info['Confianza IA (%)']}%")
    col3.metric("Precio Compra Ideal", f"${info['Precio Compra Ideal']}")
    col4.metric("Precio Venta Objetivo", f"${info['Precio Venta Objetivo']}")
    
    st.info(f"📌 **Estrategia Recomendada:** {info['Horizonte']}")
    
    # Módulo de Motivos de la Opinión
    st.markdown("### 📝 Motivos y Fundamentos de la Opinión de la IA")
    for motivo in info["Motivos"]:
        st.markdown(f"- {motivo}")
    
    # Gráfica interactiva de precios
    st.markdown("### 📈 Gráfico de Precios e Indicadores")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_empresa.index,
        open=df_empresa['Open'],
        high=df_empresa['High'],
        low=df_empresa['Low'],
        close=df_empresa['Close'],
        name="Precio"
    ))
    fig.add_trace(go.Scatter(x=df_empresa.index, y=df_empresa['SMA_20'], name="Media Móvil 20", line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=df_empresa.index, y=df_empresa['SMA_50'], name="Media Móvil 50", line=dict(color='blue')))
    
    fig.update_layout(
        title=f"Evolución Histórica y Medias Móviles de {empresa_seleccionada}",
        xaxis_title="Fecha",
        yaxis_title="Precio ($)",
        template="plotly_dark",
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)
