import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from tradingview_ta import TA_Handler, Interval
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Real-Time Zone Scanner", layout="wide")

# --- Auto-refresh ---
refresh_interval = st.number_input("Refresh Interval (seconds)", 5, 300, 30)
count = st_autorefresh(interval=refresh_interval * 1000, limit=None, key="zone_refresh")

st.title("📊 Real-Time Multi-Pair Zone Screener")

# --- Market / Pair Selection ---
market_type = st.selectbox("Market Type", ["Forex", "Commodities", "Stocks / Indices"])
selected_assets = []
if market_type=="Forex":
    forex_base = st.selectbox("Base Currency", ["USD","GBP","EUR","NZD","CHF"])
    forex_pairs = {
        "USD":["USDJPY","USDCAD","USDCHF","AUDUSD","NZDUSD","EURUSD","GBPUSD"],
        "GBP":["GBPUSD","GBPCAD","GBPJPY","GBPNZD","GBPAUD","GBPSGD"],
        "EUR":["EURUSD","EURJPY","EURGBP","EURAUD","EURNZD","EURCHF"],
        "NZD":["NZDUSD","NZDJPY","NZDCAD","NZDAUD","NZDCHF"],
        "CHF":["USDCHF","EURCHF","CHFJPY","CHFGBP","CHFNZD"]
    }
    selected_assets = st.multiselect("Select Pairs", forex_pairs[forex_base], default=forex_pairs[forex_base])
elif market_type=="Commodities":
    selected_assets = st.multiselect("Select Commodities", ["Gold","Silver","Zinc","Aluminium","Copper","Crude Oil"], default=["Gold","Silver"])
else:
    region = st.selectbox("Region / Index", ["US","Japan","UK","Germany","India"])
    stocks = {
        "US":["US30","US100","AAPL","MSFT","GOOGL","AMZN","TSLA","META","NFLX"],
        "Japan":["JP225","7203.T","6758.T","9984.T"],
        "UK":["FTSE100","BARC.L","HSBA.L","RDSA.L"],
        "Germany":["DAX30","SAP.DE","BMW.DE","ALV.DE"],
        "India":["NIFTY50","RELIANCE.NS","TCS.NS","HDFCBANK.NS"]
    }
    selected_assets = st.multiselect("Select Stocks / Indices", stocks[region], default=[stocks[region][0]])

# --- Timeframe / Zone Type / Fresh-Tested ---
timeframe = st.selectbox("Timeframe", ["1m","5m","15m","1h","2h","4h","12h","1d","1w"])
zone_type = st.multiselect("Zone Type", ["Supply","Demand","Both"], default=["Both"])
fresh_option = st.radio("Zone Status", ["Fresh","Tested","All"], index=0)

# --- Interval Map (only supported intervals) ---
interval_map = {
    "1m": Interval.INTERVAL_1_MINUTE,
    "5m": Interval.INTERVAL_5_MINUTES,
    "15m": Interval.INTERVAL_15_MINUTES,
    "1h": Interval.INTERVAL_1_HOUR,
    "2h": Interval.INTERVAL_2_HOURS,
    "4h": Interval.INTERVAL_4_HOURS,
    "12h": Interval.INTERVAL_12_HOURS,
    "1d": Interval.INTERVAL_1_DAY,
    "1w": Interval.INTERVAL_1_WEEK
}

# --- Helper Functions ---
def get_handler(symbol):
    if market_type=="Forex":
        return TA_Handler(symbol=symbol, screener="forex", exchange="FX_IDC", interval=interval_map[timeframe])
    elif market_type=="Commodities":
        return TA_Handler(symbol=symbol, screener="commodities", exchange="COMEX", interval=interval_map[timeframe])
    else:
        return TA_Handler(symbol=symbol, screener="america", exchange="NASDAQ", interval=interval_map[timeframe])

def get_latest_candle(handler):
    analysis = handler.get_analysis()
    return {
        "time": datetime.now(),
        "open": analysis.indicators["open"],
        "high": analysis.indicators["high"],
        "low": analysis.indicators["low"],
        "close": analysis.indicators["close"]
    }

def detect_zone(candle):
    body = abs(candle["close"]-candle["open"])
    range_ = candle["high"]-candle["low"]
    if range_ == 0:
        return None
    if body / range_ < 0.2:  # relative body < 20% of candle
        return "Demand" if candle["close"]>candle["open"] else "Supply"
    return None

# --- Real-Time Scan ---
zones = []
for asset in selected_assets:
    try:
        handler = get_handler(asset)
        try:
            candle = get_latest_candle(handler)
        except Exception as e:
            st.warning(f"Could not fetch latest candle for {asset}: {e}")
            continue

        z_type = detect_zone(candle)
        if z_type:
            zone_info = {
                "pair": asset,
                "time": candle["time"],
                "high": candle["high"],
                "low": candle["low"],
                "zone_type": z_type,
                "fresh": True,
                "distance": round(abs(candle["close"]-candle["high"]),5)
            }
            zones.append(zone_info)

    except Exception as e:
        st.warning(f"Error processing {asset}: {e}")

df_zones = pd.DataFrame(zones)
for col in ["pair","time","high","low","zone_type","fresh","distance"]:
    if col not in df_zones.columns:
        df_zones[col] = pd.Series(dtype="object")

# --- Apply Filters ---
if zone_type and "Both" not in zone_type:
    df_zones = df_zones[df_zones["zone_type"].isin(zone_type)]
if fresh_option=="Fresh":
    df_zones = df_zones[df_zones["fresh"]==True]
elif fresh_option=="Tested":
    df_zones = df_zones[df_zones["fresh"]==False]

# --- Display Table ---
st.subheader("Latest Detected Zones")
if df_zones.empty:
    st.info("No zones detected yet.")
else:
    st.dataframe(df_zones.tail(20))

# --- Plot Extendable Zones ---
if not df_zones.empty:
    fig = go.Figure()
    for _, row in df_zones.iterrows():
        color = "Green" if row["zone_type"]=="Demand" else "Red"
        opacity = 0.5 if row["fresh"] else 0.2

        x0 = pd.to_datetime(row["time"])
        x1 = datetime.now()

        fig.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=row["low"],
            y1=row["high"],
            line=dict(color=color),
            fillcolor=color,
            opacity=opacity
        )

    fig.update_xaxes(type="date")
    st.plotly_chart(fig)
