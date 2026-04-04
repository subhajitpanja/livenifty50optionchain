"""
Live NIFTY Option Chain — Gradio Dashboard (Optimized)
=======================================================
Run:  python optionchain_gradio.py
URL:  http://localhost:7860

Pure HTML rendering — no Pandas Styler, no transitions, no animations.
"""

# ─── Shield imports from VS Code terminal SIGINT ──────────────────────────
# VS Code "Run Python File in Dedicated Terminal" opens a new shell, runs
# venv activation, then fires the python command.  During this setup a
# stray Ctrl-C / SIGINT is frequently delivered into the child process.
# Whichever heavy C-extension import (numpy, jinja2, etc.) happens to be
# running at that instant gets a KeyboardInterrupt and leaves half-loaded
# modules in sys.modules, crashing the app.
#
# Fix: temporarily ignore SIGINT for the entire import phase, then restore
# the default handler so Ctrl-C works normally during runtime.
# ──────────────────────────────────────────────────────────────────────────
import signal
import sys
import time as _time
import logging as _logging

# ─── Suppress verbose httpx / httpcore / asyncio noise ─────────────────────
for _noisy in ('httpx', 'httpcore', 'httpcore.http11', 'httpcore.connection',
               'asyncio', 'hpack', 'urllib3.connectionpool'):
    _logging.getLogger(_noisy).setLevel(_logging.WARNING)

_t0 = _time.perf_counter()
_original_sigint = signal.getsignal(signal.SIGINT)
signal.signal(signal.SIGINT, signal.SIG_IGN)   # block Ctrl-C during imports

try:
    import gradio as gr
    from oc_data_fetcher import fetch_all_data, format_lakh
    from color_constants import (
        H1_CLR, H2_CLR, H3_CLR,
        CALL_BAR, PUT_BAR, CALL_BAR_NEG, PUT_BAR_NEG,
        BU_CALL, BU_PUT, BU_FUT,
        OI_RANK_CALL, OI_RANK_PUT,
        GREEN, RED, ORANGE, BLUE, GOLD, CYAN, MUTED, MUTED_LIGHT, ATM_BG, TEXT_DEFAULT,
        LIMEGREEN, BRIGHT_RED, WHITE, BLACK, DEEP_ORANGE,
        NEUTRAL_PURPLE, RED_BRIGHT, YELLOW_GREEN,
        PANEL_BG, LIGHT_BLUE, TEXT_LIGHT, TEXT_GREEN, TEXT_RED,
        GRID_COLOR, BORDER_COLOR,
        # RGBA constants for plotly charts
        RSI_OVERBOUGHT_LINE, RSI_NEUTRAL_LINE, RSI_OVERSOLD_LINE,
        RSI_OVERBOUGHT_ZONE, RSI_OVERSOLD_ZONE,
        ANNOTATION_BG_PRIMARY, ANNOTATION_BG_SECONDARY, ANNOTATION_BG_TERTIARY, LEGEND_BG,
        CANDLE_INCREASING_75, CANDLE_DECREASING_75, CANDLE_INCREASING_80, CANDLE_DECREASING_80,
        SPIKE_COLOR, GRAY_LINE_25, GRAY_LINE_35, BAND_FILL_BLUE,
        GOLD_LINE_60, BLUE_LINE_50, BLUE_LINE_40,
        RANK_PUT_1, RANK_PUT_2, RANK_PUT_3, RANK_CALL_1, RANK_CALL_2, RANK_CALL_3,
        DEFAULT_PUT_RGBA, DEFAULT_CALL_RGBA, TRANSPARENT,
    )
    from ui_labels import (
        LBL_SPOT, LBL_ATM, LBL_EXPIRY, LBL_VIX, LBL_FUT,
        SEC_TOTALS, SEC_SENTIMENT, SEC_OTM, SEC_ITM, SEC_CALL_OI, SEC_PUT_OI,
        LBL_TOTAL_OI, LBL_TOTAL_OI_CHG, LBL_TOTAL_VOL,
        LBL_TOTAL_LB_OI, LBL_TOTAL_SC_OI, LBL_TOTAL_SB_OI, LBL_TOTAL_LU_OI,
        LBL_TOTAL_LB_OI_CHG, LBL_TOTAL_SC_OI_CHG, LBL_TOTAL_SB_OI_CHG, LBL_TOTAL_LU_OI_CHG,
        LBL_BULLISH_OI, LBL_BEARISH_OI, LBL_BULLISH_OI_CHG, LBL_BEARISH_OI_CHG,
        LBL_CALL_PREMIUM, LBL_PUT_PREMIUM, LBL_CALL_PREM_CHG, LBL_PUT_PREM_CHG,
        LBL_PE_CE_OI_CHG, LBL_PCR_OI, LBL_PCR_OI_CHG, LBL_PCR_VOL,
        LBL_OTM_OI, LBL_OTM_OI_CHG, LBL_OTM_VOL, LBL_PCR_OTM_OI, LBL_PCR_OTM_OI_CHG,
        LBL_ITM_OI, LBL_ITM_OI_CHG, LBL_ITM_VOL, LBL_PCR_ITM_OI, LBL_PCR_ITM_OI_CHG,
        LBL_NO_DATA, LBL_ZONE_POSITIVE, LBL_ZONE_NEGATIVE, LBL_ZONE_TRANSITION,
    )
    import pandas as pd
    import json
    from pathlib import Path
    from string import Template
    from paths import (PROJECT_ROOT, HTML_DIR, CSS_STYLES_FILE,
                       INSTRUMENTS_DIR, OPTIONCHAIN_CSV_DIR, CACHE_DIR,
                       OI_HISTORY_FILE as _OI_HISTORY_PATH, ensure_dirs)
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from Dhan_Tradehull import Tradehull
    from concurrent.futures import ThreadPoolExecutor
finally:
    signal.signal(signal.SIGINT, _original_sigint)  # restore Ctrl-C

print(f"[OK] Gradio {gr.__version__} ready  ({_time.perf_counter() - _t0:.1f}s)")

parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from Credential.Credential import client_code, token_id


# ═══════════════════════════════════════════════════════════════════════════
#^# WEEKEND MOCK MODE — simulate prev-day OI when market is closed
# ═══════════════════════════════════════════════════════════════════════════
import datetime as _dt
import random as _random
from rich.console import Console as _RichConsole
from rich.table import Table as _RichTable
from rich.panel import Panel as _RichPanel
from tui_components import tui_dashboard as _tui

# ─── TUI startup log ──────────────────────────────────────────────────
_tui.log_info(f"Gradio {gr.__version__} loaded in {_time.perf_counter() - _t0:.1f}s")
_tui.log_info(f"Python {sys.version.split()[0]} | {sys.platform}")

import os as _os
_os.environ.setdefault('PYTHONIOENCODING', 'utf-8')  # help subprocesses

# Force Windows console to UTF-8 so Rich can print Unicode chars (arrows, symbols etc.)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

_dbg_console = _RichConsole(force_terminal=True)  #~# shared Rich console for debug logging

_MOCK_MODE: bool = False          #~# toggled by startup prompt or Gradio checkbox
_MOCK_PREV_SNAP: dict = {}        #~# cached so it stays stable across 3s refresh ticks

#~# Number of historical tabs for OC and OI Distribution (Live + N history snapshots)
HISTORY_TAB_COUNT = 14


def _is_weekend() -> bool:
    return _dt.date.today().weekday() >= 5  # 5=Saturday, 6=Sunday


# ═══════════════════════════════════════════════════════════════════════════
#^# MARKET SESSION DETECTOR — prevent API spam on holidays/weekends/off-hours
# ═══════════════════════════════════════════════════════════════════════════
#~# NSE holidays (yyyy-mm-dd) — update yearly; covers 2025-2026
_NSE_HOLIDAYS: set = {
    # 2025
    '2025-02-26', '2025-03-14', '2025-03-31', '2025-04-10', '2025-04-14',
    '2025-04-18', '2025-05-01',
    '2025-08-15', '2025-08-27', '2025-10-02', '2025-10-20', '2025-10-21',
    '2025-10-22', '2025-11-05', '2025-11-26', '2025-12-25',
    # 2026
    '2026-01-26', '2026-02-17', '2026-03-10', '2026-03-17',
    '2026-03-30', '2026-04-03', '2026-04-14', '2026-05-01', '2026-05-25',
    '2026-07-17', '2026-08-15', '2026-08-17', '2026-10-02', '2026-10-09',
    '2026-10-19', '2026-10-20', '2026-11-09', '2026-11-24', '2026-12-25',
}


def _is_nse_holiday(d: _dt.date = None) -> bool:
    """Check if a date is an NSE holiday."""
    d = d or _dt.date.today()
    return str(d) in _NSE_HOLIDAYS


def _is_market_open() -> bool:
    """Return True if NSE market is likely open RIGHT NOW.
    Checks: weekday, not NSE holiday, and within 09:00–15:40 IST.
    """
    try:
        now_ist = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=5, minutes=30)))
    except Exception:
        now_ist = _dt.datetime.now()
    d = now_ist.date()
    # Weekend
    if d.weekday() >= 5:
        return False
    # Holiday
    if str(d) in _NSE_HOLIDAYS:
        return False
    # Time window: 09:00 – 15:40 IST (40 min buffer after close for settlement)
    t = now_ist.time()
    if t < _dt.time(9, 0) or t > _dt.time(15, 40):
        return False
    return True


def _market_status_str() -> str:
    """Return a short human-readable market status string."""
    try:
        now_ist = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=5, minutes=30)))
    except Exception:
        now_ist = _dt.datetime.now()
    d = now_ist.date()
    t = now_ist.time()
    day_name = d.strftime('%A')
    if d.weekday() >= 5:
        return f"{day_name} — Weekend (market closed)"
    if str(d) in _NSE_HOLIDAYS:
        return f"{day_name} — NSE Holiday (market closed)"
    if t < _dt.time(9, 0):
        return f"{day_name} — Pre-market (opens 09:15)"
    if t > _dt.time(15, 40):
        return f"{day_name} — Post-market (closed 15:30)"
    return f"{day_name} — Market OPEN"


# ═══════════════════════════════════════════════════════════════════════════
#^# DYNAMIC ATM SELECTION — bypasses Tradehull's broken get_expiry_list
# ═══════════════════════════════════════════════════════════════════════════
#~# Tradehull v3.1.0 has a recursive bug in get_expiry_list() that prints
#~# dozens of "Exception at getting Expiry list" messages per call.
#~# Instead, we resolve CE/PE symbols directly from the instrument CSV
#~# using the DhanHQ /v2/optionchain/expirylist API for dynamic expiry dates.
#~# This eliminates ALL Tradehull expiry-list spam.

import requests as _requests

_ATM_COOLDOWN_SEC: float = 120.0
_atm_cache: dict = {}
_expiry_list_cache: dict = {}  # key = underlying → {'expiries': [...], 'ts': float}
_instrument_df_cache = None

_INDEX_STEP = {'NIFTY': 50, 'BANKNIFTY': 100, 'FINNIFTY': 50, 'MIDCPNIFTY': 25}
_INDEX_SECURITY_IDS_OC = {'NIFTY': 13, 'BANKNIFTY': 25, 'FINNIFTY': 27, 'MIDCPNIFTY': 442}
_INDEX_EXCHANGE_SEG = {'NIFTY': 'IDX_I', 'BANKNIFTY': 'IDX_I', 'FINNIFTY': 'IDX_I', 'MIDCPNIFTY': 'IDX_I'}


def _load_instrument_df():
    """Load the instrument CSV (cached after first load).
    Searches: data/source/instruments/ → fallback to most recent."""
    global _instrument_df_cache
    if _instrument_df_cache is not None:
        return _instrument_df_cache
    today_str = _dt.date.today().strftime('%Y-%m-%d')
    fname = f'all_instrument {today_str}.csv'
    #~# Search in instruments directory
    search_dirs = [
        INSTRUMENTS_DIR,
    ]
    csv_path = None
    for deps in search_dirs:
        candidate = deps / fname
        if candidate.exists():
            csv_path = candidate
            break
    if csv_path is None:
        #~# fallback: try the most recent file from any location
        for deps in search_dirs:
            candidates = sorted(deps.glob('all_instrument *.csv'), reverse=True)
            if candidates:
                csv_path = candidates[0]
                break
    if csv_path and csv_path.exists():
        try:
            _instrument_df_cache = pd.read_csv(csv_path, low_memory=False)
            _instrument_df_cache['SEM_EXPIRY_DATE'] = pd.to_datetime(
                _instrument_df_cache['SEM_EXPIRY_DATE'], errors='coerce')
            _dbg_console.print(f"[dim]\\[Instrument] Loaded {csv_path.name} ({len(_instrument_df_cache)} rows)[/]")
        except Exception as e:
            _dbg_console.print(f"[red]\\[Instrument] Failed to load {csv_path}: {e}[/]")
    else:
        _dbg_console.print("[yellow]\\[Instrument] No instrument CSV found in data/source/instruments/[/]")
    return _instrument_df_cache


def _fetch_expiry_list_dynamic(underlying: str) -> list:
    """Fetch expiry list from DhanHQ API /v2/optionchain/expirylist.
    Falls back to instrument CSV if API fails.
    Returns sorted list of YYYY-MM-DD date strings (future only)."""
    now = _time.time()
    cached = _expiry_list_cache.get(underlying)
    if cached and (now - cached['ts']) < 300:  # 5 min cache
        return cached['expiries']

    security_id = _INDEX_SECURITY_IDS_OC.get(underlying)
    exchange_seg = _INDEX_EXCHANGE_SEG.get(underlying, 'IDX_I')
    today_str = _dt.date.today().strftime('%Y-%m-%d')
    expiries = []

    #~# Method 1: DhanHQ API (reliable, dynamic)
    if security_id:
        try:
            url = 'https://api.dhan.co/v2/optionchain/expirylist'
            headers = {
                'access-token': token_id,
                'client-id': str(client_code),
                'Content-Type': 'application/json',
            }
            payload = {'UnderlyingScrip': security_id, 'UnderlyingSeg': exchange_seg}
            resp = _requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success' and 'data' in data:
                    all_exp = sorted(data['data'])
                    expiries = [e for e in all_exp if e >= today_str]
                    _dbg_console.print(
                        f"[dim]\\[Expiry] {underlying}: {len(expiries)} future expiries from API "
                        f"(next: {expiries[:3]})[/]")
        except Exception as e:
            _dbg_console.print(f"[yellow]\\[Expiry] API failed for {underlying}: {e}[/]")

    #~# Method 2: Fallback to instrument CSV
    if not expiries:
        idf = _load_instrument_df()
        if idf is not None:
            try:
                mask = (
                    (idf['SEM_EXM_EXCH_ID'] == 'NSE') &
                    (idf['SEM_INSTRUMENT_NAME'] == 'OPTIDX') &
                    (idf['SEM_TRADING_SYMBOL'].str.startswith(f'{underlying}-', na=False))
                )
                exp_dates = idf.loc[mask, 'SEM_EXPIRY_DATE'].dropna().dt.date.unique()
                expiries = sorted([str(d) for d in exp_dates if str(d) >= today_str])
                _dbg_console.print(
                    f"[dim]\\[Expiry] {underlying}: {len(expiries)} from instrument CSV "
                    f"(next: {expiries[:3]})[/]")
            except Exception as e:
                _dbg_console.print(f"[red]\\[Expiry] Instrument CSV parse failed: {e}[/]")

    if expiries:
        _expiry_list_cache[underlying] = {'expiries': expiries, 'ts': now}
    return expiries


def _resolve_ce_pe_symbols(underlying: str, expiry_date_str: str, strike: int):
    """Look up CE/PE SEM_CUSTOM_SYMBOL + SEM_SMST_SECURITY_ID from instrument CSV.
    Returns (ce_symbol, pe_symbol, ce_security_id, pe_security_id) or (None,None,None,None)."""
    idf = _load_instrument_df()
    if idf is None:
        return None, None, None, None
    try:
        mask = (
            (idf['SEM_EXM_EXCH_ID'] == 'NSE') &
            (idf['SEM_TRADING_SYMBOL'].str.startswith(f'{underlying}-', na=False)) &
            (idf['SEM_EXPIRY_DATE'].dt.date.astype(str) == expiry_date_str) &
            (idf['SEM_STRIKE_PRICE'] == float(strike))
        )
        filtered = idf[mask]
        ce_rows = filtered[filtered['SEM_OPTION_TYPE'] == 'CE']
        pe_rows = filtered[filtered['SEM_OPTION_TYPE'] == 'PE']
        ce_sym = ce_rows.iloc[-1]['SEM_CUSTOM_SYMBOL'] if not ce_rows.empty else None
        pe_sym = pe_rows.iloc[-1]['SEM_CUSTOM_SYMBOL'] if not pe_rows.empty else None
        ce_sec_id = str(int(ce_rows.iloc[-1]['SEM_SMST_SECURITY_ID'])) if not ce_rows.empty else None
        pe_sec_id = str(int(pe_rows.iloc[-1]['SEM_SMST_SECURITY_ID'])) if not pe_rows.empty else None
        return ce_sym, pe_sym, ce_sec_id, pe_sec_id
    except Exception as e:
        _dbg_console.print(f"[red]\\[Resolve] {underlying} {expiry_date_str} {strike}: {e}[/]")
        return None, None, None, None


# ═══════════════════════════════════════════════════════════════════════════
#^# DIRECT OPTION INTRADAY FETCHER — replaces tsl.get_historical_data entirely
# ═══════════════════════════════════════════════════════════════════════════
#~# Uses dhanhq v2.1.0 /v2/charts/intraday endpoint directly.
#~# For NFO options: exchangeSegment='NSE_FNO', instrument='OPTIDX'
#~# security_id comes from instrument CSV's SEM_SMST_SECURITY_ID column.
#~# Also checks data/source/optionchain/ folder for cached daily CSV data.

_option_intraday_cache: dict = {}  # key=(security_id, interval) → {'df':..., 'ts':...}


def _fetch_option_intraday(security_id: str, interval: int = 5,
                           symbol_label: str = '') -> pd.DataFrame:
    """Fetch intraday OHLCV for an NFO option via Dhan /v2/charts/intraday.

    Args:
        security_id: SEM_SMST_SECURITY_ID from instrument CSV (string).
        interval: candle interval in minutes (1, 5, 15, 25, 60).
        symbol_label: human label for rich debug logging.

    Returns DataFrame with columns: timestamp, open, high, low, close, volume.
    Cached for 60s per (security_id, interval).
    """
    from oc_data_fetcher import API_HEADERS
    import datetime as _dtmod

    cache_key = (security_id, interval)
    cached = _option_intraday_cache.get(cache_key)
    if cached and (_time.time() - cached.get('ts', 0)) < 60:
        return cached['df']

    #~# 5 trading days ≈ 7 calendar days
    to_dt = _dtmod.datetime.now()
    from_dt = to_dt - _dtmod.timedelta(days=7)
    from_date = from_dt.strftime('%Y-%m-%d %H:%M:%S')
    to_date = to_dt.strftime('%Y-%m-%d %H:%M:%S')

    try:
        url = 'https://api.dhan.co/v2/charts/intraday'
        payload = {
            'securityId': str(security_id),
            'exchangeSegment': 'NSE_FNO',
            'instrument': 'OPTIDX',
            'interval': int(interval),
            'oi': True,
            'fromDate': from_date,
            'toDate': to_date,
        }
        r = _requests.post(url, json=payload, headers=API_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'open' in data and 'close' in data and 'timestamp' in data:
                df = pd.DataFrame(data)
                if not df.empty:
                    df['timestamp'] = (pd.to_datetime(df['timestamp'], unit='s',
                                                      errors='coerce')
                                       .dt.tz_localize('UTC')
                                       .dt.tz_convert('Asia/Kolkata')
                                       .dt.tz_localize(None))
                    df.columns = [c.lower() for c in df.columns]
                    _option_intraday_cache[cache_key] = {'df': df, 'ts': _time.time()}
                    _dbg_console.print(
                        f"[dim]\\[OptionData] {symbol_label} secId={security_id} "
                        f"{interval}m → {len(df)} candles from API[/]")
                    return df
            else:
                _dbg_console.print(
                    f"[yellow]\\[OptionData] {symbol_label} secId={security_id}: "
                    f"API returned no OHLCV data (status={r.status_code})[/]")
        else:
            _dbg_console.print(
                f"[yellow]\\[OptionData] {symbol_label} secId={security_id}: "
                f"HTTP {r.status_code}[/]")
    except Exception as e:
        _dbg_console.print(
            f"[red]\\[OptionData] {symbol_label} secId={security_id}: {e}[/]")

    #~# Fallback: return stale cache if available
    if cached:
        _dbg_console.print(
            f"[dim]\\[OptionData] {symbol_label}: using stale cache[/]")
        return cached['df']
    return pd.DataFrame()


def _check_dependencies_for_data(underlying: str, date_str: str = None) -> pd.DataFrame:
    """Check data/source/optionchain/ folder for cached daily CSV data.
    These CSVs contain option chain snapshots saved by previous runs.
    Supports both old naming (YYYY-MM-DD.csv) and new naming
    (YYYY-MM-DD_exp_YYYY-MM-DD.csv) conventions.
    Returns DataFrame or empty DataFrame if not found.
    """
    deps_dir = OPTIONCHAIN_CSV_DIR
    if not deps_dir.exists():
        return pd.DataFrame()

    #~# Try exact date, then loop backwards up to 15 days
    import datetime as _dtmod
    if date_str:
        dates_to_check = [date_str]
    else:
        today = _dtmod.date.today()
        dates_to_check = [str(today - _dtmod.timedelta(days=i)) for i in range(16)]

    for d_str in dates_to_check:
        #~# Check new naming convention first: YYYY-MM-DD_exp_*.csv
        new_pattern = list(deps_dir.glob(f'{d_str}_exp_*.csv'))
        if new_pattern:
            csv_path = sorted(new_pattern)[-1]  # latest if multiple
            try:
                #~# Skip the metadata rows (Date, Expiry Date) at top
                df = pd.read_csv(csv_path, skiprows=2)
                if not df.empty:
                    _dbg_console.print(
                        f"[dim]\\[Cache] Found cached data: {csv_path.name} "
                        f"({len(df)} rows)[/]")
                    return df
            except Exception:
                #~# Try without skipping rows (old metadata format)
                try:
                    df = pd.read_csv(csv_path)
                    if not df.empty:
                        _dbg_console.print(
                            f"[dim]\\[Cache] Found cached data: {csv_path.name} "
                            f"({len(df)} rows, no skiprows)[/]")
                        return df
                except Exception:
                    pass

        #~# Fallback: old naming convention YYYY-MM-DD.csv
        csv_path = deps_dir / f'{d_str}.csv'
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                if not df.empty:
                    _dbg_console.print(
                        f"[dim]\\[Cache] Found cached data: {csv_path.name} "
                        f"({len(df)} rows)[/]")
                    return df
            except Exception:
                pass
    return pd.DataFrame()


def _atm_strike_with_cooldown(tsl, underlying: str, expiry_idx: int):
    """Dynamic ATM selection — uses DhanHQ expiry API + instrument CSV.
    Completely bypasses Tradehull's broken ATM_Strike_Selection.
    Returns (ce_symbol, pe_symbol, expiry_date_str) or None on failure."""
    now = _time.perf_counter()
    cache_key = (underlying, expiry_idx)
    cached = _atm_cache.get(cache_key)

    #~# Return cached success if within 60s
    if cached and cached.get('ok') and (now - cached['ts']) < 60:
        return cached['result']
    #~# Return None immediately if last failure was within cooldown
    if cached and not cached.get('ok') and (now - cached['ts']) < _ATM_COOLDOWN_SEC:
        return None

    try:
        #~# Step 1: Get expiry list dynamically
        expiries = _fetch_expiry_list_dynamic(underlying)
        if not expiries:
            _dbg_console.print(
                f"[yellow]\\[ATM] {underlying}: no expiries found — cooldown {_ATM_COOLDOWN_SEC:.0f}s[/]")
            _atm_cache[cache_key] = {'result': None, 'ts': now, 'ok': False}
            return None

        if expiry_idx >= len(expiries):
            _dbg_console.print(
                f"[yellow]\\[ATM] {underlying}: expiry_idx={expiry_idx} out of range "
                f"(only {len(expiries)} available) — using last[/]")
            expiry_idx = len(expiries) - 1
        expiry_date_str = expiries[expiry_idx]

        #~# Step 2: Get spot price for ATM calculation
        spot = 0.0
        try:
            from oc_data_fetcher import get_cached_spot_price
            spot = get_cached_spot_price(underlying)
        except Exception:
            pass
        if spot <= 0 and tsl:
            try:
                spot = tsl.get_ltp_data(underlying) or 0.0
            except Exception:
                pass
        if spot <= 0:
            _dbg_console.print(
                f"[yellow]\\[ATM] {underlying}: no spot price — cooldown {_ATM_COOLDOWN_SEC:.0f}s[/]")
            _atm_cache[cache_key] = {'result': None, 'ts': now, 'ok': False}
            return None

        #~# Step 3: Calculate ATM strike
        step = _INDEX_STEP.get(underlying, 50)
        atm_strike = int(round(spot / step) * step)

        #~# Step 4: Resolve CE/PE symbols from instrument CSV
        ce_sym, pe_sym, _ce_sid, _pe_sid = _resolve_ce_pe_symbols(underlying, expiry_date_str, atm_strike)
        if not ce_sym or not pe_sym:
            _dbg_console.print(
                f"[yellow]\\[ATM] {underlying}: CE/PE not found for "
                f"expiry={expiry_date_str} strike={atm_strike} — cooldown {_ATM_COOLDOWN_SEC:.0f}s[/]")
            _atm_cache[cache_key] = {'result': None, 'ts': now, 'ok': False}
            return None

        result = (ce_sym, pe_sym, expiry_date_str)
        _dbg_console.print(
            f"[dim]\\[ATM] {underlying} exp={expiry_date_str} strike={atm_strike} "
            f"CE={ce_sym} PE={pe_sym}[/]")
        _atm_cache[cache_key] = {'result': result, 'ts': now, 'ok': True}
        return result

    except Exception as e:
        _dbg_console.print(
            f"[red]\\[ATM] {underlying} expiry={expiry_idx}: {e} "
            f"— cooldown {_ATM_COOLDOWN_SEC:.0f}s[/]")
        _atm_cache[cache_key] = {'result': None, 'ts': now, 'ok': False}
        return None


# ═══════════════════════════════════════════════════════════════════════════
#^# LAST AVAILABLE TRADING DAY FINDER — 15-day lookback loop
# ═══════════════════════════════════════════════════════════════════════════

def _find_last_trading_day(date_series, label: str = '', max_lookback: int = 15):
    """Search backwards from today through yesterday, day-2, ... up to max_lookback days
    to find the most recent date that has data in `date_series`.

    Args:
        date_series: pandas Series of date strings (YYYY-MM-DD).
        label: label for debug logging (e.g. 'Chart', 'EMA-Candle').
        max_lookback: how many days back to search (default 15).

    Returns:
        (found_date_str, days_back)  — the date string and how many days back,
        or (None, -1) if nothing found.
    """
    unique_dates = set(date_series.dropna().unique())
    today = _dt.date.today()

    for days_back in range(0, max_lookback + 1):
        check_date = today - _dt.timedelta(days=days_back)
        check_str = str(check_date)
        if check_str in unique_dates:
            if days_back > 0:
                _dbg_console.print(
                    f"[dim]\\[{label}] No data for today ({today}), "
                    f"found last available: {check_str} ({days_back}d ago, "
                    f"{check_date.strftime('%A')})[/]")
            return check_str, days_back

    _dbg_console.print(
        f"[yellow]\\[{label}] No data found in last {max_lookback} days "
        f"(checked {today} back to {today - _dt.timedelta(days=max_lookback)})[/]")
    return None, -1


def _ask_weekend_mock() -> bool:
    """Ask in terminal whether to activate mock prev-day OI data."""
    day_name = _dt.date.today().strftime("%A")
    print(f"\n{'='*60}")
    print(f"  [!]  Today is {day_name} -- market is CLOSED.")
    print(f"  The combined OI panel needs a previous-day snapshot.")
    print(f"{'='*60}")
    try:
        ans = input("  Activate mock prev-day OI for combined panel? [y/N]: ").strip().lower()
        return ans == 'y'
    except (EOFError, KeyboardInterrupt):
        return False


if _is_weekend():
    _MOCK_MODE = _ask_weekend_mock()
    if _MOCK_MODE:
        print("  [OK] Mock mode ACTIVE -- combined panel will show simulated data.\n")
    else:
        print("  – Mock mode off.\n")

# ═══════════════════════════════════════════════════════════════════════════
#^# TEMPLATE LOADER — loads HTML from templates/html/ and CSS from templates/css/
# ═══════════════════════════════════════════════════════════════════════════
_TEMPLATE_DIR = HTML_DIR
_CSS_FILE = CSS_STYLES_FILE

#~# Cache loaded template strings and CSS to avoid repeated disk reads
_template_cache: dict[str, str] = {}
_css_cache: str = ''


def _load_css() -> str:
    """? Load and cache the shared stylesheet."""
    global _css_cache
    if not _css_cache:
        _css_cache = _CSS_FILE.read_text(encoding='utf-8')
    return _css_cache


def _load_template(_tpl_name: str) -> Template:
    """? Load an HTML template by name (without .html) and return a string.Template."""
    if _tpl_name not in _template_cache:
        path = _TEMPLATE_DIR / f'{_tpl_name}.html'
        _template_cache[_tpl_name] = path.read_text(encoding='utf-8')
    return Template(_template_cache[_tpl_name])


def _render(_tpl_name: str, **kwargs) -> str:
    """? Render a template with the given variables using safe_substitute."""
    return _load_template(_tpl_name).safe_substitute(**kwargs)


# ═══════════════════════════════════════════════════════════════════════════
#^# OI HISTORY (shared with optionchain_richprint_modified.py)
# ═══════════════════════════════════════════════════════════════════════════
OI_HISTORY_FILE = _OI_HISTORY_PATH


def _load_oi_history() -> list:
    try:
        if OI_HISTORY_FILE.exists():
            with open(OI_HISTORY_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    cleaned = []
                    for entry in data:
                        if not cleaned:
                            cleaned.append(entry)
                        else:
                            last = cleaned[-1]
                            if (format_lakh(float(entry.get('bullish_oi', 0) or 0)) != format_lakh(float(last.get('bullish_oi', 0) or 0))
                                    or format_lakh(float(entry.get('bearish_oi', 0) or 0)) != format_lakh(float(last.get('bearish_oi', 0) or 0))):
                                cleaned.append(entry)
                    return cleaned
    except Exception:
        pass
    return []


def _update_oi_history(bullish_oi: float, bearish_oi: float, timestamp: str):
    """* Update OI history, only if values changed from last entry"""
    try:
        history = _load_oi_history()
        bull_disp = format_lakh(float(bullish_oi))
        bear_disp = format_lakh(float(bearish_oi))
        should_add = True
        if history:
            last = history[-1]
            if (format_lakh(float(last.get('bullish_oi', 0) or 0)) == bull_disp
                    and format_lakh(float(last.get('bearish_oi', 0) or 0)) == bear_disp):
                should_add = False
        if should_add and (bullish_oi > 0 or bearish_oi > 0):
            history.append(
                {'timestamp': timestamp, 'bullish_oi': bullish_oi, 'bearish_oi': bearish_oi})
            history = history[-20:]
            OI_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(OI_HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#^# COLOR CONSTANTS — imported from color_constants.py
# ═══════════════════════════════════════════════════════════════════════════


def render_opening_cards(display_open: float, saved_strike, c_ltp: float = 0, p_ltp: float = 0,
                         today_high: float = 0, today_low: float = 0) -> str:
    """? Return the opening-cards HTML from template.

    Loads opening_cards.html and substitutes live values.
    """
    total_straddle = c_ltp + p_ltp

    #~# Compute Open vs High/Low label for daily timeframe
    open_hilo_label = ''
    if display_open > 0 and (today_high > 0 or today_low > 0):
        parts = []
        if today_low > 0:
            diff_low = abs(display_open - today_low)
            if diff_low == 0:
                parts.append('<span style="color:#ff9800;font-weight:600">Open = Low</span>')
            elif diff_low <= 50:
                parts.append('<span style="color:#ff9800">Open &amp; Low Nearby</span>')
        if today_high > 0:
            diff_high = abs(display_open - today_high)
            if diff_high == 0:
                parts.append('<span style="color:#4caf50;font-weight:600">Open = High</span>')
            elif diff_high <= 50:
                parts.append('<span style="color:#4caf50">Open &amp; High Nearby</span>')
        if parts:
            open_hilo_label = (
                '<div class="oc-card__sub" style="margin-top:3px">'
                + ' &nbsp;|&nbsp; '.join(parts)
                + '</div>'
            )

    return _render('opening_cards',
                   display_open=f'{display_open:,.2f}',
                   saved_strike=saved_strike or 'N/A',
                   total_straddle=f'{total_straddle:,.2f}',
                   c_ltp=f'{c_ltp:.2f}',
                   p_ltp=f'{p_ltp:.2f}',
                   open_hilo_label=open_hilo_label)


_prev_close_cache: dict = {}  #~# key = underlying → {'close': float, 'ts': float}


def _get_prev_close(underlying: str = 'NIFTY') -> float:
    """Return previous trading day's closing price from daily OHLCV (cached 5 min)."""
    cached = _prev_close_cache.get(underlying)
    if cached and (_time.time() - cached.get('ts', 0)) < 300:
        return cached['close']
    try:
        df = _fetch_ohlcv_daily(underlying)
        if df is not None and not df.empty:
            df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp']).reset_index(drop=True)
            today_str = _dt.date.today().strftime('%Y-%m-%d')
            df['date_str'] = df['timestamp'].astype(str).str[:10]
            prev_df = df[df['date_str'] < today_str]
            if not prev_df.empty:
                prev_close = float(prev_df.iloc[-1]['close'])
                _prev_close_cache[underlying] = {'close': prev_close, 'ts': _time.time()}
                return prev_close
    except Exception:
        pass
    return 0.0


def _header(d: dict) -> str:
    s, a, m = d['spot_price'], d['atm_strike'], d['metrics']
    v, vc = d['vix_current'], d['vix_change_pct']
    v_yesterday = d.get('vix_yesterday', 0)
    f, fe = d['fut_price'], d['fut_expiry']

    bull, bear = m.get('bullish_oi', 0), m.get('bearish_oi', 0)

    #~# Update OI history only on full data refresh (flag set by refresh_data)
    if d.get('_update_oi', False):
        _update_oi_history(bull, bear, d.get('update_time', ''))

    #~# Build header boxes from box.html template
    def _b(lbl, val, c=WHITE):
        return _render('box', label=lbl, value=val, color=c)

    #~# VIX display: show live value, fallback value, or yesterday's close if live data unavailable
    if v > 0:
        #~# Live or fallback VIX value from API
        vc_cls = 'oc-vix-chg--up' if vc > 0 else 'oc-vix-chg--down'
        vix_display = _render('vix_value', vix_val=f'{v:.2f}', vix_cls=vc_cls, vix_change=f'{vc:+.2f}')
        vix_color = GOLD
    elif v_yesterday > 0:
        #?# Show yesterday's close only if we have no other data
        vix_display = _render('vix_value_stale', vix_val=f'{v_yesterday:.2f}')
        vix_color = ORANGE
    else:
        vix_display = 'N/A'
        vix_color = MUTED

    #~# SPOT change from previous close
    underlying = d.get('underlying', 'NIFTY')
    prev_close = _get_prev_close(underlying)
    if prev_close > 0 and s > 0:
        spot_chg = s - prev_close
        spot_chg_pct = (spot_chg / prev_close) * 100
        chg_cls = 'oc-spot-chg--up' if spot_chg >= 0 else 'oc-spot-chg--down'
        spot_display = _render('spot_value',
                               spot_val=f'{s:,.2f}',
                               chg_cls=chg_cls,
                               spot_chg=f'{spot_chg:+,.2f}',
                               spot_chg_pct=f'{spot_chg_pct:+.2f}')
    else:
        spot_display = f'{s:,.2f}'

    #~# PCR OI
    pcr_oi = m.get('pcr_oi', 0)
    pcr_color = GREEN if pcr_oi >= 1 else RED if pcr_oi > 0 else MUTED

    #~# ATM IV (average of CE and PE IV at ATM strike)
    atm_iv = 0.0
    if 'option_df' in d and not d['option_df'].empty and a:
        try:
            atm_rows = d['option_df'][
                d['option_df']['Strike'].astype(str).str.split('.').str[0] == str(int(a))]
            if not atm_rows.empty:
                c_iv = float(atm_rows.iloc[0].get('C_IV', 0) or 0)
                p_iv = float(atm_rows.iloc[0].get('P_IV', 0) or 0)
                atm_iv = (c_iv + p_iv) / 2 if (c_iv > 0 and p_iv > 0) else max(c_iv, p_iv)
        except Exception:
            pass
    iv_color = CYAN if atm_iv > 0 else MUTED

    boxes = ''.join([
        _b(LBL_SPOT, spot_display, GOLD),
        _b(LBL_ATM, f'{a:,.0f}', GREEN),
        _b(LBL_EXPIRY, d['expiry'], BLUE),
        _b(LBL_VIX, vix_display, vix_color),
        _b(LBL_FUT, _render('fut_value', fut_price=f'{f:,.2f}', fut_expiry=fe)),
        _b('PCR', f'{pcr_oi:.2f}', pcr_color),
        _b('IV', f'{atm_iv:.1f}', iv_color),
    ])

    #^# Synced Day Open + Opening Straddle (same open-price source)
    try:
        from oc_data_fetcher import ensure_day_open_synced
        sync = ensure_day_open_synced(underlying,
                                      spot_price=d.get('spot_price', 0))
        display_open = sync.get('open_price', 0) or 0
        saved_strike = sync.get('atm_strike', 0) or 0
    except Exception:
        display_open = 0
        saved_strike = 0

    #~# Fetch live LTPs for the saved opening straddle strike
    c_ltp, p_ltp = 0.0, 0.0
    if saved_strike and 'option_df' in d and not d['option_df'].empty:
        try:
            #~# Filter for the saved strike
            #~# Accessing dataframe here is fast since it's already in memory
            rows = d['option_df'][d['option_df']['Strike'].astype(str).str.split('.').str[0] == str(int(saved_strike))]
            if not rows.empty:
                row = rows.iloc[0]
                c_ltp = float(row.get('C_LTP', 0) or 0)
                p_ltp = float(row.get('P_LTP', 0) or 0)
        except Exception:
            pass

    #~# Today's Daily High / Low (from cached 5-min intraday) for Open vs H/L label
    _today_high, _today_low = 0.0, 0.0
    try:
        import datetime as _dt_hilo
        _intra = _fetch_ohlcv_direct(underlying, 5)
        if _intra is not None and not _intra.empty:
            _today_mask = _intra['timestamp'].dt.date == _dt_hilo.date.today()
            _today_bars = _intra.loc[_today_mask]
            if not _today_bars.empty:
                _today_high = float(_today_bars['high'].max())
                _today_low  = float(_today_bars['low'].min())
    except Exception:
        pass

    #~# Render opening cards via helper
    opening_cards = render_opening_cards(display_open, saved_strike, c_ltp, p_ltp,
                                         today_high=_today_high,
                                         today_low=_today_low)

    #~# Render header from template
    css = _load_css()
    return _render('header',
                   css=css,
                   underlying=d['underlying'],
                   update_time=d['update_time'],
                   boxes=boxes,
                   opening_cards=opening_cards)


def _oi_history_panel(d: dict) -> str:
    """* Separate panel showing last 20 OI history entries."""
    m = d['metrics']
    bull, bear = m.get('bullish_oi', 0), m.get('bearish_oi', 0)
    tot = bull + bear
    bp = (bull / tot * 100) if tot > 0 else 50

    #~# Load OI history for last 20 bars
    oi_history = _load_oi_history()
    oi_history = [e for e in oi_history if (
        e.get('bullish_oi', 0) or 0) > 0 or (e.get('bearish_oi', 0) or 0) > 0]
    oi_history = oi_history[-20:]

    hist_rows = ''
    for entry in oi_history:
        ts = entry.get('timestamp', '')
        ts_display = ts.split()[-1] if ' ' in ts else ts
        bv = float(entry.get('bullish_oi', 0) or 0)
        brv = float(entry.get('bearish_oi', 0) or 0)
        row_tot = bv + brv
        b_pct = (bv / row_tot * 100) if row_tot > 0 else 50
        br_pct = 100 - b_pct

        hist_rows += _render('oi_history_row',
                             ts_display=ts_display,
                             bull_val=format_lakh(bv),
                             bear_val=format_lakh(brv),
                             b_pct=f'{b_pct:.0f}',
                             br_pct=f'{br_pct:.0f}')

    if not hist_rows:
        hist_rows = _render('oi_history_single',
                            bull_val=format_lakh(bull),
                            bear_val=format_lakh(bear),
                            b_pct=f'{bp:.0f}',
                            br_pct=f'{100-bp:.0f}')

    css = _load_css()
    return _render('oi_history',
                   css=css,
                   hist_rows=hist_rows)


def _oc_table(df: pd.DataFrame, atm: float) -> str:
    if df.empty:
        return _render('no_data')

    cols = [
        ('Build Up', 'C_BuildUp', 'c'), ('IV', 'C_IV', 'r'),
        ('OI Chg%', 'C_OI_Chg_Pct', 'r'), ('OI', 'C_OI', 'r'),
        ('LTP Chg%', 'C_LTP_Chg_Pct', 'r'), ('LTP', 'C_LTP', 'r'),
        ('Strike', 'Strike', 'c'),
        ('LTP', 'P_LTP', 'r'), ('LTP Chg%', 'P_LTP_Chg_Pct', 'r'),
        ('OI', 'P_OI', 'r'), ('OI Chg%', 'P_OI_Chg_Pct', 'r'),
        ('IV', 'P_IV', 'r'), ('Build Up', 'P_BuildUp', 'c'),
    ]
    atm_int = int(atm) if atm else 0

    #~# Pre-compute top-3 OI for H1/H2/H3 markers
    c_oi_vals = sorted(df['C_OI'].dropna().unique(), reverse=True)[
        :3] if 'C_OI' in df.columns else []
    p_oi_vals = sorted(df['P_OI'].dropna().unique(), reverse=True)[
        :3] if 'P_OI' in df.columns else []
    c_oi_rank = {int(v): i + 1 for i, v in enumerate(c_oi_vals) if v > 0}
    p_oi_rank = {int(v): i + 1 for i, v in enumerate(p_oi_vals) if v > 0}

    #~# Build header cells using CSS classes — with sort metadata
    hdr = ''
    for i, (n, key, a) in enumerate(cols):
        cls = 'oc-table__th'
        if i < 6:
            cls += ' oc-table__th--call'
        elif i == 6:
            cls += ' oc-table__th--strike'
        else:
            cls += ' oc-table__th--put'
        ta = 'text-align:center' if a == 'c' else 'text-align:right'
        sk = 'str' if key in ('C_BuildUp', 'P_BuildUp') else 'num'
        hdr += _render('oc_th', cls=cls, style=ta, name=n, col_idx=str(i), sort_key=sk)

    parts = []
    for _, row in df.iterrows():
        strike = row.get('Strike', 0)
        try:
            is_atm = int(float(strike)) == atm_int
        except (ValueError, TypeError):
            is_atm = False

        row_cls = 'oc-table__row--atm' if is_atm else 'oc-table__row'
        #~# No text color override for ATM row — preserve signal colors for all cells
        dc = TEXT_DEFAULT

        cells = []
        for cidx, (_, key, align) in enumerate(cols):
            val = row.get(key, '')
            sort_val = ''  #~# numeric sort value for column sorting
            _oi_ranked = False  #~# flag for H1/H2/H3 OI cells

            #~# Build Up column — keep signal colors on ATM too
            if key in ('C_BuildUp', 'P_BuildUp'):
                txt = str(val) if val and val == val else '-'
                #~# Compact display: LB P↑ OI↑, SB P↓ OI↑, SC P↑ OI↓, LU P↓ OI↓
                _bu_display = {
                    'LB': 'LB P↑OI↑',
                    'SB': 'SB P↓OI↑',
                    'SC': 'SC P↑OI↓',
                    'LU': 'LU P↓OI↓',
                }
                txt = _bu_display.get(str(val).strip(), txt)
                bu_map = BU_CALL if key == 'C_BuildUp' else BU_PUT
                c = bu_map.get(str(val).strip(), MUTED)
                #~# Sort: LB=1, SC=2, SB=3, LU=4, else 9
                _bu_ord = {'LB': 1, 'SC': 2, 'SB': 3, 'LU': 4}
                sort_val = str(_bu_ord.get(str(val).strip(), 9))

            #~# Strike column — YELLOW on ATM rows
            elif key == 'Strike':
                try:
                    sv = int(float(val))
                    txt = f'{sv:,}'
                    sort_val = str(sv)
                except Exception:
                    txt = '-'
                    sort_val = '0'
                c = GOLD if is_atm else dc

            #~# OI column with H1/H2/H3 rank markers
            elif key in ('C_OI', 'P_OI'):
                try:
                    oi_int = int(val)
                    sort_val = str(oi_int)
                    rank_map = c_oi_rank if key == 'C_OI' else p_oi_rank
                    clr_map = OI_RANK_CALL if key == 'C_OI' else OI_RANK_PUT
                    rank = rank_map.get(oi_int, 0)
                    if rank:
                        lbl = f'H{rank}'
                        rc = clr_map[rank]
                        oi_disp = f'{oi_int/100_000:.2f} L' if oi_int >= 100_000 else f'{oi_int:,}'
                        txt = _render('oc_oi_rank', rank_color=rc, rank_label=lbl, oi_display=oi_disp)
                        c = rc
                        _oi_ranked = True  #~# H1/H2/H3 — use bg color template
                    else:
                        txt = f'{oi_int:,}'
                        c = dc
                except (ValueError, TypeError):
                    txt = '-'
                    sort_val = '0'
                    c = MUTED

            #~# IV / OI Chg% / LTP Chg% columns — keep real signal colors
            elif key in ('C_IV', 'P_IV', 'C_OI_Chg_Pct', 'P_OI_Chg_Pct', 'C_LTP_Chg_Pct', 'P_LTP_Chg_Pct'):
                try:
                    v = float(val)
                    sort_val = f'{v:.6f}'
                    txt = f'{v:.1f}' if 'IV' in key else f'{v:+.2f}%'
                    if 'Chg' in key:
                        c = GREEN if v > 0 else RED if v < 0 else MUTED
                    elif 'IV' in key:
                        c = MUTED_LIGHT
                    else:
                        c = dc
                except (ValueError, TypeError):
                    txt = '-'
                    sort_val = '0'
                    c = MUTED

            #~# LTP column — with OH/OL badge, CYAN text
            elif key in ('C_LTP', 'P_LTP'):
                try:
                    fv = float(val)
                    txt = f'{fv:.2f}'
                    sort_val = f'{fv:.6f}'
                except (ValueError, TypeError):
                    txt = '-'
                    sort_val = '0'
                #~# Check OH/OL tag from data
                #~# Color logic: Call OH / Put OL = RED (bearish), Call OL / Put OH = GREEN (bullish)
                oh_ol_key = 'C_OH_OL' if key == 'C_LTP' else 'P_OH_OL'
                is_call = key == 'C_LTP'
                oh_ol_tag = str(row.get(oh_ol_key, '') or '')
                if oh_ol_tag == 'OH':
                    badge_class = 'oc-badge oc-badge--oh-call' if is_call else 'oc-badge oc-badge--oh-put'
                    txt = f"{txt} {_render('oc_badge', badge_class=badge_class, badge_text='O=H')}"
                    c = CYAN
                elif oh_ol_tag == 'OL':
                    badge_class = 'oc-badge oc-badge--ol-call' if is_call else 'oc-badge oc-badge--ol-put'
                    txt = f"{txt} {_render('oc_badge', badge_class=badge_class, badge_text='O=L')}"
                    c = CYAN
                else:
                    c = CYAN

            #~# LTP column (other — fallback)
            else:
                try:
                    fv = float(val)
                    txt = f'{fv:.2f}'
                    sort_val = f'{fv:.6f}'
                except (ValueError, TypeError):
                    txt = '-'
                    sort_val = '0'
                c = dc

            ta_cls = 'oc-table__td--center' if align == 'c' else 'oc-table__td--right'
            bold_cls = ' oc-table__td--bold' if is_atm or key in (
                'C_BuildUp', 'P_BuildUp', 'Strike') else ''
            #~# BuildUp columns: color as background, black text
            if key in ('C_BuildUp', 'P_BuildUp'):
                cells.append(
                    _render('oc_td_buildup', align_cls=ta_cls, bold_cls=bold_cls, color=c, text=txt, sort_val=sort_val))
            #~# OI H1/H2/H3 columns: rank color as background, white for Call / black for Put
            elif _oi_ranked:
                _oi_txt_clr = WHITE if key == 'C_OI' else BLACK
                cells.append(
                    _render('oc_td_oi_rank', align_cls=ta_cls, bold_cls=bold_cls, bg_color=c, text_color=_oi_txt_clr, text=txt, sort_val=sort_val))
            else:
                cells.append(
                    _render('oc_td', align_cls=ta_cls, bold_cls=bold_cls, color=c, text=txt, sort_val=sort_val))

        parts.append(
            _render('oc_row', row_cls=row_cls, cells=''.join(cells)))

    css = _load_css()
    return _render('oc_table',
                   css=css,
                   header_cells=hdr,
                   body_rows=''.join(parts))


def _futures(futures_data: list, ul: str) -> str:
    """* Futures OI Build Up table — defensive formatting for missing keys."""
    if not futures_data:
        return ""

    rows = []
    for item in futures_data:
        buildup = item.get('buildup', '')
        oi_chg_pct = item.get('oi_chg_pct', 0) or 0
        oi_val = item.get('oi', 0) or 0
        ltp_chg_pct = item.get('ltp_chg_pct', 0) or 0
        ltp = item.get('ltp', 0) or 0
        expiry = item.get('expiry', '')

        color = BU_FUT.get(buildup, MUTED)
        #~# Display with Price/OI arrows for futures build-up
        _bu_fut_display = {
            'Long Build Up':  'Long Build Up [Price ↑ + OI ↑]',
            'Short Build Up': 'Short Build Up [Price ↓ + OI ↑]',
            'Short Covering':  'Short Covering [Price ↑ + OI ↓]',
            'Long Unwinding':  'Long Unwinding [Price ↓ + OI ↓]',
        }
        buildup = _bu_fut_display.get(buildup, buildup)
        oi_chg_color = GREEN if oi_chg_pct > 0 else RED
        ltp_chg_color = GREEN if ltp_chg_pct > 0 else RED

        try:
            oi_display = format_lakh(float(oi_val))  #~# show L/Cr unit e.g. "2.26 L"
        except Exception:
            oi_display = str(oi_val)
        try:
            ltp_display = f"{float(ltp):,.2f}"
        except Exception:
            ltp_display = str(ltp)

        rows.append(
            _render('futures_row',
                    buildup_color=color,
                    buildup=buildup,
                    oi_chg_color=oi_chg_color,
                    oi_chg_pct=f'{oi_chg_pct:+.2f}%',
                    oi_display=oi_display,
                    ltp_chg_color=ltp_chg_color,
                    ltp_chg_pct=f'{ltp_chg_pct:+.2f}%',
                    ltp_display=ltp_display,
                    expiry=expiry)
        )

    css = _load_css()
    return _render('futures',
                   css=css,
                   ul=ul,
                   body_rows=''.join(rows))


#^# NSE-Style Vertical Grouped OI Bar Charts

def _fmt_oi(v):
    """? Format OI value in L/Cr notation."""
    av = abs(v)
    if av >= 10_000_000:
        return f"{v/10_000_000:.1f}Cr"
    elif av >= 100_000:
        return f"{v/100_000:.1f}L"
    elif av >= 1000:
        return f"{v/1000:.0f}K"
    return f"{v:,.0f}"


def _oi_combined_chart(df: pd.DataFrame, atm: float, spot: float,
                       prev_snap: dict) -> str:
    """
    ^^# NEW: Combined OI Distribution + Change in OI panel.
    Each strike has a Put bar (green, left) and Call bar (red, right).
    For each side:
      INCREASE  → solid base (prev-close OI) + diagonal-stripe top (added OI)
      DECREASE  → solid base (today's remaining OI) + hollow-border top (removed OI)
      NO CHANGE → solid base (current OI), no top segment
      NO PREV   → solid base (current OI), no top segment
    This is a brand-new section that does NOT modify the existing two panels.

    When prev_snap is empty (no previous-day data), we synthesise a pseudo-
    previous snapshot from intraday OI change: prev = current - intraday_chg.
    This gives the day-start OI so the combined chart still shows meaningful
    stripe (increase) / hollow (decrease) segments.
    """
    if df.empty:
        return ""

    #~# If no previous-day snapshot, synthesise one from intraday OI change
    #~# so the combined chart shows change instead of being identical to OI Dist.
    use_intraday_fallback = not prev_snap
    if use_intraday_fallback:
        prev_snap = {}
        for _, row in df.iterrows():
            try:
                s = int(float(row.get('Strike', 0)))
            except (ValueError, TypeError):
                continue
            c_curr = float(row.get('C_OI', 0) or 0)
            p_curr = float(row.get('P_OI', 0) or 0)
            c_chg  = float(row.get('C_OI_Chg', 0) or 0)
            p_chg  = float(row.get('P_OI_Chg', 0) or 0)
            #~# prev = current - intraday change (= day-start OI)
            prev_snap[str(s)] = {
                'c_oi': max(0, c_curr - c_chg),
                'p_oi': max(0, p_curr - p_chg),
            }

    atm_int = int(atm) if atm else 0
    data_rows = []
    mx = 1

    for _, row in df.iterrows():
        try:
            s = int(float(row.get('Strike', 0)))
        except (ValueError, TypeError):
            continue
        c_curr = float(row.get('C_OI', 0) or 0)
        p_curr = float(row.get('P_OI', 0) or 0)
        sk = str(s)
        prev = prev_snap.get(sk, {})
        c_prev = float(prev.get('c_oi', 0) or 0)
        p_prev = float(prev.get('p_oi', 0) or 0)
        #~# scale must cover both today AND yesterday so both fully visible
        mx = max(mx, c_curr, p_curr, c_prev, p_prev)
        data_rows.append((s, c_curr, p_curr, c_prev, p_prev))

    if not data_rows:
        return ""

    mx = mx * 1.25
    CH = 750

    #~# Pre-compute H1/H2/H3 rank maps based on current-day OI (same logic as OI Distribution)
    c_sorted = sorted([(c, s) for s, c, p, cp, pp in data_rows if c > 0], reverse=True)[:3]
    p_sorted = sorted([(p, s) for s, c, p, cp, pp in data_rows if p > 0], reverse=True)[:3]
    c_rank_map = {s: r + 1 for r, (_, s) in enumerate(c_sorted)}
    p_rank_map = {s: r + 1 for r, (_, s) in enumerate(p_sorted)}

    _HATCH = f"repeating-linear-gradient(45deg,{PANEL_BG} 0px,{PANEL_BG} 3px,transparent 3px,transparent 8px)"

    #~# Y-axis ticks & gridlines
    ytk = ''
    grd = ''
    for i in range(6):
        v = mx / 5 * i
        b = int(v / mx * CH)
        tick_b = 10 if i == 0 else b
        ytk += _render('ytick', bottom=str(tick_b), label=_fmt_oi(v))
        grid_cls = 'oc-grid-line--solid' if i == 0 else 'oc-grid-line--dashed'
        grd += _render('gridline', grid_cls=grid_cls, bottom=str(b))

    brs = ''
    for s, c_curr, p_curr, c_prev, p_prev in data_rows:
        is_atm = s == atm_int

        #~# H1/H2/H3 rank colors — shown on ALL strikes including ATM
        p_rank = p_rank_map.get(s, 0)
        c_rank = c_rank_map.get(s, 0)
        p_clr = OI_RANK_PUT.get(p_rank, '')   # e.g. '#32cd32' for H1 put
        c_clr = OI_RANK_CALL.get(c_rank, '')  # e.g. '#a50004' for H1 call

        # ─── PUT (green) ───────────────────────────────────────────────
        p_diff = p_curr - p_prev
        if p_prev > 0:
            if p_diff > 0:
                ph_base      = max(1, int(p_prev / mx * CH))
                ph_top       = max(1, int(p_diff / mx * CH))
                put_base_cls = 'bar-put--fill'
                put_top_cls  = 'bar-put--hatch'
                p_top_show   = 'block'
                #~# H rank: override both segments with rank color + hatch stripe
                put_base_style = f'background:{p_clr};' if p_clr else ''
                put_top_style  = f'background:{p_clr};background-image:{_HATCH};' if p_clr else ''
            elif p_diff < 0:
                ph_base      = max(1, int(p_curr / mx * CH)) if p_curr > 0 else 1
                ph_top       = max(1, int(abs(p_diff) / mx * CH))
                put_base_cls = 'bar-put--fill'
                put_top_cls  = 'bar-put--hollow'
                p_top_show   = 'block'
                put_base_style = f'background:{p_clr};' if p_clr else ''
                put_top_style  = f'border-color:{p_clr};' if p_clr else ''
            else:
                ph_base      = max(1, int(p_curr / mx * CH)) if p_curr > 0 else 1
                ph_top       = 0
                put_base_cls = 'bar-put--fill'
                put_top_cls  = 'bar-put--fill'
                p_top_show   = 'none'
                put_base_style = f'background:{p_clr};' if p_clr else ''
                put_top_style  = ''
        else:
            ph_base      = max(1, int(p_curr / mx * CH)) if p_curr > 0 else 1
            ph_top       = 0
            put_base_cls = 'bar-put--fill'
            put_top_cls  = 'bar-put--fill'
            p_top_show   = 'none'
            put_base_style = f'background:{p_clr};' if p_clr else ''
            put_top_style  = ''

        # ─── CALL (red) ────────────────────────────────────────────────
        c_diff = c_curr - c_prev
        if c_prev > 0:
            if c_diff > 0:
                ch_base       = max(1, int(c_prev / mx * CH))
                ch_top        = max(1, int(c_diff / mx * CH))
                call_base_cls = 'bar-call--fill'
                call_top_cls  = 'bar-call--hatch'
                c_top_show    = 'block'
                call_base_style = f'background:{c_clr};' if c_clr else ''
                call_top_style  = f'background:{c_clr};background-image:{_HATCH};' if c_clr else ''
            elif c_diff < 0:
                ch_base       = max(1, int(c_curr / mx * CH)) if c_curr > 0 else 1
                ch_top        = max(1, int(abs(c_diff) / mx * CH))
                call_base_cls = 'bar-call--fill'
                call_top_cls  = 'bar-call--hollow'
                c_top_show    = 'block'
                call_base_style = f'background:{c_clr};' if c_clr else ''
                call_top_style  = f'border-color:{c_clr};' if c_clr else ''
            else:
                ch_base       = max(1, int(c_curr / mx * CH)) if c_curr > 0 else 1
                ch_top        = 0
                call_base_cls = 'bar-call--fill'
                call_top_cls  = 'bar-call--fill'
                c_top_show    = 'none'
                call_base_style = f'background:{c_clr};' if c_clr else ''
                call_top_style  = ''
        else:
            ch_base       = max(1, int(c_curr / mx * CH)) if c_curr > 0 else 1
            ch_top        = 0
            call_base_cls = 'bar-call--fill'
            call_top_cls  = 'bar-call--fill'
            c_top_show    = 'none'
            call_base_style = f'background:{c_clr};' if c_clr else ''
            call_top_style  = ''

        atm_marker = _render('atm_marker') if is_atm else ''
        strike_cls = 'strike-label--atm' if is_atm else ''

        brs += _render('oi_bar_combined',
                       atm_marker=atm_marker,
                       CH=str(CH),
                       ph_base=str(ph_base),
                       ph_top=str(ph_top),
                       ch_base=str(ch_base),
                       ch_top=str(ch_top),
                       put_base_cls=put_base_cls,
                       put_top_cls=put_top_cls,
                       call_base_cls=call_base_cls,
                       call_top_cls=call_top_cls,
                       p_top_show=p_top_show,
                       c_top_show=c_top_show,
                       put_base_style=put_base_style,
                       put_top_style=put_top_style,
                       call_base_style=call_base_style,
                       call_top_style=call_top_style,
                       strike_cls=strike_cls,
                       strike_display=f'{s:,}')

    sp = _render('spot_display', spot=f'{spot:,.2f}') if spot > 0 else ''
    lg = _render('legend_combined')

    #~# Subtitle reflects data source: intraday fallback vs actual prev-day snapshot
    if use_intraday_fallback:
        _sub = 'Solid = Day-start OI · Stripe = Intraday Increase · Hollow border = Intraday Decrease'
    else:
        _sub = 'Solid = Prev-close OI · Stripe = Increase today · Hollow border = Decrease today'

    return _render('oi_chart',
                   PUT_BAR=PUT_BAR,
                   CALL_BAR=CALL_BAR,
                   H2_CLR=H2_CLR,
                   H3_CLR=H3_CLR,
                   title='📊+📈 OI Distribution + Change',
                   subtitle=_sub,
                   CH=str(CH),
                   yticks=ytk,
                   gridlines=grd,
                   bars=brs,
                   spot_display=sp,
                   legend=lg)


#~# Fallback cache: always show last valid OI charts even if current fetch returns empty
_last_valid_oi_charts: str = ''


def _generate_mock_prev_snapshot(df: pd.DataFrame) -> dict:
    """
    Generate a stable fake previous-day OI snapshot from current df.
    Uses seed=42 so bars don't flicker on every 3s refresh.
    Mix of +40%/-40% relative to current OI creates visible increases & decreases.
    """
    mock: dict = {}
    rng = _random.Random(42)  #~# fixed seed = stable across refreshes
    for _, row in df.iterrows():
        try:
            s = int(float(row.get('Strike', 0)))
        except (ValueError, TypeError):
            continue
        c = float(row.get('C_OI', 0) or 0)
        p = float(row.get('P_OI', 0) or 0)
        #~# Each strike independently randomised: range 0.55–1.45 of today's value
        mock[str(s)] = {
            'c_oi': round(c * rng.uniform(0.55, 1.45), 0),
            'p_oi': round(p * rng.uniform(0.55, 1.45), 0),
        }
    return mock


def _oi_charts(data: dict) -> str:
    """
    Single combined panel: 📊+📈 OI Distribution + Change.
    Falls back to last valid render when current data is empty/unavailable.
    """
    global _last_valid_oi_charts

    df = data.get('option_df', pd.DataFrame())
    atm = data.get('atm_strike', 0)
    spot = data.get('spot_price', 0)
    prev_snap = data.get('prev_oi_snapshot', {})

    #!# If df is empty, return the last valid cached HTML immediately
    if df.empty:
        return _last_valid_oi_charts

    #~# Weekend mock mode: inject a synthetic prev-day snapshot so combined panel renders
    global _MOCK_PREV_SNAP
    if _MOCK_MODE and not prev_snap:
        if not _MOCK_PREV_SNAP:
            _MOCK_PREV_SNAP = _generate_mock_prev_snapshot(df)
        prev_snap = _MOCK_PREV_SNAP

    #^# Single combined panel — shows OI distribution + intraday change
    combined = _oi_combined_chart(df, atm, spot, prev_snap)

    #~# Render via oi_charts.html template
    css = _load_css()
    result = _render('oi_charts',
                     css=css,
                     combined=combined)

    #!# Cache this render as last-valid so it persists across empty cycles
    if combined:
        _last_valid_oi_charts = result

    return result


def _top_oi_table(option_df) -> str:
    """!
    Renders 'Highest Call & Put OI' as a unified table with a common Strike column
    in the center. Call data fills the left side, Put data fills the right side.
    All unique strikes from both top-3 Call OI and top-3 Put OI are merged and
    sorted descending. Empty cells are shown where a side has no data for that strike.
    """
    try:
        if option_df is None or option_df.empty:
            return ''

        # ── same ranking logic as _oc_table ──────────────────────────────
        c_oi_vals = sorted(option_df['C_OI'].dropna().unique(), reverse=True)[:3] \
                    if 'C_OI' in option_df.columns else []
        p_oi_vals = sorted(option_df['P_OI'].dropna().unique(), reverse=True)[:3] \
                    if 'P_OI' in option_df.columns else []

        # Build {strike: (rank, oi)} maps for each side
        call_map = {}  # strike → (rank, oi_val)
        for i, oi_val in enumerate(c_oi_vals):
            if oi_val > 0:
                r = i + 1
                strike_row = option_df[option_df['C_OI'] == oi_val].iloc[0]
                call_map[int(strike_row['Strike'])] = (r, oi_val)

        put_map = {}  # strike → (rank, oi_val)
        for i, oi_val in enumerate(p_oi_vals):
            if oi_val > 0:
                r = i + 1
                strike_row = option_df[option_df['P_OI'] == oi_val].iloc[0]
                put_map[int(strike_row['Strike'])] = (r, oi_val)

        # Merge all unique strikes from both sides, sorted descending
        all_strikes = sorted(set(call_map.keys()) | set(put_map.keys()), reverse=True)
        if not all_strikes:
            return ''

        body = ''
        for strike in all_strikes:
            c_data = call_map.get(strike)  # (rank, oi) or None
            p_data = put_map.get(strike)   # (rank, oi) or None

            if c_data:
                c_rank, c_oi = c_data
                c_clr = OI_RANK_CALL.get(c_rank, TEXT_DEFAULT)
                call_oi = format_lakh(c_oi)
                call_rank = f'H{c_rank}'
                call_oi_style = f'color:{c_clr}'
                call_rank_style = f'color:{c_clr}'
            else:
                call_oi = ''
                call_rank = ''
                call_oi_style = ''
                call_rank_style = ''

            if p_data:
                p_rank, p_oi = p_data
                p_clr = OI_RANK_PUT.get(p_rank, TEXT_DEFAULT)
                put_oi = format_lakh(p_oi)
                put_rank = f'H{p_rank}'
                put_oi_style = f'color:{p_clr}'
                put_rank_style = f'color:{p_clr}'
            else:
                put_oi = ''
                put_rank = ''
                put_oi_style = ''
                put_rank_style = ''

            body += _render('top_oi_unified_row',
                            call_oi=call_oi, call_rank=call_rank,
                            call_oi_style=call_oi_style, call_rank_style=call_rank_style,
                            common_strike=f'{strike:,}',
                            put_rank=put_rank, put_oi=put_oi,
                            put_oi_style=put_oi_style, put_rank_style=put_rank_style)

        return _render('top_oi', body_rows=body)
    except Exception:
        return ''


def _analytics(m: dict, data: dict | None = None) -> str:
    option_df = data.get('option_df') if data else None

    def _tbl(title, rows, mode='3col'):
        if mode == '3col':
            hdr = _render('analytics_header_3col')
            body = ''
            for r in rows:
                lbl, cv, pv = r[0], r[1], r[2]
                # Optional per-cell color: (label, call_val, put_val, call_color, put_color)
                call_color = r[3] if len(r) > 3 else None
                put_color  = r[4] if len(r) > 4 else None
                call_style = f' style="color:{call_color}"' if call_color else ''
                put_style  = f' style="color:{put_color}"' if put_color else ''

                if isinstance(cv, str):
                    if call_color or put_color:
                        body += _render('analytics_row_3col_str_colored',
                                        label=lbl, call_val=cv, put_val=pv,
                                        call_style=call_style, put_style=put_style)
                    else:
                        body += _render('analytics_row_3col_str',
                                        label=lbl, call_val=cv, put_val=pv)
                else:
                    net = pv - cv
                    nc = 'oc-analytics__td--put' if net > 0 else 'oc-analytics__td--call'
                    if call_color or put_color:
                        body += _render('analytics_row_3col_num_colored',
                                        label=lbl, call_val=format_lakh(cv),
                                        put_val=format_lakh(pv),
                                        call_style=call_style, put_style=put_style,
                                        net_cls=nc, net_val=format_lakh(net))
                    else:
                        body += _render('analytics_row_3col_num',
                                        label=lbl,
                                        call_val=format_lakh(cv),
                                        put_val=format_lakh(pv),
                                        net_cls=nc,
                                        net_val=format_lakh(net))
        else:
            hdr = _render('analytics_header_2col')
            body = ''
            for row in rows:
                lbl, val = row[0], row[1]
                raw = row[2] if len(row) > 2 else None
                if raw is None:
                    val_cls = ''
                elif raw > 0:
                    val_cls = 'oc-analytics__td--put'
                elif raw < 0:
                    val_cls = 'oc-analytics__td--call'
                else:
                    val_cls = ''
                body += _render('analytics_row_2col', label=lbl, value=val, val_cls=val_cls)

        return _render('analytics_card',
                       H2_CLR=H2_CLR,
                       title=title,
                       header=hdr,
                       body=body)

    totals = _tbl(SEC_TOTALS, [
        (LBL_TOTAL_OI, m.get('total_call_oi', 0), m.get('total_put_oi', 0)),
        (LBL_TOTAL_OI_CHG, m.get('total_call_oi_chg', 0), m.get('total_put_oi_chg', 0)),
        (LBL_TOTAL_VOL, m.get('total_call_vol', 0), m.get('total_put_vol', 0)),
        # Build-up OI rows: call cell uses BU_CALL color, put cell uses BU_PUT color
        (LBL_TOTAL_LB_OI,     m.get('call_lb', 0),     m.get('put_lb', 0),     BU_CALL['LB'], BU_PUT['LB']),
        (LBL_TOTAL_SC_OI,     m.get('call_sc', 0),     m.get('put_sc', 0),     BU_CALL['SC'], BU_PUT['SC']),
        (LBL_TOTAL_SB_OI,     m.get('call_sb', 0),     m.get('put_sb', 0),     BU_CALL['SB'], BU_PUT['SB']),
        (LBL_TOTAL_LU_OI,     m.get('call_lu', 0),     m.get('put_lu', 0),     BU_CALL['LU'], BU_PUT['LU']),
        (LBL_TOTAL_LB_OI_CHG, m.get('call_lb_chg', 0), m.get('put_lb_chg', 0), BU_CALL['LB'], BU_PUT['LB']),
        (LBL_TOTAL_SC_OI_CHG, m.get('call_sc_chg', 0), m.get('put_sc_chg', 0), BU_CALL['SC'], BU_PUT['SC']),
        (LBL_TOTAL_SB_OI_CHG, m.get('call_sb_chg', 0), m.get('put_sb_chg', 0), BU_CALL['SB'], BU_PUT['SB']),
        (LBL_TOTAL_LU_OI_CHG, m.get('call_lu_chg', 0), m.get('put_lu_chg', 0), BU_CALL['LU'], BU_PUT['LU']),
    ])

    pcr = m.get('pcr_oi', 0)
    sentiment = _tbl(SEC_SENTIMENT, [
        (LBL_BULLISH_OI,     format_lakh(m.get('bullish_oi', 0)),              m.get('bullish_oi', 0)),
        (LBL_BEARISH_OI,     format_lakh(m.get('bearish_oi', 0)),             -m.get('bearish_oi', 0)),
        (LBL_BULLISH_OI_CHG, format_lakh(m.get('bullish_oi_chg', 0)),          m.get('bullish_oi_chg', 0)),
        (LBL_BEARISH_OI_CHG, format_lakh(m.get('bearish_oi_chg', 0)),         -m.get('bearish_oi_chg', 0)),
        (LBL_CALL_PREMIUM,  format_lakh(m.get('total_call_premium', 0)),      m.get('total_call_premium', 0)),
        (LBL_PUT_PREMIUM,   format_lakh(m.get('total_put_premium', 0)),       m.get('total_put_premium', 0)),
        (LBL_CALL_PREM_CHG, format_lakh(m.get('total_call_premium_chg', 0)),   m.get('total_call_premium_chg', 0)),
        (LBL_PUT_PREM_CHG,  format_lakh(m.get('total_put_premium_chg', 0)),    m.get('total_put_premium_chg', 0)),
        (LBL_PE_CE_OI_CHG,         format_lakh(m.get('pe_ce_diff', 0)),              m.get('pe_ce_diff', 0)),
        (LBL_PCR_OI,               f"{pcr:.2f}",                                     pcr - 1),
        (LBL_PCR_OI_CHG,           f"{m.get('pcr_oi_chg', 0):.2f}",                 m.get('pcr_oi_chg', 0) - 1),
        (LBL_PCR_VOL,           f"{m.get('pcr_vol', 0):.2f}",                     m.get('pcr_vol', 0) - 1),
    ], mode='2col')

    otm_c, otm_p = m.get('otm_call_oi', 0), m.get('otm_put_oi', 0)
    pcr_otm = (otm_p / otm_c) if otm_c > 0 else 0
    otm_cc, otm_pc = m.get('otm_call_oi_chg', 0), m.get('otm_put_oi_chg', 0)
    pcr_otm_c = (otm_pc / otm_cc) if otm_cc != 0 else 0
    otm = _tbl(SEC_OTM, [
        (LBL_OTM_OI, m.get('otm_call_oi', 0), m.get('otm_put_oi', 0)),
        (LBL_OTM_OI_CHG, otm_cc, otm_pc),
        (LBL_OTM_VOL, m.get('otm_call_vol', 0), m.get('otm_put_vol', 0)),
        (LBL_PCR_OTM_OI, f"{pcr_otm:.2f}", f"{pcr_otm_c:.2f}"),
        (LBL_PCR_OTM_OI_CHG, f"{pcr_otm_c:.2f}", ""),
    ])

    itm_c, itm_p = m.get('itm_call_oi', 0), m.get('itm_put_oi', 0)
    pcr_itm = (itm_p / itm_c) if itm_c > 0 else 0
    itm_cc, itm_pc = m.get('itm_call_oi_chg', 0), m.get('itm_put_oi_chg', 0)
    pcr_itm_c = (itm_pc / itm_cc) if itm_cc != 0 else 0
    itm = _tbl(SEC_ITM, [
        (LBL_ITM_OI, m.get('itm_call_oi', 0), m.get('itm_put_oi', 0)),
        (LBL_ITM_OI_CHG, itm_cc, itm_pc),
        (LBL_ITM_VOL, m.get('itm_call_vol', 0), m.get('itm_put_vol', 0)),
        (LBL_PCR_ITM_OI, f"{pcr_itm:.2f}", f"{pcr_itm_c:.2f}"),
        (LBL_PCR_ITM_OI_CHG, f"{pcr_itm_c:.2f}", ""),
    ])

    top_oi_html = _top_oi_table(option_df) if (option_df is not None and not option_df.empty) else ''
    return _render('analytics',
                   H2_CLR=H2_CLR,
                   top_oi=top_oi_html,
                   row1=totals + sentiment,
                   row2=otm + itm)


# ═══════════════════════════════════════════════════════════════════════════
#^# NIFTY 50 MULTI-TIMEFRAME TECHNICAL INDICATORS TABLE
# ═══════════════════════════════════════════════════════════════════════════

_tf_indicators_cache: dict = {'html': '', 'ts': 0}

# ── Direct Dhan API OHLCV fetcher (5-day intraday) for indicator accuracy ──
_tf_ohlcv_cache: dict = {}  #~# key = (underlying, interval) → {'df': ..., 'ts': float}


def _fetch_ohlcv_direct(underlying: str, interval: int) -> pd.DataFrame:
    """Fetch intraday OHLCV from Dhan /charts/intraday with full 5-day range.

    Returns DataFrame with columns: timestamp, open, high, low, close, volume.
    Cached for 60s per (underlying, interval).
    """
    from oc_data_fetcher import INDEX_SECURITY_IDS, API_HEADERS
    import requests, datetime as _dtmod

    cache_key = (underlying, interval)
    cached = _tf_ohlcv_cache.get(cache_key)
    if cached and (_time.time() - cached.get('ts', 0)) < 60:
        return cached['df']

    security_id = INDEX_SECURITY_IDS.get(underlying, 0)
    if not security_id:
        return pd.DataFrame()

    #~# 5 trading days = ~7 calendar days to be safe
    to_date = _dtmod.date.today().strftime('%Y-%m-%d')
    from_date = (_dtmod.date.today() - _dtmod.timedelta(days=7)).strftime('%Y-%m-%d')

    try:
        url = "https://api.dhan.co/v2/charts/intraday"
        payload = {
            'securityId': str(security_id),
            'exchangeSegment': 'IDX_I',
            'instrument': 'INDEX',
            'interval': interval,
            'fromDate': from_date,
            'toDate': to_date,
        }
        r = requests.post(url, json=payload, headers=API_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            #~# Dhan API returns parallel arrays at top level:
            #~# {open:[], high:[], low:[], close:[], volume:[], timestamp:[]}
            if 'open' in data and 'close' in data and 'timestamp' in data:
                df = pd.DataFrame(data)
                if not df.empty:
                    #~# Convert epoch timestamps to datetime (UTC→IST)
                    df['timestamp'] = (pd.to_datetime(df['timestamp'], unit='s',
                                                      errors='coerce')
                                       .dt.tz_localize('UTC')
                                       .dt.tz_convert('Asia/Kolkata')
                                       .dt.tz_localize(None))
                    #~# Normalise column names to lowercase
                    df.columns = [c.lower() for c in df.columns]
                    _tf_ohlcv_cache[cache_key] = {'df': df, 'ts': _time.time()}
                    return df
    except Exception as e:
        print(f"[TF] Direct OHLCV fetch ({underlying}, {interval}m) error: {e}")

    #~# Return stale cache if available
    if cached:
        return cached['df']
    return pd.DataFrame()


def _fetch_ohlcv_daily(underlying: str) -> pd.DataFrame:
    """Fetch daily OHLCV from Dhan /charts/historical with 1-year range.

    Appends today's partial daily candle (built from 5-min intraday) so that
    indicators match TradingView's live daily chart behaviour.
    Cached for 60s per (underlying, 'daily').
    """
    from oc_data_fetcher import INDEX_SECURITY_IDS, API_HEADERS
    import requests, datetime as _dtmod

    cache_key = (underlying, 'daily')
    cached = _tf_ohlcv_cache.get(cache_key)
    if cached and (_time.time() - cached.get('ts', 0)) < 60:
        return cached['df']

    security_id = INDEX_SECURITY_IDS.get(underlying, 0)
    if not security_id:
        return pd.DataFrame()

    to_date = _dtmod.date.today().strftime('%Y-%m-%d')
    from_date = (_dtmod.date.today() - _dtmod.timedelta(days=365)).strftime('%Y-%m-%d')

    try:
        url = "https://api.dhan.co/v2/charts/historical"
        payload = {
            'securityId': str(security_id),
            'exchangeSegment': 'IDX_I',
            'instrument': 'INDEX',
            'expiryCode': 0,
            'fromDate': from_date,
            'toDate': to_date,
        }
        r = requests.post(url, json=payload, headers=API_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            #~# Same parallel-array format as intraday
            if 'open' in data and 'close' in data and 'timestamp' in data:
                df = pd.DataFrame(data)
                if not df.empty:
                    df['timestamp'] = (pd.to_datetime(df['timestamp'], unit='s',
                                                      errors='coerce')
                                       .dt.tz_localize('UTC')
                                       .dt.tz_convert('Asia/Kolkata')
                                       .dt.tz_localize(None))
                    df.columns = [c.lower() for c in df.columns]

                    #~# Append today's partial candle from 5-min intraday data
                    #~# (historical API excludes the current incomplete day)
                    try:
                        intra_df = _fetch_ohlcv_direct(underlying, 5)
                        if intra_df is not None and not intra_df.empty:
                            today = _dtmod.date.today()
                            today_mask = intra_df['timestamp'].dt.date == today
                            today_candles = intra_df.loc[today_mask]
                            if not today_candles.empty:
                                today_row = pd.DataFrame([{
                                    'timestamp': pd.Timestamp(today),
                                    'open':   float(today_candles.iloc[0]['open']),
                                    'high':   float(today_candles['high'].max()),
                                    'low':    float(today_candles['low'].min()),
                                    'close':  float(today_candles.iloc[-1]['close']),
                                    'volume': int(today_candles['volume'].sum()),
                                }])
                                df = pd.concat([df, today_row], ignore_index=True)
                    except Exception:
                        pass  #~# proceed with historical-only data

                    _tf_ohlcv_cache[cache_key] = {'df': df, 'ts': _time.time()}
                    return df
    except Exception as e:
        print(f"[TF] Daily OHLCV fetch ({underlying}) error: {e}")

    if cached:
        return cached['df']
    return pd.DataFrame()


def _calc_macd(series, fast=12, slow=26, signal=9):
    """Compute MACD line, signal line, and histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _resample_ohlcv(df, target_minutes):
    """Resample a lower-timeframe OHLCV DataFrame to a higher timeframe.
    Expects columns: timestamp, open, high, low, close, volume.
    """
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    rule = f'{target_minutes}min'
    resampled = df.resample(rule, origin='start').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
    }).dropna(subset=['open'])
    resampled = resampled.reset_index()
    return resampled


def _build_tf_indicators_table(underlying='NIFTY', spot_price=0.0):
    """
    Build an HTML table showing LTP, RSI(14), MACD/Signal, Zone, 34-EMA, 61-EMA
    for NIFTY 50 across 5min, 10min, 15min, 30min, 60min, Daily timeframes.
    Uses DIRECT Dhan API with 5-day range for intraday and 1-year for daily.
    10-min and 30-min are resampled from 5-min and 15-min data.
    Uses 60s cache to avoid excessive API calls.
    """
    global _tf_indicators_cache
    now = _time.time()
    if _tf_indicators_cache.get('html') and (now - _tf_indicators_cache.get('ts', 0)) < 60:
        return _tf_indicators_cache['html']

    def _fetch_tf(label, api_interval, resample_from_interval=None, resample_minutes=None):
        """Fetch OHLCV data directly from Dhan API or resample from lower TF."""
        if label == 'Daily':
            df = _fetch_ohlcv_daily(underlying)
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                return None
            return df
        if resample_from_interval and resample_minutes:
            base_df = _fetch_ohlcv_direct(underlying, resample_from_interval)
            if base_df is None or not isinstance(base_df, pd.DataFrame) or base_df.empty:
                return None
            return _resample_ohlcv(base_df, resample_minutes)
        else:
            df = _fetch_ohlcv_direct(underlying, api_interval)
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                return None
            return df

    # (display_label, api_interval_int, resample_source_interval, resample_minutes)
    timeframes = [
        ('5 Min',  5,    None, None),
        ('10 Min', None, 5,    10),     # resample 5-min → 10-min
        ('15 Min', 15,   None, None),
        ('30 Min', None, 15,   30),     # resample 15-min → 30-min
        ('60 Min', 60,   None, None),
        ('Daily',  None, None, None),   # uses _fetch_ohlcv_daily
    ]

    #~# Column count (Timeframe, RSI, MACD·Zone, 34/61-EMA) = 4
    _num_cols = 4
    ltp_str = f'{spot_price:,.2f}' if spot_price else '—'

    rows_html = ''
    for label, api_interval, resample_from_interval, resample_min in timeframes:
        try:
            df = _fetch_tf(label, api_interval, resample_from_interval, resample_min)
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                rows_html += _render('tf_indicators_empty_row',
                                     label=label, colspan=_num_cols - 1,
                                     color=MUTED_LIGHT, message=LBL_NO_DATA)
                continue

            close = df['close'].astype(float)

            # RSI(14) — 5-tier color scale
            rsi_series = _calc_rsi(close, 14)
            rsi_val = float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else 0
            if rsi_val > 70:
                rsi_clr = GREEN              # overbought — bright green
            elif rsi_val > 50 and abs(rsi_val - 50) > 0.5:
                rsi_clr = YELLOW_GREEN       # 50-70 zone — yellow-green
            elif abs(rsi_val - 50) <= 0.5:
                rsi_clr = BLUE               # exactly ~50 — blue neutral
            elif rsi_val >= 30:
                rsi_clr = ORANGE             # 30-50 zone — orange
            else:
                rsi_clr = BRIGHT_RED         # oversold — bright red

            # MACD (12,26,9)
            macd_line, signal_line, histogram = _calc_macd(close)
            macd_val = float(macd_line.dropna().iloc[-1]) if not macd_line.dropna().empty else 0
            signal_val = float(signal_line.dropna().iloc[-1]) if not signal_line.dropna().empty else 0
            #~# MACD/Signal number color: green if MACD > Signal, red otherwise
            macd_clr = LIMEGREEN if macd_val > signal_val else BRIGHT_RED
            #~# Zone text + color based on signs of MACD and Signal
            if macd_val > 0 and signal_val > 0:
                zone_text = LBL_ZONE_POSITIVE
                zone_clr  = LIMEGREEN
            elif macd_val < 0 and signal_val < 0:
                zone_text = LBL_ZONE_NEGATIVE
                zone_clr  = BRIGHT_RED
            else:
                zone_text = LBL_ZONE_TRANSITION
                zone_clr  = GOLD

            # 61-EMA and 34-EMA — combined, single color
            ema61 = float(close.ewm(span=61, adjust=False).mean().iloc[-1])
            ema34 = float(close.ewm(span=34, adjust=False).mean().iloc[-1])
            ema_clr = LIMEGREEN if ema34 > ema61 else BRIGHT_RED

            rows_html += _render('tf_indicators_row',
                                  label=label, rsi_clr=rsi_clr, rsi_val=f'{rsi_val:.2f}',
                                  macd_clr=macd_clr, macd_val=f'{macd_val:.2f}',
                                  signal_val=f'{signal_val:.2f}', zone_clr=zone_clr,
                                  zone_text=zone_text, ema_clr=ema_clr,
                                  ema34=f'{ema34:,.2f}', ema61=f'{ema61:,.2f}')
        except Exception as e:
            rows_html += _render('tf_indicators_empty_row',
                                  label=label, colspan=_num_cols - 1,
                                  color=RED, message=f'Error: {e}')

    html = _render('tf_indicators',
                    H2_CLR=H2_CLR, underlying=underlying,
                    ltp_str=ltp_str, rows_html=rows_html)

    _tf_indicators_cache = {'html': html, 'ts': now}
    return html


# ═══════════════════════════════════════════════════════════════════════════
#^# 15-MIN STRADDLE CHART (via Dhan Tradehull)
# ═══════════════════════════════════════════════════════════════════════════

_tradehull_instance = None
_tradehull_init_failed = False
_tradehull_init_started = False


def _get_tradehull():
    """Lazy singleton for Tradehull API client."""
    global _tradehull_instance, _tradehull_init_failed
    if _tradehull_init_failed:
        return None
    if _tradehull_instance is None:
        try:
            _tradehull_instance = Tradehull(client_code, token_id)
            _dbg_console.print("[bold green]\\[Tradehull] Connected successfully[/]")
        except Exception as e:
            _dbg_console.print(f"[bold red]\\[Tradehull] Init FAILED: {e}[/]")
            _tradehull_init_failed = True
            return None
    return _tradehull_instance


def _init_tradehull_background():
    """Initialize Tradehull in background so it doesn't block first data load."""
    global _tradehull_init_started
    if _tradehull_init_started:
        return
    _tradehull_init_started = True
    import threading
    def _init():
        try:
            _get_tradehull()
        except Exception:
            pass
    threading.Thread(target=_init, daemon=True, name="tradehull-init").start()


# Kick off Tradehull init immediately (runs in background, doesn't block)
_init_tradehull_background()


# ═══════════════════════════════════════════════════════════════════════════
#^# CHART BACKGROUND BUILDER — non-blocking chart rendering
# ═══════════════════════════════════════════════════════════════════════════
_chart_executor = ThreadPoolExecutor(max_workers=1)
_chart_build_in_progress = False


def _chart_loading_placeholder(label: str):
    """Return a minimal Plotly figure with 'Loading…' text as chart placeholder."""
    fig = go.Figure()
    fig.add_annotation(
        text=f"Loading {label}...",
        xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=18, color=MUTED_LIGHT, family="Inter, sans-serif"),
    )
    fig.update_layout(
        paper_bgcolor=PANEL_BG, plot_bgcolor=PANEL_BG,
        height=580, margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


def _get_cached_or_placeholder_charts():
    """Return cached chart figures if available, else loading placeholders."""
    results = []
    labels = [
        ((0, '15'), '15-Min Current Expiry'),
        ((1, '15'), '15-Min Next Expiry'),
        ((0, '5'), '5-Min Current Expiry'),
        ((1, '5'), '5-Min Next Expiry'),
    ]
    for key, label in labels:
        cached = _straddle_fig_cache.get(key, {}).get('fig')
        results.append(cached if cached is not None else _chart_loading_placeholder(label))
    return tuple(results)


def _build_charts_background(data: dict):
    """Build straddle charts in background thread — updates cache silently."""
    global _chart_build_in_progress
    if _chart_build_in_progress:
        return  # skip if already building
    _chart_build_in_progress = True
    try:
        _build_straddle_charts(data)
    except Exception as e:
        print(f"[WARN] Background chart build error: {e}")
    finally:
        _chart_build_in_progress = False


#~# Per-expiry+timeframe data caches (60s TTL each)  key = (expiry_idx, timeframe)
_straddle_data_cache: dict = {}
#~# Per-expiry+timeframe figure caches  key = (expiry_idx, timeframe)
_straddle_fig_cache: dict = {}


def _calc_rsi(series, period=14):
    """Compute RSI(period) on a price series."""
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=1).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan')).fillna(float('inf'))
    return (100 - (100 / (1 + rs))).round(2)


def _build_one_straddle_chart(strike, open_price, underlying, expiry_idx, chart_label, timeframe='15'):
    """
    Build one straddle chart with VWAP + RSI(14) for a given expiry & timeframe.

    Layout:
      Top 72%   — Straddle close line + VWAP overlay + Opening-straddle hline
      Bottom 28% — RSI (14) with OB/OS bands

    Annotation positions (non-overlapping):
      - Current price badge     →  right of last data point
      - PnL change badge        →  paper-coords bottom-right
      - RSI current value badge →  paper-coords very bottom-right
    Day Open & Opening Straddle are shown in the chart title (heading).
    """
    global _straddle_data_cache, _straddle_fig_cache
    now = _time.time()
    cache_key = (expiry_idx, timeframe)
    fc  = _straddle_fig_cache.get(cache_key, {})
    dc  = _straddle_data_cache.get(cache_key, {})

    if (fc.get('fig') is not None
            and fc.get('strike') == strike
            and (now - fc.get('ts', 0)) < 60):
        return fc['fig']

    try:
        #~# Get expiry date dynamically — no Tradehull ATM_Strike_Selection call
        expiries = _fetch_expiry_list_dynamic(underlying)
        if not expiries or expiry_idx >= len(expiries):
            return fc.get('fig')
        expiry_date_str = expiries[min(expiry_idx, len(expiries) - 1)]

        #~# Resolve CE/PE symbols + security IDs from instrument CSV
        ce_sym, pe_sym, ce_sec_id, pe_sec_id = _resolve_ce_pe_symbols(underlying, expiry_date_str, strike)
        if not ce_sym or not pe_sym or not ce_sec_id or not pe_sec_id:
            _dbg_console.print(
                f"[yellow]\\[Chart] {underlying} exp={expiry_date_str} strike={strike}: "
                f"CE/PE not found in instrument file[/]")
            return fc.get('fig')

        if (dc.get('strike') == strike and dc.get('ce_sym') == ce_sym
                and (now - dc.get('ts', 0)) < 60):
            ce_df = dc['ce_df']
            pe_df = dc['pe_df']
        else:
            #~# Direct Dhan API — no Tradehull dependency
            ce_df = _fetch_option_intraday(ce_sec_id, int(timeframe), symbol_label=ce_sym)
            pe_df = _fetch_option_intraday(pe_sec_id, int(timeframe), symbol_label=pe_sym)
            _straddle_data_cache[cache_key] = {
                'ce_df': ce_df, 'pe_df': pe_df, 'ts': now,
                'strike': strike, 'ce_sym': ce_sym, 'pe_sym': pe_sym,
            }

        if (ce_df is None or pe_df is None
                or not isinstance(ce_df, pd.DataFrame)
                or not isinstance(pe_df, pd.DataFrame)
                or ce_df.empty or pe_df.empty):
            return fc.get('fig')

        #~# 15-day lookback: check today → yesterday → day-2 → … → day-15
        ce_dates = ce_df['timestamp'].astype(str).str[:10]
        pe_dates = pe_df['timestamp'].astype(str).str[:10]
        #~# Find a date present in BOTH CE and PE data
        _label = f"Chart exp={expiry_idx} tf={timeframe}"
        found_date, days_back = _find_last_trading_day(ce_dates, _label)
        _using_last_day = days_back > 0
        if found_date is None:
            return fc.get('fig')
        ce_today = ce_df[ce_dates == found_date].copy()
        pe_today = pe_df[pe_dates == found_date].copy()
        if ce_today.empty or pe_today.empty:
            return fc.get('fig')

        m = pd.merge(
            ce_today[['timestamp','open','high','low','close','volume']].rename(
                columns={'open':'ce_o','high':'ce_h','low':'ce_l','close':'ce_c','volume':'ce_v'}),
            pe_today[['timestamp','open','high','low','close','volume']].rename(
                columns={'open':'pe_o','high':'pe_h','low':'pe_l','close':'pe_c','volume':'pe_v'}),
            on='timestamp', how='inner',
        )
        if m.empty:
            return fc.get('fig')

        m['s_open']  = m['ce_o'] + m['pe_o']
        m['s_high']  = m['ce_h'] + m['pe_h']
        m['s_low']   = m['ce_l'] + m['pe_l']
        m['s_close'] = m['ce_c'] + m['pe_c']
        m['s_vol']   = m['ce_v'] + m['pe_v']

        #~# Per-leg VWAP: compute VWAP for CE and PE separately, then sum.
        #~# Using combined s_high/s_low inflates the range (CE & PE highs/lows
        #~# don't coincide — they're anti-correlated), distorting VWAP upward
        #~# especially on larger timeframes like 15-min.
        ce_tp      = (m['ce_h'] + m['ce_l'] + m['ce_c']) / 3
        pe_tp      = (m['pe_h'] + m['pe_l'] + m['pe_c']) / 3
        ce_cum_tpv = (ce_tp * m['ce_v'].fillna(0)).cumsum()
        ce_cum_vol = m['ce_v'].fillna(0).cumsum().replace(0, float('nan'))
        pe_cum_tpv = (pe_tp * m['pe_v'].fillna(0)).cumsum()
        pe_cum_vol = m['pe_v'].fillna(0).cumsum().replace(0, float('nan'))
        m['vwap']  = (ce_cum_tpv / ce_cum_vol) + (pe_cum_tpv / pe_cum_vol)
        m['rsi']     = _calc_rsi(m['s_close'], 14)

        opening_straddle = float(m['s_open'].iloc[0])
        current_straddle = float(m['s_close'].iloc[-1])
        pnl       = current_straddle - opening_straddle
        pnl_pct   = (pnl / opening_straddle * 100) if opening_straddle > 0 else 0
        pnl_color = CALL_BAR if pnl > 0 else PUT_BAR
        pnl_sign  = '+' if pnl > 0 else ''
        current_rsi = float(m['rsi'].dropna().iloc[-1]) if not m['rsi'].dropna().empty else 50.0
        rsi_color = WHITE

        all_y = m['s_close'].tolist() + m['vwap'].dropna().tolist()
        y_min = min(all_y) * 0.91
        y_max = max(all_y) * 1.15

        fig = make_subplots(
            rows=2, cols=1,
            row_heights=[0.72, 0.28],
            shared_xaxes=True,
            vertical_spacing=0.05,
        )

        # ── Straddle line ──────────────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=m['timestamp'], y=m['s_close'],
            name=f'Straddle {strike}',
            mode='lines+markers',
            line=dict(color=LIGHT_BLUE, width=2.5),
            marker=dict(size=5, color=LIGHT_BLUE),
            hovertemplate='\u20b9%{y:.2f}<extra>Straddle</extra>',
        ), row=1, col=1)

        # ── VWAP ──────────────────────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=m['timestamp'], y=m['vwap'],
            name='VWAP',
            mode='lines',
            line=dict(color=DEEP_ORANGE, width=2.0, dash='dot'),
            hovertemplate='\u20b9%{y:.2f}<extra>VWAP</extra>',
        ), row=1, col=1)

        # ── RSI ───────────────────────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=m['timestamp'], y=m['rsi'],
            name='RSI (14)',
            mode='lines',
            line=dict(color=WHITE, width=1.8),
            hovertemplate='%{y:.1f}<extra>RSI</extra>',
        ), row=2, col=1)
        fig.add_hline(y=70, line_dash='dot',
                      line_color=RSI_OVERBOUGHT_LINE, line_width=1.2, row=2, col=1)
        fig.add_hline(y=50, line_dash='dot',
                      line_color=RSI_NEUTRAL_LINE, line_width=1.0, row=2, col=1)
        fig.add_hline(y=30, line_dash='dot',
                      line_color=RSI_OVERSOLD_LINE, line_width=1.2, row=2, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor=RSI_OVERBOUGHT_ZONE,
                      line_width=0, row=2, col=1)
        fig.add_hrect(y0=0,  y1=30,  fillcolor=RSI_OVERSOLD_ZONE,
                      line_width=0, row=2, col=1)

        # ── Annotations ───────────────────────────────────────────────
        # Current straddle price on last candle
        fig.add_annotation(
            x=m['timestamp'].iloc[-1], y=current_straddle,
            text=f' \u20b9{current_straddle:.2f}',
            showarrow=True, arrowhead=2, arrowcolor=pnl_color,
            xanchor='left',
            font=dict(color=H1_CLR, size=14, family='Inter, monospace'),
            bgcolor=ANNOTATION_BG_PRIMARY,
            bordercolor=pnl_color, borderwidth=1.5, borderpad=5,
            row=1, col=1,
        )
        # PnL badge — paper coords, right side
        fig.add_annotation(
            xref='paper', yref='paper', x=0.99, y=0.295,
            text=f'  Chg: {pnl_sign}\u20b9{pnl:.2f}  ({pnl_sign}{pnl_pct:.1f}%)  ',
            showarrow=False, xanchor='right',
            font=dict(color=pnl_color, size=13, family='Inter, monospace'),
            bgcolor=ANNOTATION_BG_SECONDARY,
            bordercolor=pnl_color, borderwidth=1.5, borderpad=6,
        )
        # RSI current value badge
        fig.add_annotation(
            xref='paper', yref='paper', x=0.99, y=0.01,
            text=f'  RSI  {current_rsi:.1f}  ',
            showarrow=False, xanchor='right',
            font=dict(color=rsi_color, size=12, family='Inter, monospace'),
            bgcolor=ANNOTATION_BG_TERTIARY,
            bordercolor=rsi_color, borderwidth=1, borderpad=4,
        )

        # ── Layout ────────────────────────────────────────────────────
        # ── Title includes Day Open & Opening Straddle ─────────────
        _open_part = f'  \u2502  Day Open \u20b9{open_price:,.2f}' if open_price > 0 else ''
        fig.update_layout(
            title=dict(
                text=(f'\U0001f4c8 {timeframe}-Min Straddle  \u2502  {chart_label}'
                      f'  \u2502  Strike {strike}'
                      f'  \u2502  Live \u20b9{current_straddle:.2f}'
                      f'{_open_part}'
                      f'  \u2502  \u20b9{opening_straddle:.2f} \u2190 Opening Straddle'),
                font=dict(size=14, color=GOLD, family='Inter, sans-serif'),
                x=0.01, pad=dict(t=4),
            ),
            paper_bgcolor=PANEL_BG,
            plot_bgcolor=PANEL_BG,
            font=dict(color=TEXT_LIGHT, family='Inter, sans-serif', size=11),
            height=580,
            margin=dict(l=65, r=40, t=55, b=30),
            hovermode='x unified',
            legend=dict(
                bgcolor=LEGEND_BG,
                bordercolor=BORDER_COLOR, borderwidth=1,
                font=dict(size=11),
                orientation='h',
                yanchor='bottom', y=1.03, xanchor='right', x=1,
            ),
        )
        ax = dict(gridcolor=GRID_COLOR, showgrid=True, zeroline=False, tickfont=dict(size=10),
                  showspikes=True, spikecolor=SPIKE_COLOR,
                  spikethickness=1, spikedash='solid', spikesnap='cursor', spikemode='across')
        fig.update_xaxes(**ax, tickformat='%H:%M')
        fig.update_yaxes(**ax, tickformat='.2f')
        fig.update_yaxes(title_text='Price (\u20b9)', title_font=dict(size=11),
                         range=[y_min, y_max], row=1, col=1)
        fig.update_yaxes(title_text='RSI', title_font=dict(size=11),
                         range=[0, 100], dtick=20, row=2, col=1)

        _straddle_fig_cache[cache_key] = {'fig': fig, 'ts': now, 'strike': strike}
        return fig

    except Exception as e:
        print(f"[WARN] Straddle chart expiry={expiry_idx} error: {e}")
        import traceback; traceback.print_exc()
        return fc.get('fig')


def _build_straddle_charts(data: dict):
    """
    Build FOUR straddle charts via direct Dhan API (no Tradehull):
      Fig-1: 15-min Current weekly expiry  (expiry=0)
      Fig-2: 15-min Next weekly expiry     (expiry=1)
      Fig-3:  5-min Current weekly expiry  (expiry=0)
      Fig-4:  5-min Next weekly expiry     (expiry=1)
    Both charts share the same OPENING STRADDLE STRIKE from day-open sync.
    Returns (fig15_current, fig15_next, fig5_current, fig5_next) — any may be None on failure.
    """
    underlying = data.get('underlying', 'NIFTY')
    _default = (
        _straddle_fig_cache.get((0, '15'), {}).get('fig'),
        _straddle_fig_cache.get((1, '15'), {}).get('fig'),
        _straddle_fig_cache.get((0, '5'), {}).get('fig'),
        _straddle_fig_cache.get((1, '5'), {}).get('fig'),
    )

    #~# Skip chart build if market is closed AND cache already has figures;
    #~# if cache is empty, proceed to build with last available historical data.
    if not _is_market_open():
        _has_cached = any(v is not None for v in _default)
        if _has_cached:
            if not getattr(_build_straddle_charts, '_offhours_logged', False):
                _dbg_console.print(
                    f"[yellow]\\[Straddle] {_market_status_str()} — "
                    f"using cached/last-available charts (market closed)[/]")
                _build_straddle_charts._offhours_logged = True
            return _default
        #~# Cache empty — build once with last available data
        if not getattr(_build_straddle_charts, '_offhours_logged', False):
            _dbg_console.print(
                f"[yellow]\\[Straddle] {_market_status_str()} — "
                f"cache empty, building charts with last available data[/]")
            _build_straddle_charts._offhours_logged = True
    else:
        _build_straddle_charts._offhours_logged = False

    try:
        from oc_data_fetcher import ensure_day_open_synced
        sync       = ensure_day_open_synced(underlying, spot_price=data.get('spot_price', 0))
        open_price = float(sync.get('open_price', 0) or 0)
        strike     = int(sync.get('atm_strike', 0) or 0)
    except Exception:
        return _default
    if not strike:
        return None, None, None, None
    _dbg_console.print(
        f"[dim]\\[Straddle] Building 4 charts: {underlying} strike={strike} open={open_price:.2f}[/]")
    fig0_15 = _build_one_straddle_chart(strike, open_price, underlying, 0, 'Current Expiry', '15')
    fig1_15 = _build_one_straddle_chart(strike, open_price, underlying, 1, 'Next Expiry', '15')
    fig0_5  = _build_one_straddle_chart(strike, open_price, underlying, 0, 'Current Expiry', '5')
    fig1_5  = _build_one_straddle_chart(strike, open_price, underlying, 1, 'Next Expiry', '5')
    return fig0_15, fig1_15, fig0_5, fig1_5


def _build_straddle_chart(data: dict):
    """Thin wrapper — delegates to _build_straddle_charts, returns current-expiry 15-min chart."""
    fig0_15, _, _, _ = _build_straddle_charts(data)
    return fig0_15


# ═══════════════════════════════════════════════════════════════════════════
#^# ATM TRIPLE STRADDLE ROW + EMA CANDLESTICK CHART (NEW — do not touch above)
# ═══════════════════════════════════════════════════════════════════════════

def _get_strike_step(underlying: str) -> int:
    """Return the ONE-STRIKE step for the ATM-triple row.
    Must match INDEX_STEP_MAP in oc_data_fetcher.
    NIFTY → 50, BANKNIFTY → 100, FINNIFTY → 50, MIDCPNIFTY → 25."""
    _steps = {'NIFTY': 50, 'BANKNIFTY': 100, 'FINNIFTY': 50,
              'MIDCPNIFTY': 25, 'SENSEX': 100, 'BANKEX': 100}
    return _steps.get(str(underlying).upper(), 50)


#~# Separate figure/data cache for strike-specific straddle charts
#~# key = (expiry_idx, timeframe, strike)  — isolated from existing cache
_straddle_fig_cache_ws: dict = {}
_straddle_data_cache_ws: dict = {}
#~# Named cache for ATM-triple row so placeholder getter can distinguish Up/ATM/Down
#~# key = 'up' | 'atm' | 'down'
_atm_triple_named_cache: dict = {}


def _build_strike_straddle_chart(strike: int, open_price: float,
                                  underlying: str, expiry_idx: int,
                                  chart_label: str, timeframe: str = '5'):
    """
    Build a straddle chart (VWAP + RSI) for a SPECIFIC strike with its own cache.
    Does NOT touch _straddle_fig_cache or _straddle_data_cache used by existing charts.
    """
    global _straddle_fig_cache_ws, _straddle_data_cache_ws
    now = _time.time()
    cache_key = (expiry_idx, timeframe, strike)
    fc = _straddle_fig_cache_ws.get(cache_key, {})
    dc = _straddle_data_cache_ws.get(cache_key, {})

    if fc.get('fig') is not None and (now - fc.get('ts', 0)) < 60:
        return fc['fig']

    try:
        #~# Get expiry date dynamically — no Tradehull ATM_Strike_Selection call
        expiries = _fetch_expiry_list_dynamic(underlying)
        if not expiries or expiry_idx >= len(expiries):
            return fc.get('fig')
        expiry_date_str = expiries[min(expiry_idx, len(expiries) - 1)]
        _expiry_str = expiry_date_str  # for chart title

        #~# Resolve CE/PE symbols + security IDs from instrument CSV
        ce_sym, pe_sym, ce_sec_id, pe_sec_id = _resolve_ce_pe_symbols(underlying, expiry_date_str, strike)
        if not ce_sym or not pe_sym or not ce_sec_id or not pe_sec_id:
            _dbg_console.print(
                f"[yellow]\\[Chart-WS] {underlying} exp={expiry_date_str} strike={strike}: "
                f"CE/PE not found in instrument file[/]")
            return fc.get('fig')

        if dc.get('ce_sym') == ce_sym and (now - dc.get('ts', 0)) < 60:
            ce_df = dc['ce_df']
            pe_df = dc['pe_df']
        else:
            #~# Direct Dhan API — no Tradehull dependency
            ce_df = _fetch_option_intraday(ce_sec_id, int(timeframe), symbol_label=ce_sym)
            pe_df = _fetch_option_intraday(pe_sec_id, int(timeframe), symbol_label=pe_sym)
            #~# Only cache when BOTH legs have valid data; caching None blocks retries for 60s
            if (ce_df is not None and pe_df is not None
                    and isinstance(ce_df, pd.DataFrame) and isinstance(pe_df, pd.DataFrame)
                    and not ce_df.empty and not pe_df.empty):
                _straddle_data_cache_ws[cache_key] = {
                    'ce_df': ce_df, 'pe_df': pe_df, 'ts': now,
                    'ce_sym': ce_sym, 'pe_sym': pe_sym,
                }

        if (ce_df is None or pe_df is None
                or not isinstance(ce_df, pd.DataFrame)
                or not isinstance(pe_df, pd.DataFrame)
                or ce_df.empty or pe_df.empty):
            return fc.get('fig')

        #~# 15-day lookback: check today → yesterday → day-2 → … → day-15
        ce_dates = ce_df['timestamp'].astype(str).str[:10]
        pe_dates = pe_df['timestamp'].astype(str).str[:10]
        _label = f"Chart-WS strike={strike} tf={timeframe}"
        found_date, days_back = _find_last_trading_day(ce_dates, _label)
        _using_last_day = days_back > 0
        if found_date is None:
            return fc.get('fig')
        ce_today = ce_df[ce_dates == found_date].copy()
        pe_today = pe_df[pe_dates == found_date].copy()
        if ce_today.empty or pe_today.empty:
            return fc.get('fig')

        m = pd.merge(
            ce_today[['timestamp', 'open', 'high', 'low', 'close', 'volume']].rename(
                columns={'open': 'ce_o', 'high': 'ce_h', 'low': 'ce_l',
                         'close': 'ce_c', 'volume': 'ce_v'}),
            pe_today[['timestamp', 'open', 'high', 'low', 'close', 'volume']].rename(
                columns={'open': 'pe_o', 'high': 'pe_h', 'low': 'pe_l',
                         'close': 'pe_c', 'volume': 'pe_v'}),
            on='timestamp', how='inner',
        )
        if m.empty:
            return fc.get('fig')

        m['s_open']  = m['ce_o'] + m['pe_o']
        m['s_high']  = m['ce_h'] + m['pe_h']
        m['s_low']   = m['ce_l'] + m['pe_l']
        m['s_close'] = m['ce_c'] + m['pe_c']
        m['s_vol']   = m['ce_v'] + m['pe_v']

        #~# Per-leg VWAP: compute VWAP for CE and PE separately, then sum.
        ce_tp      = (m['ce_h'] + m['ce_l'] + m['ce_c']) / 3
        pe_tp      = (m['pe_h'] + m['pe_l'] + m['pe_c']) / 3
        ce_cum_tpv = (ce_tp * m['ce_v'].fillna(0)).cumsum()
        ce_cum_vol = m['ce_v'].fillna(0).cumsum().replace(0, float('nan'))
        pe_cum_tpv = (pe_tp * m['pe_v'].fillna(0)).cumsum()
        pe_cum_vol = m['pe_v'].fillna(0).cumsum().replace(0, float('nan'))
        m['vwap'] = (ce_cum_tpv / ce_cum_vol) + (pe_cum_tpv / pe_cum_vol)
        m['rsi']  = _calc_rsi(m['s_close'], 14)

        opening_straddle = float(m['s_open'].iloc[0])
        current_straddle = float(m['s_close'].iloc[-1])
        pnl       = current_straddle - opening_straddle
        pnl_pct   = (pnl / opening_straddle * 100) if opening_straddle > 0 else 0
        pnl_color = CALL_BAR if pnl > 0 else PUT_BAR
        pnl_sign  = '+' if pnl > 0 else ''
        current_rsi = float(m['rsi'].dropna().iloc[-1]) if not m['rsi'].dropna().empty else 50.0
        rsi_color = WHITE

        all_y = m['s_close'].tolist() + m['vwap'].dropna().tolist()
        y_min = min(all_y) * 0.91
        y_max = max(all_y) * 1.15

        fig = make_subplots(rows=2, cols=1, row_heights=[0.72, 0.28],
                            shared_xaxes=True, vertical_spacing=0.05)

        fig.add_trace(go.Scatter(
            x=m['timestamp'], y=m['s_close'],
            name=f'Straddle {strike}', mode='lines+markers',
            line=dict(color=LIGHT_BLUE, width=2.5),
            marker=dict(size=5, color=LIGHT_BLUE),
            hovertemplate='\u20b9%{y:.2f}<extra>Straddle</extra>',
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=m['timestamp'], y=m['vwap'],
            name='VWAP', mode='lines',
            line=dict(color=DEEP_ORANGE, width=2.0, dash='dot'),
            hovertemplate='\u20b9%{y:.2f}<extra>VWAP</extra>',
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=m['timestamp'], y=m['rsi'],
            name='RSI (14)', mode='lines',
            line=dict(color=WHITE, width=1.8),
            hovertemplate='%{y:.1f}<extra>RSI</extra>',
        ), row=2, col=1)
        fig.add_hline(y=70, line_dash='dot',
                      line_color=RSI_OVERBOUGHT_LINE, line_width=1.2, row=2, col=1)
        fig.add_hline(y=50, line_dash='dot',
                      line_color=RSI_NEUTRAL_LINE, line_width=1.0, row=2, col=1)
        fig.add_hline(y=30, line_dash='dot',
                      line_color=RSI_OVERSOLD_LINE, line_width=1.2, row=2, col=1)
        fig.add_hrect(y0=70, y1=100,
                      fillcolor=RSI_OVERBOUGHT_ZONE, line_width=0, row=2, col=1)
        fig.add_hrect(y0=0, y1=30,
                      fillcolor=RSI_OVERSOLD_ZONE, line_width=0, row=2, col=1)

        fig.add_annotation(
            x=m['timestamp'].iloc[-1], y=current_straddle,
            text=f' \u20b9{current_straddle:.2f}',
            showarrow=True, arrowhead=2, arrowcolor=pnl_color, xanchor='left',
            font=dict(color=H1_CLR, size=14, family='Inter, monospace'),
            bgcolor=ANNOTATION_BG_PRIMARY,
            bordercolor=pnl_color, borderwidth=1.5, borderpad=5,
            row=1, col=1,
        )
        fig.add_annotation(
            xref='paper', yref='paper', x=0.99, y=0.295,
            text=f'  Chg: {pnl_sign}\u20b9{pnl:.2f}  ({pnl_sign}{pnl_pct:.1f}%)  ',
            showarrow=False, xanchor='right',
            font=dict(color=pnl_color, size=13, family='Inter, monospace'),
            bgcolor=ANNOTATION_BG_SECONDARY,
            bordercolor=pnl_color, borderwidth=1.5, borderpad=6,
        )
        fig.add_annotation(
            xref='paper', yref='paper', x=0.99, y=0.01,
            text=f'  RSI  {current_rsi:.1f}  ',
            showarrow=False, xanchor='right',
            font=dict(color=rsi_color, size=12, family='Inter, monospace'),
            bgcolor=ANNOTATION_BG_TERTIARY,
            bordercolor=rsi_color, borderwidth=1, borderpad=4,
        )

        _open_part = f'  \u2502  Day Open \u20b9{open_price:,.2f}' if open_price > 0 else ''
        _exp_part  = f'  \u2502  Exp: {_expiry_str}' if _expiry_str else ''
        fig.update_layout(
            title=dict(
                text=(f'\U0001f4c8 {timeframe}-Min  \u2502  {chart_label}'
                      f'  \u2502  Strike {strike}'
                      f'{_exp_part}'
                      f'  \u2502  \u20b9{current_straddle:.2f}'
                      f'{_open_part}'
                      f'  \u2502  \u20b9{opening_straddle:.2f} \u2190 Opening'),
                font=dict(size=13, color=GOLD, family='Inter, sans-serif'),
                x=0.01, pad=dict(t=4),
            ),
            paper_bgcolor=PANEL_BG, plot_bgcolor=PANEL_BG,
            font=dict(color=TEXT_LIGHT, family='Inter, sans-serif', size=11),
            height=520, margin=dict(l=60, r=35, t=52, b=28),
            hovermode='x unified',
            legend=dict(
                bgcolor=LEGEND_BG, bordercolor=BORDER_COLOR, borderwidth=1,
                font=dict(size=11), orientation='h',
                yanchor='bottom', y=1.03, xanchor='right', x=1,
            ),
        )
        _ax = dict(gridcolor=GRID_COLOR, showgrid=True, zeroline=False, tickfont=dict(size=10),
                   showspikes=True, spikecolor=SPIKE_COLOR,
                   spikethickness=1, spikedash='solid', spikesnap='cursor', spikemode='across')
        fig.update_xaxes(**_ax, tickformat='%H:%M')
        fig.update_yaxes(**_ax, tickformat='.2f')
        fig.update_yaxes(title_text='Price (\u20b9)', title_font=dict(size=11),
                         range=[y_min, y_max], row=1, col=1)
        fig.update_yaxes(title_text='RSI', title_font=dict(size=11),
                         range=[0, 100], dtick=20, row=2, col=1)

        _straddle_fig_cache_ws[cache_key] = {'fig': fig, 'ts': now}
        return fig

    except Exception as e:
        print(f"[WARN] Strike straddle chart ({underlying}, {strike}, {expiry_idx}) error: {e}")
        import traceback; traceback.print_exc()
        return fc.get('fig')


def _build_atm_triple_charts(data: dict) -> tuple:
    """
    Build three 5-min straddle charts (current expiry, separate cache):
      [0]  ATM - step  — one strike DOWN (left column)
      [1]  ATM         — at-the-money    (middle column)
      [2]  ATM + step  — one strike UP   (right column)
    ATM is computed from CURRENT SPOT PRICE (not opening straddle).
    These charts are completely independent of the opening-straddle row.
    Returns (fig_down, fig_atm, fig_up) — any may be None on failure.
    """
    global _atm_triple_named_cache
    underlying = data.get('underlying', 'NIFTY')

    #~# Skip chart build if market is closed AND cache already has figures;
    #~# if cache is empty, proceed to build with last available historical data.
    if not _is_market_open():
        _cached_down = _atm_triple_named_cache.get('down')
        _cached_atm  = _atm_triple_named_cache.get('atm')
        _cached_up   = _atm_triple_named_cache.get('up')
        _has_cached  = any(v is not None for v in (_cached_down, _cached_atm, _cached_up))
        if _has_cached:
            if not getattr(_build_atm_triple_charts, '_offhours_logged', False):
                _dbg_console.print(
                    f"[yellow]\\[ATM-Triple] {_market_status_str()} — "
                    f"using cached charts (market closed)[/]")
                _build_atm_triple_charts._offhours_logged = True
            return (_cached_down, _cached_atm, _cached_up)
        #~# Cache empty — build once with last available data
        if not getattr(_build_atm_triple_charts, '_offhours_logged', False):
            _dbg_console.print(
                f"[yellow]\\[ATM-Triple] {_market_status_str()} — "
                f"cache empty, building charts with last available data[/]")
            _build_atm_triple_charts._offhours_logged = True
    else:
        _build_atm_triple_charts._offhours_logged = False

    #~# ATM strike based on CURRENT spot price — independent of opening straddle
    spot_price = float(data.get('spot_price', 0) or 0)
    if spot_price <= 0:
        try:
            from oc_data_fetcher import get_cached_spot_price
            spot_price = get_cached_spot_price(underlying)
        except Exception:
            pass
    if spot_price <= 0:
        return None, None, None

    step = _get_strike_step(underlying)
    atm_strike = int(round(spot_price / step) * step)

    #~# Day open price (for chart title display only, does NOT affect strike selection)
    try:
        from oc_data_fetcher import ensure_day_open_synced
        sync       = ensure_day_open_synced(underlying, spot_price=spot_price)
        open_price = float(sync.get('open_price', 0) or 0)
    except Exception:
        open_price = 0.0

    #~# Left = ATM - step (one strike DOWN), Middle = ATM, Right = ATM + step (one strike UP)
    fig_down = _build_strike_straddle_chart(
        atm_strike - step, open_price, underlying,
        0, f'\u2193 {atm_strike - step}  (-1 Strike)', '5')
    fig_atm  = _build_strike_straddle_chart(
        atm_strike, open_price, underlying,
        0, f'ATM  {atm_strike}', '5')
    fig_up   = _build_strike_straddle_chart(
        atm_strike + step, open_price, underlying,
        0, f'\u2191 {atm_strike + step}  (+1 Strike)', '5')
    #~# Store into named cache so placeholder getter can distinguish columns
    if fig_down is not None:
        _atm_triple_named_cache['down'] = fig_down
    if fig_atm is not None:
        _atm_triple_named_cache['atm'] = fig_atm
    if fig_up is not None:
        _atm_triple_named_cache['up'] = fig_up
    return fig_down, fig_atm, fig_up


#~# EMA candlestick chart cache — key = underlying
_ema_candle_fig_cache: dict = {}


def _build_ema_candlestick_chart(underlying: str = 'NIFTY'):
    """
    Build a 5-min candlestick chart for the underlying with:
      Row 1 (50%): Candlestick + EMA(5) of High (green) + EMA(5) of Low (red)
      Row 2 (25%): RSI(14) with OB/OS bands
      Row 3 (25%): MACD histogram + MACD line + Signal line
    Horizontal separators between each row.
    Timestamps are converted from UTC → IST (+5:30).
    """
    global _ema_candle_fig_cache
    now = _time.time()
    cached = _ema_candle_fig_cache.get(underlying, {})
    if cached.get('fig') is not None and (now - cached.get('ts', 0)) < 60:
        return cached['fig']

    try:
        df = _fetch_ohlcv_direct(underlying, 5)
        if df is None or df.empty:
            return cached.get('fig')

        #~# Timestamps already in IST from _fetch_ohlcv_direct
        df = df.copy()

        #~# Sort full multi-day df first for proper indicator warm-up
        df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp']).reset_index(drop=True)
        full_close = df['close'].astype(float)
        full_high  = df['high'].astype(float)
        full_low   = df['low'].astype(float)

        #~# Compute indicators on FULL multi-day data for proper EWM warm-up
        df['ema5_high'] = full_high.ewm(span=5, adjust=False).mean()
        df['ema5_low']  = full_low.ewm(span=5, adjust=False).mean()
        macd_full, signal_full, hist_full = _calc_macd(full_close)
        df['macd']      = macd_full.values
        df['signal']    = signal_full.values
        df['macd_hist'] = hist_full.values
        df['rsi']       = _calc_rsi(full_close, 14).values

        #~# 15-day lookback: check today → yesterday → day-2 → … → day-15
        _ema_date_series = df['timestamp'].dt.date.astype(str)
        found_date, days_back = _find_last_trading_day(
            _ema_date_series, f"EMA-Candle {underlying}")
        if found_date is None:
            return cached.get('fig')
        today_df = df[_ema_date_series == found_date].copy()
        if today_df.empty:
            return cached.get('fig')

        today_df = today_df.sort_values('timestamp')\
                           .drop_duplicates(subset=['timestamp'])\
                           .reset_index(drop=True)
        close_s = today_df['close'].astype(float)
        high_s  = today_df['high'].astype(float)
        low_s   = today_df['low'].astype(float)

        last_close  = float(close_s.iloc[-1])
        current_rsi = float(today_df['rsi'].dropna().iloc[-1]) if not today_df['rsi'].dropna().empty else 50.0
        rsi_color   = WHITE
        last_macd   = float(today_df['macd'].dropna().iloc[-1]) if not today_df['macd'].dropna().empty else 0.0
        last_sig    = float(today_df['signal'].dropna().iloc[-1]) if not today_df['signal'].dropna().empty else 0.0
        macd_clr    = PUT_BAR if last_macd > last_sig else CALL_BAR

        #~# Symmetric MACD y-axis: always show equal range above and below 0
        _macd_abs_max = max(
            today_df['macd'].abs().max() if not today_df['macd'].dropna().empty else 1,
            today_df['signal'].abs().max() if not today_df['signal'].dropna().empty else 1,
            today_df['macd_hist'].abs().max() if not today_df['macd_hist'].dropna().empty else 1,
        )
        _macd_pad   = _macd_abs_max * 1.25  # 25% headroom
        _macd_range = [-_macd_pad, _macd_pad]

        fig = make_subplots(
            rows=3, cols=1,
            row_heights=[0.50, 0.25, 0.25],
            shared_xaxes=True,
            vertical_spacing=0.04,
        )

        #~# Row 1: Candlestick — fixed 5-min bar width to prevent overlap
        _bar_width_ms = 5 * 60 * 1000 * 0.8  # 80% of 5 minutes in ms
        fig.add_trace(go.Candlestick(
            x=today_df['timestamp'],
            open=today_df['open'].astype(float),
            high=high_s,
            low=low_s,
            close=close_s,
            name='5-Min OHLC',
            increasing_line_color=PUT_BAR,
            decreasing_line_color=CALL_BAR,
            increasing_fillcolor=CANDLE_INCREASING_75,
            decreasing_fillcolor=CANDLE_DECREASING_75,
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=today_df['timestamp'], y=today_df['ema5_high'],
            name='EMA(5) High', mode='lines',
            line=dict(color=GREEN, width=2.0),
            hovertemplate='%{y:.2f}<extra>EMA(5) High</extra>',
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=today_df['timestamp'], y=today_df['ema5_low'],
            name='EMA(5) Low', mode='lines',
            line=dict(color=RED_BRIGHT, width=2.0),
            hovertemplate='%{y:.2f}<extra>EMA(5) Low</extra>',
        ), row=1, col=1)

        #~# Row 2: RSI
        fig.add_trace(go.Scatter(
            x=today_df['timestamp'], y=today_df['rsi'],
            name='RSI (14)', mode='lines',
            line=dict(color=WHITE, width=1.8),
            hovertemplate='%{y:.1f}<extra>RSI</extra>',
        ), row=2, col=1)
        fig.add_hline(y=70, line_dash='dot',
                      line_color=RSI_OVERBOUGHT_LINE, line_width=1.2, row=2, col=1)
        fig.add_hline(y=50, line_dash='dot',
                      line_color=RSI_NEUTRAL_LINE, line_width=1.0, row=2, col=1)
        fig.add_hline(y=30, line_dash='dot',
                      line_color=RSI_OVERSOLD_LINE, line_width=1.2, row=2, col=1)
        fig.add_hrect(y0=70, y1=100,
                      fillcolor=RSI_OVERBOUGHT_ZONE, line_width=0, row=2, col=1)
        fig.add_hrect(y0=0, y1=30,
                      fillcolor=RSI_OVERSOLD_ZONE, line_width=0, row=2, col=1)

        #~# Row 3: MACD histogram + lines
        hist_colors = [PUT_BAR if v >= 0 else CALL_BAR
                       for v in today_df['macd_hist'].fillna(0)]
        fig.add_trace(go.Bar(
            x=today_df['timestamp'], y=today_df['macd_hist'],
            name='MACD Hist', marker_color=hist_colors, opacity=0.75,
            hovertemplate='%{y:.2f}<extra>Hist</extra>',
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=today_df['timestamp'], y=today_df['macd'],
            name='MACD', mode='lines',
            line=dict(color=LIGHT_BLUE, width=1.6),
            hovertemplate='%{y:.2f}<extra>MACD</extra>',
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=today_df['timestamp'], y=today_df['signal'],
            name='Signal', mode='lines',
            line=dict(color=DEEP_ORANGE, width=1.6, dash='dot'),
            hovertemplate='%{y:.2f}<extra>Signal</extra>',
        ), row=3, col=1)
        fig.add_hline(y=0, line_dash='solid', line_color=GRAY_LINE_25,
                      line_width=1.0, row=3, col=1)

        #~# Badges
        fig.add_annotation(
            xref='paper', yref='paper', x=0.99, y=0.205,
            text=f'  RSI  {current_rsi:.1f}  ',
            showarrow=False, xanchor='right',
            font=dict(color=rsi_color, size=11, family='Inter, monospace'),
            bgcolor=ANNOTATION_BG_TERTIARY, bordercolor=rsi_color,
            borderwidth=1, borderpad=4,
        )
        fig.add_annotation(
            xref='paper', yref='paper', x=0.99, y=0.01,
            text=f'  MACD {last_macd:.2f} / Sig {last_sig:.2f}  ',
            showarrow=False, xanchor='right',
            font=dict(color=macd_clr, size=11, family='Inter, monospace'),
            bgcolor=ANNOTATION_BG_TERTIARY, bordercolor=macd_clr,
            borderwidth=1, borderpad=4,
        )

        fig.update_layout(
            title=dict(
                text=(f'\U0001f56f {underlying}  5-Min Candlestick'
                      f'  \u2502  EMA(5) High & EMA(5) Low'
                      f'  \u2502  RSI  \u2502  MACD'
                      f'  \u2502  Close \u20b9{last_close:,.2f}'),
                font=dict(size=14, color=GOLD, family='Inter, sans-serif'),
                x=0.01, pad=dict(t=4),
            ),
            paper_bgcolor=PANEL_BG, plot_bgcolor=PANEL_BG,
            font=dict(color=TEXT_LIGHT, family='Inter, sans-serif', size=11),
            height=850, margin=dict(l=65, r=40, t=55, b=30),
            hovermode='x unified',
            legend=dict(
                bgcolor=LEGEND_BG, bordercolor=BORDER_COLOR, borderwidth=1,
                font=dict(size=11), orientation='h',
                yanchor='bottom', y=1.03, xanchor='right', x=1,
            ),
        )
        _ax2 = dict(gridcolor=GRID_COLOR, showgrid=True, tickfont=dict(size=10),
                    showspikes=True, spikecolor=SPIKE_COLOR,
                    spikethickness=1, spikedash='solid', spikesnap='cursor', spikemode='across')
        #~# If equity market is closed, clamp x-axis to 09:15–15:30 so chart doesn't show empty space
        _ema_xrange = None
        if not _is_market_open() and not today_df.empty:
            _ema_day_str = found_date  # e.g. '2026-03-04'
            _ema_xrange = [f'{_ema_day_str} 09:00', f'{_ema_day_str} 15:40']
        fig.update_xaxes(**_ax2, tickformat='%H:%M', rangeslider_visible=False, zeroline=False, range=_ema_xrange, row=1, col=1)
        fig.update_xaxes(**_ax2, tickformat='%H:%M', zeroline=False, range=_ema_xrange, row=2, col=1)
        fig.update_xaxes(**_ax2, tickformat='%H:%M', zeroline=False, range=_ema_xrange, row=3, col=1)
        fig.update_yaxes(**_ax2, tickformat='.2f', zeroline=False,
                         title_text=f'{underlying} (\u20b9)',
                         title_font=dict(size=11), row=1, col=1)
        fig.update_yaxes(**_ax2, title_text='RSI', title_font=dict(size=11),
                         zeroline=False, range=[0, 100], dtick=20, row=2, col=1)
        fig.update_yaxes(**_ax2, tickformat='.2f',
                         title_text='MACD', title_font=dict(size=11),
                         range=_macd_range,
                         zeroline=True, zerolinecolor=GRAY_LINE_35,
                         zerolinewidth=1.2, row=3, col=1)

        #~# Horizontal separators between Chart/RSI and RSI/MACD
        for sep_y in (0.52, 0.25):
            fig.add_shape(
                type='line', xref='paper', yref='paper',
                x0=0, x1=1, y0=sep_y, y1=sep_y,
                line=dict(color=BORDER_COLOR, width=1.2),
            )

        _ema_candle_fig_cache[underlying] = {'fig': fig, 'ts': now}
        return fig

    except Exception as e:
        print(f"[WARN] EMA candlestick chart ({underlying}) error: {e}")
        import traceback; traceback.print_exc()
        return cached.get('fig')


#~# Cache for OI + Candlestick combined panel — key = underlying
_oi_candle_fig_cache: dict = {}


def _build_oi_candlestick_panel(data: dict, underlying: str = 'NIFTY'):
    """
    Combined panel: 5-min Candlestick + EMA(5) High/Low Band + Vertical OI Distribution + Change.

    Layout (Plotly make_subplots 1×2, shared y-axis = price/strike levels):
      Col 1 (75%): 5-min Candlestick + EMA(5) High (green) + EMA(5) Low (red)
      Col 2 (25%): Horizontal butterfly OI bars — Put (green ←) | Call (red →)
                   Brighter bars = OI increasing, Dimmer = OI decreasing
    """
    global _oi_candle_fig_cache
    now = _time.time()
    cached = _oi_candle_fig_cache.get(underlying, {})
    if cached.get('fig') is not None and (now - cached.get('ts', 0)) < 60:
        return cached['fig']

    try:
        # ── Fetch 5-min OHLCV ──
        df = _fetch_ohlcv_direct(underlying, 5)
        if df is None or df.empty:
            return cached.get('fig')

        #~# Timestamps already in IST from _fetch_ohlcv_direct
        df = df.copy()
        df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp']).reset_index(drop=True)

        # EMA(5) on full multi-day data for proper warm-up
        full_high = df['high'].astype(float)
        full_low = df['low'].astype(float)
        df['ema5_high'] = full_high.ewm(span=5, adjust=False).mean()
        df['ema5_low'] = full_low.ewm(span=5, adjust=False).mean()

        # Filter to latest trading day
        _date_series = df['timestamp'].dt.date.astype(str)
        found_date, _ = _find_last_trading_day(_date_series, f"OI-Candle {underlying}")
        if found_date is None:
            return cached.get('fig')
        today_df = df[_date_series == found_date].copy()
        if today_df.empty:
            return cached.get('fig')
        today_df = today_df.sort_values('timestamp').drop_duplicates(subset=['timestamp']).reset_index(drop=True)

        # ── Prepare OI data ──
        option_df = data.get('option_df', pd.DataFrame())
        atm = data.get('atm_strike', 0)
        atm_int = int(atm) if atm else 0
        spot = data.get('spot_price', 0)

        strikes = []
        call_oi = []
        put_oi = []
        call_chg = []
        put_chg = []

        if not option_df.empty:
            for _, row in option_df.iterrows():
                try:
                    s = int(float(row.get('Strike', 0)))
                except (ValueError, TypeError):
                    continue
                c_curr = float(row.get('C_OI', 0) or 0)
                p_curr = float(row.get('P_OI', 0) or 0)
                c_chg_val = float(row.get('C_OI_Chg', 0) or 0)
                p_chg_val = float(row.get('P_OI_Chg', 0) or 0)
                strikes.append(s)
                call_oi.append(c_curr)
                put_oi.append(p_curr)
                call_chg.append(c_chg_val)
                put_chg.append(p_chg_val)

        # ── Build figure (1 row × 2 cols, shared y-axis) ──
        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.70, 0.30],
            shared_yaxes=True,
            horizontal_spacing=0.04,
        )

        # ── Col 1: Candlestick + EMA(5) High/Low band ──
        fig.add_trace(go.Candlestick(
            x=today_df['timestamp'],
            open=today_df['open'].astype(float),
            high=today_df['high'].astype(float),
            low=today_df['low'].astype(float),
            close=today_df['close'].astype(float),
            name='5-Min',
            increasing_line_color=PUT_BAR,
            decreasing_line_color=CALL_BAR,
            increasing_fillcolor=CANDLE_INCREASING_80,
            decreasing_fillcolor=CANDLE_DECREASING_80,
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=today_df['timestamp'], y=today_df['ema5_high'],
            name='EMA(5) High', mode='lines',
            line=dict(color=GREEN, width=1.8),
            hovertemplate='%{y:.2f}<extra>EMA5 Hi</extra>',
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=today_df['timestamp'], y=today_df['ema5_low'],
            name='EMA(5) Low', mode='lines',
            line=dict(color=RED_BRIGHT, width=1.8),
            hovertemplate='%{y:.2f}<extra>EMA5 Lo</extra>',
        ), row=1, col=1)

        #~# Shade the band between EMA(5) High and EMA(5) Low
        fig.add_trace(go.Scatter(
            x=pd.concat([today_df['timestamp'], today_df['timestamp'][::-1]]),
            y=pd.concat([today_df['ema5_high'], today_df['ema5_low'][::-1]]),
            fill='toself',
            fillcolor=BAND_FILL_BLUE,
            line=dict(width=0),
            name='EMA Band',
            showlegend=False,
            hoverinfo='skip',
        ), row=1, col=1)

        # ── Col 2: OI Distribution + Change (stacked segments like HTML panel) ──
        #~# For each strike, each side (Put/Call) has:
        #~#   INCREASE: solid base (prev OI) + hatched-stripe top (added OI)
        #~#   DECREASE: solid base (remaining OI) + hollow-border top (removed OI)
        #~#   NO CHANGE / NO PREV: just solid base (current OI)
        if strikes:
            #~# Pre-compute H1/H2/H3 rank for top-3 OI
            c_sorted_r = sorted(enumerate(call_oi), key=lambda x: x[1], reverse=True)[:3]
            p_sorted_r = sorted(enumerate(put_oi), key=lambda x: x[1], reverse=True)[:3]
            c_rank = {i: r + 1 for r, (i, v) in enumerate(c_sorted_r) if v > 0}
            p_rank = {i: r + 1 for r, (i, v) in enumerate(p_sorted_r) if v > 0}

            #~# Exact match with color_constants.py OI_RANK_PUT / OI_RANK_CALL & CSS styles.css
            _RANK_PUT_CLR  = {1: RANK_PUT_1,  2: RANK_PUT_2,  3: RANK_PUT_3}
            _RANK_CALL_CLR = {1: RANK_CALL_1, 2: RANK_CALL_2, 3: RANK_CALL_3}

            #~# Decompose each bar into base + change segments
            put_base = []     # solid: prev OI (increase) or current OI (decrease/nochange)
            put_inc = []      # stripe segment: added OI (positive change)
            put_dec = []      # hollow segment: removed OI (negative change)
            call_base = []
            call_inc = []
            call_dec = []

            for i in range(len(strikes)):
                p_curr = put_oi[i]
                p_chg_v = put_chg[i]
                c_curr = call_oi[i]
                c_chg_v = call_chg[i]

                # prev OI = current - intraday change
                p_prev = max(0, p_curr - p_chg_v)
                c_prev = max(0, c_curr - c_chg_v)

                # Put side — match HTML panel logic: only show stripe/hollow when prev > 0
                if p_chg_v > 0 and p_prev > 0:  # increase with valid prev
                    put_base.append(p_prev)
                    put_inc.append(p_chg_v)
                    put_dec.append(0)
                elif p_chg_v < 0 and p_prev > 0:  # decrease with valid prev
                    put_base.append(p_curr)
                    put_inc.append(0)
                    put_dec.append(abs(p_chg_v))
                else:  # no change, or no valid prev data
                    put_base.append(p_curr)
                    put_inc.append(0)
                    put_dec.append(0)

                # Call side — same logic
                if c_chg_v > 0 and c_prev > 0:
                    call_base.append(c_prev)
                    call_inc.append(c_chg_v)
                    call_dec.append(0)
                elif c_chg_v < 0 and c_prev > 0:
                    call_base.append(c_curr)
                    call_inc.append(0)
                    call_dec.append(abs(c_chg_v))
                else:
                    call_base.append(c_curr)
                    call_inc.append(0)
                    call_dec.append(0)

            #~# Color arrays for base bars (rank-aware) — exact match with CSS .bar-put--fill / .bar-call--fill
            _DEFAULT_PUT  = DEFAULT_PUT_RGBA    # #26a69a — matches var(--put-bar) in styles.css
            _DEFAULT_CALL = DEFAULT_CALL_RGBA   # #ef5350 — matches var(--call-bar) in styles.css
            put_base_colors = []
            call_base_colors = []
            for i in range(len(strikes)):
                pr = p_rank.get(i, 0)
                cr = c_rank.get(i, 0)
                put_base_colors.append(_RANK_PUT_CLR.get(pr, _DEFAULT_PUT))
                call_base_colors.append(_RANK_CALL_CLR.get(cr, _DEFAULT_CALL))

            #~# Increase segment colors (rank-aware) — same color as base; stripe pattern applied via marker_pattern
            put_inc_colors = []
            call_inc_colors = []
            for i in range(len(strikes)):
                pr = p_rank.get(i, 0)
                cr = c_rank.get(i, 0)
                put_inc_colors.append(_RANK_PUT_CLR.get(pr, _DEFAULT_PUT) if pr else _DEFAULT_PUT)
                call_inc_colors.append(_RANK_CALL_CLR.get(cr, _DEFAULT_CALL) if cr else _DEFAULT_CALL)

            #~# Both Put and Call go the SAME direction, grouped per strike
            #~# barmode='stack' + offsetgroup: traces in same group stack; different groups side-by-side
            #~# Stack order: Base → Increase → Decrease (only one of inc/dec is non-zero per strike)

            #~# Conditional border widths: only show border when there's an actual decrease
            #~# Decrease (hollow) border colors — exact match with CSS .bar-put--hollow / .bar-call--hollow
            put_dec_lw = [0.5 if v > 0 else 0 for v in put_dec]
            call_dec_lw = [0.5 if v > 0 else 0 for v in call_dec]
            put_dec_lc = [_DEFAULT_PUT if v > 0 else TRANSPARENT for v in put_dec]
            call_dec_lc = [_DEFAULT_CALL if v > 0 else TRANSPARENT for v in call_dec]

            # ─── PUT BASE (solid) ───
            fig.add_trace(go.Bar(
                y=strikes,
                x=put_base,
                orientation='h',
                name='Put Base',
                marker_color=put_base_colors,
                marker_line_width=0,
                hovertemplate='Strike %{y:,}<br>Put OI: %{customdata[0]:,.0f}'
                              '<br>Chg: %{customdata[1]:+,.0f}<extra></extra>',
                customdata=list(zip(put_oi, put_chg)),
                legendgroup='put', showlegend=True,
                offsetgroup='put',
            ), row=1, col=2)

            # ─── PUT INCREASE (hatched stripe, stacks after base) ───
            #~# Swap: fgcolor=bar color (visible stripes), bgcolor=#0e1117 (dark gaps)
            #~# This avoids Plotly SVG white-artifact when bgcolor is a per-bar array
            fig.add_trace(go.Bar(
                y=strikes,
                x=put_inc,
                orientation='h',
                name='Put ↑ Inc',
                marker=dict(
                    color=TRANSPARENT,
                    line_width=0,
                    pattern=dict(
                        shape='/',
                        fgcolor=put_inc_colors,
                        bgcolor=[PANEL_BG] * len(strikes),
                        solidity=0.6,
                    ),
                ),
                hovertemplate='Strike %{y:,}<br>Put Increase: %{customdata:,.0f}<extra></extra>',
                customdata=put_inc,
                legendgroup='put', showlegend=True,
                offsetgroup='put',
            ), row=1, col=2)

            # ─── PUT DECREASE (hollow border only, stacks after base) ───
            fig.add_trace(go.Bar(
                y=strikes,
                x=put_dec,
                orientation='h',
                name='Put ↓ Dec',
                marker_color=[TRANSPARENT] * len(strikes),
                marker_line_color=put_dec_lc,
                marker_line_width=put_dec_lw,
                hovertemplate='Strike %{y:,}<br>Put Decrease: %{customdata:,.0f}<extra></extra>',
                customdata=put_dec,
                legendgroup='put', showlegend=True,
                offsetgroup='put',
            ), row=1, col=2)

            # ─── CALL BASE (solid, same side) ───
            fig.add_trace(go.Bar(
                y=strikes,
                x=call_base,
                orientation='h',
                name='Call Base',
                marker_color=call_base_colors,
                marker_line_width=0,
                hovertemplate='Strike %{y:,}<br>Call OI: %{customdata[0]:,.0f}'
                              '<br>Chg: %{customdata[1]:+,.0f}<extra></extra>',
                customdata=list(zip(call_oi, call_chg)),
                legendgroup='call', showlegend=True,
                offsetgroup='call',
            ), row=1, col=2)

            # ─── CALL INCREASE (hatched stripe, stacks after base) ───
            #~# Swap: fgcolor=bar color (visible stripes), bgcolor=#0e1117 (dark gaps)
            fig.add_trace(go.Bar(
                y=strikes,
                x=call_inc,
                orientation='h',
                name='Call ↑ Inc',
                marker=dict(
                    color=TRANSPARENT,
                    line_width=0,
                    pattern=dict(
                        shape='/',
                        fgcolor=call_inc_colors,
                        bgcolor=[PANEL_BG] * len(strikes),
                        solidity=0.6,
                    ),
                ),
                hovertemplate='Strike %{y:,}<br>Call Increase: %{customdata:,.0f}<extra></extra>',
                customdata=call_inc,
                legendgroup='call', showlegend=True,
                offsetgroup='call',
            ), row=1, col=2)

            # ─── CALL DECREASE (hollow border only, stacks after base) ───
            fig.add_trace(go.Bar(
                y=strikes,
                x=call_dec,
                orientation='h',
                name='Call ↓ Dec',
                marker_color=[TRANSPARENT] * len(strikes),
                marker_line_color=call_dec_lc,
                marker_line_width=call_dec_lw,
                hovertemplate='Strike %{y:,}<br>Call Decrease: %{customdata:,.0f}<extra></extra>',
                customdata=call_dec,
                legendgroup='call', showlegend=True,
                offsetgroup='call',
            ), row=1, col=2)

        #~# ATM horizontal dotted line (no label — line only)
        if atm_int:
            fig.add_hline(
                y=float(atm_int), line_dash='dot',
                line_color=GOLD_LINE_60, line_width=1.5,
            )
        #~# Spot price line (line only)
        if spot and spot > 0:
            fig.add_hline(
                y=float(spot), line_dash='dot',
                line_color=BLUE_LINE_50, line_width=1,
            )

        #~# Spot annotation only — ATM has dotted line only (no label)
        if spot and spot > 0:
            fig.add_annotation(
                text=f'Spot {spot:,.0f}',
                font=dict(color=BLUE, size=9),
                xref='paper', x=0.74, xanchor='left',
                yref='y', y=float(spot),
                yanchor='middle',
                bgcolor=ANNOTATION_BG_TERTIARY,
                bordercolor=BLUE_LINE_40,
                borderwidth=1,
                showarrow=False,
            )

        # ── Layout ──
        last_close = float(today_df['close'].iloc[-1])
        ema_hi = float(today_df['ema5_high'].iloc[-1])
        ema_lo = float(today_df['ema5_low'].iloc[-1])
        band_pos = 'ABOVE' if last_close > ema_hi else ('BELOW' if last_close < ema_lo else 'IN BAND')
        band_clr = GREEN if band_pos == 'ABOVE' else (RED_BRIGHT if band_pos == 'BELOW' else GOLD)

        fig.update_layout(
            title=dict(
                text=(f'\U0001f56f {underlying} 5-Min + EMA(5) High/Low Band'
                      f'  \u2502  OI Distribution + Change'
                      f'  \u2502  \u20b9{last_close:,.2f}'
                      f'  \u2502  <span style="color:{band_clr}">{band_pos}</span>'),
                font=dict(size=14, color=GOLD, family='Inter, sans-serif'),
                x=0.01, pad=dict(t=4),
            ),
            paper_bgcolor=PANEL_BG, plot_bgcolor=PANEL_BG,
            font=dict(color=TEXT_LIGHT, family='Inter, sans-serif', size=11),
            height=1800,
            margin=dict(l=65, r=40, t=55, b=50),
            hovermode='x unified',
            barmode='stack',
            bargap=0.08,
            bargroupgap=0.0,
            legend=dict(
                bgcolor=LEGEND_BG, bordercolor=BORDER_COLOR, borderwidth=1,
                font=dict(size=10), orientation='h',
                yanchor='bottom', y=1.03, xanchor='right', x=1,
            ),
        )

        _ax = dict(gridcolor=GRID_COLOR, showgrid=True, tickfont=dict(size=10))
        #~# Spike settings for the time (candlestick) axis only — white + transparent
        _spike_ax = dict(**_ax, showspikes=True, spikecolor=SPIKE_COLOR,
                         spikethickness=1, spikedash='solid', spikesnap='cursor', spikemode='across')
        #~# Always clamp x-axis to trading window with buffer so edge candles aren't clipped
        _day_str = found_date  # e.g. '2026-03-04'
        _candle_xrange = [f'{_day_str} 09:00', f'{_day_str} 15:40']
        fig.update_xaxes(**_spike_ax, tickformat='%H:%M', rangeslider_visible=False,
                         zeroline=False, range=_candle_xrange, row=1, col=1)
        fig.update_xaxes(**_ax, zeroline=False, showticklabels=True,
                         showspikes=False,
                         title_text='\u2190 Put OI (green) + Call OI (red)',
                         title_font=dict(size=10, color=MUTED_LIGHT),
                         tickformat='~s', autorange='reversed', row=1, col=2)
        fig.update_yaxes(**_ax, tickformat=',.0f', zeroline=False,
                         dtick=50,
                         title_text=f'{underlying} (\u20b9)',
                         title_font=dict(size=11), row=1, col=1)

        #~# Badge: EMA band status
        fig.add_annotation(
            xref='paper', yref='paper', x=0.01, y=0.98,
            text=f'  EMA(5) Band: {band_pos}  |  Hi {ema_hi:,.2f}  Lo {ema_lo:,.2f}  ',
            showarrow=False, xanchor='left',
            font=dict(color=band_clr, size=11, family='Inter, monospace'),
            bgcolor=ANNOTATION_BG_TERTIARY, bordercolor=band_clr,
            borderwidth=1, borderpad=4,
        )
        #~# Subtitle: explain bar segments
        fig.add_annotation(
            xref='paper', yref='paper', x=0.73, y=-0.06,
            text='Solid = Day-start OI · Stripe = Increase · Hollow = Decrease',
            showarrow=False, xanchor='center',
            font=dict(color=MUTED_LIGHT, size=10, family='Inter, sans-serif'),
        )

        _oi_candle_fig_cache[underlying] = {'fig': fig, 'ts': now}
        return fig

    except Exception as e:
        print(f"[WARN] OI+Candle panel ({underlying}) error: {e}")
        import traceback; traceback.print_exc()
        return cached.get('fig')


#~# Dedicated background executor for the new ATM triple + EMA charts
_atm_row_executor = ThreadPoolExecutor(max_workers=2)
_atm_triple_build_in_progress = False


def _build_atm_triple_background(data: dict):
    """Build ATM triple straddle row charts + EMA candlestick + OI+Candle panel in a background thread."""
    global _atm_triple_build_in_progress
    if _atm_triple_build_in_progress:
        return
    _atm_triple_build_in_progress = True
    try:
        _build_atm_triple_charts(data)
        _build_ema_candlestick_chart(data.get('underlying', 'NIFTY'))
        _build_oi_candlestick_panel(data, data.get('underlying', 'NIFTY'))
    except Exception as e:
        print(f"[WARN] ATM triple background build error: {e}")
    finally:
        _atm_triple_build_in_progress = False


def _get_cached_or_placeholder_atm_row(underlying: str = 'NIFTY'):
    """Return cached ATM triple row + EMA candlestick + OI candle panel figures, or loading placeholders."""
    #~# Use named cache so each column gets its own correct figure
    fig_left   = _atm_triple_named_cache.get('down') or _chart_loading_placeholder('\u2193 -1 Strike')
    fig_mid    = _atm_triple_named_cache.get('atm')  or _chart_loading_placeholder('ATM Strike')
    fig_right  = _atm_triple_named_cache.get('up')   or _chart_loading_placeholder('\u2191 +1 Strike')
    #~# EMA candlestick
    ema_cached = _ema_candle_fig_cache.get(underlying, {}).get('fig')
    ema_fig    = ema_cached if ema_cached is not None else _chart_loading_placeholder('EMA Candle')
    #~# OI + Candlestick combined panel
    oi_candle_cached = _oi_candle_fig_cache.get(underlying, {}).get('fig')
    oi_candle_fig = oi_candle_cached if oi_candle_cached is not None else _chart_loading_placeholder('OI + Candle')
    return fig_left, fig_mid, fig_right, ema_fig, oi_candle_fig


# ═══════════════════════════════════════════════════════════════════════════
#^# DATA REFRESH
# ═══════════════════════════════════════════════════════════════════════════

#~# Cached data to reduce refreshes
_cached_full_data = {}
_cached_underlying = None


def refresh_data(underlying, expiry_idx, num_strikes):
    """* Full refresh - fetches all data including option chain"""
    global _cached_full_data, _cached_underlying, _last_valid_oc_html
    try:
        underlying = str(underlying)
        data = fetch_all_data(underlying, int(expiry_idx), int(num_strikes))
        if data['error']:
            err = _render('error', message=data['error'])
            _oc_hist = _get_oc_history_htmls()
            _oi_dist_hist = _get_oi_dist_history_htmls()
            return (err, "", "", _last_valid_oi_charts, *_oi_dist_hist, _get_oi_dist_ts_html(), _last_valid_oc_html, *_oc_hist, _get_oc_ts_html(), "", None, None, None, None, "", None, None, None, None, None)
        _cached_underlying = underlying

        header_html = _header(data)
        #~# Clear flag so cached data won't re-trigger OI history on fast refreshes
        data['_update_oi'] = False
        _cached_full_data['_update_oi'] = False

        #~# Charts: return cached/placeholder immediately, build in background
        s_fig0_15, s_fig1_15, s_fig0_5, s_fig1_5 = _get_cached_or_placeholder_charts()
        _chart_executor.submit(_build_charts_background, data)
        #~# New ATM triple row + EMA candlestick + OI candle — build in background, return cached/placeholder
        atm_up_ph, atm_atm_ph, atm_down_ph, ema_ph, oi_candle_ph = _get_cached_or_placeholder_atm_row(underlying)
        _atm_row_executor.submit(_build_atm_triple_background, data)
        tf_table = _build_tf_indicators_table(underlying, spot_price=data.get('spot_price', 0))
        _oc_live = _oc_table(data['option_df'], data['atm_strike'])
        _analytics_live = _analytics(data['metrics'], data)
        _oc_combined = _oc_live + _analytics_live
        _last_valid_oc_html = _oc_combined
        _push_oc_snapshot(_oc_combined, df=data['option_df'])
        _oc_hist = _get_oc_history_htmls()
        _oi_charts_live = _oi_charts(data)
        _push_oi_dist_snapshot(_oi_charts_live, df=data.get('option_df'))
        _oi_dist_hist = _get_oi_dist_history_htmls()
        return (
            header_html,
            _oi_history_panel(data),
            "",  #~# tech_analysis slot (removed, kept for output parity)
            _oi_charts_live,
            *_oi_dist_hist,
            _get_oi_dist_ts_html(),
            _oc_combined,
            *_oc_hist,
            _get_oc_ts_html(),
            _futures(data.get('futures_buildup', []), underlying),
            s_fig0_15,
            s_fig1_15,
            s_fig0_5,
            s_fig1_5,
            tf_table,
            atm_up_ph,
            atm_atm_ph,
            atm_down_ph,
            ema_ph,
            oi_candle_ph,
        )
    except Exception as e:
        err = _render('error', message=str(e))
        _oc_hist = _get_oc_history_htmls()
        _oi_dist_hist = _get_oi_dist_history_htmls()
        return (err, "", "", _last_valid_oi_charts, *_oi_dist_hist, _get_oi_dist_ts_html(), _last_valid_oc_html, *_oc_hist, _get_oc_ts_html(), "", None, None, None, None, "", None, None, None, None, None)


_refresh_counter = 0  # track refresh cycles

# ═══════════════════════════════════════════════════════════════════════════
#^# OC HISTORY — last HISTORY_TAB_COUNT option chain HTML snapshots for UI tabs
# ═══════════════════════════════════════════════════════════════════════════
from collections import deque as _deque
_oc_html_history: _deque[str] = _deque(maxlen=HISTORY_TAB_COUNT)  # newest first
_last_valid_oc_html: str = ''  # fallback: last successful OC table HTML
_OC_EMPTY = _render('oc_empty')

_oc_ts_history: _deque[str] = _deque(maxlen=HISTORY_TAB_COUNT)  # timestamps parallel to _oc_html_history
_oc_last_data_hash: str = ''  # fingerprint of last pushed DataFrame content

def _push_oc_snapshot(html: str, df=None):
    """Push current OC table HTML into history only if data actually changed."""
    import datetime as _dt_snap
    import hashlib as _hl
    global _oc_last_data_hash
    # Use DataFrame fingerprint for robust dedup (immune to CSS / formatting noise)
    if df is not None and not df.empty:
        # Round floats to remove micro-noise (e.g. LTP 100.12345 vs 100.12346)
        _key_cols = [c for c in ('Strike', 'C_OI', 'P_OI', 'C_LTP', 'P_LTP',
                                  'C_IV', 'P_IV', 'C_BuildUp', 'P_BuildUp',
                                  'C_OI_Chg_Pct', 'P_OI_Chg_Pct',
                                  'C_LTP_Chg_Pct', 'P_LTP_Chg_Pct') if c in df.columns]
        _snap = df[_key_cols].copy()
        for col in _snap.select_dtypes(include='number').columns:
            _snap[col] = _snap[col].round(2)
        data_hash = _hl.md5(_snap.to_csv(index=False).encode()).hexdigest()
        if data_hash == _oc_last_data_hash:
            return  # same underlying data — skip
        _oc_last_data_hash = data_hash
    else:
        # fallback: compare raw HTML
        if _oc_html_history and _oc_html_history[0] == html:
            return
    _oc_html_history.appendleft(html)
    _oc_ts_history.appendleft(_dt_snap.datetime.now().strftime("%H:%M:%S"))

def _get_oc_history_htmls() -> list[str]:
    """Return HISTORY_TAB_COUNT HTML strings for history tabs (pad with empty if not yet filled)."""
    result = list(_oc_html_history)
    while len(result) < HISTORY_TAB_COUNT:
        result.append(_OC_EMPTY)
    return result[:HISTORY_TAB_COUNT]

def _get_oc_ts_html() -> str:
    """Return a hidden div carrying tab timestamps as a JSON data attribute."""
    import json as _json
    ts_list = list(_oc_ts_history)
    while len(ts_list) < HISTORY_TAB_COUNT:
        ts_list.append('')
    escaped = _json.dumps(ts_list[:HISTORY_TAB_COUNT])
    return _render('oc_ts_data', ts_json=escaped)


# ═══════════════════════════════════════════════════════════════════════════
#^# OI DISTRIBUTION HISTORY — last HISTORY_TAB_COUNT snapshots for UI tabs
# ═══════════════════════════════════════════════════════════════════════════
_oi_dist_html_history: _deque[str] = _deque(maxlen=HISTORY_TAB_COUNT)
_oi_dist_ts_history: _deque[str] = _deque(maxlen=HISTORY_TAB_COUNT)
_oi_dist_last_hash: str = ''
_OI_DIST_EMPTY = '<div class="oc-empty">No OI snapshot yet — collecting history...</div>'


def _push_oi_dist_snapshot(html: str, df=None):
    """Push current OI Distribution HTML into history only if data actually changed."""
    import datetime as _dt_snap
    import hashlib as _hl
    global _oi_dist_last_hash
    if not html or not html.strip():
        return
    if df is not None and not df.empty:
        _key_cols = [c for c in ('Strike', 'C_OI', 'P_OI', 'C_OI_Chg', 'P_OI_Chg') if c in df.columns]
        if _key_cols:
            _snap = df[_key_cols].copy()
            for col in _snap.select_dtypes(include='number').columns:
                _snap[col] = _snap[col].round(0)
            data_hash = _hl.md5(_snap.to_csv(index=False).encode()).hexdigest()
            if data_hash == _oi_dist_last_hash:
                return
            _oi_dist_last_hash = data_hash
    else:
        if _oi_dist_html_history and _oi_dist_html_history[0] == html:
            return
    _oi_dist_html_history.appendleft(html)
    _oi_dist_ts_history.appendleft(_dt_snap.datetime.now().strftime("%H:%M:%S"))


def _get_oi_dist_history_htmls() -> list[str]:
    """Return HISTORY_TAB_COUNT HTML strings for OI dist history tabs."""
    result = list(_oi_dist_html_history)
    while len(result) < HISTORY_TAB_COUNT:
        result.append(_OI_DIST_EMPTY)
    return result[:HISTORY_TAB_COUNT]


def _get_oi_dist_ts_html() -> str:
    """Return a hidden div carrying OI dist tab timestamps as a JSON data attribute."""
    import json as _json
    ts_list = list(_oi_dist_ts_history)
    while len(ts_list) < HISTORY_TAB_COUNT:
        ts_list.append('')
    escaped = _json.dumps(ts_list[:HISTORY_TAB_COUNT])
    return f'<div id="oi-dist-ts-data" class="oc-hidden" data-ts=\'{escaped}\'></div>'


def smart_refresh(underlying, expiry_idx, num_strikes):
    """!
    Priority-based refresh:
      P1 – Option chain (full fetch_all_data)
      P2 – Spot price
      P3 – VIX, Futures (batch LTP between full refreshes)

    Every call does a FULL refresh so option chain always updates.
    Rich console logging tracks timing and errors.
    """
    global _cached_full_data, _cached_underlying, _refresh_counter, _last_valid_oc_html
    import time as _time

    _refresh_counter += 1
    cycle = _refresh_counter
    t0 = _time.time()

    try:
        underlying = str(underlying)

        #^# P1: Full option chain refresh (always)
        try:
            t_oc = _time.time()
            data = fetch_all_data(underlying, int(expiry_idx), int(num_strikes))
            dt_oc = _time.time() - t_oc

            if data['error']:
                _tui.log_error(f"#{cycle} Option chain error: {data['error']}")
                err = _render('error', message=data['error'])
                _oc_hist = _get_oc_history_htmls()
                _oi_dist_hist = _get_oi_dist_history_htmls()
                return (err, "", "", _last_valid_oi_charts, *_oi_dist_hist, _get_oi_dist_ts_html(), _last_valid_oc_html, *_oc_hist, _get_oc_ts_html(), "", None, None, None, None, "", None, None, None, None, None)

            data['_update_oi'] = True
            _cached_full_data = data
            _cached_underlying = underlying

        except Exception as oc_err:
            _tui.log_error(f"#{cycle} OC fetch exception: {oc_err}")
            if _cached_full_data:
                data = _cached_full_data
                dt_oc = 0.0
            else:
                raise

        #^# P2/P3: Spot + VIX + Futures already batched inside fetch_all_data
        #~# No duplicate API call needed — just read what fetch_all_data set.
        dt_ltp = 0.0
        spot_ok = data.get('spot_price', 0) > 0
        vix_ok  = data.get('vix_current', 0) > 0
        fut_ok  = data.get('fut_price', 0) > 0

        #^# Update timestamp
        import datetime
        data['update_time'] = datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")
        _cached_full_data = data
        data['_update_oi'] = True

        header_html = _header(data)
        data['_update_oi'] = False
        _cached_full_data['_update_oi'] = False

        #^# TUI Dashboard — enhanced terminal display
        dt_total = _time.time() - t0
        mkt_open = _is_market_open()
        mkt_status = _market_status_str()
        _odf = data.get('option_df')
        _tui.update(
            cycle=cycle,
            dt_oc=dt_oc,
            dt_total=dt_total,
            data=data,
            market_open=mkt_open,
            market_status=mkt_status,
            option_df=_odf,
        )

        #~# Charts: return cached/placeholder immediately, build in background
        s_fig0_15, s_fig1_15, s_fig0_5, s_fig1_5 = _get_cached_or_placeholder_charts()
        _chart_executor.submit(_build_charts_background, data)
        #~# New ATM triple row + EMA candlestick + OI candle — build in background, return cached/placeholder
        atm_up_ph, atm_atm_ph, atm_down_ph, ema_ph, oi_candle_ph = _get_cached_or_placeholder_atm_row(underlying)
        _atm_row_executor.submit(_build_atm_triple_background, data)
        tf_table = _build_tf_indicators_table(underlying, spot_price=data.get('spot_price', 0))
        _oc_live = _oc_table(data['option_df'], data['atm_strike'])
        _analytics_live = _analytics(data['metrics'], data)
        _oc_combined = _oc_live + _analytics_live
        _last_valid_oc_html = _oc_combined
        _push_oc_snapshot(_oc_combined, df=data['option_df'])
        _oc_hist = _get_oc_history_htmls()
        _oi_charts_live = _oi_charts(data)
        _push_oi_dist_snapshot(_oi_charts_live, df=data.get('option_df'))
        _oi_dist_hist = _get_oi_dist_history_htmls()
        return (
            header_html,
            _oi_history_panel(data),
            "",  #~# tech_analysis slot (removed, kept for output parity)
            _oi_charts_live,
            *_oi_dist_hist,
            _get_oi_dist_ts_html(),
            _oc_combined,
            *_oc_hist,
            _get_oc_ts_html(),
            _futures(data.get('futures_buildup', []), underlying),
            s_fig0_15,
            s_fig1_15,
            s_fig0_5,
            s_fig1_5,
            tf_table,
            atm_up_ph,
            atm_atm_ph,
            atm_down_ph,
            ema_ph,
            oi_candle_ph,
        )
    except Exception as e:
        _tui.log_error(f"#{cycle} FATAL: {e}")
        dt_total = _time.time() - t0
        _tui.update(
            cycle=cycle, dt_oc=0, dt_total=dt_total,
            data=_cached_full_data or {'underlying': str(underlying)},
            market_open=_is_market_open(),
            market_status=_market_status_str(),
            error=str(e),
        )
        err = _render('error', message=str(e))
        _oc_hist = _get_oc_history_htmls()
        _oi_dist_hist = _get_oi_dist_history_htmls()
        return (err, "", "", _last_valid_oi_charts, *_oi_dist_hist, _get_oi_dist_ts_html(), _last_valid_oc_html, *_oc_hist, _get_oc_ts_html(), "", None, None, None, None, "", None, None, None, None, None)


# ═══════════════════════════════════════════════════════════════════════════
#^# GRADIO UI
# ═══════════════════════════════════════════════════════════════════════════

#&# Gradio-level CSS loaded from shared stylesheet (templates/css/styles.css)
_CSS = _load_css()

# ─── Initial loader HTML (shown once until first data arrives) ────────────
_INITIAL_LOADER = _render('initial_loader')

#~# JavaScript for Option Chain table column sorting — injected via gr.Blocks(js=...)
_OC_SORT_JS = """
// ── Suppress "mgt.clearMarks is not a function" from Plotly internals ──
(function() {
    if (typeof window.performance !== 'undefined') {
        if (typeof window.performance.clearMarks !== 'function') {
            window.performance.clearMarks = function() {};
        }
        if (typeof window.performance.clearMeasures !== 'function') {
            window.performance.clearMeasures = function() {};
        }
    }
})();

function ocSortCol(th) {
  var table = th.closest('table');
  if (!table) return;
  var tbody = table.querySelector('tbody');
  if (!tbody) return;
  var colIdx = parseInt(th.getAttribute('data-col'));
  if (isNaN(colIdx)) return;
  var sortKey = th.getAttribute('data-sort-key') || 'num';

  var arrow = th.querySelector('.oc-sort-arrow');
  var dir = 'asc';
  if (arrow && arrow.classList.contains('oc-sort-arrow--asc')) dir = 'desc';

  var allArrows = th.parentElement.querySelectorAll('.oc-sort-arrow');
  for (var i = 0; i < allArrows.length; i++) {
    allArrows[i].className = 'oc-sort-arrow';
  }
  if (arrow) arrow.className = 'oc-sort-arrow oc-sort-arrow--' + dir;

  var rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort(function(a, b) {
    var cellA = a.children[colIdx];
    var cellB = b.children[colIdx];
    if (!cellA || !cellB) return 0;
    if (sortKey === 'str') {
      var sA = (cellA.textContent || '').trim().toLowerCase();
      var sB = (cellB.textContent || '').trim().toLowerCase();
      return dir === 'asc' ? sA.localeCompare(sB) : sB.localeCompare(sA);
    }
    var vA = parseFloat(cellA.getAttribute('data-sort-val'));
    var vB = parseFloat(cellB.getAttribute('data-sort-val'));
    if (isNaN(vA)) vA = -Infinity;
    if (isNaN(vB)) vB = -Infinity;
    return dir === 'asc' ? (vA - vB) : (vB - vA);
  });
  for (var j = 0; j < rows.length; j++) {
    tbody.appendChild(rows[j]);
  }
}
// Expose globally so onclick handlers in Gradio HTML components can call it
window.ocSortCol = ocSortCol;

// ── Tab timestamp updater (handles both OC and OI dist tabs) ───────────
(function() {
    var _tsTimer = null;
    function _updateTabs(tsDataId, containerId, labelPrefix) {
        var tsDiv = document.getElementById(tsDataId);
        if (!tsDiv) return;
        var raw = tsDiv.getAttribute('data-ts');
        if (!raw) return;
        var timestamps;
        try { timestamps = JSON.parse(raw); } catch(e) { return; }
        var container = document.getElementById(containerId);
        if (!container) return;
        var tablistBtns = container.querySelectorAll('[role="tablist"] button[role="tab"]');
        var overflowBtns = container.querySelectorAll('.overflow-dropdown button');
        var allBtns = [];
        for (var i = 0; i < tablistBtns.length; i++) allBtns.push(tablistBtns[i]);
        for (var j = 0; j < overflowBtns.length; j++) allBtns.push(overflowBtns[j]);
        var pat = new RegExp('^' + labelPrefix + '\\\\s*#(\\\\d+)$');
        for (var k = 0; k < allBtns.length; k++) {
            var btn = allBtns[k];
            var orig = btn.getAttribute('data-orig-label');
            if (!orig) {
                orig = btn.textContent.trim();
                btn.setAttribute('data-orig-label', orig);
            }
            var m = orig.match(pat);
            if (!m) continue;
            var tsIdx = parseInt(m[1], 10) - 2;
            if (tsIdx < 0 || tsIdx >= timestamps.length) continue;
            var ts = timestamps[tsIdx];
            if (ts) {
                btn.setAttribute('data-oc-ts', ts);
            } else {
                btn.removeAttribute('data-oc-ts');
            }
            btn.textContent = orig;
        }
    }
    function updateAllTimestamps() {
        _updateTabs('oc-ts-data', 'oc-tabs', 'OC');
        _updateTabs('oi-dist-ts-data', 'oi-dist-tabs', 'OI');
    }
    function scheduleUpdate() {
        if (_tsTimer) clearTimeout(_tsTimer);
        _tsTimer = setTimeout(updateAllTimestamps, 200);
    }
    var _obs = new MutationObserver(scheduleUpdate);
    function initTabObserver() {
        var observed = false;
        var tsDiv = document.getElementById('oc-ts-data');
        if (tsDiv) { _obs.observe(tsDiv, { attributes: true }); observed = true; }
        var container = document.getElementById('oc-tabs');
        if (container) { _obs.observe(container, { childList: true, subtree: true }); observed = true; }
        var oiTsDiv = document.getElementById('oi-dist-ts-data');
        if (oiTsDiv) { _obs.observe(oiTsDiv, { attributes: true }); observed = true; }
        var oiContainer = document.getElementById('oi-dist-tabs');
        if (oiContainer) { _obs.observe(oiContainer, { childList: true, subtree: true }); observed = true; }
        if (observed) updateAllTimestamps();
        else setTimeout(initTabObserver, 500);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { setTimeout(initTabObserver, 500); });
    } else {
        setTimeout(initTabObserver, 500);
    }
    setInterval(updateAllTimestamps, 2000);
})();
"""

with gr.Blocks(title="NIFTY Option Chain Live") as demo:
    gr.Markdown("# 📊 Live Option Chain Dashboard")

    with gr.Row():
        underlying_dd = gr.Dropdown(
            ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"], value="NIFTY", label="Underlying", scale=1)
        expiry_idx = gr.Number(value=0, label="Expiry Index", scale=1)
        strikes_sl = gr.Slider(5, 25, value=15, step=1,
                               label="Strikes ± ATM", scale=1)
        refresh_btn = gr.Button("🔄 Refresh", variant="primary", scale=1)
        mock_chk = gr.Checkbox(
            label="🧪 Weekend Mock Mode",
            value=_MOCK_MODE,
            scale=1,
            interactive=True,
            info="Simulate prev-day OI for 📊+📈 panel when market is closed",
        )
    header_out = gr.HTML(value=_INITIAL_LOADER)
    oi_history_out = gr.HTML()
    tech_analysis_out = gr.HTML()
    #^# OI Distribution tabs: Live + HISTORY_TAB_COUNT history snapshots
    oi_dist_hist_tabs = []
    with gr.Tabs(elem_id="oi-dist-tabs"):
        with gr.Tab("📊+📈 Live"):
            oi_charts_out = gr.HTML()
        for i in range(1, HISTORY_TAB_COUNT + 1):
            with gr.Tab(f"OI #{i+1}"):
                oi_dist_hist_tabs.append(gr.HTML())
    oi_dist_ts_out = gr.HTML(elem_id="oi-dist-ts-wrapper")
    #^# Option Chain tabs: Live + HISTORY_TAB_COUNT history snapshots
    oc_hist_tabs = []
    with gr.Tabs(elem_id="oc-tabs"):
        with gr.Tab("📊 Live"):
            oc_out = gr.HTML()
        for i in range(1, HISTORY_TAB_COUNT + 1):
            with gr.Tab(f"OC #{i+1}"):
                oc_hist_tabs.append(gr.HTML())
    oc_ts_out = gr.HTML(elem_id="oc-ts-wrapper")  #~# carries tab timestamps, hidden via CSS
    futures_out = gr.HTML()
    with gr.Row():
        straddle_chart_w0 = gr.Plot(label="📈 15-Min Straddle — Current Expiry")
        straddle_chart_w1 = gr.Plot(label="📈 15-Min Straddle — Next Expiry")
    with gr.Row():
        straddle_chart_5m_w0 = gr.Plot(label="📈 5-Min Straddle — Current Expiry")
        straddle_chart_5m_w1 = gr.Plot(label="📈 5-Min Straddle — Next Expiry")
    tf_indicators_out = gr.HTML()
    #^# NEW: ATM Triple Straddle Row (VWAP + RSI) — 3 columns  Left=−1 strike | Mid=ATM | Right=+1 strike
    with gr.Row():
        atm_up_chart   = gr.Plot(label="📈 5-Min Straddle — ↓ −1 Strike  │ VWAP + RSI")
        atm_atm_chart  = gr.Plot(label="📈 5-Min Straddle — ATM Strike  │ VWAP + RSI")
        atm_down_chart = gr.Plot(label="📈 5-Min Straddle — ↑ +1 Strike  │ VWAP + RSI")
    #^# NEW: 5-Min Candlestick with 5 EMA High & 5 EMA Low
    ema_candle_out = gr.Plot(label="🕯 5-Min Candlestick — EMA(5) High & EMA(5) Low")
    #^# NEW: 5-Min Candlestick + EMA(5) High/Low Band + Vertical OI Distribution + Change
    oi_candle_out = gr.Plot(label="🕯📊 5-Min Candle + EMA(5) Band + OI Distribution")

    ins = [underlying_dd, expiry_idx, strikes_sl]
    outs = [header_out, oi_history_out, tech_analysis_out,
            oi_charts_out,
            *oi_dist_hist_tabs,
            oi_dist_ts_out,
            oc_out,
            *oc_hist_tabs,
            oc_ts_out,
            futures_out,
            straddle_chart_w0, straddle_chart_w1,
            straddle_chart_5m_w0, straddle_chart_5m_w1,
            tf_indicators_out,
            atm_up_chart, atm_atm_chart, atm_down_chart,
            ema_candle_out,
            oi_candle_out]

    #~# Checkbox toggles global mock mode and clears cached mock snap so it regenerates
    def _toggle_mock_mode(enabled: bool):
        global _MOCK_MODE, _MOCK_PREV_SNAP
        _MOCK_MODE = enabled
        _MOCK_PREV_SNAP = {}  #~# clear so it regenerates fresh on next refresh
    mock_chk.change(fn=_toggle_mock_mode, inputs=[mock_chk])

    #~# Full refresh on button click
    refresh_btn.click(fn=refresh_data, inputs=ins, outputs=outs, show_progress="hidden")
    
    #~# Initial load — replaces the loader with real data (hidden progress so no extra fade)
    demo.load(fn=refresh_data, inputs=ins, outputs=outs, show_progress="hidden")

    #~# Silent auto-refresh every 3 seconds — NO loading fade/spinner/opacity change
    #~# show_progress="hidden" ensures zero visual disruption during interval updates
    gr.Timer(value=3, active=True).tick(
        fn=smart_refresh, inputs=ins, outputs=outs, show_progress="hidden")


def _kill_port_7860():
    """Kill any process holding port 7860 so Gradio can bind cleanly."""
    import subprocess
    try:
        result = subprocess.run(
            ['netstat', '-ano'], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if ':7860' in line and 'LISTENING' in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit() and int(pid) != 0:
                    subprocess.run(['taskkill', '/F', '/PID', pid],
                                   capture_output=True, timeout=5)
                    _dbg_console.print(f"[yellow]\\[Port] Killed PID {pid} on port 7860[/]")
    except Exception:
        pass


if __name__ == "__main__":
    _kill_port_7860()
    _tui.log_info("Starting Gradio server on http://0.0.0.0:7860")
    _tui.log_info(f"Market: {_market_status_str()}")
    demo.queue(default_concurrency_limit=1)  # prevent stacked refreshes
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        js=_OC_SORT_JS,
        theme=gr.themes.Base(
            primary_hue="blue",
            secondary_hue="green",
            neutral_hue="gray",
        ),
        css=_CSS,
    )
