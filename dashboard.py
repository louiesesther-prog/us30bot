import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# --- 1. DASHBOARD CONFIG ---
st.set_page_config(page_title="US30 Quant Bot", layout="wide")
st.title("📊 US30 (YM=F) 15m Analysis")

# --- 2. DATA FETCHING ---
@st.cache_data(ttl=600)  # Refresh every 10 mins
def get_clean_data():
    # 'YM=F' is the Dow Futures - more reliable volume than '^DJI'
    ticker = 'YM=F'
    df_raw = yf.download(tickers=ticker, period='60d', interval='15m')
    
    if df_raw.empty:
        return pd.DataFrame()

    # Flatten MultiIndex headers
    if isinstance(df_raw.columns, pd.MultiIndex):
        df_raw.columns = df_raw.columns.get_level_values(0)
    
    df = df_raw.reset_index()
    
    # Force rename the first column to timestamp
    df.columns.values[0] = 'timestamp'
    # Force lowercase for all column names
    df.columns = [str(col).lower() for col in df.columns]
    
    # Ensure timestamp is datetime and volume is numeric
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
    
    return df

# --- 3. PATTERN LOGIC ---
try:
    df = get_clean_data()

    if df.empty:
        st.error("No data received from Yahoo Finance. Check ticker or internet connection.")
    else:
        # Calculate Volume Spike (Z-Score)
        df['vol_mean'] = df['volume'].rolling(window=20).mean()
        df['vol_std'] = df['volume'].rolling(window=20).std()
        df['z_score'] = (df['volume'] - df['vol_mean']) / df['vol_std']
        
        # Sidebar Controls
        st.sidebar.header("Settings")
        z_thresh = st.sidebar.slider("Spike Sensitivity", 1.5, 7.0, 3.0)
        
        # Identify Spikes (Currently showing ALL sessions to verify data)
        df['spike_detected'] = df['z_score'] > z_thresh
        spikes_df = df[df['spike_detected']].copy()

        # --- 4. DISPLAY ---
        col1, col2 = st.columns([3, 1])

        with col1:
            st.subheader("15-Minute Candlestick Chart")
            fig = go.Figure(data=[go.Candlestick(
                x=df['timestamp'],
                open=df['open'], high=df['high'],
                low=df['low'], close=df['close'],
                name="US30"
            )])

            # Mark spikes
            fig.add_trace(go.Scatter(
                x=spikes_df['timestamp'],
                y=spikes_df['high'] * 1.001,
                mode='markers',
                marker=dict(color='#FFD700', size=10, symbol='triangle-down'),
                name="Volume Spike"
            ))

            fig.update_layout(
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                height=600,
                margin=dict(l=0, r=0, t=0, b=0)
            )
            # Use 'stretch' for 2026 Streamlit compatibility
            st.plotly_chart(fig, width="stretch")

        with col2:
            st.subheader("🕒 Spike Log")
            if not spikes_df.empty:
                spikes_df['time'] = spikes_df['timestamp'].dt.strftime('%H:%M')
                spikes_df['date'] = spikes_df['timestamp'].dt.strftime('%Y-%m-%d')
                
                st.dataframe(
                    spikes_df[['date', 'time', 'z_score']].sort_values(by='date', ascending=False),
                    width="stretch",
                    height=550
                )
            else:
                st.info("Adjust slider to see spikes.")

        # --- 5. UNIFORMITY ---
        st.divider()
        if not spikes_df.empty:
            st.subheader("📈 Time Frequency")
            pattern_freq = spikes_df.groupby('time').size().reset_index(name='occurrences')
            st.bar_chart(pattern_freq, x='time', y='occurrences', color="#FFD700")

except Exception as e:
    st.error(f"Logic Error: {e}")
