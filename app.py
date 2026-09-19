import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Configuración de la página
st.set_page_config(page_title="Consultor de Inversión IA", layout="wide")

st.title("📊 Consultor de Inversión Personal")
st.write("Consulta oportunidades del mercado o busca libremente cualquier empresa para recibir el análisis de la IA.")

# Lista base para la tabla resumen de mercado
TICKERS_MERCADO = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "TSLA", "META"]

@st.cache_data(ttl=1800)
def analizar_empresa(symbol):
    try:
        ticker_obj = yf.Ticker(symbol)
        df = ticker_obj.history(period="1y", interval="1d")
        
        if df.empty or len(df) < 30:
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
            motivos.append(f"🟢 **Sobrevendida (RSI {rsi_actual:.1f}):** El activo cotiza en mínimos recientes, lo que históricamente favorece un rebote a la alza.")
        elif rsi_actual > 70:
            confianza -= 20
            motivos.append(f"🔴 **Sobrecomprada (RSI {rsi_actual:.1f}):** Subida acelerada en poco tiempo; existe riesgo de corrección técnica.")
        else:
            motivos.append(f"🟡 **RSI Equilibrado ({rsi_actual:.1f}):** El precio se mueve en rangos de consolidación sin presión extrema.")
            
        if precio_actual > sma20:
            confianza += 15
            motivos.append("🟢 **Fuerza a Corto Plazo:** El precio está por encima de la media de 20 días, indicando impulso comprador.")
        else:
            motivos.append("🔴 **Debilidad a Corto Plazo:** Cotiza por debajo de su media de 20 días.")

        if sma20 > sma50:
            confianza += 10
            motivos.append("🟢 **Estructura Alcista:** La tendencia de medio plazo es positiva (Media 20 > Media 50).")
        else:
            motivos.append("🔴 **Estructura Bajista:** Tendencia de medio plazo debilitada.")
            
        confianza = max(10, min(99, confianza))
        
        # Horizonte de inversión
        volatilidad = float(df['Close'].pct_change().std() * 100)
        horizonte = "Corto Plazo (Trading)" if volatilidad > 2.0 else "Largo Plazo (Inversión)"
        
        # Precios Ideales
        precio_compra_ideal = precio_actual * 0.98
        precio_venta_ideal = precio_actual * (1.12 if horizonte.startswith("Largo") else 1.05)
        
        return {
            "Symbol": symbol.upper(),
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

# --- VISTA 1: TABLA RESUMEN DE MERCADO ---
st.subheader("💡 Oportunidades Destacadas del Mercado")

resultados_mercado = []
for ticker in TICKERS_MERCADO:
    res = analizar_empresa(ticker)
    if res:
        resultados_mercado.append({
            "Empresa": res["Symbol"],
            "Precio ($)": res["Precio Actual"],
            "Confianza IA": f"{res['Confianza IA (%)']}%",
            "Horizonte": res["Horizonte"],
            "Compra Ideal ($)": res["Precio Compra Ideal"],
            "Objetivo Venta ($)": res["Precio Venta Objetivo"]
        })

st.dataframe(pd.DataFrame(resultados_mercado), use_container_width=True)

st.markdown("---")

# --- VISTA 2: BUSCADOR LIBRE Y ANÁLISIS EXCLUSIVO ---
st.subheader("🔍 Buscador Libre de Empresas")
st.write("Escribe el ticker de cualquier empresa global (Ej: `TSLA`, `AMD`, `SAN.MC`, `PLTR`, `BABA`) para analizarla al instante:")

col_input, col_select = st.columns([2, 2])

with col_input:
    ticker_libre = st.text_input("Escribe cualquier símbolo/ticker:", value="").strip().upper()

with col_select:
    empresa_desplegable = st.selectbox(
        "O selecciona una de la tabla destacada:",
        options=["(Usar búsqueda de texto)"] + TICKERS_MERCADO
    )

# Determinar qué empresa analizar
empresa_a_consultar = None
if ticker_libre:
    empresa_a_consultar = ticker_libre
elif empresa_desplegable != "(Usar búsqueda de texto)":
    empresa_a_consultar = empresa_desplegable
else:
    empresa_a_consultar = "AAPL" # Por defecto

# Ejecutar análisis de la empresa seleccionada o buscada
analisis = analizar_empresa(empresa_a_consultar)

if analisis:
    st.markdown(f"## 📌 Dictamen de IA para **{analisis['Symbol']}**")
    
    # Métricas principales
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Precio Actual", f"${analisis['Precio Actual']}")
    c2.metric("Confianza IA", f"{analisis['Confianza IA (%)']}%")
    c3.metric("Precio Compra Ideal", f"${analisis['Precio Compra Ideal']}")
    c4.metric("Precio Venta Objetivo", f"${analisis['Precio Venta Objetivo']}")
    
    st.info(f"🎯 **Perfil Sugerido:** {analisis['Horizonte']}")
    
    # Resumen y motivos de la opinión
    st.markdown("### 📝 Motivos de la Recomendación")
    for m in analisis["Motivos"]:
        st.markdown(f"- {m}")
        
    # Gráfico interactivo
    st.markdown("### 📈 Gráfico Técnico e Indicadores")
    df_chart = analisis["DF"]
    
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_chart.index, open=df_chart['Open'], high=df_chart['High'],
        low=df_chart['Low'], close=df_chart['Close'], name="Precio"
    ))
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA_20'], name="Media Móvil 20", line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA_50'], name="Media Móvil 50", line=dict(color='blue')))
    
    fig.update_layout(
        title=f"Evolución Histórica de {analisis['Symbol']}",
        xaxis_title="Fecha", yaxis_title="Precio ($)",
        template="plotly_dark", height=450
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error(f"❌ No se pudieron obtener datos para el ticker **'{empresa_a_consultar}'**. Asegúrate de que el código es correcto (ejemplo: `TSLA` para Tesla, `SAN.MC` para Banco Santander).")
