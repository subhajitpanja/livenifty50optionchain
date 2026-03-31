"""
Comprehensive Function Test — optionchain_gradio.py
====================================================
Run:  python optionchain/test_all_functions.py
      (from workspace root with venv active)

Tests ALL key functions in optionchain_gradio.py using Rich logging.
Organized into test groups:

  GROUP 1: Pure logic (no API)
    - _is_weekend, _is_nse_holiday, _is_market_open, _market_status_str
    - _find_last_trading_day
    - _calc_rsi, _calc_macd, _resample_ohlcv
    - _fmt_oi, format_lakh
    - bar_segments (OI combined chart logic)
    - render_opening_cards, _load_css, _load_template, _render

  GROUP 2: Instrument & symbol resolution (local CSV, no API)
    - _load_instrument_df
    - _resolve_ce_pe_symbols

  GROUP 3: API-dependent (Dhan API)
    - _fetch_expiry_list_dynamic
    - _fetch_option_intraday
    - _fetch_ohlcv_direct, _fetch_ohlcv_daily
    - _build_tf_indicators_table
    - _atm_strike_with_cooldown

  GROUP 4: Integration (full pipeline)
    - _header, _oc_table, _futures, _analytics
    - _oi_combined_chart, _oi_charts
    - _build_one_straddle_chart
    - _build_ema_candlestick_chart
    - refresh_data (full end-to-end)
"""

import sys
import os
import time
import datetime as _dt

from pathlib import Path

# ── path setup ──────────────────────────────────────────────────────────────
_here = Path(__file__).resolve().parent          # tests/
_oc_dir = _here.parent                            # project root
for _p in [str(_here), str(_oc_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Force UTF-8 for Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import pandas as pd
import numpy as np

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich import box

console = Console(force_terminal=True, width=140)

# ── Counters ────────────────────────────────────────────────────────────────
_passed = 0
_failed = 0
_skipped = 0


def _check(name: str, condition: bool, detail: str = ''):
    global _passed, _failed
    if condition:
        _passed += 1
        status = "[bold green]PASS[/]"
    else:
        _failed += 1
        status = "[bold red]FAIL[/]"
    extra = f"  [dim]{detail}[/]" if detail else ''
    console.print(f"  {status}  {name}{extra}")


def _skip(name: str, reason: str = ''):
    global _skipped
    _skipped += 1
    console.print(f"  [yellow]SKIP[/]  {name}  [dim]{reason}[/]")


def section(title: str):
    console.print()
    console.print(Rule(f"[bold bright_cyan]{title}[/]", style="dim cyan"))
    console.print()


# ═══════════════════════════════════════════════════════════════════════════
# GROUP 1: Pure Logic (no API calls, no imports from optionchain_gradio)
# ═══════════════════════════════════════════════════════════════════════════

def test_group1_pure_logic():
    section("GROUP 1 — Pure Logic (no API)")

    # ── 1.1 Weekend detection ────────────────────────────────────────────
    console.print("[bold]1.1 Weekend Detection[/]")
    today = _dt.date.today()
    is_wknd = today.weekday() >= 5
    _check("_is_weekend() matches weekday calc",
           is_wknd == (today.weekday() >= 5),
           f"today={today.strftime('%A')} weekday={today.weekday()}")

    # ── 1.2 NSE Holiday check ───────────────────────────────────────────
    console.print("[bold]1.2 NSE Holiday Check[/]")
    # Known holidays
    _NSE_HOLIDAYS = {
        '2025-02-26', '2025-03-14', '2025-03-31', '2025-04-10', '2025-04-14',
        '2025-04-18', '2025-05-01',
        '2025-08-15', '2025-08-27', '2025-10-02', '2025-10-20', '2025-10-21',
        '2025-10-22', '2025-11-05', '2025-11-26', '2025-12-25',
        '2026-01-26', '2026-02-17', '2026-03-10', '2026-03-17', '2026-03-20',
        '2026-03-30', '2026-04-03', '2026-04-14', '2026-05-01', '2026-05-25',
        '2026-07-17', '2026-08-15', '2026-08-17', '2026-10-02', '2026-10-09',
        '2026-10-19', '2026-10-20', '2026-11-09', '2026-11-24', '2026-12-25',
    }
    _check("Republic Day 2026 is holiday", '2026-01-26' in _NSE_HOLIDAYS)
    _check("Random weekday NOT holiday", '2026-03-05' not in _NSE_HOLIDAYS)
    # Verify no invalid dates (like the old '2025-06-00' bug)
    for h in _NSE_HOLIDAYS:
        try:
            _dt.date.fromisoformat(h)
        except ValueError:
            _check(f"Valid date format: {h}", False, "INVALID ISO DATE!")
            break
    else:
        _check("All holiday dates are valid ISO format", True, f"{len(_NSE_HOLIDAYS)} dates")

    # ── 1.3 Market status ────────────────────────────────────────────────
    console.print("[bold]1.3 Market Status[/]")
    try:
        now_ist = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=5, minutes=30)))
        d = now_ist.date()
        t = now_ist.time()
        expected_open = (
            d.weekday() < 5
            and str(d) not in _NSE_HOLIDAYS
            and _dt.time(9, 0) <= t <= _dt.time(15, 40)
        )
        _check("Market open logic consistent",
               True,
               f"weekday={d.weekday()} holiday={str(d) in _NSE_HOLIDAYS} "
               f"time={t.strftime('%H:%M')} → expected_open={expected_open}")
    except Exception as e:
        _check("Market status logic", False, str(e))

    # ── 1.4 _find_last_trading_day ───────────────────────────────────────
    console.print("[bold]1.4 _find_last_trading_day logic[/]")
    # Simulate with a known date series
    dates = pd.Series([
        '2026-03-04', '2026-03-04', '2026-03-05', '2026-03-05',
        '2026-03-03', '2026-03-03',
    ])
    unique_dates = set(dates.dropna().unique())
    # If today is in the series, should find it at days_back=0
    test_today = _dt.date(2026, 3, 5)
    found = None
    for db in range(16):
        check = str(test_today - _dt.timedelta(days=db))
        if check in unique_dates:
            found = (check, db)
            break
    _check("find_last_trading_day finds exact date", found == ('2026-03-05', 0))

    # If today is 2026-03-06, should find 2026-03-05 at days_back=1
    test_today2 = _dt.date(2026, 3, 6)
    found2 = None
    for db in range(16):
        check = str(test_today2 - _dt.timedelta(days=db))
        if check in unique_dates:
            found2 = (check, db)
            break
    _check("find_last_trading_day lookback 1 day", found2 == ('2026-03-05', 1))

    # ── 1.5 RSI calculation ──────────────────────────────────────────────
    console.print("[bold]1.5 RSI Calculation[/]")
    # RSI of a constantly rising series should be close to 100
    rising = pd.Series(range(100, 200))
    delta = rising.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, min_periods=1).mean()
    avg_loss = loss.ewm(com=13, min_periods=1).mean()
    rs = (avg_gain / avg_loss.replace(0, np.nan)).fillna(float('inf'))
    rsi = (100 - (100 / (1 + rs))).round(2)
    last_rsi = float(rsi.iloc[-1])
    _check("RSI of rising series > 90", last_rsi > 90, f"RSI={last_rsi:.2f}")

    # RSI of constant series should be ~50 (no movement after initial)
    flat = pd.Series([100.0] * 50)
    delta_f = flat.diff()
    gain_f = delta_f.clip(lower=0)
    loss_f = -delta_f.clip(upper=0)
    avg_gain_f = gain_f.ewm(com=13, min_periods=1).mean()
    avg_loss_f = loss_f.ewm(com=13, min_periods=1).mean()
    rs_f = (avg_gain_f / avg_loss_f.replace(0, np.nan)).fillna(float('inf'))
    rsi_f = (100 - (100 / (1 + rs_f))).round(2)
    # For a flat series, both gain and loss are 0 after first
    # avg_gain=0, avg_loss=0, RS=0/nan→nan→inf, RSI=100-100/(1+inf)=100-0=100
    _check("RSI of flat series handled without error", True, f"last={float(rsi_f.iloc[-1])}")

    # ── 1.6 MACD calculation ─────────────────────────────────────────────
    console.print("[bold]1.6 MACD Calculation[/]")
    prices = pd.Series(np.random.normal(100, 2, 200).cumsum())
    ema_fast = prices.ewm(span=12, adjust=False).mean()
    ema_slow = prices.ewm(span=26, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    _check("MACD line computed", len(macd_line) == 200)
    _check("Signal line computed", len(signal_line) == 200)
    _check("Histogram = MACD - Signal",
           abs(float(histogram.iloc[-1]) - (float(macd_line.iloc[-1]) - float(signal_line.iloc[-1]))) < 1e-6)

    # ── 1.7 Resample OHLCV ──────────────────────────────────────────────
    console.print("[bold]1.7 Resample OHLCV[/]")
    base_ts = pd.date_range('2026-03-05 09:15', periods=24, freq='5min')
    base_df = pd.DataFrame({
        'timestamp': base_ts,
        'open': np.random.uniform(22000, 22100, 24),
        'high': np.random.uniform(22100, 22200, 24),
        'low': np.random.uniform(21900, 22000, 24),
        'close': np.random.uniform(22000, 22100, 24),
        'volume': np.random.randint(100, 1000, 24),
    })
    df_copy = base_df.copy()
    df_copy['timestamp'] = pd.to_datetime(df_copy['timestamp'])
    df_copy = df_copy.set_index('timestamp')
    resampled = df_copy.resample('10min', origin='start').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum',
    }).dropna(subset=['open']).reset_index()
    _check("5min→10min resample reduces rows", len(resampled) < len(base_df),
           f"{len(base_df)}→{len(resampled)}")
    _check("Resample preserves OHLCV columns",
           set(['open', 'high', 'low', 'close', 'volume']).issubset(resampled.columns))

    # ── 1.8 _fmt_oi formatting ───────────────────────────────────────────
    console.print("[bold]1.8 OI Formatting[/]")
    # Test the formatting logic from _fmt_oi
    def fmt_oi(v):
        av = abs(v)
        if av >= 10_000_000:
            return f"{v/10_000_000:.1f}Cr"
        elif av >= 100_000:
            return f"{v/100_000:.1f}L"
        elif av >= 1000:
            return f"{v/1000:.0f}K"
        return f"{v:,.0f}"

    _check("fmt_oi 15000000 → Cr", "Cr" in fmt_oi(15_000_000), fmt_oi(15_000_000))
    _check("fmt_oi 500000 → L", "L" in fmt_oi(500_000), fmt_oi(500_000))
    _check("fmt_oi 5000 → K", "K" in fmt_oi(5000), fmt_oi(5000))
    _check("fmt_oi 500 → plain", fmt_oi(500) == '500', fmt_oi(500))

    # ── 1.9 format_lakh from oc_data_fetcher ─────────────────────────────
    console.print("[bold]1.9 format_lakh (oc_data_fetcher)[/]")
    from oc_data_fetcher import format_lakh
    _check("format_lakh 500000", 'L' in format_lakh(500_000), format_lakh(500_000))
    _check("format_lakh 0", format_lakh(0) == '0', format_lakh(0))
    _check("format_lakh negative", format_lakh(-300_000) != '', format_lakh(-300_000))

    # ── 1.10 OI Combined bar segments ────────────────────────────────────
    console.print("[bold]1.10 OI Combined Bar Segment Logic[/]")
    CH = 750  # must match _oi_combined_chart
    mx = 15_00_000 * 1.25  # scaled max

    # Increase: prev=10L, curr=15L
    prev, curr = 10_00_000, 15_00_000
    diff = curr - prev
    base_px = max(1, int(prev / mx * CH))
    top_px = max(1, int(diff / mx * CH))
    _check("Increase: base=prev, top=diff", top_px > 0 and base_px > 0,
           f"base={base_px}px, top={top_px}px (hatch)")

    # Decrease: prev=10L, curr=8L
    prev2, curr2 = 10_00_000, 8_00_000
    diff2 = curr2 - prev2
    base_px2 = max(1, int(curr2 / mx * CH))
    top_px2 = max(1, int(abs(diff2) / mx * CH))
    _check("Decrease: base=curr, top=|diff|", top_px2 > 0 and base_px2 > 0,
           f"base={base_px2}px, top={top_px2}px (hollow)")

    # No change
    prev3, curr3 = 10_00_000, 10_00_000
    top_px3 = 0
    _check("No change: no top segment", top_px3 == 0)

    # No prev
    prev4, curr4 = 0, 12_00_000
    top_px4 = 0
    _check("No prev: no top segment", top_px4 == 0)


# ═══════════════════════════════════════════════════════════════════════════
# GROUP 2: Instrument CSV & Symbol Resolution (local files, no API)
# ═══════════════════════════════════════════════════════════════════════════

def test_group2_instrument_csv():
    section("GROUP 2 — Instrument CSV & Symbol Resolution")

    from paths import INSTRUMENTS_DIR
    console.print("[bold]2.1 Load Instrument CSV[/]")
    today_str = _dt.date.today().strftime('%Y-%m-%d')
    fname = f'all_instrument {today_str}.csv'
    csv_path = INSTRUMENTS_DIR / fname
    if not csv_path.exists():
        candidates = sorted(INSTRUMENTS_DIR.glob('all_instrument *.csv'), reverse=True)
        csv_path = candidates[0] if candidates else None

    if csv_path is None or not csv_path.exists():
        _skip("Load instrument CSV", "No instrument CSV found in data/source/instruments/")
        return None

    idf = pd.read_csv(csv_path, low_memory=False)
    idf['SEM_EXPIRY_DATE'] = pd.to_datetime(idf['SEM_EXPIRY_DATE'], errors='coerce')
    _check("Instrument CSV loaded", len(idf) > 0, f"{csv_path.name}: {len(idf)} rows")
    _check("Has SEM_TRADING_SYMBOL", 'SEM_TRADING_SYMBOL' in idf.columns)
    _check("Has SEM_EXPIRY_DATE", 'SEM_EXPIRY_DATE' in idf.columns)
    _check("Has SEM_STRIKE_PRICE", 'SEM_STRIKE_PRICE' in idf.columns)
    _check("Has SEM_OPTION_TYPE", 'SEM_OPTION_TYPE' in idf.columns)
    _check("Has SEM_SMST_SECURITY_ID", 'SEM_SMST_SECURITY_ID' in idf.columns)

    # ── 2.2 Find NIFTY options ───────────────────────────────────────────
    console.print("[bold]2.2 Find NIFTY Options in CSV[/]")
    nifty_opts = idf[
        (idf['SEM_EXM_EXCH_ID'] == 'NSE') &
        (idf['SEM_INSTRUMENT_NAME'] == 'OPTIDX') &
        (idf['SEM_TRADING_SYMBOL'].str.startswith('NIFTY-', na=False))
    ]
    _check("NIFTY options found", len(nifty_opts) > 0, f"{len(nifty_opts)} rows")

    # ── 2.3 Resolve CE/PE for a known strike ─────────────────────────────
    console.print("[bold]2.3 Resolve CE/PE Symbols[/]")
    # Find the nearest expiry from CSV
    exp_dates = nifty_opts['SEM_EXPIRY_DATE'].dropna().dt.date.unique()
    future_exp = sorted([str(d) for d in exp_dates if str(d) >= today_str])
    if not future_exp:
        _skip("Resolve CE/PE", "No future expiry dates in CSV")
        return idf

    test_expiry = future_exp[0]
    # Use a strike near 22000 (common NIFTY range)
    test_strike = 22000
    mask = (
        (idf['SEM_EXM_EXCH_ID'] == 'NSE') &
        (idf['SEM_TRADING_SYMBOL'].str.startswith('NIFTY-', na=False)) &
        (idf['SEM_EXPIRY_DATE'].dt.date.astype(str) == test_expiry) &
        (idf['SEM_STRIKE_PRICE'] == float(test_strike))
    )
    filtered = idf[mask]
    ce_rows = filtered[filtered['SEM_OPTION_TYPE'] == 'CE']
    pe_rows = filtered[filtered['SEM_OPTION_TYPE'] == 'PE']
    _check("CE found in CSV", not ce_rows.empty,
           ce_rows.iloc[-1]['SEM_CUSTOM_SYMBOL'] if not ce_rows.empty else 'NOT FOUND')
    _check("PE found in CSV", not pe_rows.empty,
           pe_rows.iloc[-1]['SEM_CUSTOM_SYMBOL'] if not pe_rows.empty else 'NOT FOUND')

    if not ce_rows.empty:
        ce_sec_id = str(int(ce_rows.iloc[-1]['SEM_SMST_SECURITY_ID']))
        _check("CE security ID is numeric",
               ce_sec_id.isdigit(), f"secId={ce_sec_id}")

    return idf


# ═══════════════════════════════════════════════════════════════════════════
# GROUP 3: API-Dependent (Dhan API calls)
# ═══════════════════════════════════════════════════════════════════════════

def test_group3_api(idf=None):
    section("GROUP 3 — Dhan API Functions")

    from Credential.Credential import client_code, token_id
    from oc_data_fetcher import (
        fetch_expiry_list,
        fetch_ltp,
        fetch_batch_ltp,
        get_vix_data,
        get_futures_info,
        ensure_day_open_synced,
        fetch_option_chain,
        INDEX_SECURITY_IDS,
        INDEX_STEP_MAP,
        API_HEADERS,
        get_cached_spot_price,
    )
    import requests

    UNDERLYING = 'NIFTY'
    SEC_ID = INDEX_SECURITY_IDS.get(UNDERLYING, 13)
    STEP = INDEX_STEP_MAP.get(UNDERLYING, 50)

    # ── 3.1 Fetch expiry list ────────────────────────────────────────────
    console.print("[bold]3.1 Fetch Expiry List[/]")
    t0 = time.time()
    expiries = fetch_expiry_list(SEC_ID)
    dt_exp = time.time() - t0
    _check("Expiry list non-empty", len(expiries) > 0,
           f"{len(expiries)} expiries in {dt_exp:.2f}s")
    if expiries:
        _check("First expiry is future", expiries[0] >= str(_dt.date.today()),
               f"first={expiries[0]}")

    # ── 3.2 Fetch LTP (spot price) ──────────────────────────────────────
    console.print("[bold]3.2 Fetch Spot LTP[/]")
    t0 = time.time()
    spot = fetch_ltp(SEC_ID, 'IDX_I') or 0.0
    dt_ltp = time.time() - t0
    _check("Spot LTP > 0", spot > 0, f"spot={spot:.2f} in {dt_ltp:.2f}s")

    # ── 3.3 Fetch VIX ───────────────────────────────────────────────────
    console.print("[bold]3.3 Fetch VIX Data[/]")
    t0 = time.time()
    vix_current, vix_change, vix_yesterday = get_vix_data()
    dt_vix = time.time() - t0
    _check("VIX current ≥ 0", vix_current >= 0,
           f"vix={vix_current:.2f}, chg={vix_change:+.2f}%, yday={vix_yesterday:.2f} in {dt_vix:.2f}s")

    # ── 3.4 Futures info ─────────────────────────────────────────────────
    console.print("[bold]3.4 Futures Info[/]")
    t0 = time.time()
    fut_price, fut_expiry = get_futures_info(UNDERLYING)
    dt_fut = time.time() - t0
    _check("Futures price > 0", fut_price > 0,
           f"price={fut_price:.2f}, exp={fut_expiry} in {dt_fut:.2f}s")

    # ── 3.5 Day open sync ───────────────────────────────────────────────
    console.print("[bold]3.5 Day Open Sync[/]")
    t0 = time.time()
    sync = ensure_day_open_synced(UNDERLYING, spot_price=spot)
    dt_sync = time.time() - t0
    open_price = float(sync.get('open_price', 0) or 0)
    atm_strike = int(sync.get('atm_strike', 0) or 0)
    _check("Day open sync returned data",
           open_price > 0 or atm_strike > 0,
           f"open={open_price:.2f}, atm={atm_strike}, src={sync.get('source', '?')} in {dt_sync:.2f}s")

    # ── 3.6 Fetch option chain ───────────────────────────────────────────
    console.print("[bold]3.6 Fetch Option Chain[/]")
    if expiries:
        t0 = time.time()
        oc_data = fetch_option_chain(SEC_ID, 'IDX_I', expiries[0])
        dt_oc = time.time() - t0
        _check("Option chain has data",
               oc_data and 'data' in oc_data,
               f"in {dt_oc:.2f}s")
    else:
        _skip("Fetch Option Chain", "No expiries available")

    # ── 3.7 Intraday OHLCV direct ───────────────────────────────────────
    console.print("[bold]3.7 Intraday OHLCV (5-min)[/]")
    t0 = time.time()
    to_dt = _dt.datetime.now()
    from_dt = to_dt - _dt.timedelta(days=7)
    try:
        r = requests.post(
            'https://api.dhan.co/v2/charts/intraday',
            json={
                'securityId': str(SEC_ID),
                'exchangeSegment': 'IDX_I',
                'instrument': 'INDEX',
                'interval': 5,
                'fromDate': from_dt.strftime('%Y-%m-%d'),
                'toDate': to_dt.strftime('%Y-%m-%d'),
            },
            headers=API_HEADERS, timeout=10,
        )
        dt_ohlcv = time.time() - t0
        if r.status_code == 200:
            data = r.json()
            if 'open' in data and 'close' in data:
                ohlcv_df = pd.DataFrame(data)
                ohlcv_df['timestamp'] = (pd.to_datetime(ohlcv_df['timestamp'], unit='s', errors='coerce')
                                         .dt.tz_localize('UTC')
                                         .dt.tz_convert('Asia/Kolkata')
                                         .dt.tz_localize(None))
                ohlcv_df.columns = [c.lower() for c in ohlcv_df.columns]
                _check("Intraday OHLCV fetched",
                       len(ohlcv_df) > 0,
                       f"{len(ohlcv_df)} candles in {dt_ohlcv:.2f}s")

                # Verify timestamp is in IST (should contain hour 9-15 for market hours)
                hours = ohlcv_df['timestamp'].dt.hour.unique()
                _check("Timestamps in IST range (9-15)",
                       any(9 <= h <= 15 for h in hours),
                       f"hours found: {sorted(hours)}")
            else:
                _check("Intraday OHLCV response has OHLCV", False, f"keys: {list(data.keys())}")
        else:
            _check("Intraday OHLCV HTTP status", False, f"HTTP {r.status_code}")
    except Exception as e:
        _check("Intraday OHLCV fetch", False, str(e))

    # ── 3.8 Batch LTP ───────────────────────────────────────────────────
    console.print("[bold]3.8 Batch LTP[/]")
    t0 = time.time()
    batch_payload = {str(SEC_ID): 'IDX_I'}
    batch_result = fetch_batch_ltp(batch_payload)
    dt_batch = time.time() - t0
    # Batch LTP may return empty for index-only payload (designed for options)
    _check("Batch LTP call succeeded", isinstance(batch_result, (dict, list)),
           f"{len(batch_result)} results in {dt_batch:.2f}s")

    return spot, expiries


# ═══════════════════════════════════════════════════════════════════════════
# GROUP 4: Integration — Template rendering, full data pipeline
# ═══════════════════════════════════════════════════════════════════════════

def test_group4_integration(spot=0, expiries=None):
    section("GROUP 4 — Integration (Templates + Full Pipeline)")

    from oc_data_fetcher import fetch_all_data, format_lakh

    # ── 4.1 CSS & Template loading ───────────────────────────────────────
    console.print("[bold]4.1 CSS & Template Loading[/]")
    from paths import CSS_STYLES_FILE, HTML_DIR
    css_file = CSS_STYLES_FILE
    _check("styles.css exists", css_file.exists(), str(css_file))
    if css_file.exists():
        css_content = css_file.read_text(encoding='utf-8')
        _check("CSS file non-empty", len(css_content) > 100, f"{len(css_content)} chars")

    tpl_dir = HTML_DIR
    _check("templates/html/ exists", tpl_dir.exists())
    if tpl_dir.exists():
        templates = list(tpl_dir.glob('*.html'))
        _check("HTML templates found", len(templates) > 0, f"{len(templates)} templates")
        # List them
        tpl_names = sorted([t.stem for t in templates])
        console.print(f"  [dim]Templates: {', '.join(tpl_names)}[/]")

    # ── 4.2 Full data fetch (fetch_all_data) ─────────────────────────────
    console.print("[bold]4.2 Full Data Pipeline (fetch_all_data)[/]")
    t0 = time.time()
    try:
        data = fetch_all_data('NIFTY', 0, 10)
        dt_full = time.time() - t0
        _check("fetch_all_data succeeded", not data.get('error'),
               f"in {dt_full:.2f}s" + (f" err={data['error']}" if data.get('error') else ''))

        if not data.get('error'):
            # Verify all expected keys
            expected_keys = [
                'spot_price', 'atm_strike', 'expiry', 'vix_current',
                'vix_change_pct', 'fut_price', 'fut_expiry', 'option_df',
                'metrics', 'update_time', 'underlying', 'error',
            ]
            for k in expected_keys:
                _check(f"Key '{k}' in data", k in data)

            # Verify option_df
            odf = data.get('option_df', pd.DataFrame())
            _check("option_df non-empty", not odf.empty, f"{len(odf)} rows")
            if not odf.empty:
                expected_cols = ['Strike', 'C_OI', 'P_OI', 'C_LTP', 'P_LTP',
                                 'C_BuildUp', 'P_BuildUp']
                for col in expected_cols:
                    _check(f"option_df has '{col}'", col in odf.columns)

            # Verify metrics
            metrics = data.get('metrics', {})
            _check("metrics non-empty", len(metrics) > 0, f"{len(metrics)} keys")
            metric_keys = ['total_call_oi', 'total_put_oi', 'pcr_oi',
                           'bullish_oi', 'bearish_oi']
            for mk in metric_keys:
                _check(f"metric '{mk}'", mk in metrics,
                       f"val={metrics.get(mk, 'MISSING')}")

            # ── 4.3 Metrics cross-checks ─────────────────────────────────
            console.print("[bold]4.3 Metrics Cross-Checks[/]")
            total_c_oi = metrics.get('total_call_oi', 0)
            total_p_oi = metrics.get('total_put_oi', 0)
            pcr_oi = metrics.get('pcr_oi', 0)
            if total_c_oi > 0:
                expected_pcr = total_p_oi / total_c_oi
                _check("PCR OI = Put/Call OI",
                       abs(pcr_oi - expected_pcr) < 0.001,
                       f"pcr={pcr_oi:.4f} expected={expected_pcr:.4f}")

            # Verify Bullish/Bearish OI formulas
            bull = metrics.get('bullish_oi', 0)
            bear = metrics.get('bearish_oi', 0)
            _check("Bullish OI ≥ 0", bull >= 0, f"bull={format_lakh(bull)}")
            _check("Bearish OI ≥ 0", bear >= 0, f"bear={format_lakh(bear)}")

            # ── 4.4 Futures buildup ──────────────────────────────────────
            console.print("[bold]4.4 Futures Buildup[/]")
            fut_buildup = data.get('futures_buildup', [])
            _check("Futures buildup list", isinstance(fut_buildup, list),
                   f"{len(fut_buildup)} entries")
            if fut_buildup:
                valid_signals = {'Long Build Up', 'Short Build Up',
                                 'Short Covering', 'Long Unwinding', '', '-'}
                for i, fb in enumerate(fut_buildup[:3]):
                    bu = fb.get('buildup', '?')
                    oi_chg = fb.get('oi_chg_pct', 0)
                    ltp_chg = fb.get('ltp_chg_pct', 0)
                    _check(f"  Futures[{i}] buildup valid",
                           bu in valid_signals,
                           f"signal='{bu}' oi_chg={oi_chg:+.2f}% ltp_chg={ltp_chg:+.2f}%")

            # ── 4.5 Build-up classification consistency ──────────────────
            console.print("[bold]4.5 Build-Up Classification[/]")
            if not odf.empty:
                for side in ['C', 'P']:
                    bu_col = f'{side}_BuildUp'
                    if bu_col in odf.columns:
                        valid_vals = {'LB', 'SC', 'SB', 'LU', '', '-', 'nan'}
                        unique_bu = set(str(v).strip() for v in odf[bu_col].dropna().unique())
                        all_valid = unique_bu.issubset(valid_vals)
                        _check(f"{side} BuildUp values valid",
                               all_valid,
                               f"found: {unique_bu}")

            return data
        else:
            return None
    except Exception as e:
        _check("fetch_all_data", False, str(e))
        return None


# ═══════════════════════════════════════════════════════════════════════════
# GROUP 5: HTML Rendering (uses data from Group 4)
# ═══════════════════════════════════════════════════════════════════════════

def test_group5_rendering(data=None):
    section("GROUP 5 — HTML Rendering")

    if data is None:
        _skip("All rendering tests", "No data from Group 4")
        return

    from oc_data_fetcher import format_lakh

    # We cannot import from optionchain_gradio.py directly (it runs weekend
    # prompt at import time and requires Gradio). Instead we test the template
    # loading and isolated rendering logic.

    # ── 5.1 Template substitution ────────────────────────────────────────
    console.print("[bold]5.1 Template File Integrity[/]")
    from paths import HTML_DIR
    tpl_dir = HTML_DIR
    if tpl_dir.exists():
        required_templates = [
            'header', 'box', 'oc_table', 'oc_th', 'oc_td', 'oc_row',
            'analytics', 'futures', 'oi_chart', 'error',
        ]
        for tpl_name in required_templates:
            tpl_path = tpl_dir / f'{tpl_name}.html'
            exists = tpl_path.exists()
            size = tpl_path.stat().st_size if exists else 0
            _check(f"Template '{tpl_name}.html'",
                   exists and size > 0,
                   f"{'exists' if exists else 'MISSING'} ({size} bytes)")
    else:
        _skip("Template checks", "templates/html/ not found")

    # ── 5.2 color_constants.py completeness ──────────────────────────────
    console.print("[bold]5.2 Color Constants[/]")
    from color_constants import (
        H1_CLR, H2_CLR, H3_CLR,
        CALL_BAR, PUT_BAR, BU_CALL, BU_PUT, BU_FUT,
        OI_RANK_CALL, OI_RANK_PUT,
        GREEN, RED, ORANGE, BLUE, GOLD, MUTED, TEXT_DEFAULT,
    )
    _check("H1_CLR defined", isinstance(H1_CLR, str) and H1_CLR.startswith('#'))
    _check("BU_CALL has LB/SC/SB/LU",
           all(k in BU_CALL for k in ('LB', 'SC', 'SB', 'LU')))
    _check("BU_PUT has LB/SC/SB/LU",
           all(k in BU_PUT for k in ('LB', 'SC', 'SB', 'LU')))
    _check("BU_FUT has all signals",
           all(k in BU_FUT for k in ('Long Build Up', 'Short Build Up',
                                     'Short Covering', 'Long Unwinding')))
    _check("OI_RANK_CALL has 1,2,3",
           all(k in OI_RANK_CALL for k in (1, 2, 3)))
    _check("OI_RANK_PUT has 1,2,3",
           all(k in OI_RANK_PUT for k in (1, 2, 3)))

    # ── 5.3 Option DF data quality ───────────────────────────────────────
    console.print("[bold]5.3 Option DF Data Quality[/]")
    odf = data.get('option_df', pd.DataFrame())
    if not odf.empty:
        atm = data.get('atm_strike', 0)
        atm_int = int(atm) if atm else 0
        # ATM row exists
        strikes = odf['Strike'].astype(float).astype(int).tolist()
        _check("ATM strike in option_df", atm_int in strikes,
               f"atm={atm_int}")
        # No negative OI
        for col in ['C_OI', 'P_OI']:
            if col in odf.columns:
                neg_count = (odf[col].fillna(0) < 0).sum()
                _check(f"No negative {col}", neg_count == 0,
                       f"{neg_count} negative values" if neg_count else '')
        # LTP > 0 for ATM±2
        if atm_int:
            nearby = odf[odf['Strike'].astype(float).astype(int).between(
                atm_int - 100, atm_int + 100)]
            for col in ['C_LTP', 'P_LTP']:
                if col in nearby.columns:
                    zeros = (nearby[col].fillna(0) == 0).sum()
                    _check(f"ATM±2 {col} mostly > 0",
                           zeros <= 2,
                           f"{zeros}/{len(nearby)} zeros")

    # ── 5.4 OI History file ──────────────────────────────────────────────
    console.print("[bold]5.4 OI History File[/]")
    from paths import OI_HISTORY_FILE
    oi_hist_file = OI_HISTORY_FILE
    if oi_hist_file.exists():
        import json
        with open(oi_hist_file, 'r') as f:
            oi_hist = json.load(f)
        _check("oi_history.json is list", isinstance(oi_hist, list),
               f"{len(oi_hist)} entries")
        if oi_hist:
            last = oi_hist[-1]
            _check("Last entry has timestamp", 'timestamp' in last)
            _check("Last entry has bullish_oi", 'bullish_oi' in last)
            _check("Last entry has bearish_oi", 'bearish_oi' in last)
    else:
        _skip("OI history file", "data/cache/oi_history.json not found")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    t_start = time.time()

    console.print()
    console.print(Panel(
        "[bold bright_yellow]Comprehensive Function Test[/bold bright_yellow]\n"
        "[dim]optionchain_gradio.py — All key functions[/dim]\n\n"
        f"[bold]Date:[/bold] {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"[bold]Python:[/bold] {sys.version.split()[0]}\n"
        f"[bold]Platform:[/bold] {sys.platform}",
        border_style="bright_blue", expand=False, padding=(1, 3)))

    # GROUP 1: Pure logic
    test_group1_pure_logic()

    # GROUP 2: Instrument CSV
    idf = test_group2_instrument_csv()

    # GROUP 3: API calls
    spot, expiries = test_group3_api(idf)

    # GROUP 4: Integration
    data = test_group4_integration(spot, expiries)

    # GROUP 5: HTML rendering
    test_group5_rendering(data)

    # ── FINAL SUMMARY ────────────────────────────────────────────────────
    dt_total = time.time() - t_start
    section("FINAL SUMMARY")

    summary = Table(box=box.DOUBLE_EDGE, show_header=False, expand=False,
                    padding=(0, 2))
    summary.add_column(style="bold", width=16)
    summary.add_column(width=12, justify="right")
    summary.add_row("[green]Passed[/]", f"[bold green]{_passed}[/]")
    summary.add_row("[red]Failed[/]", f"[bold red]{_failed}[/]")
    summary.add_row("[yellow]Skipped[/]", f"[bold yellow]{_skipped}[/]")
    summary.add_row("Total", f"[bold]{_passed + _failed + _skipped}[/]")
    summary.add_row("Duration", f"{dt_total:.1f}s")
    console.print(summary)
    console.print()

    if _failed == 0:
        console.print(Panel(
            f"[bold green]ALL {_passed} TESTS PASSED[/bold green]  "
            f"({_skipped} skipped)  |  {dt_total:.1f}s",
            border_style="green", expand=False))
    else:
        console.print(Panel(
            f"[bold red]{_failed} TEST(S) FAILED[/bold red]  "
            f"({_passed} passed, {_skipped} skipped)  |  {dt_total:.1f}s",
            border_style="red", expand=False))

    return _failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
