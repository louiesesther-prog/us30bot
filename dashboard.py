import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# --- 1. DASHBOARD CONFIG ---
st.set_page_config(page_title="US30 Quant Bot - Spike Tracker", layout="wide")
st.title("📊 US30 (YM=F) 15m Volume Spike Analysis")

# --- 2. DATA FETCHING ---
@st.cache_data(ttl=900)
def get_clean_data():
    ticker = 'YM=F'
    # Download 60 days of 15m data
    raw_data = yf.download(tickers=ticker, period='60d', interval='15m')
    
    # Flatten MultiIndex if it exists
    if isinstance(raw_data.columns, pd.MultiIndex):
        raw_data.columns = raw_data.columns.get_level_values(0)
    
    # Reset index to move the Date/Time into a column
    df_working = raw_data.reset_index()
    
    # FORCE Rename the first column to 'timestamp' no matter what it is called
    df_working.columns.values[0] = 'timestamp'
    
    # Standardize all column names to lowercase
    df_working.columns = [str(col).lower() for col in df_working.columns]
    
    # Ensure timestamp is actually a datetime object
    df_working['timestamp'] = pd.to_datetime(df_working['timestamp'])
    
    # Clean volume data
    df_working['volume'] = pd.to_numeric(df_working['volume'], errors='coerce').fillna(0)
    
    return df_working

# --- 3. PATTERN LOGIC ---
try:
    # We call the function and assign it to 'df'
    df = get_clean_data()
    
    # DOUBLE CHECK: If for some reason 'timestamp' isn't there, force it again
    if 'timestamp' not in df.columns:
        df.rename(columns={df.columns[0]: 'timestamp'}, inplace=True)

    # Calculate Volume Spike (Z-Score)
    df['vol_mean'] = df['volume'].rolling(window=20).mean()
    df['vol_std'] = df['volume'].rolling(window=20).std()
    df['z_score'] = (df['volume'] - df['vol_mean']) / df['vol_std']
    
    # Filter for Non-US Sessions (00:00 to 09:00 EST)
    df['hour'] = df['timestamp'].dt.hour
    df['is_non_us'] = df['hour'].between(0, 8)
    
    # Sidebar Controls
    st.sidebar.header("Strategy Settings")
    z_thresh = st.sidebar.slider("Spike Sensitivity (Z-Score)", 2.0, 7.0, 3.5)
    
    # Identify Spikes
    df['spike_detected'] = (df['z_score'] > z_thresh) & (df['is_non_us'])
    spikes_df = df[df['spike_detected']].copy()

    # --- 4. DISPLAY DASHBOARD ---
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader("15-Minute Candlestick Chart")
        fig = go.Figure(data=[go.Candlestick(
            x=df['timestamp'],
            open=df['open'], high=df['high'],
            low=df['low'], close=df['close'],
            name="US30"
        )])

        fig.add_trace(go.Scatter(
            x=spikes_df['timestamp'],
            y=spikes_df['high'] * 1.002,
            mode='markers',
            marker=dict(color='#FFD700', size=12, symbol='triangle-down'),
            name="Institutional Spike"
        ))

        fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=600)
        st.plotly_chart(fig, width="stretch")

    with col2:
        st.subheader("🕒 Spike History")
        if not spikes_df.empty:
            # Create helper columns for the display
            spikes_df['Time'] = spikes_df['timestamp'].dt.strftime('%H:%M')
            spikes_df['Date'] = spikes_df['timestamp'].dt.strftime('%Y-%m-%d')
            
            st.dataframe(
                spikes_df[['Date', 'Time', 'z_score']].sort_values(by='Date', ascending=False),
                width="stretch",
                height=550
            )
        else:
            st.warning("No spikes found. Try lowering Z-Score.")

    # --- 5. UNIFORMITY ANALYSIS ---
    st.divider()
    if not spikes_df.empty:
        st.subheader("📈 Time Uniformity (Seasonal Patterns)")
        pattern_freq = spikes_df.groupby('Time').size().reset_index(name='Occurrences')
        st.bar_chart(pattern_freq, x='Time', y='Occurrences', color="#FFD700")

except Exception as e:
    # This will print the EXACT column names if it fails again
    st.error(f"Error: {e}")
    if 'df' in locals():
        st.write("Columns found in data:", df.columns.tolist())