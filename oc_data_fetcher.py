"""
Option Chain Data Fetcher - Shared Module
==========================================
Reusable data fetching logic for Streamlit/Gradio web dashboards.
Extracts core API calls from optionchain.py / optionchain_modified.py.

No Rich library dependencies - returns plain Python dicts and DataFrames.
"""

import sys
import os
import time
import datetime
import requests
import pandas as pd
import json
import glob
from pathlib import Path
from typing import Optional, Dict, Tuple, List

from paths import (
    INSTRUMENTS_DIR, VIX_DIR, FUTURES_DIR, OPTIONCHAIN_CSV_DIR,
    CACHE_DIR, OUTPUT_DIR,
    SPOT_PRICE_CACHE_FILE, VIX_CACHE_FILE, OI_SNAPSHOTS_FILE,
    DAY_OPEN_SYNC_FILE, DAY_OPENING_PRICES_FILE, DAY_OPENING_STRADDLES_FILE,
    ensure_dirs,
)

# Add parent directory to path for imports
parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from Credential.Credential import client_code, token_id

# ═════════════════════════════════════════════════════════════════════════════
#^# CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════
OPTION_CHAIN_DELAY = 0.0   #~# Option chain = 20 req/sec — no forced sleep needed

INDEX_SECURITY_IDS = {
    'NIFTY': 13, 'BANKNIFTY': 25, 'FINNIFTY': 27, 'MIDCPNIFTY': 442
}

VIX_SECURITY_ID = 21  # India VIX

INDEX_STEP_MAP = {
    'NIFTY': 50, 'BANKNIFTY': 100, 'FINNIFTY': 50, 'MIDCPNIFTY': 25
}

LOT_SIZE_MAP = {
    'NIFTY': 65, 'BANKNIFTY': 15, 'FINNIFTY': 25, 'MIDCPNIFTY': 50
}

API_HEADERS = {
    'access-token': token_id,
    'client-id': str(client_code),
    'Content-Type': 'application/json'
}


# ═════════════════════════════════════════════════════════════════════════════
#^# TTL CACHE — instant UI re-renders from cache, background API refresh
# ═════════════════════════════════════════════════════════════════════════════
_cache: Dict[str, dict] = {}  #~# key -> {'data': ..., 'ts': float}

def _cache_get(key: str, ttl: float = 30.0):
    """* Return cached value if within TTL, else None."""
    entry = _cache.get(key)
    if entry and (time.time() - entry['ts']) < ttl:
        return entry['data']
    return None

def _cache_set(key: str, data):
    _cache[key] = {'data': data, 'ts': time.time()}


# ═════════════════════════════════════════════════════════════════════════════
#^# SPOT PRICE CACHE — stores last valid spot price for each underlying
#!# Prevents spot price from showing 0 when API data is unavailable
# ═════════════════════════════════════════════════════════════════════════════
# SPOT_PRICE_CACHE_FILE imported from paths.py
#~# Persistent JSON cache for spot prices across sessions

def _load_spot_price_cache() -> dict:
    """* Load spot price cache from JSON file."""
    try:
        if SPOT_PRICE_CACHE_FILE.exists():
            with open(SPOT_PRICE_CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_spot_price_cache(cache: dict):
    """* Save spot price cache to JSON file."""
    try:
        SPOT_PRICE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SPOT_PRICE_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def update_spot_price_cache(underlying: str, spot_price: float):
    """! Update spot price cache only if spot_price is valid (> 0)."""
    if spot_price > 0:
        try:
            cache = _load_spot_price_cache()
            cache[underlying] = {
                'spot_price': spot_price,
                'timestamp': datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")
            }
            _save_spot_price_cache(cache)
        except Exception:
            pass


def get_cached_spot_price(underlying: str) -> float:
    """* Get last cached spot price for an underlying."""
    try:
        cache = _load_spot_price_cache()
        if underlying in cache:
            return float(cache[underlying].get('spot_price', 0.0))
    except Exception:
        pass
    return 0.0


# ═════════════════════════════════════════════════════════════════════════════
#^# OI SNAPSHOT STORAGE — per-strike OI stored to JSON with timestamp
#~# Enables Change in OI calculation vs last/previous day's close
# ═════════════════════════════════════════════════════════════════════════════
OI_SNAPSHOT_FILE = OI_SNAPSHOTS_FILE  # from paths.py

def _load_oi_snapshots() -> list:
    """* Load OI snapshots from JSON file."""
    try:
        if OI_SNAPSHOT_FILE.exists():
            with open(OI_SNAPSHOT_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_oi_snapshots(snapshots: list):
    """* Save OI snapshots to JSON file."""
    try:
        OI_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OI_SNAPSHOT_FILE, 'w') as f:
            json.dump(snapshots, f, indent=2)
    except Exception:
        pass


def save_oi_snapshot(df: pd.DataFrame, underlying: str):
    """
    * Store current per-strike OI data as a snapshot with timestamp.
    * Appends to oi_snapshots.json. Keeps only last 50 snapshots.
    """
    if df is None or df.empty:
        return
    try:
        now = datetime.datetime.now()
        strikes = {}
        for _, row in df.iterrows():
            strike = row.get('Strike', 0)
            if strike > 0:
                strikes[str(int(strike))] = {
                    'c_oi': float(row.get('C_OI', 0) or 0),
                    'p_oi': float(row.get('P_OI', 0) or 0),
                }

        snapshot = {
            'timestamp': now.strftime("%Y-%m-%d %H:%M:%S"),
            'date': now.strftime("%Y-%m-%d"),
            'underlying': underlying,
            'strikes': strikes,
        }

        snapshots = _load_oi_snapshots()
        snapshots.append(snapshot)
        # Keep only the last 50 snapshots
        if len(snapshots) > 50:
            snapshots = snapshots[-50:]
        _save_oi_snapshots(snapshots)
    except Exception:
        pass


def get_previous_oi_snapshot(underlying: str) -> Dict[str, dict]:
    """
    * Get the last available OI snapshot from a PREVIOUS day (not today).
    * Returns dict: {strike_str: {'c_oi': float, 'p_oi': float}}
    """
    cached = _cache_get('prev_oi_snap', ttl=3600)
    if cached is not None:
        return cached

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    snapshots = _load_oi_snapshots()

    # * Walk backwards to find the latest snapshot from a previous day
    for snap in reversed(snapshots):
        if snap.get('underlying') == underlying and snap.get('date') != today_str:
            result = snap.get('strikes', {})
            _cache_set('prev_oi_snap', result)
            return result

    _cache_set('prev_oi_snap', {})
    return {}


# ═════════════════════════════════════════════════════════════════════════════
#^# HELPER FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════
def parse_indian_number(val) -> float:
    if val is None or val == '' or val == '-':
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(',', '').strip())
    except (ValueError, TypeError):
        return 0.0


def format_lakh(val: float) -> str:
    if abs(val) >= 10_000_000:
        return f"{val/10_000_000:.2f} Cr"
    elif abs(val) >= 100_000:
        return f"{val/100_000:.2f} L"
    elif abs(val) >= 1000:
        return f"{val/1000:.1f}K"
    else:
        return f"{val:,.0f}"


# ═════════════════════════════════════════════════════════════════════════════
#^# API FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════
def fetch_expiry_list(security_id: int, exchange_seg: str = "IDX_I") -> list:
    cache_key = f"expiry_{security_id}_{exchange_seg}"
    cached = _cache_get(cache_key, ttl=300)  #~# 5 min — expiry list rarely changes
    if cached:
        return cached

    url = "https://api.dhan.co/v2/optionchain/expirylist"
    payload = {"UnderlyingScrip": security_id, "UnderlyingSeg": exchange_seg}
    try:
        r = requests.post(url, json=payload, headers=API_HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get('status') == 'success':
            result = data.get('data', [])
            _cache_set(cache_key, result)
            return result
    except Exception:
        pass
    return []


def fetch_option_chain(security_id: int, exchange_seg: str, expiry_date: str,
                       max_retries: int = 3) -> Optional[dict]:
    url = "https://api.dhan.co/v2/optionchain"
    payload = {
        "UnderlyingScrip": security_id,
        "UnderlyingSeg": exchange_seg,
        "Expiry": expiry_date
    }
    for attempt in range(max_retries):
        try:
            r = requests.post(url, json=payload, headers=API_HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                time.sleep(5 * (attempt + 1))
            elif e.response.status_code == 400:
                return None
            else:
                time.sleep(3)
        except Exception:
            time.sleep(3)
    return None


#~# Global LTP rate-limiter — Dhan blocks if you call too fast
import threading as _threading
_ltp_lock = _threading.Lock()
_last_ltp_ts: float = 0.0
_LTP_MIN_INTERVAL = 0.6   # seconds between consecutive LTP calls


def _ltp_throttle():
    """Block briefly if the last LTP call was < _LTP_MIN_INTERVAL seconds ago."""
    global _last_ltp_ts
    with _ltp_lock:
        elapsed = time.time() - _last_ltp_ts
        if elapsed < _LTP_MIN_INTERVAL:
            time.sleep(_LTP_MIN_INTERVAL - elapsed)
        _last_ltp_ts = time.time()


def fetch_ltp(security_id: int, exchange_seg: str = "IDX_I", _max_retries: int = 3) -> Optional[float]:
    url = "https://api.dhan.co/v2/marketfeed/ltp"
    payload = {exchange_seg: [security_id]}
    for attempt in range(_max_retries + 1):
        _ltp_throttle()
        try:
            r = requests.post(url, json=payload, headers=API_HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                #~# Detect "Too many requests" rate-limit response
                if _is_rate_limited(data) or (
                    isinstance(data.get('data'), dict) and
                    isinstance(data['data'].get('data', {}), dict) and
                    any('too many' in str(v).lower()
                        for v in data['data'].get('data', {}).values())):
                    backoff = 2 ** attempt
                    print(f"[LTP] Rate limited for sec={security_id} (attempt {attempt+1}/{_max_retries+1}), backing off {backoff}s...", flush=True)
                    time.sleep(backoff)
                    continue
                if 'data' in data and exchange_seg in data['data']:
                    quote = data['data'][exchange_seg]
                    if isinstance(quote, dict) and str(security_id) in quote:
                        ltp = quote[str(security_id)].get('last_price')
                        if ltp and ltp > 0:
                            return float(ltp)
        except Exception:
            if attempt < _max_retries:
                time.sleep(2 ** attempt)
                continue
    return None


def _is_rate_limited(data: dict) -> bool:
    """Check if API response indicates rate limiting (Too many requests)."""
    if data.get('status') == 'failure':
        inner = data.get('data', {})
        if isinstance(inner, dict):
            inner_data = inner.get('data', inner)
            if isinstance(inner_data, dict):
                for v in inner_data.values():
                    if 'too many' in str(v).lower():
                        return True
    return False


def fetch_batch_ltp(payload: dict, _max_retries: int = 3) -> dict:
    """* Fetch LTP for multiple securities across exchanges in a SINGLE API call.

    Args:
        payload: e.g. {"IDX_I": [26000, 21], "NSE_FNO": [12345]}
        _max_retries: max retry attempts on rate-limit (default 3)
    Returns:
        * Nested dict  {exchange: {sec_id_str: {"last_price": float}}}
    """
    url = "https://api.dhan.co/v2/marketfeed/ltp"
    for attempt in range(_max_retries + 1):
        _ltp_throttle()
        try:
            r = requests.post(url, json=payload, headers=API_HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if _is_rate_limited(data):
                    backoff = 2 ** attempt  # 1s, 2s, 4s
                    print(f"[Batch LTP] Rate limited (attempt {attempt+1}/{_max_retries+1}), backing off {backoff}s...", flush=True)
                    time.sleep(backoff)
                    continue
                if data.get('status') == 'failure':
                    print(f"[Batch LTP] API failure: {data}", flush=True)
                    return {}
                if 'data' in data and isinstance(data['data'], dict):
                    return data['data']
            else:
                print(f"[Batch LTP] HTTP {r.status_code}, retrying...", flush=True)
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            print(f"[Batch LTP] Error: {e}", flush=True)
            if attempt < _max_retries:
                time.sleep(2 ** attempt)
                continue
    print("[Batch LTP] All retries exhausted.", flush=True)
    return {}


# ═════════════════════════════════════════════════════════════════════════════
#^# BATCH OHLC FETCH — used for OH/OL (Open=High / Open=Low) detection
# ═════════════════════════════════════════════════════════════════════════════
_oh_ol_cache: dict = {}      #~# key = frozenset of sec_ids → {'data': dict, 'ts': float}
_OH_OL_CACHE_TTL = 30.0      #~# refresh every 30s (OHLC doesn't change as fast)


def fetch_batch_ohlc(security_ids: list, exchange_seg: str = "NSE_FNO",
                     _max_retries: int = 2) -> dict:
    """Fetch OHLC for multiple securities in ONE API call.

    Args:
        security_ids: list of int security IDs.
        exchange_seg: exchange segment (default NSE_FNO for options).
    Returns:
        dict  {str(sec_id): {'ohlc': {'open':..,'high':..,'low':..,'close':..}, 'last_price':..}}
    """
    if not security_ids:
        return {}

    #~# Check cache
    cache_key = (exchange_seg, frozenset(security_ids))
    cached = _oh_ol_cache.get(cache_key)
    if cached and (time.time() - cached['ts']) < _OH_OL_CACHE_TTL:
        return cached['data']

    url = "https://api.dhan.co/v2/marketfeed/ohlc"
    payload = {exchange_seg: security_ids}
    for attempt in range(_max_retries + 1):
        try:
            r = requests.post(url, json=payload, headers=API_HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if _is_rate_limited(data):
                    time.sleep(2 ** attempt)
                    continue
                seg_data = (data.get('data', {}) or {}).get(exchange_seg, {})
                _oh_ol_cache[cache_key] = {'data': seg_data, 'ts': time.time()}
                return seg_data
            else:
                time.sleep(1)
        except Exception:
            if attempt < _max_retries:
                time.sleep(1)
    return {}


def enrich_oh_ol(df: pd.DataFrame) -> pd.DataFrame:
    """Add C_OH_OL and P_OH_OL columns to option DataFrame.

    Values: 'OH' (Open=High), 'OL' (Open=Low), or '' (neither).
    Uses batch OHLC fetch for all CE/PE security IDs in a single API call.
    """
    if df.empty:
        return df

    #~# Collect all CE/PE security IDs
    ce_ids = df['C_SECURITY_ID'].dropna().astype(int).tolist() if 'C_SECURITY_ID' in df.columns else []
    pe_ids = df['P_SECURITY_ID'].dropna().astype(int).tolist() if 'P_SECURITY_ID' in df.columns else []
    all_ids = [sid for sid in ce_ids + pe_ids if sid > 0]

    if not all_ids:
        df['C_OH_OL'] = ''
        df['P_OH_OL'] = ''
        return df

    #~# Batch fetch OHLC for all options
    ohlc_data = fetch_batch_ohlc(all_ids, exchange_seg="NSE_FNO")

    c_tags = []
    p_tags = []
    for _, row in df.iterrows():
        #~# CE side
        ce_sid = str(int(row.get('C_SECURITY_ID', 0) or 0))
        ce_quote = ohlc_data.get(ce_sid, {})
        ce_ohlc = ce_quote.get('ohlc', {}) or {}
        c_open = float(ce_ohlc.get('open', 0) or 0)
        c_high = float(ce_ohlc.get('high', 0) or 0)
        c_low = float(ce_ohlc.get('low', 0) or 0)
        c_tag = ''
        if c_open > 0 and c_high > 0 and c_low > 0:
            if c_open == c_high:
                c_tag = 'OH'
            elif c_open == c_low:
                c_tag = 'OL'
        c_tags.append(c_tag)

        #~# PE side
        pe_sid = str(int(row.get('P_SECURITY_ID', 0) or 0))
        pe_quote = ohlc_data.get(pe_sid, {})
        pe_ohlc = pe_quote.get('ohlc', {}) or {}
        p_open = float(pe_ohlc.get('open', 0) or 0)
        p_high = float(pe_ohlc.get('high', 0) or 0)
        p_low = float(pe_ohlc.get('low', 0) or 0)
        p_tag = ''
        if p_open > 0 and p_high > 0 and p_low > 0:
            if p_open == p_high:
                p_tag = 'OH'
            elif p_open == p_low:
                p_tag = 'OL'
        p_tags.append(p_tag)

    df['C_OH_OL'] = c_tags
    df['P_OH_OL'] = p_tags

    #~# Summary logging
    c_oh = c_tags.count('OH')
    c_ol = c_tags.count('OL')
    p_oh = p_tags.count('OH')
    p_ol = p_tags.count('OL')
    if c_oh or c_ol or p_oh or p_ol:
        print(f"[OH/OL] CE: {c_oh} OH, {c_ol} OL | PE: {p_oh} OH, {p_ol} OL  ({len(df)} strikes)", flush=True)

    return df


# ═════════════════════════════════════════════════════════════════════════════
#^# INSTRUMENT FILE CACHE — read CSV once per date, reuse everywhere
# ═════════════════════════════════════════════════════════════════════════════
_instrument_df_cache: Optional[pd.DataFrame] = None
_instrument_df_date: Optional[str] = None    #~# date string of the cached file
_instrument_df_path: Optional[str] = None    #~# path of the cached file


def _get_instrument_df() -> Optional[pd.DataFrame]:
    """* Load instrument CSV once per date. Returns cached DataFrame on subsequent calls.

    If the same day's file is already loaded, returns from memory instantly.
    If a new date's file appears, reads it fresh and caches it.
    """
    global _instrument_df_cache, _instrument_df_date, _instrument_df_path
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    #~# Same date already cached → return immediately
    if _instrument_df_cache is not None and _instrument_df_date == today_str:
        return _instrument_df_cache

    try:
        base = INSTRUMENTS_DIR
        instrument_path = base / f"all_instrument {today_str}.csv"
        if not instrument_path.exists():
            files = sorted(glob.glob(str(base / "all_instrument*.csv")))
            if files:
                instrument_path = Path(files[-1])
            else:
                return None

        path_str = str(instrument_path)

        #~# Same file path already cached (date didn't change but called again) → skip re-read
        if _instrument_df_cache is not None and _instrument_df_path == path_str:
            _instrument_df_date = today_str
            return _instrument_df_cache

        print(f"[Cache] Reading instrument file: {instrument_path.name}")
        df = pd.read_csv(instrument_path, low_memory=False)
        _instrument_df_cache = df
        _instrument_df_date = today_str
        _instrument_df_path = path_str
        return df
    except Exception as e:
        print(f"[Cache] Error reading instrument file: {e}")
        return _instrument_df_cache  #~# return stale cache if available


def _get_futures_instrument(underlying: str = "NIFTY") -> Tuple[int, str]:
    """* Return (security_id, expiry_str) for nearest futures contract. Cached 1 hour."""
    cache_key = f"fut_inst_{underlying}"
    cached_inst = _cache_get(cache_key, ttl=3600)
    if cached_inst:
        return cached_inst
    try:
        df = _get_instrument_df()
        if df is None or df.empty:
            return (0, "")
        fut_prefix = f"{underlying} "
        fut_df = df[
            (df['SEM_INSTRUMENT_NAME'] == 'FUTIDX') &
            (df['SEM_CUSTOM_SYMBOL'].str.startswith(fut_prefix, na=False))
        ].copy()
        if fut_df.empty:
            return (0, "")
        fut_df['expiry_parsed'] = pd.to_datetime(fut_df['SEM_EXPIRY_DATE'])
        today = pd.Timestamp(datetime.date.today())
        fut_df = fut_df[fut_df['expiry_parsed'] >= today].sort_values('expiry_parsed')
        if fut_df.empty:
            return (0, "")
        nearest = fut_df.iloc[0]
        sec_id = int(nearest.get('SEM_SMST_SECURITY_ID', 0))
        expiry_str = nearest['expiry_parsed'].strftime("%d-%b-%Y")
        _cache_set(cache_key, (sec_id, expiry_str))
        return (sec_id, expiry_str)
    except Exception:
        return (0, "")


# ═════════════════════════════════════════════════════════════════════════════
#^# VIX  (Tradehull for live data, Dhan API fallback)
# ═════════════════════════════════════════════════════════════════════════════
# VIX_CACHE_FILE imported from paths.py
_vix_yesterday_cache: Optional[float] = None  #~# Cached yesterday's close
_vix_change_cache: Optional[float] = None      #~# Cached percent change
_last_valid_vix: Optional[float] = None        #~# Last valid VIX from API

def _load_vix_cache() -> dict:
    """* Load VIX cache from JSON file."""
    try:
        if VIX_CACHE_FILE.exists():
            with open(VIX_CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_vix_cache(cache: dict):
    """* Save VIX cache to JSON file."""
    try:
        VIX_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(VIX_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def get_vix_data() -> Tuple[float, float, float]:
    """* Returns (vix_current, vix_change_pct, vix_yesterday). Cached 15s.
    
    * Formula (same as PineScript):
        vix_today   = current live VIX price
        vix_yesterday = previous trading day close (from CSV)
        change_pct  = (vix_today - vix_yesterday) / vix_yesterday * 100
    
    * LIVE VIX SOURCES (in order):
    1. Tradehull get_ltp_data(["INDIA VIX"]) — real-time
    2. Dhan LTP API (security ID 21)
    3. Today's CSV close (if file exists)
    4. Last valid VIX from cache (fallback)
    
    * YESTERDAY'S CLOSE:
    Read from the most recent indiavix_YYYY-MM-DD.csv 'Close' column.
    """
    global _vix_yesterday_cache, _vix_change_cache, _last_valid_vix

    cached = _cache_get('vix', ttl=15)
    if cached and cached[0] > 0:
        return cached

    # * Step 1: Get LIVE VIX (try multiple sources)
    vix_current = 0.0
    
    # Source 1: Dhan LTP API (security ID 21) — fast & reliable
    vix_current = fetch_ltp(VIX_SECURITY_ID, "IDX_I") or 0.0

    # Source 3: Today's CSV close (if exists)
    today_date = datetime.date.today()
    if vix_current <= 0:
        today_csv = VIX_DIR / f"indiavix_{today_date.strftime('%Y-%m-%d')}.csv"
        if today_csv.exists():
            try:
                df = pd.read_csv(today_csv)
                df.columns = df.columns.str.strip()
                if not df.empty and 'Close' in df.columns:
                    vix_current = float(str(df['Close'].iloc[0]).replace(',', '').strip())
            except Exception:
                pass
    
    # Source 4: Last valid VIX from cache
    if vix_current <= 0 and _last_valid_vix and _last_valid_vix > 0:
        vix_current = _last_valid_vix
    elif vix_current <= 0:
        # Try loading from file (after restart)
        try:
            cache = _load_vix_cache()
            saved = cache.get('last_valid_vix', 0)
            if saved and saved > 0:
                vix_current = saved
        except Exception:
            pass
    
    # Store valid VIX for future fallback
    if vix_current > 0:
        _last_valid_vix = vix_current
        try:
            cache = _load_vix_cache()
            cache['last_valid_vix'] = vix_current
            _save_vix_cache(cache)
        except Exception:
            pass

    # * Step 2: Get YESTERDAY'S CLOSE from CSV
    # Like PineScript: vix_yesterday = close[1] (previous day's close)
    vix_yesterday = 0.0
    for days_back in range(1, 8):
        check_date = today_date - datetime.timedelta(days=days_back)
        csv_path = VIX_DIR / f"indiavix_{check_date.strftime('%Y-%m-%d')}.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                df.columns = df.columns.str.strip()
                if not df.empty and 'Close' in df.columns:
                    vix_yesterday = float(str(df['Close'].iloc[0]).replace(',', '').strip())
                    break
            except Exception:
                continue

    # * Step 3: Calculate % change (PineScript formula)
    # change = (vix_today - vix_yesterday) / vix_yesterday * 100
    vix_change_pct = 0.0
    if vix_current > 0 and vix_yesterday > 0:
        vix_change_pct = ((vix_current - vix_yesterday) / vix_yesterday) * 100
        _vix_change_cache = vix_change_pct
        try:
            cache = _load_vix_cache()
            cache['last_change_pct'] = vix_change_pct
            _save_vix_cache(cache)
        except Exception:
            pass
    elif _vix_change_cache is not None:
        vix_change_pct = _vix_change_cache
    else:
        try:
            cache = _load_vix_cache()
            _vix_change_cache = cache.get('last_change_pct', 0.0)
            vix_change_pct = _vix_change_cache
        except Exception:
            vix_change_pct = 0.0
    
    _vix_yesterday_cache = vix_yesterday

    result = (vix_current, vix_change_pct, vix_yesterday)
    if vix_current > 0:
        _cache_set('vix', result)
    return result


# ═════════════════════════════════════════════════════════════════════════════
#^# FUTURES DATA HANDLING
# ═════════════════════════════════════════════════════════════════════════════
def get_futures_info(underlying: str = "NIFTY") -> Tuple[float, str]:
    """* Returns (fut_price, fut_expiry_str) using instrument file + LTP API"""
    sec_id, expiry_str = _get_futures_instrument(underlying)
    if sec_id > 0:
        fut_ltp = fetch_ltp(sec_id, "NSE_FNO")
        if fut_ltp:
            return fut_ltp, expiry_str
    return 0.0, expiry_str


# ═════════════════════════════════════════════════════════════════════════════
#^# FUTURES BUILD-UP DATA (OI Analysis)
# ═════════════════════════════════════════════════════════════════════════════
_futures_instruments_cache: Optional[list] = None

def _load_futures_instruments(underlying: str = "NIFTY") -> list:
    """* Load futures instruments from instrument file"""
    global _futures_instruments_cache
    if _futures_instruments_cache is not None:
        return _futures_instruments_cache

    try:
        df = _get_instrument_df()
        if df is None or df.empty:
            _futures_instruments_cache = []
            return []

        fut_prefix = f"{underlying} "
        fut_df = df[
            (df['SEM_INSTRUMENT_NAME'] == 'FUTIDX') &
            (df['SEM_CUSTOM_SYMBOL'].str.startswith(fut_prefix, na=False))
        ].copy()

        if fut_df.empty:
            _futures_instruments_cache = []
            return []

        fut_df['expiry_parsed'] = pd.to_datetime(fut_df['SEM_EXPIRY_DATE'])
        today = pd.Timestamp(datetime.date.today())
        fut_df = fut_df[fut_df['expiry_parsed'] >= today].sort_values('expiry_parsed')

        instruments = []
        for _, row in fut_df.iterrows():
            instruments.append({
                'symbol': row['SEM_CUSTOM_SYMBOL'],
                'expiry': row['expiry_parsed'].strftime("%d-%b-%Y"),
                'expiry_key': row['expiry_parsed'].strftime("%Y-%m-%d"),
                'security_id': int(row.get('SEM_SMST_SECURITY_ID', 0)),
            })

        _futures_instruments_cache = instruments
        return instruments
    except Exception:
        _futures_instruments_cache = []
        return []


def _fetch_futures_quotes(security_ids: list) -> dict:
    """* Fetch market quotes for futures contracts via DhanHQ API"""
    url = "https://api.dhan.co/v2/marketfeed/quote"
    headers = {
        'access-token': token_id,
        'client-id': str(client_code),
        'Content-Type': 'application/json'
    }
    payload = {"NSE_FNO": security_ids}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'NSE_FNO' in data['data']:
                return data['data']['NSE_FNO']
        return {}
    except Exception:
        return {}


def load_previous_futures_data(underlying: str = "NIFTY") -> list:
    """* Load previous day's futures data from CSV for build-up calculation"""
    pattern = f"{underlying}_FUTURE_*.csv"
    csv_files = list(FUTURES_DIR.glob(pattern))

    if not csv_files:
        return []

    csv_files_sorted = sorted(csv_files, key=lambda x: x.stem, reverse=True)
    today_str = datetime.date.today().strftime('%Y-%m-%d')

    csv_file = None
    for f in csv_files_sorted:
        date_part = f.stem.replace(f'{underlying}_FUTURE_', '')
        if date_part != today_str:
            csv_file = f
            break

    if csv_file is None and csv_files_sorted:
        csv_file = csv_files_sorted[0]

    if not csv_file:
        return []

    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig')
        df.columns = [c.strip().replace('\n', ' ').replace('\r', '') for c in df.columns]

        result = []
        for _, row in df.iterrows():
            expiry_raw = str(row.iloc[2]).strip()
            ltp = parse_indian_number(row.iloc[5])
            oi = parse_indian_number(row.iloc[13]) if len(df.columns) > 13 else 0

            try:
                expiry_date = datetime.datetime.strptime(expiry_raw, "%d-%b-%Y").date()
                expiry_key = expiry_date.strftime("%Y-%m-%d")
            except Exception:
                expiry_key = expiry_raw

            result.append({
                'expiry': expiry_raw,
                'expiry_key': expiry_key,
                'prev_ltp': ltp,
                'prev_oi': oi,
            })
        return result
    except Exception:
        return []


_prev_futures_cache: Optional[list] = None
# Add a new cache for last valid buildup results
_last_valid_futures_buildup: Optional[list] = None  #~# Persists last good result

def get_futures_buildup_data(underlying: str = "NIFTY") -> list:
    """
    * Get futures build-up data: live OI + LTP merged with previous day.
    * Returns list of dicts with expiry, ltp, prev_ltp, oi, prev_oi, oi_chg_pct, ltp_chg_pct, buildup.
    * Falls back to last valid data if live quotes return zero OI/LTP.
    """
    global _prev_futures_cache, _last_valid_futures_buildup

    instruments = _load_futures_instruments(underlying)
    if not instruments:
        return _last_valid_futures_buildup or []

    # * Load previous data once
    if _prev_futures_cache is None:
        _prev_futures_cache = load_previous_futures_data(underlying)

    # * Fetch live LTP + OI in ONE batch via quote API (saves N-1 API calls)
    security_ids = [inst['security_id'] for inst in instruments if inst['security_id'] > 0]
    quotes = {}
    if security_ids:
        quotes = _fetch_futures_quotes(security_ids)

    # * Build previous data lookup
    prev_lookup = {}
    for p in (_prev_futures_cache or []):
        prev_lookup[p['expiry_key']] = p

    lot_size = LOT_SIZE_MAP.get(underlying, 65)  #~# Used to normalize API OI (qty→contracts)
    results = []
    any_valid = False  #~# Track if at least one contract has valid live data

    for inst in instruments:
        quote = quotes.get(str(inst['security_id']), {})
        ltp = float(quote.get('last_price', 0) or 0)
        oi_qty = int(quote.get('oi', 0) or quote.get('open_interest', 0) or quote.get('OI', 0) or 0)

        #!# Dhan API returns OI in qty (shares), CSV stores OI in contracts
        #!# Normalize: divide live OI qty by lot_size → contracts for apples-to-apples comparison
        oi_contracts = oi_qty // lot_size if lot_size > 0 else oi_qty

        prev = prev_lookup.get(inst['expiry_key'], {})
        prev_ltp = prev.get('prev_ltp', 0)
        prev_oi = prev.get('prev_oi', 0)  #~# Already in contracts (from NSE CSV)

        # !# Skip calculation if live data is absent (zero OI AND zero LTP)
        # !# This prevents false -100% readings when API returns no data
        live_data_valid = ltp > 0 or oi_qty > 0
        if live_data_valid:
            any_valid = True

        #~# Both sides now in contracts — no more ~6500% inflation
        oi_chg_pct = ((oi_contracts - prev_oi) / prev_oi * 100) if (prev_oi > 0 and live_data_valid) else 0
        ltp_chg_pct = ((ltp - prev_ltp) / prev_ltp * 100) if (prev_ltp > 0 and live_data_valid) else 0

        # Determine build-up only when live data is valid
        if live_data_valid:
            if oi_contracts > prev_oi and ltp > prev_ltp:
                buildup = "Long Build Up"
            elif oi_contracts > prev_oi and ltp <= prev_ltp:
                buildup = "Short Build Up"
            elif oi_contracts <= prev_oi and ltp > prev_ltp:
                buildup = "Short Covering"
            else:
                buildup = "Long Unwinding"
        else:
            buildup = ""  #~# Unknown — no live data yet

        results.append({
            'expiry': inst['expiry'],
            'ltp': ltp,
            'prev_ltp': prev_ltp,
            'oi': oi_contracts,        #~# Normalized to contracts (for display & signal)
            'oi_qty': oi_qty,          #~# Raw qty from Dhan API (for debug/logging)
            'prev_oi': prev_oi,        #~# Prev day close OI in contracts (from CSV)
            'lot_size': lot_size,      #~# Lot size used for normalization
            'oi_chg_pct': oi_chg_pct,
            'ltp_chg_pct': ltp_chg_pct,
            'buildup': buildup,
        })

    # !# If NO contract has valid live data, return last known good result
    if not any_valid and _last_valid_futures_buildup:
        return _last_valid_futures_buildup

    # * Update cache only when we have valid data
    if any_valid:
        _last_valid_futures_buildup = results

    return results


# ═════════════════════════════════════════════════════════════════════════════
#^# PREVIOUS DAY DATA (Cache & Reference)
# ═════════════════════════════════════════════════════════════════════════════
def load_previous_day_data(underlying: str = "NIFTY") -> Dict[float, dict]:
    prev_data = {}
    csv_files = list(OPTIONCHAIN_CSV_DIR.glob("????-??-??.csv"))
    csv_file = None

    if csv_files:
        csv_files_sorted = sorted(csv_files, key=lambda x: x.stem, reverse=True)
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        for f in csv_files_sorted:
            if f.stem != today_str:
                csv_file = f
                break
        if csv_file is None and csv_files_sorted:
            csv_file = csv_files_sorted[0]

    if csv_file and csv_file.exists():
        try:
            df = pd.read_csv(csv_file, skiprows=1, header=0)
            for _, row in df.iterrows():
                strike = parse_indian_number(row.get('STRIKE', None))
                if strike > 0:
                    prev_data[strike] = {
                        'call_ltp': parse_indian_number(row.get('LTP', 0)),
                        'put_ltp': parse_indian_number(row.get('LTP.1', 0)),
                        'call_oi': parse_indian_number(row.get('OI', 0)),
                        'put_oi': parse_indian_number(row.get('OI.1', 0)),
                    }
        except Exception:
            pass

    return prev_data


# ═════════════════════════════════════════════════════════════════════════════
#^# CORE: PARSE OPTION CHAIN → DataFrame
# ═════════════════════════════════════════════════════════════════════════════
def parse_option_chain(oc_data: dict, spot_price: float, underlying: str,
                       num_strikes: int = 15,
                       prev_day: Optional[Dict[float, dict]] = None
                       ) -> Tuple[float, pd.DataFrame, pd.DataFrame]:
    """
    * Parse raw API response into DataFrames.
    * Returns (atm_strike, filtered_df, full_df)
    """
    if not oc_data or oc_data.get('status') != 'success':
        return 0, pd.DataFrame(), pd.DataFrame()

    data = oc_data.get('data', {})
    last_price = data.get('last_price', spot_price)
    oc = data.get('oc', {})
    if not oc:
        return 0, pd.DataFrame(), pd.DataFrame()

    lot_size = LOT_SIZE_MAP.get(underlying, 65)
    prev_day = prev_day or {}

    rows = []
    for strike_key, strike_data in oc.items():
        try:
            strike = float(strike_key)
            ce = strike_data.get('ce', {})
            pe = strike_data.get('pe', {})

            call_ltp = ce.get('last_price', 0) or 0
            put_ltp = pe.get('last_price', 0) or 0

            # Previous day data
            prev = prev_day.get(strike, {})
            call_prev_close = prev.get('call_ltp', 0) or 0
            put_prev_close = prev.get('put_ltp', 0) or 0

            # OI (in contracts from API)
            call_oi_contracts = ce.get('oi', 0) or 0
            put_oi_contracts = pe.get('oi', 0) or 0
            call_oi_lots = call_oi_contracts / lot_size
            put_oi_lots = put_oi_contracts / lot_size

            call_prev_oi = ce.get('previous_oi', 0) or 0
            put_prev_oi = pe.get('previous_oi', 0) or 0
            call_oi_chg = call_oi_contracts - call_prev_oi
            put_oi_chg = put_oi_contracts - put_prev_oi

            # LTP change %
            call_pct = 0.0
            if call_prev_close > 0 and call_ltp > 0:
                call_pct = ((call_ltp - call_prev_close) / call_prev_close) * 100
            put_pct = 0.0
            if put_prev_close > 0 and put_ltp > 0:
                put_pct = ((put_ltp - put_prev_close) / put_prev_close) * 100

            # OI change % (from previous OI in same day)
            call_oi_chg_pct = 0.0
            if call_prev_oi > 0:
                call_oi_chg_pct = (call_oi_chg / call_prev_oi) * 100
            put_oi_chg_pct = 0.0
            if put_prev_oi > 0:
                put_oi_chg_pct = (put_oi_chg / put_prev_oi) * 100

            # Build Up
            call_build = _get_buildup(call_oi_chg, call_pct)
            put_build = _get_buildup(put_oi_chg, put_pct)

            rows.append({
                'Strike': strike,
                'C_SECURITY_ID': int(ce.get('security_id', 0) or 0),
                'P_SECURITY_ID': int(pe.get('security_id', 0) or 0),
                'C_OI': call_oi_lots,
                'C_OI_Chg': call_oi_chg / lot_size,
                'C_OI_Chg_Pct': call_oi_chg_pct,
                'C_Volume': ce.get('volume', 0) or 0,
                'C_LTP': call_ltp,
                'C_LTP_Chg_Pct': call_pct,
                'C_IV': ce.get('implied_volatility', 0) or 0,
                'C_Bid': ce.get('top_bid_price', 0) or 0,
                'C_Ask': ce.get('top_ask_price', 0) or 0,
                'C_BuildUp': call_build,
                'P_OI': put_oi_lots,
                'P_OI_Chg': put_oi_chg / lot_size,
                'P_OI_Chg_Pct': put_oi_chg_pct,
                'P_Volume': pe.get('volume', 0) or 0,
                'P_LTP': put_ltp,
                'P_LTP_Chg_Pct': put_pct,
                'P_IV': pe.get('implied_volatility', 0) or 0,
                'P_Bid': pe.get('top_bid_price', 0) or 0,
                'P_Ask': pe.get('top_ask_price', 0) or 0,
                'P_BuildUp': put_build,
            })
        except (ValueError, TypeError):
            continue

    if not rows:
        return 0, pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(rows).sort_values('Strike').reset_index(drop=True)

    step = INDEX_STEP_MAP.get(underlying, 50)
    atm_strike = round(last_price / step) * step

    df_filtered = df[
        (df['Strike'] >= atm_strike - num_strikes * step) &
        (df['Strike'] <= atm_strike + num_strikes * step)
    ].reset_index(drop=True)

    return atm_strike, df_filtered, df


def _get_buildup(oi_chg, ltp_chg_pct):
    if oi_chg > 0 and ltp_chg_pct > 0:
        return "LB"
    elif oi_chg < 0 and ltp_chg_pct > 0:
        return "SC"
    elif oi_chg > 0 and ltp_chg_pct < 0:
        return "SB"
    elif oi_chg < 0 and ltp_chg_pct < 0:
        return "LU"
    return "-"


# ═════════════════════════════════════════════════════════════════════════════
#^# ANALYTICS / METRICS (PCR, Build-up, OTM/ITM)
# ═════════════════════════════════════════════════════════════════════════════
def calculate_metrics(full_df: pd.DataFrame, spot_price: float,
                      underlying: str = "NIFTY") -> dict:
    lot_size = LOT_SIZE_MAP.get(underlying, 65)

    m = {
        # Totals
        'total_call_oi': 0, 'total_put_oi': 0,
        'total_call_oi_chg': 0, 'total_put_oi_chg': 0,
        'total_call_vol': 0, 'total_put_vol': 0,
        # Build Up OI (LB, SC, SB, LU)
        'call_lb': 0, 'call_sc': 0, 'call_sb': 0, 'call_lu': 0, 'call_neutral': 0,
        'put_lb': 0, 'put_sc': 0, 'put_sb': 0, 'put_lu': 0, 'put_neutral': 0,
        # Build Up OI Change (LB, SC, SB, LU) — tracks OI change per buildup type
        'call_lb_chg': 0, 'call_sc_chg': 0, 'call_sb_chg': 0, 'call_lu_chg': 0,
        'put_lb_chg': 0, 'put_sc_chg': 0, 'put_sb_chg': 0, 'put_lu_chg': 0,
        # PCR
        'pcr_oi': 0, 'pcr_vol': 0, 'pcr_oi_chg': 0,
        'pe_ce_diff': 0,
        # Max OI
        'max_call_oi_strike': 0, 'max_put_oi_strike': 0,
        'max_call_oi': 0, 'max_put_oi': 0,
        # OTM metrics
        'otm_call_oi': 0, 'otm_put_oi': 0,
        'otm_call_oi_chg': 0, 'otm_put_oi_chg': 0,
        'otm_call_vol': 0, 'otm_put_vol': 0,
        # ITM metrics
        'itm_call_oi': 0, 'itm_put_oi': 0,
        'itm_call_oi_chg': 0, 'itm_put_oi_chg': 0,
        'itm_call_vol': 0, 'itm_put_vol': 0,
        # Premium
        'total_call_premium': 0, 'total_put_premium': 0,
        # Premium Change (OI_Chg * LTP)
        'total_call_premium_chg': 0, 'total_put_premium_chg': 0,
        # Bullish/Bearish OI
        'bullish_oi': 0, 'bearish_oi': 0,
        'bullish_oi_chg': 0, 'bearish_oi_chg': 0,
    }

    if full_df is None or full_df.empty:
        return m

    m['total_call_oi'] = full_df['C_OI'].sum()
    m['total_put_oi'] = full_df['P_OI'].sum()
    m['total_call_oi_chg'] = full_df['C_OI_Chg'].sum()
    m['total_put_oi_chg'] = full_df['P_OI_Chg'].sum()
    m['total_call_vol'] = full_df['C_Volume'].sum()
    m['total_put_vol'] = full_df['P_Volume'].sum()

    # PCR
    if m['total_call_oi'] > 0:
        m['pcr_oi'] = m['total_put_oi'] / m['total_call_oi']
    if m['total_call_vol'] > 0:
        m['pcr_vol'] = m['total_put_vol'] / m['total_call_vol']
    if m['total_call_oi_chg'] != 0:
        m['pcr_oi_chg'] = m['total_put_oi_chg'] / m['total_call_oi_chg']

    m['pe_ce_diff'] = m['total_put_oi_chg'] - m['total_call_oi_chg']

    # Max OI strikes (resistance / support)
    if not full_df.empty:
        max_call_idx = full_df['C_OI'].idxmax()
        max_put_idx = full_df['P_OI'].idxmax()
        m['max_call_oi_strike'] = full_df.loc[max_call_idx, 'Strike']
        m['max_put_oi_strike'] = full_df.loc[max_put_idx, 'Strike']
        m['max_call_oi'] = full_df.loc[max_call_idx, 'C_OI']
        m['max_put_oi'] = full_df.loc[max_put_idx, 'P_OI']

    # Build Up counts + OTM/ITM + Premium
    for _, row in full_df.iterrows():
        strike = row['Strike']
        cb = row.get('C_BuildUp', '-')
        pb = row.get('P_BuildUp', '-')
        c_oi = row['C_OI']
        p_oi = row['P_OI']
        c_oi_chg = row.get('C_OI_Chg', 0)
        p_oi_chg = row.get('P_OI_Chg', 0)
        c_vol = row.get('C_Volume', 0)
        p_vol = row.get('P_Volume', 0)

        # Build Up OI counts
        if cb == 'LB': m['call_lb'] += c_oi; m['call_lb_chg'] += c_oi_chg
        elif cb == 'SC': m['call_sc'] += c_oi; m['call_sc_chg'] += c_oi_chg
        elif cb == 'SB': m['call_sb'] += c_oi; m['call_sb_chg'] += c_oi_chg
        elif cb == 'LU': m['call_lu'] += c_oi; m['call_lu_chg'] += c_oi_chg
        else:           m['call_neutral'] += c_oi   #~# oi_chg==0 or ltp_chg_pct==0

        if pb == 'LB': m['put_lb'] += p_oi; m['put_lb_chg'] += p_oi_chg
        elif pb == 'SC': m['put_sc'] += p_oi; m['put_sc_chg'] += p_oi_chg
        elif pb == 'SB': m['put_sb'] += p_oi; m['put_sb_chg'] += p_oi_chg
        elif pb == 'LU': m['put_lu'] += p_oi; m['put_lu_chg'] += p_oi_chg
        else:           m['put_neutral'] += p_oi    #~# oi_chg==0 or ltp_chg_pct==0

        # Premium (OI * LTP)
        m['total_call_premium'] += c_oi * row.get('C_LTP', 0)
        m['total_put_premium'] += p_oi * row.get('P_LTP', 0)

        # Premium Change (OI_Chg * LTP — approximation of premium change)
        m['total_call_premium_chg'] += c_oi_chg * row.get('C_LTP', 0)
        m['total_put_premium_chg'] += p_oi_chg * row.get('P_LTP', 0)

        # ITM / OTM
        call_itm = strike < spot_price
        put_itm = strike > spot_price

        if call_itm:
            m['itm_call_oi'] += c_oi
            m['itm_call_oi_chg'] += c_oi_chg
            m['itm_call_vol'] += c_vol
        else:
            m['otm_call_oi'] += c_oi
            m['otm_call_oi_chg'] += c_oi_chg
            m['otm_call_vol'] += c_vol

        if put_itm:
            m['itm_put_oi'] += p_oi
            m['itm_put_oi_chg'] += p_oi_chg
            m['itm_put_vol'] += p_vol
        else:
            m['otm_put_oi'] += p_oi
            m['otm_put_oi_chg'] += p_oi_chg
            m['otm_put_vol'] += p_vol

    # Bullish/Bearish OI
    # Bullish = Call LB (price up + OI up) + Call SC (price up + OI down)
    #         + Put SB (price down + OI up = bearish for put = bullish for index)
    #         + Put LU (price down + OI down)
    m['bullish_oi'] = m['call_lb'] + m['call_sc'] + m['put_sb'] + m['put_lu']
    m['bearish_oi'] = m['call_sb'] + m['call_lu'] + m['put_lb'] + m['put_sc']

    # Bullish/Bearish OI Change
    m['bullish_oi_chg'] = m['call_lb_chg'] + m['call_sc_chg'] + m['put_sb_chg'] + m['put_lu_chg']
    m['bearish_oi_chg'] = m['call_sb_chg'] + m['call_lu_chg'] + m['put_lb_chg'] + m['put_sc_chg']

    # Aliases with _oi suffix for richprint compatibility
    m['call_lb_oi'] = m['call_lb']
    m['call_sc_oi'] = m['call_sc']
    m['call_sb_oi'] = m['call_sb']
    m['call_lu_oi'] = m['call_lu']
    m['put_lb_oi'] = m['put_lb']
    m['put_sc_oi'] = m['put_sc']
    m['put_sb_oi'] = m['put_sb']
    m['put_lu_oi'] = m['put_lu']

    return m


# ═════════════════════════════════════════════════════════════════════════════
#^# HIGH-LEVEL: FETCH EVERYTHING IN ONE CALL
# ═════════════════════════════════════════════════════════════════════════════
_prev_day_cache: Dict[str, Dict[float, dict]] = {}  #~# Per-underlying cache
_last_fetch_time = 0.0                             #&# Rate limit control


def fetch_all_data(underlying: str = "NIFTY", expiry_index: int = 0,
                   num_strikes: int = 15) -> dict:
    """
    * Single function to fetch all live data via optimized batch calls.
    * Returns dict with all display data needed by Streamlit/Gradio.
    * Batches spot/VIX/futures in ONE API call to minimize latency.
    """
    global _last_fetch_time

    # * Rate limit (OPTION_CHAIN_DELAY = 0 → no sleep needed for 20 req/sec option chain)
    elapsed = time.time() - _last_fetch_time
    if elapsed < OPTION_CHAIN_DELAY:
        time.sleep(OPTION_CHAIN_DELAY - elapsed)

    result = {
        'underlying': underlying,
        'spot_price': 0.0,
        'atm_strike': 0,
        'expiry': '',
        'expiry_list': [],
        'update_time': datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S"),
        'vix_current': 0.0, 'vix_change_pct': 0.0, 'vix_yesterday': 0.0,
        'fut_price': 0.0, 'fut_expiry': '',
        'option_df': pd.DataFrame(),
        'full_df': pd.DataFrame(),
        'metrics': {},
        'futures_buildup': [],
        'error': None,
    }

    try:
        security_id = INDEX_SECURITY_IDS.get(underlying)
        if not security_id:
            result['error'] = f"Unknown underlying: {underlying}"
            return result

        # ── Single batch LTP: spot + VIX + near futures in ONE API call ──────
        try:
            fut_sec_id_pre, fut_expiry_pre = _get_futures_instrument(underlying)
        except Exception:
            fut_sec_id_pre, fut_expiry_pre = 0, ''
        batch_pl = {"IDX_I": [security_id, VIX_SECURITY_ID]}
        if fut_sec_id_pre > 0:
            batch_pl["NSE_FNO"] = [fut_sec_id_pre]
        try:
            bltp = fetch_batch_ltp(batch_pl)
        except Exception:
            bltp = {}
        idx_d = bltp.get("IDX_I", {})

        # * Spot (from batch)
        spot_price = float((idx_d.get(str(security_id)) or {}).get("last_price", 0) or 0)
        if spot_price <= 0:
            spot_price = get_cached_spot_price(underlying)
        else:
            update_spot_price_cache(underlying, spot_price)
        result['spot_price'] = spot_price

        # * Expiry list
        expiry_list = fetch_expiry_list(security_id, "IDX_I")
        result['expiry_list'] = expiry_list
        if not expiry_list:
            result['error'] = "Could not fetch expiry dates. Market may be closed."
            return result
        if expiry_index >= len(expiry_list):
            expiry_index = 0
        result['expiry'] = expiry_list[expiry_index]

        # * VIX (from batch; inject into cache so get_vix_data() stays fast)
        vix_batch = float((idx_d.get(str(VIX_SECURITY_ID)) or {}).get("last_price", 0) or 0)
        if vix_batch > 0:
            vix_yday = _vix_yesterday_cache or 0.0
            if not vix_yday:
                _, _, vix_yday = get_vix_data()   # * first call: loads yesterday from CSV
            vix_chg = round((vix_batch - vix_yday) / vix_yday * 100, 2) if vix_yday > 0 else 0.0
            _cache_set('vix', (vix_batch, vix_chg, vix_yday))  # * refresh 15s cache
            result['vix_current'], result['vix_change_pct'], result['vix_yesterday'] = vix_batch, vix_chg, vix_yday
        else:
            result['vix_current'], result['vix_change_pct'], result['vix_yesterday'] = get_vix_data()

        # * Futures (from batch)
        if fut_sec_id_pre > 0:
            fno_d = bltp.get("NSE_FNO", {})
            fp = float((fno_d.get(str(fut_sec_id_pre)) or {}).get("last_price", 0) or 0)
            result['fut_price']  = round(fp, 2) if fp > 0 else 0.0
            result['fut_expiry'] = fut_expiry_pre
        else:
            result['fut_price'], result['fut_expiry'] = get_futures_info(underlying)

        # Previous day data (cached per underlying)
        if underlying not in _prev_day_cache:
            _prev_day_cache[underlying] = load_previous_day_data(underlying)
        prev_day = _prev_day_cache[underlying]

        # * Option chain (separate call; 20 req/sec limit)
        oc_data = fetch_option_chain(security_id, "IDX_I", result['expiry'])
        _last_fetch_time = time.time()

        atm, df_filtered, full_df = parse_option_chain(
            oc_data, result['spot_price'], underlying, num_strikes, prev_day
        )
        result['atm_strike'] = atm

        # * Enrich with OH/OL (Open=High / Open=Low) tags via batch OHLC fetch
        df_filtered = enrich_oh_ol(df_filtered)
        full_df = enrich_oh_ol(full_df)

        result['option_df'] = df_filtered
        result['full_df'] = full_df

        # * If ATM couldn't be determined from API (atm==0), fallback to rounding spot price
        try:
            if (not result['atm_strike'] or int(result['atm_strike']) == 0) and result.get('spot_price', 0) > 0:
                step = INDEX_STEP_MAP.get(underlying, 50)
                result['atm_strike'] = int(round(result['spot_price'] / step) * step)
        except Exception:
            pass

        # * Attempt to save today's opening straddle on first successful fetch (if not already saved)
        try:
            saved = _load_saved_opening_straddle(underlying)
            # saved is dict(); if empty or has no strike saved, try to compute and save
            if not saved or not saved.get('strike'):
                if not full_df.empty:
                    # prefer filtered DF (contains ATM nearby); fallback to full_df
                    df_for_straddle = df_filtered if not df_filtered.empty else full_df

                    # Determine the ATM strike to use for the day's opening straddle.
                    # Use ensure_day_open_synced() as the single source of truth — it
                    # fetches via the OHLC endpoint and caches in day_open_sync.json.
                    opening_price = 0.0
                    try:
                        day_open_info = ensure_day_open_synced(underlying, spot_price=result.get('spot_price', 0))
                        op = day_open_info.get('open_price', 0)
                        if op and op > 0:
                            opening_price = float(op)
                    except Exception:
                        opening_price = 0.0

                    # Fallback to atm_strike from option chain when opening price unavailable
                    if opening_price and opening_price > 0:
                        step = INDEX_STEP_MAP.get(underlying, 50)
                        opening_atm = int(round(opening_price / step) * step)
                    else:
                        opening_atm = int(result.get('atm_strike', 0) or 0)

                    if opening_atm and opening_atm > 0:
                        strd = get_straddle_price(opening_atm, result.get('spot_price', 0), df_for_straddle)
                        if not strd.get('error'):
                            # Attempt to find option security ids for the chosen strike so
                            # the saver can fetch the static daily OPEN for each option.
                            call_sec_id = 0
                            put_sec_id = 0
                            try:
                                chosen = int(strd.get('strike', int(opening_atm)))
                                match = df_for_straddle[df_for_straddle['Strike'] == chosen]
                                if not match.empty:
                                    row = match.iloc[0]
                                    call_sec_id = int(row.get('C_SECURITY_ID', 0) or 0)
                                    put_sec_id = int(row.get('P_SECURITY_ID', 0) or 0)
                            except Exception:
                                call_sec_id = 0
                                put_sec_id = 0

                            _save_opening_straddle(
                                underlying,
                                strd.get('strike', int(opening_atm)),
                                strd.get('call_ltp', 0),
                                strd.get('put_ltp', 0),
                                call_sec_id,
                                put_sec_id
                            )
        except Exception:
            pass

        # * Metrics (PCR, OTM/ITM, Build-up counts)
        result['metrics'] = calculate_metrics(full_df, result['spot_price'], underlying)

        # * Save OI snapshot for Change in OI history
        save_oi_snapshot(full_df, underlying)

        # * Previous OI snapshot (for Change in OI chart comparison)
        result['prev_oi_snapshot'] = get_previous_oi_snapshot(underlying)

        # * Futures build-up data
        try:
            result['futures_buildup'] = get_futures_buildup_data(underlying)
        except Exception:
            result['futures_buildup'] = []

        # * Day open price — always use ensure_day_open_synced() which fetches
        # * from OHLC API and only falls back to spot when OHLC is unavailable.
        # * Re-verifies against OHLC on every call until 'ohlc_verified'.
        try:
            sync_rec = ensure_day_open_synced(underlying, spot_price=result.get('spot_price', 0))
            result['day_open_price'] = sync_rec.get('open_price', 0.0) or 0.0
            result['day_open_ts']    = sync_rec.get('timestamp', '') or ''
        except Exception:
            result['day_open_price'] = 0.0
            result['day_open_ts']    = ''

    except Exception as e:
        result['error'] = str(e)

    return result


# =============================================================================
#^# TECHNICAL INDICATORS & INTRADAY OHLC
# =============================================================================

def calculate_rsi(prices: list, period: int = 14) -> float:
    """? Calculate RSI from price list."""
    if len(prices) < period + 1:
        return 0.0
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 0.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def calculate_vwap(closes: list, volumes: list) -> float:
    """? Calculate Volume Weight Average Price."""
    if not closes or not volumes or len(closes) != len(volumes):
        return 0.0
    
    if sum(volumes) == 0:
        return sum(closes) / len(closes) if closes else 0.0
    
    vwap = sum(c * v for c, v in zip(closes, volumes)) / sum(volumes)
    return round(vwap, 2)


def calculate_ema(prices: list, period: int = 61) -> float:
    """? Calculate EMA from price list."""
    if len(prices) < period:
        return 0.0
    
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    
    for price in prices[period:]:
        ema = price * k + ema * (1 - k)
    
    return round(ema, 2)


# =============================================================================
#^# DAY OPEN SYNC — unified open price + opening straddle strike (atomic, timestamped)
#!# Single source of truth to prevent DAY OPEN PRICE and OPENING STRADDLE divergence
# =============================================================================
# DAY_OPEN_SYNC_FILE imported from paths.py


def _load_day_open_sync(underlying: str) -> dict:
    """* Load today's day-open sync record for `underlying`. Returns {} if absent."""
    try:
        if not DAY_OPEN_SYNC_FILE.exists():
            return {}
        with open(DAY_OPEN_SYNC_FILE, 'r') as f:
            data = json.load(f)
        today = datetime.date.today().strftime("%Y-%m-%d")
        return data.get(f"{underlying}_{today}", {}) or {}
    except Exception:
        return {}


def _save_day_open_sync(underlying: str, open_price: float, atm_strike: int, source_method: str = '') -> None:
    """! Atomically write today's open_price + atm_strike to day_open_sync.json."""
    try:
        DAY_OPEN_SYNC_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if DAY_OPEN_SYNC_FILE.exists():
            try:
                with open(DAY_OPEN_SYNC_FILE, 'r') as f:
                    existing = json.load(f)
            except Exception:
                existing = {}
        today = datetime.date.today().strftime("%Y-%m-%d")
        key = f"{underlying}_{today}"
        existing[key] = {
            "open_price": round(float(open_price), 2),
            "atm_strike": int(atm_strike),
            "timestamp": datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S"),
            "date": today,
            "underlying": underlying,
            "source_method": source_method,
        }
        with open(DAY_OPEN_SYNC_FILE, 'w') as f:
            json.dump(existing, f, indent=2)
    except Exception:
        pass


def ensure_day_open_synced(underlying: str, spot_price: float = 0.0) -> dict:
    """!
    Ensure DAY OPEN PRICE and OPENING STRADDLE STRIKE are always in sync.

    Rules
    -----
    - Today's record already in day_open_sync.json  -> return it (cached_today).
      BUT: if source was 'fallback' or open looks suspicious, re-verify via OHLC API.
    - Weekday and time >= 09:16 AM and no today record:
        * Fetch open price via Dhan OHLC API.
        * ATM strike = round(open_price / step) * step.
        * Save both atomically with full timestamp (live).
    - No live data: return most recent record from any previous date (previous).
    - Nothing at all: use spot_price / cached spot (fallback).

    Returns dict with keys:
        open_price, atm_strike, timestamp, date, underlying, source
    """
    #~# 1. Already have today's record?
    rec = _load_day_open_sync(underlying)
    cached_exists = bool(rec and rec.get('open_price', 0) > 0)

    #~# If we have a cached record AND it was fetched via live OHLC (verified), return it
    if cached_exists and rec.get('source_method') == 'ohlc_verified':
        rec['source'] = 'cached_today'
        return rec

    #~# 2. Attempt live OHLC fetch (weekday + past 09:16)
    now = datetime.datetime.now()
    past_916 = now >= now.replace(hour=9, minute=16, second=0, microsecond=0)
    is_weekday = now.weekday() <= 4

    if is_weekday and past_916:
        security_id = INDEX_SECURITY_IDS.get(underlying, 0)
        ohlc_open = 0.0
        if security_id:
            try:
                r = requests.post(
                    "https://api.dhan.co/v2/marketfeed/ohlc",
                    json={"IDX_I": [security_id]},
                    headers=API_HEADERS, timeout=10
                )
                if r.status_code == 200:
                    body = r.json()
                    quote = (body.get('data', {})
                                 .get('IDX_I', {})
                                 .get(str(security_id), {}))
                    ohlc_open = float(
                        (quote.get('ohlc') or {}).get('open', 0) or 0
                    )
            except Exception:
                pass

        #~# Use OHLC open if available; otherwise keep existing or fallback to spot
        if ohlc_open > 0:
            open_price = ohlc_open
            source_method = 'ohlc_verified'
        elif cached_exists:
            #~# OHLC failed but we already have a cached value — keep it
            rec['source'] = 'cached_today'
            return rec
        else:
            #~# No OHLC and no cache — fallback to spot (will be re-verified next cycle)
            open_price = spot_price or get_cached_spot_price(underlying)
            source_method = 'spot_fallback'

        if open_price > 0:
            #~# Only overwrite if OHLC verified OR no existing record
            if source_method == 'ohlc_verified' or not cached_exists:
                step = INDEX_STEP_MAP.get(underlying, 50)
                atm_strike = int(round(open_price / step) * step)
                _save_day_open_sync(underlying, open_price, atm_strike, source_method=source_method)
                _save_opening_price(underlying, open_price)   #~# keep legacy cache in sync
            rec = _load_day_open_sync(underlying)
            if rec:
                rec['source'] = 'live'
                return rec
    elif cached_exists:
        #~# Not past 9:16 or weekend, but we have a cached record
        rec['source'] = 'cached_today'
        return rec

    #~# 3. Most recent record from a previous date
    try:
        if DAY_OPEN_SYNC_FILE.exists():
            with open(DAY_OPEN_SYNC_FILE, 'r') as f:
                all_data = json.load(f)
            prefix = f"{underlying}_"
            candidates = [
                (k, v) for k, v in all_data.items() if k.startswith(prefix)
            ]
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                prev_rec = dict(candidates[0][1])
                prev_rec['source'] = 'previous'
                return prev_rec
    except Exception:
        pass

    #!# 4. Absolute fallback
    step = INDEX_STEP_MAP.get(underlying, 50)
    fallback_spot = spot_price or get_cached_spot_price(underlying)
    atm_fallback = int(round(fallback_spot / step) * step) if fallback_spot > 0 else 0
    return {
        "open_price": round(float(fallback_spot), 2),
        "atm_strike": atm_fallback,
        "timestamp": "",
        "date": "",
        "underlying": underlying,
        "source": "fallback",
    }


def _get_opening_price_cache_file() -> str:
    """? Get the path to the opening price cache JSON file."""
    DAY_OPENING_PRICES_FILE.parent.mkdir(parents=True, exist_ok=True)
    return str(DAY_OPENING_PRICES_FILE)


def _load_saved_opening_price(underlying: str) -> float:
    """?
    Load the saved opening price for today from JSON file.
    Returns the opening price if saved for today, else 0.
    """
    import json
    import os
    import datetime
    
    try:
        cache_file = _get_opening_price_cache_file()
        if not os.path.exists(cache_file):
            return 0

        with open(cache_file, 'r') as f:
            data = json.load(f)

        today = datetime.date.today().strftime("%Y-%m-%d")
        key = f"{underlying}_{today}"
        saved_price = data.get(key, 0)
        return float(saved_price) if saved_price else 0
    except Exception:
        return 0


def _load_latest_opening_price(underlying: str) -> tuple:
    """?
    Load the most recently saved opening price for any date.
    Returns a tuple (price: float, date_str: str) or (0, "") when none.
    """
    import json
    import os
    try:
        cache_file = _get_opening_price_cache_file()
        if not os.path.exists(cache_file):
            return 0, ''
        with open(cache_file, 'r') as f:
            data = json.load(f)
        # Find keys matching underlying_YYYY-MM-DD and pick the latest date
        prefix = f"{underlying}_"
        candidates = []
        for k, v in data.items():
            if k.startswith(prefix):
                date_part = k.replace(prefix, '')
                candidates.append((date_part, v))
        if not candidates:
            return 0, ''
        # sort by date descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        latest_date, latest_val = candidates[0]
        return float(latest_val), str(latest_date)
    except Exception:
        return 0, ''


def _save_opening_price(underlying: str, price: float) -> None:
    """!
    Save the opening price for today to JSON file.
    One price per underlying per day - never overwrites if already saved.
    """
    import json
    import os
    import datetime
    
    try:
        cache_file = _get_opening_price_cache_file()
        today = datetime.date.today().strftime("%Y-%m-%d")
        key = f"{underlying}_{today}"
        
        # Load existing data
        data = {}
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                data = json.load(f)
        
        # Only save if not already saved for today
        if key not in data or not data.get(key):
            data[key] = round(price, 2)
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
    except Exception:
        pass


def _get_opening_straddle_cache_file() -> str:
    """? Get the path to the opening straddle cache JSON file."""
    DAY_OPENING_STRADDLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    return str(DAY_OPENING_STRADDLES_FILE)


def _load_saved_opening_straddle(underlying: str) -> dict:
    """?
    Load saved opening straddle for today from JSON file.
    Returns dict with keys: strike, call, put, total or empty dict if not present.
    """
    import json
    import os
    import datetime
    try:
        cache_file = _get_opening_straddle_cache_file()
        if not os.path.exists(cache_file):
            return {}
        with open(cache_file, 'r') as f:
            data = json.load(f)
        today = datetime.date.today().strftime("%Y-%m-%d")
        key = f"{underlying}_{today}"
        return data.get(key, {}) or {}
    except Exception:
        return {}


def get_security_daily_open(security_id: int, exchange_seg: str = "NSE_FNO") -> float:
    """// Fetch the daily candle Open for the given security_id using charts/history (Interval=1).

    Returns the 'Open' value if available, else 0.0.
    """
    try:
        if not security_id or security_id <= 0:
            return 0.0

        # First try marketfeed/ohlc which often contains the day's open for individual securities
        try:
            ohlc_url = "https://api.dhan.co/v2/marketfeed/ohlc"
            payload = {exchange_seg: [int(security_id)]}
            r = requests.post(ohlc_url, json=payload, headers=API_HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if 'data' in data and exchange_seg in data['data']:
                    q = data['data'][exchange_seg].get(str(security_id), {})
                    if q:
                        o = q.get('ohlc', {})
                        val = o.get('open') or o.get('Open') or 0
                        try:
                            return float(val)
                        except Exception:
                            pass
        except Exception:
            pass

        # Fallback: try charts/history daily candle
        try:
            url = "https://api.dhan.co/v2/charts/history"
            today = datetime.date.today()
            payload = {
                "SecurityId": int(security_id),
                "ExchangeSegment": exchange_seg,
                "Interval": 1,
                "FromDate": today.strftime("%Y-%m-%d"),
                "ToDate": today.strftime("%Y-%m-%d"),
            }
            r = requests.post(url, json=payload, headers=API_HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get('status') == 'success':
                    candles = data.get('data', [])
                    if candles and len(candles) > 0:
                        first = candles[0]
                        open_val = first.get('Open') or first.get('open') or 0
                        try:
                            return float(open_val)
                        except Exception:
                            pass
        except Exception:
            pass

    except Exception:
        pass
    return 0.0


def _save_opening_straddle(underlying: str, strike: int, call_ltp: float, put_ltp: float,
                           call_sec_id: int = 0, put_sec_id: int = 0) -> None:
    """
    Save opening straddle for today to JSON file. If option security ids provided,
    fetch the daily 'Open' price for each option and save those values (these are static for the day).
    Does not overwrite existing entry for the day.
    """
    import json
    import os
    import datetime
    try:
        cache_file = _get_opening_straddle_cache_file()
        today = datetime.date.today().strftime("%Y-%m-%d")
        key = f"{underlying}_{today}"
        data = {}
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                data = json.load(f)

        if key not in data or not data.get(key):
            # Prefer daily open from option instrument if provided
            call_open = 0.0
            put_open = 0.0
            if call_sec_id and call_sec_id > 0:
                call_open = get_security_daily_open(call_sec_id, exchange_seg="NSE_FNO")
            if put_sec_id and put_sec_id > 0:
                put_open = get_security_daily_open(put_sec_id, exchange_seg="NSE_FNO")

            # Fallback to passed LTPs if daily open not available
            call_val = round(call_open, 2) if call_open and call_open > 0 else round(float(call_ltp or 0), 2)
            put_val = round(put_open, 2) if put_open and put_open > 0 else round(float(put_ltp or 0), 2)
            total = round(call_val + put_val, 2)
            data[key] = {
                'strike': int(strike),
                'call': call_val,
                'put': put_val,
                'total': total
            }
            try:
                with open(cache_file, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass
    except Exception:
        pass


def get_intraday_technicals(underlying: str, timeframe_minutes: int = 5) -> dict:
    """//
    Fetch intraday OHLC data and calculate RSI, VWAP, 61 EMA for today.
    Gets actual day open price from OHLC endpoint (ohlc.open is constant throughout day).
    Falls back to spot price if chart data unavailable.
    Returns dict with {open, high, low, close, rsi, vwap, ema61, ...}
    """
    try:
        security_id = INDEX_SECURITY_IDS.get(underlying, 0)
        if not security_id:
            return {'error': f'Unknown underlying: {underlying}', 'open': 0, 'high': 0, 'low': 0, 'close': 0, 'rsi': 0, 'vwap': 0, 'ema61': 0}
        
        headers = {
            'access-token': token_id,
            'client-id': str(client_code),
            'Content-Type': 'application/json'
        }
        
        # First check if opening price was already saved for today
        today_open = _load_saved_opening_price(underlying)

        day_high = 0
        day_low = 0
        today_close = 0

        # If not saved for today, attempt ONE API fetch to get today's opening price
        # If API returns a valid opening price (>0) we save it. If API doesn't return
        # a valid open (market closed/holiday), fall back to most recent cached opening
        # (previous date) so UI still shows a sensible value.
        if today_open <= 0:
            ohlc_url = "https://api.dhan.co/v2/marketfeed/ohlc"
            ohlc_payload = {"IDX_I": [security_id]}

            try:
                response = requests.post(ohlc_url, json=ohlc_payload, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and 'IDX_I' in data['data']:
                        quote = data['data']['IDX_I'].get(str(security_id), {})
                        if quote:
                            ohlc = quote.get('ohlc', {})
                            api_open = float(ohlc.get('open', 0) or 0)
                            day_high = float(ohlc.get('high', 0) or 0)
                            day_low = float(ohlc.get('low', 0) or 0)
                            today_close = float(quote.get('last_price', 0) or 0)

                            if api_open > 0:
                                today_open = api_open
                                # Save to cache for today so subsequent calls use cached today value
                                _save_opening_price(underlying, today_open)
            except Exception:
                pass

            # If API did not return today's open, fall back to most recently cached opening
            if today_open <= 0:
                prev_open, prev_date = _load_latest_opening_price(underlying)
                if prev_open and prev_date:
                    today_open = prev_open
        
        # Now fetch intraday candles for RSI, VWAP, EMA
        url = "https://api.dhan.co/v2/charts/history"
        today = datetime.date.today()
        
        intraday_payload = {
            "SecurityId": security_id,
            "ExchangeSegment": "IDX_I",
            "Interval": timeframe_minutes,
            "FromDate": today.strftime("%Y-%m-%d"),
            "ToDate": today.strftime("%Y-%m-%d"),
        }
        
        closes = []
        volumes = []
        open_ts = ''
        
        try:
            response = requests.post(url, json=intraday_payload, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    candles = data.get('data', [])
                    if candles:
                        # Try to extract timestamp from the first candle if available
                        first = candles[0]
                        for key in ('Datetime', 'datetime', 'Timestamp', 'timestamp', 'Time', 'time', 'Date', 'date'):
                            if key in first and first.get(key):
                                try:
                                    # Normalize to a datetime object if possible
                                    val = first.get(key)
                                    if isinstance(val, (int, float)):
                                        # epoch
                                        dt = datetime.datetime.fromtimestamp(int(val))
                                    else:
                                        # try parse common formats
                                        try:
                                            dt = datetime.datetime.fromisoformat(str(val))
                                        except Exception:
                                            try:
                                                dt = datetime.datetime.strptime(str(val), '%Y-%m-%d %H:%M:%S')
                                            except Exception:
                                                dt = None
                                    if dt:
                                        open_ts = dt.strftime('%d-%b-%Y %H:%M:%S')
                                        break
                                except Exception:
                                    continue
                        for candle in candles:
                            try:
                                closes.append(float(candle.get('Close', 0)))
                                volumes.append(float(candle.get('Volume', 0)))
                            except (TypeError, ValueError):
                                continue
        except Exception:
            pass
        
        # Calculate indicators if we have closes
        rsi = 0
        vwap = 0
        ema61 = 0
        
        if closes and len(closes) > 0:
            rsi = calculate_rsi(closes, 14)
            vwap = calculate_vwap(closes, volumes)
            ema61 = calculate_ema(closes, 61)
        
        # Return data with actual day open price and timestamp (if available)
        if today_open > 0:
            # If open_ts not set yet, attempt to synthesize from today's date at 09:15
            if not open_ts:
                try:
                    open_ts = datetime.datetime.combine(today, datetime.time(hour=9, minute=15)).strftime('%d-%b-%Y %H:%M:%S')
                except Exception:
                    open_ts = today.strftime('%d-%b-%Y') + ' 09:15:00'

            return {
                'open': round(today_open, 2),
                'open_ts': open_ts,
                'high': round(day_high, 2) if day_high > 0 else round(today_open, 2),
                'low': round(day_low, 2) if day_low > 0 else round(today_open, 2),
                'close': round(today_close, 2),
                'rsi': rsi,
                'vwap': vwap,
                'ema61': ema61,
                'error': None
            }
        
        # Last fallback: use current spot price
        spot = fetch_ltp(security_id, "IDX_I") or 0.0
        if spot <= 0:
            spot = get_cached_spot_price(underlying)
        
        if spot > 0:
            # Use current spot as open and set timestamp to now
            now_ts = datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S')
            return {
                'open': round(spot, 2),
                'open_ts': now_ts,
                'high': round(spot, 2),
                'low': round(spot, 2),
                'close': round(spot, 2),
                'rsi': 50.0,
                'vwap': round(spot, 2),
                'ema61': round(spot, 2),
                'error': 'Using current price (no historical data)'
            }
        
        return {'error': 'No data available', 'open': 0, 'high': 0, 'low': 0, 'close': 0, 'rsi': 0, 'vwap': 0, 'ema61': 0}
    
    except Exception as e:
        return {'error': str(e), 'open': 0, 'high': 0, 'low': 0, 'close': 0, 'rsi': 0, 'vwap': 0, 'ema61': 0}


def get_straddle_price(atm_strike: float, spot_price: float, option_df: pd.DataFrame) -> dict:
    """
    Get ATM straddle price (Call LTP + Put LTP at ATM strike).
    Returns {call_ltp, put_ltp, straddle_total, ...}
    """
    try:
        if option_df.empty:
            return {'call_ltp': 0, 'put_ltp': 0, 'straddle_total': 0, 'error': 'No option data'}
        
        # Find ATM row (exact match or closest). Use idxmin/loc to pick a single row.
        if 'Strike' not in option_df.columns:
            return {'call_ltp': 0, 'put_ltp': 0, 'straddle_total': 0, 'error': 'Strike column missing'}

        atm_row = option_df[option_df['Strike'] == atm_strike]
        if atm_row.empty:
            # Use closest strike index
            try:
                nearest_idx = (option_df['Strike'] - atm_strike).abs().idxmin()
                row = option_df.loc[nearest_idx]
            except Exception:
                return {'call_ltp': 0, 'put_ltp': 0, 'straddle_total': 0, 'error': 'ATM strike not found'}
        else:
            row = atm_row.iloc[0]

        call_ltp = float(row.get('C_LTP', 0) or 0)
        put_ltp = float(row.get('P_LTP', 0) or 0)
        straddle_total = call_ltp + put_ltp
        chosen_strike = float(row.get('Strike', atm_strike))
        
        return {
            'call_ltp': round(call_ltp, 2),
            'put_ltp': round(put_ltp, 2),
            'straddle_total': round(straddle_total, 2),
            'strike': int(chosen_strike),
            'error': None
        }
    except Exception as e:
        return {'call_ltp': 0, 'put_ltp': 0, 'straddle_total': 0, 'error': str(e)}
