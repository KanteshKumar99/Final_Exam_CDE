import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import time
from datetime import datetime, timedelta
import os

# Set page configurations
st.set_page_config(
    page_title="IoT Environmental Sensor Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .metric-card {
        background-color: #1e222b;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
        margin-bottom: 20px;
    }
    .metric-header {
        font-size: 14px;
        color: #8a8f98;
        text-transform: uppercase;
        font-weight: bold;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #ffffff;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Auto-refresh setup
try:
    from streamlit_autorefresh import st_autorefresh
    # Refresh every 30 seconds
    st_autorefresh(interval=30 * 1000, key="data_refresh_trigger")
except ImportError:
    # Fallback message
    st.info("Autorefresh package not found. Rerun manually to fetch latest data.")

# Sidebar - Configuration and Connection Info
st.sidebar.title("🛠️ Settings & Connection")
use_mock_data = st.sidebar.checkbox("Use Simulated/Mock Data", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("Snowflake Config")
sf_account = st.sidebar.text_input("Account", value=os.getenv("SNOWFLAKE_ACCOUNT", ""))
sf_user = st.sidebar.text_input("User", value=os.getenv("SNOWFLAKE_USER", "KAFKA_CONNECTOR_USER"))
sf_warehouse = st.sidebar.text_input("Warehouse", value="IOT_WH")
sf_database = st.sidebar.text_input("Database", value="HACKATHON_IOT")

# Generate simulated dataset
def generate_mock_data():
    devices = [f"device_london_{i:03d}" for i in range(1, 6)]
    now = datetime.now()
    
    # Silver layer mock data (detailed log)
    silver_rows = []
    center_lat, center_lon = 51.5030, 0.0032
    
    for i in range(120): # past 2 hours
        timestamp = now - timedelta(minutes=i)
        for dev in devices:
            # Seed based on device name to keep coordinates consistent
            # Small offsets to place markers near O2 Arena
            idx = devices.index(dev)
            lat = center_lat + 0.0015 * np.sin(idx + i/30.0) + np.random.normal(0, 0.0001)
            lon = center_lon + 0.0025 * np.cos(idx + i/30.0) + np.random.normal(0, 0.0001)
            
            aqi = int(abs(np.sin(i/10.0 + idx) * 100 + 40 + np.random.normal(0, 10)))
            temp = float(18.0 + np.cos(i/15.0) * 5 + np.random.normal(0, 0.3))
            
            # Severity
            if aqi <= 50: aqi_sev = "Good"
            elif aqi <= 100: aqi_sev = "Moderate"
            elif aqi <= 150: aqi_sev = "Unhealthy for Sensitive Groups"
            else: aqi_sev = "Unhealthy"
            
            silver_rows.append({
                "EVENT_ID": i * 10 + idx,
                "DEVICE_ID": dev,
                "LATITUDE": lat,
                "LONGITUDE": lon,
                "AQI": aqi,
                "TEMPERATURE": round(temp, 2),
                "EVENT_TIMESTAMP": timestamp,
                "EVENT_DATE": timestamp.date(),
                "AQI_SEVERITY": aqi_sev
            })
            
    df_silver = pd.DataFrame(silver_rows)
    
    # Gold layer mock data (daily aggregates)
    gold_rows = []
    unique_dates = df_silver["EVENT_DATE"].unique()
    for date in unique_dates:
        for dev in devices:
            dev_df = df_silver[(df_silver["DEVICE_ID"] == dev) & (df_silver["EVENT_DATE"] == date)]
            if not dev_df.empty:
                gold_rows.append({
                    "DEVICE_ID": dev,
                    "EVENT_DATE": date,
                    "TOTAL_READINGS": len(dev_df),
                    "AVG_AQI": round(dev_df["AQI"].mean(), 1),
                    "MAX_AQI": dev_df["AQI"].max(),
                    "MIN_AQI": dev_df["AQI"].min(),
                    "AVG_TEMPERATURE": round(dev_df["TEMPERATURE"].mean(), 2),
                    "MAX_TEMPERATURE": dev_df["TEMPERATURE"].max(),
                    "MIN_TEMPERATURE": dev_df["TEMPERATURE"].min(),
                    "CENTER_LATITUDE": dev_df["LATITUDE"].mean(),
                    "CENTER_LONGITUDE": dev_df["LONGITUDE"].mean()
                })
    df_gold = pd.DataFrame(gold_rows)
    
    return df_silver, df_gold

@st.cache_data(ttl=15)
def load_data(mock_mode):
    if mock_mode:
        return generate_mock_data()
    
    # Live Snowflake connection
    try:
        import snowflake.connector
        conn = snowflake.connector.connect(
            account=sf_account,
            user=sf_user,
            password=os.getenv("SNOWFLAKE_PASSWORD", "SecureTempPassword123!"),
            warehouse=sf_warehouse,
            database=sf_database,
            schema="CLEAN"
        )
        
        # Load Silver layer for detailed map & charts
        silver_query = """
        SELECT EVENT_ID, DEVICE_ID, LATITUDE, LONGITUDE, AQI, TEMPERATURE, EVENT_TIMESTAMP, EVENT_DATE, AQI_SEVERITY
        FROM HACKATHON_IOT.CLEAN.CLEAN_IOT_EVENTS
        WHERE EVENT_TIMESTAMP >= DATEADD('hour', -24, CURRENT_TIMESTAMP())
        ORDER BY EVENT_TIMESTAMP DESC;
        """
        df_silver = pd.read_sql(silver_query, conn)
        
        # Load Gold layer for summary
        gold_query = """
        SELECT DEVICE_ID, EVENT_DATE, TOTAL_READINGS, AVG_AQI, MAX_AQI, MIN_AQI, AVG_TEMPERATURE, MAX_TEMPERATURE, MIN_TEMPERATURE, CENTER_LATITUDE, CENTER_LONGITUDE
        FROM HACKATHON_IOT.ANALYTICS.DAILY_DEVICE_AGGREGATES
        ORDER BY EVENT_DATE DESC, DEVICE_ID;
        """
        df_gold = pd.read_sql(gold_query, conn)
        
        conn.close()
        return df_silver, df_gold
    except Exception as e:
        st.error(f"Failed to connect to Snowflake: {e}. Falling back to mock data.")
        return generate_mock_data()

# Load datasets
df_silver, df_gold = load_data(use_mock_data)

# Dashboard Layout Header
st.title("🌍 On-Premise IoT Data Migration to AWS")
st.markdown(f"**Real-time Telemetry Analytics Dashboard** | Last refreshed at: `{datetime.now().strftime('%H:%M:%S')}`")

# Metrics Summary Cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_devices = df_silver["DEVICE_ID"].nunique()
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-header">Active IoT Devices</div>
        <div class="metric-value">{total_devices}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    avg_aqi = round(df_silver["AQI"].mean(), 1)
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #00CC96;">
        <div class="metric-header">Average AQI (24h)</div>
        <div class="metric-value">{avg_aqi}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    max_aqi = df_silver["AQI"].max()
    max_aqi_device = df_silver.loc[df_silver["AQI"].idxmax(), "DEVICE_ID"]
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #EF553B;">
        <div class="metric-header">Max AQI Observed</div>
        <div class="metric-value">{max_aqi} <span style="font-size:14px;color:#8a8f98;">({max_aqi_device})</span></div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    total_events = len(df_silver)
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #ab63fa;">
        <div class="metric-header">Total Ingested Events (24h)</div>
        <div class="metric-value">{total_events:,}</div>
    </div>
    """, unsafe_allow_html=True)

# Main Section
row2_col1, row2_col2 = st.columns([1.2, 0.8])

with row2_col1:
    st.subheader("📍 Real-time Device Activity Map (O2 Arena, London)")
    # Filter for the latest reading per device
    latest_readings = df_silver.sort_values("EVENT_TIMESTAMP").groupby("DEVICE_ID").last().reset_index()
    
    # Renders Streamlit's built-in MapLibre Map
    map_df = latest_readings[["LATITUDE", "LONGITUDE"]].rename(columns={"LATITUDE": "latitude", "LONGITUDE": "longitude"})
    st.map(map_df, zoom=14, use_container_width=True)

with row2_col2:
    st.subheader("📊 Top Devices by Air Pollution (Max AQI)")
    # Aggregate max AQI per device
    top_devices = df_silver.groupby("DEVICE_ID")["AQI"].max().reset_index().sort_values("AQI", ascending=False)
    
    fig_bar = px.bar(
        top_devices,
        x="DEVICE_ID",
        y="AQI",
        color="AQI",
        color_continuous_scale="Reds",
        labels={"DEVICE_ID": "Device ID", "AQI": "Maximum AQI"},
        template="plotly_dark"
    )
    fig_bar.update_layout(height=350, margin=dict(l=20, r=20, t=10, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)

# Row 3 - Time series and raw data
st.markdown("---")
row3_col1, row3_col2 = st.columns([1.2, 0.8])

with row3_col1:
    st.subheader("📈 Time-Series AQI Trend (Last 2 Hours)")
    # Plotly time-series
    fig_line = px.line(
        df_silver,
        x="EVENT_TIMESTAMP",
        y="AQI",
        color="DEVICE_ID",
        labels={"EVENT_TIMESTAMP": "Timestamp", "AQI": "AQI Reading"},
        template="plotly_dark",
        color_discrete_sequence=px.colors.qualitative.Safe
    )
    fig_line.update_layout(height=350, margin=dict(l=20, r=20, t=10, b=10))
    st.plotly_chart(fig_line, use_container_width=True)

with row3_col2:
    st.subheader("📋 Latest Ingested CDC Event Log")
    # Display table of raw silver records
    display_cols = ["DEVICE_ID", "AQI", "TEMPERATURE", "AQI_SEVERITY", "EVENT_TIMESTAMP"]
    st.dataframe(
        df_silver[display_cols].head(10),
        use_container_width=True,
        height=320
    )
