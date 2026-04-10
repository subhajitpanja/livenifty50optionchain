"""
DhanHQ data-fetch helpers (instrument CSV + REST charts/expiry APIs).

Consolidates the low-level data-fetch functions that used to live inline
in optionchain_gradio.py:

    - load_instrument_df         → local instrument CSV loader (cached)
    - fetch_expiry_list_dynamic  → /v2/optionchain/expirylist (+ CSV fallback)
    - resolve_ce_pe_symbols      → lookup CE/PE SEM_CUSTOM_SYMBOL + sec-id
    - fetch_option_intraday      → /v2/charts/intraday for NFO options
    - fetch_ohlcv_direct         → /v2/charts/intraday for index spot
    - fetch_ohlcv_daily          → /v2/charts/historical + today's partial candle

All functions use module-level caches so the refresh loop stays cheap.
Logging goes via an injectable `dbg` callback so the module does not need
the Rich console from optionchain_gradio.py.
"""

from __future__ import annotations

import datetime as _dt
import time as _time
from typing import Callable

import pandas as pd
import requests as _requests

from Credential.Credential import client_code, token_id
from index_constants import INDEX_EXCHANGE_SEG, INDEX_SECURITY_IDS_OC, INDEX_STEP
from paths import INSTRUMENTS_DIR


# ──────────────────────────────────────────────────────────────────────────
# Logging hook — inject from caller via set_logger()
# ──────────────────────────────────────────────────────────────────────────
def _noop_dbg(_msg: str, _level: str = "dim") -> None:  # pragma: no cover
    return None


_dbg: Callable[[str, str], None] = _noop_dbg


def set_logger(fn: Callable[[str, str], None]) -> None:
    """Install a debug-logger. `fn(msg, level)` — level in {dim, yellow, red}."""
    global _dbg
    _dbg = fn


# ──────────────────────────────────────────────────────────────────────────
# Module-level caches
# ──────────────────────────────────────────────────────────────────────────
_instrument_df_cache: pd.DataFrame | None = None
_expiry_list_cache: dict = {}            # underlying → {'expiries', 'ts'}
_option_intraday_cache: dict = {}        # (sec_id, interval) → {'df', 'ts'}
_tf_ohlcv_cache: dict = {}               # (underlying, interval) → {'df', 'ts'}


# ══════════════════════════════════════════════════════════════════════════
# Instrument CSV
# ══════════════════════════════════════════════════════════════════════════
def load_instrument_df() -> pd.DataFrame | None:
    """
    Load (and cache) the daily instrument CSV from `data/source/instruments/`.

    Prefers today's file (`all_instrument YYYY-MM-DD.csv`); falls back to the
    most recent file by name.
    """
    global _instrument_df_cache
    if _instrument_df_cache is not None:
        return _instrument_df_cache

    today_str = _dt.date.today().strftime('%Y-%m-%d')
    fname = f'all_instrument {today_str}.csv'
    csv_path = INSTRUMENTS_DIR / fname

    if not csv_path.exists():
        candidates = sorted(INSTRUMENTS_DIR.glob('all_instrument *.csv'), reverse=True)
        csv_path = candidates[0] if candidates else None

    if csv_path and csv_path.exists():
        try:
            df = pd.read_csv(csv_path, low_memory=False)
            df['SEM_EXPIRY_DATE'] = pd.to_datetime(df['SEM_EXPIRY_DATE'], errors='coerce')
            _instrument_df_cache = df
            _dbg(f"[Instrument] Loaded {csv_path.name} ({len(df)} rows)", "dim")
        except Exception as e:
            _dbg(f"[Instrument] Failed to load {csv_path}: {e}", "red")
    else:
        _dbg("[Instrument] No instrument CSV found in data/source/instruments/", "yellow")

    return _instrument_df_cache


# ══════════════════════════════════════════════════════════════════════════
# Expiry list (DhanHQ API → instrument CSV fallback)
# ══════════════════════════════════════════════════════════════════════════
def fetch_expiry_list_dynamic(underlying: str) -> list[str]:
    """
    Return future expiries for `underlying` as sorted YYYY-MM-DD strings.

    Primary: DhanHQ `/v2/optionchain/expirylist`.
    Fallback: instrument CSV's unique `SEM_EXPIRY_DATE`s for OPTIDX.
    5-minute TTL.
    """
    now = _time.time()
    cached = _expiry_list_cache.get(underlying)
    if cached and (now - cached['ts']) < 300:
        return cached['expiries']

    security_id = INDEX_SECURITY_IDS_OC.get(underlying)
    exchange_seg = INDEX_EXCHANGE_SEG.get(underlying, 'IDX_I')
    today_str = _dt.date.today().strftime('%Y-%m-%d')
    expiries: list[str] = []

    # 1. DhanHQ API
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
                    expiries = [e for e in sorted(data['data']) if e >= today_str]
                    _dbg(f"[Expiry] {underlying}: {len(expiries)} future expiries "
                         f"(next: {expiries[:3]})", "dim")
        except Exception as e:
            _dbg(f"[Expiry] API failed for {underlying}: {e}", "yellow")

    # 2. Instrument CSV fallback
    if not expiries:
        idf = load_instrument_df()
        if idf is not None:
            try:
                mask = (
                    (idf['SEM_EXM_EXCH_ID'] == 'NSE')
                    & (idf['SEM_INSTRUMENT_NAME'] == 'OPTIDX')
                    & (idf['SEM_TRADING_SYMBOL'].str.startswith(f'{underlying}-', na=False))
                )
                exp_dates = idf.loc[mask, 'SEM_EXPIRY_DATE'].dropna().dt.date.unique()
                expiries = sorted([str(d) for d in exp_dates if str(d) >= today_str])
                _dbg(f"[Expiry] {underlying}: {len(expiries)} from CSV "
                     f"(next: {expiries[:3]})", "dim")
            except Exception as e:
                _dbg(f"[Expiry] Instrument CSV parse failed: {e}", "red")

    if expiries:
        _expiry_list_cache[underlying] = {'expiries': expiries, 'ts': now}
    return expiries


# ══════════════════════════════════════════════════════════════════════════
# CE/PE symbol + security-id resolver
# ══════════════════════════════════════════════════════════════════════════
def resolve_ce_pe_symbols(underlying: str, expiry_date_str: str, strike: int):
    """
    Look up CE/PE `SEM_CUSTOM_SYMBOL` + `SEM_SMST_SECURITY_ID` from the
    cached instrument CSV.

    Returns: (ce_symbol, pe_symbol, ce_security_id, pe_security_id) — any
    element may be `None` if the row is missing.
    """
    idf = load_instrument_df()
    if idf is None:
        return None, None, None, None
    try:
        mask = (
            (idf['SEM_EXM_EXCH_ID'] == 'NSE')
            & (idf['SEM_TRADING_SYMBOL'].str.startswith(f'{underlying}-', na=False))
            & (idf['SEM_EXPIRY_DATE'].dt.date.astype(str) == expiry_date_str)
            & (idf['SEM_STRIKE_PRICE'] == float(strike))
        )
        filtered = idf[mask]
        ce_rows = filtered[filtered['SEM_OPTION_TYPE'] == 'CE']
        pe_rows = filtered[filtered['SEM_OPTION_TYPE'] == 'PE']
        ce_sym    = ce_rows.iloc[-1]['SEM_CUSTOM_SYMBOL']    if not ce_rows.empty else None
        pe_sym    = pe_rows.iloc[-1]['SEM_CUSTOM_SYMBOL']    if not pe_rows.empty else None
        ce_sec_id = str(int(ce_rows.iloc[-1]['SEM_SMST_SECURITY_ID'])) if not ce_rows.empty else None
        pe_sec_id = str(int(pe_rows.iloc[-1]['SEM_SMST_SECURITY_ID'])) if not pe_rows.empty else None
        return ce_sym, pe_sym, ce_sec_id, pe_sec_id
    except Exception as e:
        _dbg(f"[Resolve] {underlying} {expiry_date_str} {strike}: {e}", "red")
        return None, None, None, None


# ══════════════════════════════════════════════════════════════════════════
# NFO option intraday OHLCV
# ══════════════════════════════════════════════════════════════════════════
def fetch_option_intraday(security_id: str, interval: int = 5,
                          symbol_label: str = '') -> pd.DataFrame:
    """
    Fetch intraday OHLCV for an NFO option via Dhan `/v2/charts/intraday`.

    Cached 60s per `(security_id, interval)`. On API error, returns a stale
    cached DataFrame if available, otherwise an empty DataFrame.
    """
    from oc_data_fetcher import API_HEADERS  # avoid top-level circular import

    cache_key = (security_id, interval)
    cached = _option_intraday_cache.get(cache_key)
    if cached and (_time.time() - cached.get('ts', 0)) < 60:
        return cached['df']

    to_dt = _dt.datetime.now()
    from_dt = to_dt - _dt.timedelta(days=7)

    try:
        url = 'https://api.dhan.co/v2/charts/intraday'
        payload = {
            'securityId': str(security_id),
            'exchangeSegment': 'NSE_FNO',
            'instrument': 'OPTIDX',
            'interval': int(interval),
            'oi': True,
            'fromDate': from_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'toDate':   to_dt.strftime('%Y-%m-%d %H:%M:%S'),
        }
        r = _requests.post(url, json=payload, headers=API_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'open' in data and 'close' in data and 'timestamp' in data:
                df = pd.DataFrame(data)
                if not df.empty:
                    df['timestamp'] = (pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
                                       .dt.tz_localize('UTC')
                                       .dt.tz_convert('Asia/Kolkata')
                                       .dt.tz_localize(None))
                    df.columns = [c.lower() for c in df.columns]
                    _option_intraday_cache[cache_key] = {'df': df, 'ts': _time.time()}
                    _dbg(f"[OptionData] {symbol_label} {interval}m → {len(df)} candles", "dim")
                    return df
            else:
                _dbg(f"[OptionData] {symbol_label}: no OHLCV "
                     f"(status={r.status_code})", "yellow")
        else:
            _dbg(f"[OptionData] {symbol_label}: HTTP {r.status_code}", "yellow")
    except Exception as e:
        _dbg(f"[OptionData] {symbol_label}: {e}", "red")

    if cached:
        _dbg(f"[OptionData] {symbol_label}: using stale cache", "dim")
        return cached['df']
    return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════
# Index intraday OHLCV
# ══════════════════════════════════════════════════════════════════════════
def fetch_ohlcv_direct(underlying: str, interval: int) -> pd.DataFrame:
    """
    Fetch intraday OHLCV for an index via Dhan `/v2/charts/intraday`.
    5 trading days of data (~7 calendar days). Cached 60s per key.
    """
    from oc_data_fetcher import API_HEADERS, INDEX_SECURITY_IDS

    cache_key = (underlying, interval)
    cached = _tf_ohlcv_cache.get(cache_key)
    if cached and (_time.time() - cached.get('ts', 0)) < 60:
        return cached['df']

    security_id = INDEX_SECURITY_IDS.get(underlying, 0)
    if not security_id:
        return pd.DataFrame()

    to_date   = _dt.date.today().strftime('%Y-%m-%d')
    from_date = (_dt.date.today() - _dt.timedelta(days=7)).strftime('%Y-%m-%d')

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
        r = _requests.post(url, json=payload, headers=API_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'open' in data and 'close' in data and 'timestamp' in data:
                df = pd.DataFrame(data)
                if not df.empty:
                    df['timestamp'] = (pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
                                       .dt.tz_localize('UTC')
                                       .dt.tz_convert('Asia/Kolkata')
                                       .dt.tz_localize(None))
                    df.columns = [c.lower() for c in df.columns]
                    _tf_ohlcv_cache[cache_key] = {'df': df, 'ts': _time.time()}
                    return df
    except Exception as e:
        print(f"[TF] Direct OHLCV fetch ({underlying}, {interval}m) error: {e}")

    if cached:
        return cached['df']
    return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════
# Index daily OHLCV (+ today's partial candle)
# ══════════════════════════════════════════════════════════════════════════
def fetch_ohlcv_daily(underlying: str) -> pd.DataFrame:
    """
    Fetch ~1 year of daily OHLCV for an index via Dhan `/v2/charts/historical`.

    Appends today's partial daily candle (built from 5-min intraday data)
    so indicators match TradingView's live-daily behaviour. Cached 60s.
    """
    from oc_data_fetcher import API_HEADERS, INDEX_SECURITY_IDS

    cache_key = (underlying, 'daily')
    cached = _tf_ohlcv_cache.get(cache_key)
    if cached and (_time.time() - cached.get('ts', 0)) < 60:
        return cached['df']

    security_id = INDEX_SECURITY_IDS.get(underlying, 0)
    if not security_id:
        return pd.DataFrame()

    to_date   = _dt.date.today().strftime('%Y-%m-%d')
    from_date = (_dt.date.today() - _dt.timedelta(days=365)).strftime('%Y-%m-%d')

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
        r = _requests.post(url, json=payload, headers=API_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'open' in data and 'close' in data and 'timestamp' in data:
                df = pd.DataFrame(data)
                if not df.empty:
                    df['timestamp'] = (pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
                                       .dt.tz_localize('UTC')
                                       .dt.tz_convert('Asia/Kolkata')
                                       .dt.tz_localize(None))
                    df.columns = [c.lower() for c in df.columns]

                    # Append today's partial daily candle from 5-min intraday
                    try:
                        intra_df = fetch_ohlcv_direct(underlying, 5)
                        if intra_df is not None and not intra_df.empty:
                            today = _dt.date.today()
                            today_candles = intra_df.loc[intra_df['timestamp'].dt.date == today]
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
                        pass  # fall back to historical-only data

                    _tf_ohlcv_cache[cache_key] = {'df': df, 'ts': _time.time()}
                    return df
    except Exception as e:
        print(f"[TF] Daily OHLCV fetch ({underlying}) error: {e}")

    if cached:
        return cached['df']
    return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════
# ATM resolver convenience (previously _atm_strike_with_cooldown)
# ══════════════════════════════════════════════════════════════════════════
_ATM_COOLDOWN_SEC: float = 120.0
_atm_cache: dict = {}


def atm_strike_with_cooldown(tsl, underlying: str, expiry_idx: int):
    """
    Dynamic ATM selection using the DhanHQ expiry API + instrument CSV.

    Completely bypasses Tradehull's broken ATM_Strike_Selection. Returns
    `(ce_symbol, pe_symbol, expiry_date_str)` or `None` on failure. A
    failure primes a 120 s cooldown to stop log spam.
    """
    now = _time.perf_counter()
    cache_key = (underlying, expiry_idx)
    cached = _atm_cache.get(cache_key)

    if cached and cached.get('ok') and (now - cached['ts']) < 60:
        return cached['result']
    if cached and not cached.get('ok') and (now - cached['ts']) < _ATM_COOLDOWN_SEC:
        return None

    try:
        expiries = fetch_expiry_list_dynamic(underlying)
        if not expiries:
            _dbg(f"[ATM] {underlying}: no expiries found — cooldown "
                 f"{_ATM_COOLDOWN_SEC:.0f}s", "yellow")
            _atm_cache[cache_key] = {'result': None, 'ts': now, 'ok': False}
            return None

        if expiry_idx >= len(expiries):
            _dbg(f"[ATM] {underlying}: expiry_idx={expiry_idx} out of range "
                 f"(only {len(expiries)} available) — using last", "yellow")
            expiry_idx = len(expiries) - 1
        expiry_date_str = expiries[expiry_idx]

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
            _dbg(f"[ATM] {underlying}: no spot price — cooldown "
                 f"{_ATM_COOLDOWN_SEC:.0f}s", "yellow")
            _atm_cache[cache_key] = {'result': None, 'ts': now, 'ok': False}
            return None

        step = INDEX_STEP.get(underlying, 50)
        atm_strike = int(round(spot / step) * step)

        ce_sym, pe_sym, _ce_sid, _pe_sid = resolve_ce_pe_symbols(
            underlying, expiry_date_str, atm_strike)
        if not ce_sym or not pe_sym:
            _dbg(f"[ATM] {underlying}: CE/PE not found for expiry={expiry_date_str} "
                 f"strike={atm_strike} — cooldown {_ATM_COOLDOWN_SEC:.0f}s", "yellow")
            _atm_cache[cache_key] = {'result': None, 'ts': now, 'ok': False}
            return None

        result = (ce_sym, pe_sym, expiry_date_str)
        _dbg(f"[ATM] {underlying} exp={expiry_date_str} strike={atm_strike} "
             f"CE={ce_sym} PE={pe_sym}", "dim")
        _atm_cache[cache_key] = {'result': result, 'ts': now, 'ok': True}
        return result

    except Exception as e:
        _dbg(f"[ATM] {underlying} expiry={expiry_idx}: {e} — cooldown "
             f"{_ATM_COOLDOWN_SEC:.0f}s", "red")
        _atm_cache[cache_key] = {'result': None, 'ts': now, 'ok': False}
        return None
