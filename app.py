import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Configuración de la página
st.set_page_config(page_title="Consultor de Inversión IA", layout="wide")

st.title("📊 Consultor de Inversión Multi-Activo")
st.write("Selecciona una empresa del listado para ver su análisis detallado.")

# 1. Lista de empresas a analizar
TICKERS_DEFAULT = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "TSLA", "META"]

@st.cache_data(ttl=3600)
def analizar_empresa(symbol):
    try:
        df = yf.download(symbol, period="1y", interval="1d", progress=False)
        if df.empty:
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
        
        # Algoritmo de Confianza y Horizonte
        confianza = 50
        
        if rsi_actual < 30:
            confianza += 25
        elif rsi_actual > 70:
            confianza -= 20
            
        if precio_actual > sma20:
            confianza += 15
        if sma20 > sma50:
            confianza += 10
            
        confianza = max(10, min(99, confianza))
        
        # Horizonte de inversión
        volatilidad = float(df['Close'].pct_change().std() * 100)
        horizonte = "Corto Plazo (Trading)" if volatilidad > 2.0 else "Largo Plazo (Inversión)"
        
        # Precios Ideales
        precio_compra_ideal = precio_actual * 0.98  # Recompra un 2% abajo
        precio_venta_ideal = precio_actual * (1.12 if horizonte.startswith("Largo") else 1.05)
        
        return {
            "Symbol": symbol,
            "Precio Actual": round(precio_actual, 2),
            "Confianza IA (%)": confianza,
            "Horizonte": horizonte,
            "Precio Compra Ideal": round(precio_compra_ideal, 2),
            "Precio Venta Objetivo": round(precio_venta_ideal, 2),
            "DF": df
        }
    except Exception as e:
        return None

# Cargar análisis de todas las empresas
resultados = []
datos_graficas = {}

for ticker in TICKERS_DEFAULT:
    res = analizar_empresa(ticker)
    if res:
        datos_graficas[ticker] = res["DF"]
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

# --- VISTA 2: DETALLE DE LA EMPRESA SELECCIONADA ---
st.subheader("🔍 Análisis Detallado de Empresa")

empresa_seleccionada = st.selectbox(
    "Selecciona una empresa para ver sus gráficas y estrategia:",
    options=[r["Empresa"] for r in resultados]
)

if empresa_seleccionada:
    # Obtener datos de la empresa elegida
    info = next(item for item in resultados if item["Empresa"] == empresa_seleccionada)
    df_empresa = datos_graficas[empresa_seleccionada]
    
    # Métricas destacadas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Precio Actual", f"${info['Precio ($)']}")
    col2.metric("Confianza IA", info["Confianza IA"])
    col3.metric("Precio Compra Ideal", f"${info['Compra Ideal ($)']}")
    col4.metric("Precio Venta Objetivo", f"${info['Objetivo Venta ($)']}")
    
    st.info(f"📌 **Estrategia Recomendada:** {info['Horizonte']}")
    
    # Gráfica interactiva de precios y Medias Móviles
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
