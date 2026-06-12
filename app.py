
import time
from datetime import datetime, time as dt_time
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="NSE Low Scanner", layout="wide")

AUTO_INTERVAL_SEC = 10
MAX_ROWS = 100
APP_VERSION = "V30"

st.markdown("""
<style>
.market-card {
    padding: 8px 8px;
    border-radius: 10px;
    border: 1px solid #e6e6e6;
    background: #ffffff;
    min-height: 70px;
}
.market-label {
    font-size: 12px;
    color: #555;
    font-weight: 600;
}
.market-value {
    font-size: 18px;
    font-weight: 700;
    color: #2b2f3a;
    margin-top: 4px;
}
.market-change-green {
    font-size: 11px;
    color: #0a8f28;
    font-weight: 600;
}
.market-change-red {
    font-size: 11px;
    color: #d93025;
    font-weight: 600;
}
.market-change-gray {
    font-size: 11px;
    color: #777;
    font-weight: 600;
}
.top-header {
    display: flex;
    align-items: center;
    gap: 18px;
    width: 100%;
    margin-top: 4px;
    margin-bottom: 4px;
}
.app-title {
    font-size: 28px;
    font-weight: 700;
    color: #262730;
    white-space: nowrap;
}
.version-label {
    font-size: 10px;
    font-weight: 700;
    color: #777;
    vertical-align: super;
    margin-left: 5px;
}
.market-open {
    font-size: 15px;
    font-weight: 700;
    color: #0a8f28;
    white-space: nowrap;
}
.market-closed {
    font-size: 15px;
    font-weight: 700;
    color: #d93025;
    white-space: nowrap;
}
.market-reason {
    font-size: 15px;
    font-weight: 600;
}
.ist-clock {
    margin-left: auto;
    font-size: 15px;
    font-weight: 700;
    color: #262730;
    white-space: nowrap;
}
.ist-clock span {
    margin-left: 12px;
}
.blink-dot-green, .blink-dot-red {
    height: 10px;
    width: 10px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
    animation: blink 1s infinite;
}
.blink-dot-green { background-color: #0a8f28; }
.blink-dot-red { background-color: #d93025; }
@keyframes blink {
    0% { opacity: 1; }
    50% { opacity: 0.15; }
    100% { opacity: 1; }
}

/* compact table / fit view */
div[data-testid="stDataFrame"] {
    font-size: 11px;
    width: 100% !important;
}
div[data-testid="stDataFrame"] div[role="gridcell"] {
    padding: 2px 4px !important;
}
.flash-52w {
    animation: flash52w 1s infinite;
    background-color: #dff7df !important;
    color: #057a20 !important;
    font-weight: 800 !important;
}
@keyframes flash52w {
    0% { background-color: #dff7df; }
    50% { background-color: #7CFC98; }
    100% { background-color: #dff7df; }
}

</style>
""", unsafe_allow_html=True)

INDEX_OPTIONS = {
    "ALL": "ALL",
    "NIFTY 50": "NIFTY 50",
    "NIFTY NEXT 50": "NIFTY NEXT 50",
    "NIFTY 100": "NIFTY 100",
    "NIFTY 200": "NIFTY 200",
    "NIFTY 500": "NIFTY 500",
    "NIFTY MIDCAP 100": "NIFTY MIDCAP 100",
    "NIFTY SMALLCAP 100": "NIFTY SMALLCAP 100",
}

PERIODS = {
    "3 Months Low": 92,
    "6 Months Low": 183,
    "52 Weeks Low": 365,
    "24 Months Low": 730,
    "36 Months Low": 1095,
    "60 Months Low": 1825,
}

FALLBACK_SYMBOLS = [
    "RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","BHARTIARTL","SBIN","LT","ITC","HINDUNILVR",
    "BAJFINANCE","KOTAKBANK","AXISBANK","ASIANPAINT","MARUTI","TATAMOTORS","TATASTEEL","NTPC",
    "ONGC","COALINDIA","POWERGRID","SUNPHARMA","DRREDDY","WIPRO","HCLTECH","TECHM","ULTRACEMCO",
    "ADANIENT","ADANIPORTS","BAJAJ-AUTO","EICHERMOT","HEROMOTOCO","M&M","NESTLEIND","TITAN",
    "GRASIM","JSWSTEEL","HINDALCO","CIPLA","APOLLOHOSP","BRITANNIA","DIVISLAB","BPCL","BAJAJFINSV",
    "SHRIRAMFIN","INDUSINDBK","TATACONSUM","SBILIFE","HDFCLIFE","ADANIGREEN","ADANIPOWER","AMBUJACEM",
    "BANKBARODA","BEL","BOSCHLTD","CANBK","CHOLAFIN","DABUR","DLF","GAIL","GODREJCP","HAL","HAVELLS",
    "ICICIGI","ICICIPRULI","IOC","IRCTC","JINDALSTEL","JSWENERGY","LICI","LODHA","MOTHERSON","NAUKRI",
    "PIDILITIND","PNB","RECLTD","SIEMENS","TATAPOWER","TORNTPHARM","TRENT","TVSMOTOR","VEDL","ZOMATO",
    "ZYDUSLIFE","ABB","ADANIENSOL","ATGL","BAJAJHLDNG","BANDHANBNK","BERGEPAINT","BHEL","BIOCON",
    "COLPAL","DMART","INDIGO","JIOFIN","LTIM","MCDOWELL-N","PFC","SBICARD","SHREECEM","VBL"
]

def clean_symbol(symbol):
    return str(symbol).strip().upper().replace(".NS", "").replace("&", "-")

def to_float(value):
    try:
        if hasattr(value, "iloc"):
            value = value.iloc[0]
        return float(value)
    except Exception:
        return None

@st.cache_data(ttl=30, show_spinner=False)
def get_google_time_ist():
    """
    Gets time source from Google response Date header and converts to IST.
    Fallback uses local system time only if Google is unreachable.
    """
    try:
        r = requests.get("https://www.google.com/finance", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        date_header = r.headers.get("Date")
        if date_header:
            return pd.to_datetime(date_header, utc=True).tz_convert("Asia/Kolkata")
    except Exception:
        pass
    return pd.Timestamp.now(tz="Asia/Kolkata")


@st.cache_data(ttl=300, show_spinner=False)
def get_nse_index_quote(index_name):
    """
    Indian source priority: NSE allIndices API for NIFTY and BANK NIFTY cards.
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nseindia.com/market-data/live-market-indices",
    }
    try:
        session = requests.Session()
        session.headers.update(headers)
        session.get("https://www.nseindia.com", timeout=10)
        r = session.get("https://www.nseindia.com/api/allIndices", timeout=20)
        r.raise_for_status()
        data = r.json().get("data", [])

        for item in data:
            name = str(item.get("index", "")).upper()
            if name == index_name.upper():
                value = float(item.get("last", 0))
                change = float(item.get("variation", 0))
                pct = float(item.get("percentChange", 0))
                direction = "green" if change >= 0 else "red"
                return {
                    "price": f"{value:,.2f}",
                    "change": f"{change:+,.2f}",
                    "pct": f"{abs(pct):.2f}%",
                    "direction": direction,
                    "source": "NSE",
                }
    except Exception:
        pass

    return None

def get_yfinance_quote_for_card(ticker, prefix="", multiplier=1.0, divide=1.0):
    """
    Overseas/fallback source when Indian source or Google Finance is unavailable.
    """
    last, prev = yf_last_and_prev(ticker)
    if last is None:
        return {"price": "-", "change": "-", "pct": "-", "direction": "gray", "source": "Fallback"}

    value = (last * multiplier) / divide
    prev_value = (prev * multiplier) / divide if prev is not None else None

    if prev_value is None or prev_value == 0:
        return {"price": f"{prefix}{value:,.2f}", "change": "-", "pct": "-", "direction": "gray", "source": "Fallback"}

    change = value - prev_value
    pct = (change / prev_value) * 100
    direction = "green" if change >= 0 else "red"
    return {
        "price": f"{prefix}{value:,.2f}",
        "change": f"{change:+,.2f}",
        "pct": f"{abs(pct):.2f}%",
        "direction": direction,
        "source": "Fallback",
    }

def get_google_then_fallback_card(quote_code, fallback_ticker=None, prefix="", multiplier=1.0, divide=1.0):
    """
    Source priority:
    1. Indian source / Google Finance Indian quote page where available.
    2. Overseas/fallback source via yfinance.
    """
    q = get_google_finance_quote(quote_code)
    if q and q.get("price") != "-":
        return q

    if fallback_ticker:
        return get_yfinance_quote_for_card(fallback_ticker, prefix=prefix, multiplier=multiplier, divide=divide)

    return q

def format_source_market_card(label, q):
    css = "market-change-gray"
    arrow = ""
    if q.get("direction") == "green":
        css = "market-change-green"
        arrow = "▲ "
    elif q.get("direction") == "red":
        css = "market-change-red"
        arrow = "▼ "

    change_line = "-"
    if q.get("change") != "-" and q.get("pct") != "-":
        change_line = f"{arrow}{q.get('change')} ({q.get('pct')})"

    st.markdown(
        f"""
        <div class="market-card">
            <div class="market-label">{label}</div>
            <div class="market-value">{q.get('price', '-')}</div>
            <div class="{css}">{change_line}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


@st.cache_data(ttl=30, show_spinner=False)
def get_nse_status_raw():
    """
    Takes market status and timestamp from NSE marketStatus API.
    If timestamp is not returned, uses NSE HTTP Date header converted to IST.
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nseindia.com/",
    }
    try:
        session = requests.Session()
        session.headers.update(headers)
        home = session.get("https://www.nseindia.com", timeout=10)
        r = session.get("https://www.nseindia.com/api/marketStatus", timeout=20)
        r.raise_for_status()
        data = r.json()

        # Read NSE time if present
        nse_time_text = None
        for key in ["time", "timestamp", "lastUpdateTime"]:
            if data.get(key):
                nse_time_text = str(data.get(key))
                break

        if not nse_time_text:
            for item in data.get("marketState", []):
                for key in ["tradeDate", "time", "timestamp", "lastUpdateTime"]:
                    if item.get(key):
                        nse_time_text = str(item.get(key))
                        break
                if nse_time_text:
                    break

        if nse_time_text:
            parsed = pd.to_datetime(nse_time_text, errors="coerce", dayfirst=True)
            if pd.isna(parsed):
                nse_dt = pd.Timestamp.now(tz="Asia/Kolkata")
            else:
                if parsed.tzinfo is None:
                    nse_dt = parsed.tz_localize("Asia/Kolkata")
                else:
                    nse_dt = parsed.tz_convert("Asia/Kolkata")
        else:
            date_header = r.headers.get("Date") or home.headers.get("Date")
            if date_header:
                nse_dt = pd.to_datetime(date_header, utc=True).tz_convert("Asia/Kolkata")
            else:
                nse_dt = pd.Timestamp.now(tz="Asia/Kolkata")

        raw_status = ""
        for item in data.get("marketState", []):
            market_name = str(item.get("market", "")).upper()
            if "CAPITAL" in market_name or "CM" in market_name or "NORMAL" in market_name:
                raw_status = str(item.get("marketStatus", "") or item.get("status", "")).upper()
                break

        if not raw_status and data.get("marketState"):
            item = data.get("marketState", [])[0]
            raw_status = str(item.get("marketStatus", "") or item.get("status", "")).upper()

        return raw_status, nse_dt
    except Exception:
        # Only fallback if NSE cannot be reached
        return "", pd.Timestamp.now(tz="Asia/Kolkata")

@st.cache_data(ttl=3600, show_spinner=False)
def get_nse_holiday_description_for_date(date_obj):
    try:
        today = pd.Timestamp(date_obj).strftime("%d-%b-%Y")
        url = "https://www.nseindia.com/api/holiday-master?type=trading"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.nseindia.com/resources/exchange-communication-holidays",
        }
        session = requests.Session()
        session.headers.update(headers)
        session.get("https://www.nseindia.com", timeout=10)
        r = session.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        for h in data.get("CM", []):
            if str(h.get("tradingDate", "")).strip() == today:
                desc = str(h.get("description", "NSE Holiday")).strip()
                return desc if desc else "NSE Holiday"
    except Exception:
        pass
    return None

def get_market_status():
    """
    Uses NSE status/time.
    Flash Market rules:
    - Pre-Open = green
    - Pre-close = red
    """
    raw_status, nse_dt = get_nse_status_raw()
    raw = raw_status.upper()
    current_time = nse_dt.time()

    if "PRE-OPEN" in raw or "PREOPEN" in raw:
        return "PRE-OPEN", "Flash Market : Pre-Open", "green", nse_dt

    if "PRE-CLOSE" in raw or "PRECLOSE" in raw:
        return "PRE-CLOSE", "Flash Market : Pre-close", "red", nse_dt

    if "OPEN" in raw and "CLOSE" not in raw:
        return "OPEN", "Market Open", "green", nse_dt

    if "CLOSE" in raw:
        return "CLOSED", "", "red", nse_dt

    # Fallback based on NSE timestamp
    holiday_desc = get_nse_holiday_description_for_date(nse_dt.date())
    if holiday_desc:
        return "CLOSED", f"Holiday - {holiday_desc}", "red", nse_dt

    if nse_dt.weekday() >= 5:
        return "CLOSED", f"Weekend - {nse_dt.strftime('%A')}", "red", nse_dt

    if current_time < dt_time(9, 15):
        return "PRE-OPEN", "Flash Market : Pre-Open", "green", nse_dt

    if dt_time(15, 30) <= current_time <= dt_time(16, 0):
        return "PRE-CLOSE", "Flash Market : Pre-close", "red", nse_dt

    if current_time > dt_time(16, 0):
        return "CLOSED", "Market closed after 15:30 IST", "red", nse_dt

    return "OPEN", "Market Open", "green", nse_dt

def market_status_html():
    status, reason, color, nse_dt = get_market_status()
    dot_color = "#0a8f28" if color == "green" else "#d93025"
    text_color = "#0a8f28" if color == "green" else "#d93025"

    status_map = {
        "OPEN": "Open",
        "CLOSED": "Closed",
        "PRE-OPEN": "Pre-Open",
        "PRE-CLOSE": "Pre-close",
    }
    status_display = status_map.get(status, status.title())

    reason_clean = (reason or "").strip()
    if reason_clean.lower() in ["closed", "market closed", "open", "market open"]:
        reason_html = ""
    else:
        reason_html = f"<span style='font-weight:600;'> ({reason_clean})</span>" if reason_clean else ""

    google_dt = get_google_time_ist()
    google_epoch_ms = int(google_dt.timestamp() * 1000)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    body {{
        margin: 0;
        padding: 0;
        font-family: Arial, sans-serif;
        overflow: hidden;
        background: transparent;
    }}
    .top-header {{
        display: flex;
        align-items: center;
        width: 100%;
        height: 42px;
        gap: 18px;
        box-sizing: border-box;
    }}
    .app-title {{
        font-size: 28px;
        font-weight: 700;
        color: #262730;
        white-space: nowrap;
    }}
    .market-status {{
        font-size: 15px;
        font-weight: 700;
        color: {text_color};
        white-space: nowrap;
    }}
    .blink-dot {{
        height: 10px;
        width: 10px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
        background-color: {dot_color};
        animation: blink 1s infinite;
    }}
    .nse-clock {{
        margin-left: auto;
        font-size: 15px;
        font-weight: 700;
        color: #262730;
        white-space: nowrap;
        padding-right: 4px;
    }}
    .nse-clock span {{
        margin-left: 14px;
    }}
    @keyframes blink {{
        0% {{ opacity: 1; }}
        50% {{ opacity: 0.15; }}
        100% {{ opacity: 1; }}
    }}
    </style>
    </head>
    <body>
        <div class="top-header">
            <div class="app-title">📊 NSE Low Scanner</div>
            <div class="market-status">
                <span class="blink-dot"></span>
                Market : {status_display}{reason_html}
            </div>
            <div class="nse-clock">
                <span id="nse-live-time"></span>
                <span id="nse-live-date"></span>
            </div>
        </div>

        <script>
        const googleBaseTime = {google_epoch_ms};
        const browserBaseTime = Date.now();

        function updateNSEClock() {{
            const nowMs = googleBaseTime + (Date.now() - browserBaseTime);
            const d = new Date(nowMs);

            const timeText = new Intl.DateTimeFormat('en-GB', {{
                timeZone: 'Asia/Kolkata',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: true
            }}).format(d);

            let dateText = new Intl.DateTimeFormat('en-GB', {{
                timeZone: 'Asia/Kolkata',
                weekday: 'short',
                day: '2-digit',
                month: 'short',
                year: 'numeric'
            }}).format(d);

            dateText = dateText.replace(/,/g, '').replace(/ /g, '-').toUpperCase();

            document.getElementById("nse-live-time").innerText = "Time: " + timeText + " IST";
            document.getElementById("nse-live-date").innerText = dateText;
        }}

        updateNSEClock();
        setInterval(updateNSEClock, 1000);
        </script>
    </body>
    </html>
    """


@st.cache_data(ttl=300, show_spinner=False)
def get_google_finance_quote(quote_code):
    """
    Google Finance has no official API.
    This scrapes Google Finance card values and falls back to basic HTML/text parsing.
    """
    try:
        url = f"https://www.google.com/finance/quote/{quote_code}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        html = r.text
        soup = BeautifulSoup(html, "html.parser")

        price_text = "-"
        price_el = soup.find("div", class_="YMlKec fxKbKc")
        if price_el:
            price_text = price_el.get_text(strip=True)

        if price_text == "-":
            # Fallback from common Google embedded price patterns
            m_price = re.search(r'"price":"([^"]+)"', html)
            if m_price:
                price_text = m_price.group(1)

        text_all = soup.get_text(" ", strip=True)

        change_text = "-"
        pct_text = "-"

        # Pattern: +278.40 (1.16%) / -349.44 (0.45%)
        m = re.search(r'([+-]\s*[\d,]+(?:\.\d+)?)\s*\(([\d.]+%)\)', text_all)
        if m:
            change_text = m.group(1).replace(" ", "")
            pct_text = m.group(2)

        direction = "gray"
        if change_text.startswith("+"):
            direction = "green"
        elif change_text.startswith("-"):
            direction = "red"

        return {
            "price": price_text,
            "change": change_text,
            "pct": pct_text,
            "direction": direction,
            "source": "Google Finance",
        }
    except Exception:
        return {
            "price": "-",
            "change": "-",
            "pct": "-",
            "direction": "gray",
            "source": "Google Finance",
        }

def format_google_market_card(label, quote_code):
    q = get_google_finance_quote(quote_code)

    css = "market-change-gray"
    arrow = ""
    if q["direction"] == "green":
        css = "market-change-green"
        arrow = "▲ "
    elif q["direction"] == "red":
        css = "market-change-red"
        arrow = "▼ "

    change_line = "-"
    if q["change"] != "-" and q["pct"] != "-":
        change_line = f"{arrow}{q['change']} ({q['pct']})"

    st.markdown(
        f"""
        <div class="market-card">
            <div class="market-label">{label}</div>
            <div class="market-value">{q['price']}</div>
            <div class="{css}">{change_line}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

@st.cache_data(ttl=300, show_spinner=False)
def yf_last_and_prev(ticker):
    try:
        df = yf.download(ticker, period="7d", interval="1d", progress=False, auto_adjust=False)
        if df is None or df.empty:
            return None, None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        close = df["Close"].dropna()
        if len(close) == 0:
            return None, None
        last = to_float(close.iloc[-1])
        prev = to_float(close.iloc[-2]) if len(close) >= 2 else None
        return last, prev
    except Exception:
        return None, None

def format_market_card(label, value, previous=None, prefix="", suffix=""):
    if value is None:
        value_text = "-"
        change_text = "-"
        css = "market-change-gray"
    else:
        value_text = f"{prefix}{value:,.2f}{suffix}"
        if previous is None or previous == 0:
            change_text = "-"
            css = "market-change-gray"
        else:
            change = value - previous
            pct = (change / previous) * 100
            arrow = "▲" if change >= 0 else "▼"
            css = "market-change-green" if change >= 0 else "market-change-red"
            change_text = f"{arrow} {change:,.2f} ({pct:.2f}%)"

    st.markdown(
        f"""
        <div class="market-card">
            <div class="market-label">{label}</div>
            <div class="market-value">{value_text}</div>
            <div class="{css}">{change_text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

@st.cache_data(ttl=300, show_spinner=False)
def gold_rates_india():
    gold, gold_prev = yf_last_and_prev("GC=F")
    usd, usd_prev = yf_last_and_prev("INR=X")
    if gold is None or usd is None:
        return None, None, None, None
    gold_24_10g = gold * usd / 31.1034768 * 10
    gold_22_10g = gold_24_10g * (22 / 24)
    gold_24_10g_prev = None
    gold_22_10g_prev = None
    if gold_prev is not None and usd_prev is not None:
        gold_24_10g_prev = gold_prev * usd_prev / 31.1034768 * 10
        gold_22_10g_prev = gold_24_10g_prev * (22 / 24)
    return gold_24_10g, gold_24_10g_prev, gold_22_10g, gold_22_10g_prev

@st.cache_data(ttl=300, show_spinner=False)
def silver_india_rate():
    silver, silver_prev = yf_last_and_prev("SI=F")
    usd, usd_prev = yf_last_and_prev("INR=X")
    if silver is None or usd is None:
        return None, None
    silver_kg = silver * usd / 31.1034768 * 1000
    silver_kg_prev = None
    if silver_prev is not None and usd_prev is not None:
        silver_kg_prev = silver_prev * usd_prev / 31.1034768 * 1000
    return silver_kg, silver_kg_prev

st.markdown('<div style="font-size:14px;font-weight:600;color:#555;">SELVAKUMARAN SUGMAR</div>', unsafe_allow_html=True)
components.html(market_status_html(), height=48)


# Top dashboard cards source priority:
# 1) Indian websites/APIs first (NSE / Google Finance Indian pages)
# 2) Overseas/fallback source only if Indian/Google source fails.
nifty_q = get_nse_index_quote("NIFTY 50") or get_yfinance_quote_for_card("^NSEI")
bank_q = get_nse_index_quote("NIFTY BANK") or get_yfinance_quote_for_card("^NSEBANK")

# Gold/Silver/Crude: try Indian Google Finance/MCX page first, then overseas futures fallback.
gold24_q = get_google_then_fallback_card("GOLD:MCX", "GC=F", prefix="₹")
gold22_q = get_google_then_fallback_card("GOLD:MCX", "GC=F", prefix="₹")
silver_q = get_google_then_fallback_card("SILVER:MCX", "SI=F", prefix="₹")
crude_q = get_google_then_fallback_card("CRUDEOIL:MCX", "CL=F", prefix="$")
usd_q = get_google_then_fallback_card("USD-INR", "INR=X")
btc_q = get_google_then_fallback_card("BTC-USD", "BTC-USD", prefix="$")

m1, m2, m3, m4, m5, m6, m7, m8 = st.columns(8)
with m1: format_source_market_card("NIFTY", nifty_q)
with m2: format_source_market_card("BANK NIFTY", bank_q)
with m3: format_source_market_card("GOLD 24K / 8g", gold24_q)
with m4: format_source_market_card("GOLD 22K / 8g", gold22_q)
with m5: format_source_market_card("SILVER / gm", silver_q)
with m6: format_source_market_card("CRUDE OIL", crude_q)
with m7: format_source_market_card("USD/INR", usd_q)
with m8: format_source_market_card("BITCOIN", btc_q)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_index_symbols(index_name):
    url = "https://www.nseindia.com/api/equity-stockIndices"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nseindia.com/market-data/live-equity-market",
    }

    def get_symbols_for_index(session, idx):
        try:
            r = session.get(url, params={"index": idx}, timeout=20)
            r.raise_for_status()
            data = r.json().get("data", [])
            symbols = [clean_symbol(item.get("symbol", "")) for item in data if item.get("symbol")]
            symbols = [s for s in symbols if s and s != idx and s != "NIFTY"]
            return symbols
        except Exception:
            return []

    try:
        session = requests.Session()
        session.headers.update(headers)
        session.get("https://www.nseindia.com", timeout=10)

        if index_name == "ALL":
            all_indices = [
                "NIFTY 500",
                "NIFTY MIDCAP 100",
                "NIFTY SMALLCAP 100",
                "NIFTY 200",
                "NIFTY 100",
                "NIFTY NEXT 50",
                "NIFTY 50",
            ]
            all_symbols = []
            for idx in all_indices:
                all_symbols.extend(get_symbols_for_index(session, idx))
            all_symbols = list(dict.fromkeys(all_symbols))
            if all_symbols:
                return all_symbols

        symbols = get_symbols_for_index(session, index_name)
        if symbols:
            return list(dict.fromkeys(symbols))
    except Exception:
        pass

    return FALLBACK_SYMBOLS

@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(symbol):
    ticker = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
    period_days = max(PERIODS.values()) + 60
    df = yf.download(ticker, period=f"{period_days}d", interval="1d", progress=False, auto_adjust=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df.reset_index()

@st.cache_data(ttl=3600, show_spinner=False)
def get_dividend_info(symbol, latest_close):
    try:
        ticker = yf.Ticker(symbol if symbol.endswith(".NS") else f"{symbol}.NS")
        div = ticker.dividends
        if div is None or div.empty or latest_close is None or latest_close == 0:
            return "-", "-", "-"
        div = div.dropna()
        last_dividend = float(div.iloc[-1])
        dividend_date = str(div.index[-1].date())
        cutoff = pd.Timestamp.today(tz=div.index.tz) - pd.Timedelta(days=365)
        trailing_dividend = float(div[div.index >= cutoff].sum())
        dividend_yield = (trailing_dividend / latest_close) * 100
        return round(dividend_yield, 2), round(last_dividend, 2), dividend_date
    except Exception:
        return "-", "-", "-"

def analyze_symbol(symbol, tolerance_pct, selected_period):
    df = fetch_history(symbol)
    if df.empty or "Low" not in df.columns or "Close" not in df.columns or "High" not in df.columns:
        return None

    df = df.dropna(subset=["Low", "Close", "High"]).copy()
    if df.empty:
        return None

    latest = df.iloc[-1]
    latest_close = to_float(latest["Close"])
    latest_high = to_float(latest["High"])
    latest_low = to_float(latest["Low"])
    if latest_close is None or latest_low is None or latest_high is None:
        return None

    days = PERIODS[selected_period]
    start_date = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
    wdf = df[pd.to_datetime(df["Date"]) >= start_date]
    if wdf.empty:
        return None

    selected_low = to_float(wdf["Low"].min())

    year_start = pd.Timestamp.today().normalize() - pd.Timedelta(days=365)
    ydf = df[pd.to_datetime(df["Date"]) >= year_start]
    high_52w = to_float(ydf["High"].max()) if not ydf.empty else None
    low_52w = to_float(ydf["Low"].min()) if not ydf.empty else None

    if selected_low is None or selected_low == 0:
        return None

    away_pct = ((latest_close - selected_low) / selected_low) * 100
    near = away_pct <= tolerance_pct
    highlighted = away_pct < 1.0

    away_52w = None
    flash_52w = "NO"
    if low_52w is not None and low_52w != 0:
        away_52w = ((latest_close - low_52w) / low_52w) * 100
        flash_52w = "YES" if away_52w < 1.0 else "NO"

    dividend_yield, dividend_rupee, dividend_date = get_dividend_info(symbol, latest_close)

    row = {
        "Symbol": symbol,
        "LTP/Close": round(latest_close, 2),
        "Today High": round(latest_high, 2),
        "Today Low": round(latest_low, 2),
        selected_period: round(selected_low, 2),
        f"{selected_period} Away %": round(away_pct, 2),
        f"{selected_period} Status": "VERY NEAR LOW" if highlighted else ("HIT/NEAR LOW" if near else "OK"),
        "52 Weeks High": round(high_52w, 2) if high_52w is not None else None,
        "Dividend Yield %": dividend_yield,
        "Dividend ₹": dividend_rupee,
        "Dividend Date": dividend_date,
        "_Highlighted": "YES" if highlighted else "NO",
        "_Flash52W": flash_52w,
    }

    # Avoid duplicate columns when selected_period is already 52 Weeks Low.
    if selected_period != "52 Weeks Low":
        row["52 Weeks Low"] = round(low_52w, 2) if low_52w is not None else None
        row["52 Weeks Away %"] = round(away_52w, 2) if away_52w is not None else None

    return row

def run_scan(symbols, tolerance, selected_period, max_rows=MAX_ROWS):
    rows = []
    progress = st.progress(0)
    status = st.empty()
    total = len(symbols)

    for i, symbol in enumerate(symbols, start=1):
        status.write(f"Scanning {symbol} ({i}/{total})...")
        try:
            result = analyze_symbol(symbol, tolerance, selected_period)
            if result:
                rows.append(result)
        except Exception as e:
            rows.append({"Symbol": symbol, "Error": str(e), "_Highlighted": "NO"})
        progress.progress(i / total)
        time.sleep(0.01)

    status.write("Scanning Complete!")
    df = pd.DataFrame(rows)
    away_col = f"{selected_period} Away %"
    if not df.empty and away_col in df.columns:
        df = df.sort_values(by=away_col, ascending=True, na_position="last")
    return df if max_rows is None else df.head(max_rows)

with st.sidebar:
    st.header("Settings")
    tolerance = 10.0
    selected_index = st.selectbox("Index", list(INDEX_OPTIONS.keys()), index=1)
    selected_period = st.selectbox("Period", list(PERIODS.keys()), index=2)
    show_highlighted = False
    scan_button = st.button("Scan Now", type="primary", use_container_width=True)
    st.markdown("---")
    st.markdown("🔁 Auto scan starts after first scan and repeats every 10 seconds.")
    timer_box = st.empty()

    st.markdown("---")
    st.markdown(
        "<div style='font-size:12px;color:gray;'>Current Version: V30</div>",
        unsafe_allow_html=True
    )

now_time = time.time()

# Press Scan Now once, then auto scan repeats every 10 seconds.
if scan_button:
    st.session_state.auto_scan_started = True
    st.session_state.next_scan_time = now_time
    should_scan = True
elif st.session_state.get("auto_scan_started", False):
    remaining = int(st.session_state.get("next_scan_time", now_time) - now_time)
    if remaining <= 0:
        should_scan = True
        st.session_state.next_scan_time = now_time + AUTO_INTERVAL_SEC
        remaining = AUTO_INTERVAL_SEC
    else:
        should_scan = False

    mins = max(remaining, 0) // 60
    secs = max(remaining, 0) % 60
    timer_box.markdown(f"⏳ **Next auto scan in: {mins:02d}:{secs:02d}**")
else:
    should_scan = False
    timer_box.markdown("⏳ Auto scan: waiting for first Scan Now")

if should_scan:
    symbols = fetch_index_symbols(INDEX_OPTIONS[selected_index])
    result_df = run_scan(symbols, tolerance, selected_period, None if selected_index == "ALL" else MAX_ROWS)
    if show_highlighted and not result_df.empty:
        result_df = result_df[result_df["_Highlighted"] == "YES"].copy()

    st.session_state.style_flags = result_df["_Highlighted"].to_dict() if "_Highlighted" in result_df.columns else {}
    st.session_state.flash52w_flags = result_df["_Flash52W"].to_dict() if "_Flash52W" in result_df.columns else {}

    preferred_cols = [
        "Symbol", "LTP/Close", "Today High", "Today Low",
        selected_period, f"{selected_period} Away %", f"{selected_period} Status",
    ]

    if selected_period != "52 Weeks Low":
        preferred_cols += ["52 Weeks Low", "52 Weeks Away %"]

    preferred_cols += [
        "52 Weeks High",
        "Dividend Yield %", "Dividend ₹", "Dividend Date"
    ]

    # Remove duplicate column names while preserving order.
    seen = set()
    preferred_cols = [c for c in preferred_cols if not (c in seen or seen.add(c))]
    result_df = result_df.loc[:, ~result_df.columns.duplicated()]

    existing_cols = [c for c in preferred_cols if c in result_df.columns]
    other_cols = [c for c in result_df.columns if c not in existing_cols and not c.startswith("_")]
    display_df = result_df[existing_cols + other_cols].drop(columns=["_Highlighted", "_Flash52W"], errors="ignore")

    st.session_state.result_df = display_df
    st.session_state.last_scan = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.next_scan_time = time.time() + AUTO_INTERVAL_SEC

if "result_df" in st.session_state:
    st.subheader(f"Result - {selected_index} - {selected_period}")
    st.caption(f"Showing {len(st.session_state.result_df)} rows | Last scan: {st.session_state.last_scan}")
    if not st.session_state.result_df.empty:
        def style_visible_rows(row):
            styles = [""] * len(row)

            # Normal green row highlight for selected-period low
            if st.session_state.get("style_flags", {}).get(row.name) == "YES":
                styles = ["background-color: #dff7df; color: #057a20; font-weight: 700"] * len(row)

            # 52W low-related columns green highlight when stock is within 1% of 52W low
            if st.session_state.get("flash52w_flags", {}).get(row.name) == "YES":
                for i, col in enumerate(row.index):
                    if col in ["52 Weeks Low", "52 Weeks Away %"] or (selected_period == "52 Weeks Low" and col in ["52 Weeks Low", "52 Weeks Low Away %"]):
                        styles[i] = "background-color: #7CFC98; color: #057a20; font-weight: 900"
            return styles

        # Safety: ensure no duplicate columns before styling.
        st.session_state.result_df = st.session_state.result_df.loc[:, ~st.session_state.result_df.columns.duplicated()]

        st.dataframe(
            st.session_state.result_df.style.apply(style_visible_rows, axis=1).format(precision=2),
            use_container_width=True,
            hide_index=True,
            height=700
        )
        csv = st.session_state.result_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "nse_low_scanner_result.csv", "text/csv")
    else:
        st.warning("No result found.")
else:
    st.info("Select index and period, then click Scan Now.")

if st.session_state.get("auto_scan_started", False):
    time.sleep(1)
    st.rerun()
