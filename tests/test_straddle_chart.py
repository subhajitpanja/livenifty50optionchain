"""
Test 15-Min Straddle Chart Logic — Direct Dhan API (no Tradehull)
==================================================================
Run:  python optionchain/test_straddle_chart.py
      (from workspace root with venv active)

Uses the same direct Dhan API approach as optionchain_gradio.py:
  1. Get day-open strike via ensure_day_open_synced()
  2. Fetch expiry list from Dhan /v2/optionchain/expirylist
  3. Resolve CE/PE security IDs from instrument CSV
  4. Fetch 15-min intraday OHLCV via /v2/charts/intraday
  5. Merge CE+PE into straddle, compute VWAP + RSI
  6. Build Plotly figure with rich logging
"""

import sys
import os
import time
import datetime as _dt
import requests

import pandas as pd
import plotly.graph_objects as go

from pathlib import Path

# ── path setup ──────────────────────────────────────────────────────────────
_here = Path(__file__).resolve().parent          # tests/
_oc_dir = _here.parent                            # project root
for _p in [str(_here), str(_oc_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich import box

from Credential.Credential import client_code, token_id
from oc_data_fetcher import (
    ensure_day_open_synced,
    fetch_expiry_list,
    INDEX_SECURITY_IDS,
    INDEX_STEP_MAP,
    API_HEADERS,
    get_cached_spot_price,
)

console = Console(force_terminal=True)

UNDERLYING = 'NIFTY'
STEP = INDEX_STEP_MAP.get(UNDERLYING, 50)


from paths import INSTRUMENTS_DIR

# ── helpers (same as optionchain_gradio.py) ─────────────────────────────────
def _load_instrument_df():
    today_str = _dt.date.today().strftime('%Y-%m-%d')
    fname = f'all_instrument {today_str}.csv'
    csv_path = INSTRUMENTS_DIR / fname
    if not csv_path.exists():
        candidates = sorted(INSTRUMENTS_DIR.glob('all_instrument *.csv'), reverse=True)
        csv_path = candidates[0] if candidates else None
    if csv_path and csv_path.exists():
        df = pd.read_csv(csv_path, low_memory=False)
        df['SEM_EXPIRY_DATE'] = pd.to_datetime(df['SEM_EXPIRY_DATE'], errors='coerce')
        console.print(f"[dim]\\[Instrument] Loaded {csv_path.name} ({len(df)} rows)[/]")
        return df
    console.print("[yellow]\\[Instrument] No instrument CSV found[/]")
    return None


def _resolve_ce_pe_symbols(idf, underlying, expiry_date_str, strike):
    mask = (
        (idf['SEM_EXM_EXCH_ID'] == 'NSE') &
        (idf['SEM_TRADING_SYMBOL'].str.startswith(f'{underlying}-', na=False)) &
        (idf['SEM_EXPIRY_DATE'].dt.date.astype(str) == expiry_date_str) &
        (idf['SEM_STRIKE_PRICE'] == float(strike))
    )
    filtered = idf[mask]
    ce_rows = filtered[filtered['SEM_OPTION_TYPE'] == 'CE']
    pe_rows = filtered[filtered['SEM_OPTION_TYPE'] == 'PE']
    ce_sec_id = str(int(ce_rows.iloc[-1]['SEM_SMST_SECURITY_ID'])) if not ce_rows.empty else None
    pe_sec_id = str(int(pe_rows.iloc[-1]['SEM_SMST_SECURITY_ID'])) if not pe_rows.empty else None
    ce_sym = ce_rows.iloc[-1]['SEM_CUSTOM_SYMBOL'] if not ce_rows.empty else None
    pe_sym = pe_rows.iloc[-1]['SEM_CUSTOM_SYMBOL'] if not pe_rows.empty else None
    return ce_sym, pe_sym, ce_sec_id, pe_sec_id


def _fetch_option_intraday(security_id, interval=15, label=''):
    to_dt = _dt.datetime.now()
    from_dt = to_dt - _dt.timedelta(days=7)
    payload = {
        'securityId': str(security_id),
        'exchangeSegment': 'NSE_FNO',
        'instrument': 'OPTIDX',
        'interval': int(interval),
        'oi': True,
        'fromDate': from_dt.strftime('%Y-%m-%d %H:%M:%S'),
        'toDate': to_dt.strftime('%Y-%m-%d %H:%M:%S'),
    }
    r = requests.post('https://api.dhan.co/v2/charts/intraday',
                       json=payload, headers=API_HEADERS, timeout=10)
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
                console.print(f"[dim]\\[Data] {label} → {len(df)} candles[/]")
                return df
    console.print(f"[yellow]\\[Data] {label} → HTTP {r.status_code}[/]")
    return pd.DataFrame()


def _calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=1).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan')).fillna(float('inf'))
    return (100 - (100 / (1 + rs))).round(2)


# ══════════════════════════════════════════════════════════════════════════
# MAIN TEST
# ══════════════════════════════════════════════════════════════════════════
def run_test():
    console.print()
    console.print(Panel(
        "[bold yellow]15-Min Straddle Chart Test[/bold yellow]\n"
        "[dim]Direct Dhan API — no Tradehull dependency[/dim]",
        border_style="blue", expand=False))
    console.print()

    results = Table(title="Test Steps", box=box.ROUNDED, show_header=True,
                    header_style="bold cyan", expand=False)
    results.add_column("Step", style="bold", width=6, justify="center")
    results.add_column("Description", width=40)
    results.add_column("Result", width=50)
    results.add_column("Status", width=8, justify="center")

    all_pass = True

    # Step 1: Day open sync
    sync = ensure_day_open_synced(UNDERLYING)
    open_price = float(sync.get('open_price', 0) or 0)
    strike = int(sync.get('atm_strike', 0) or 0)
    source = sync.get('source', '?')
    ok = strike > 0
    if not ok:
        all_pass = False
    results.add_row("1", "Day Open Sync",
                    f"Open={open_price:,.2f}  Strike={strike}  Src={source}",
                    "[green]PASS[/]" if ok else "[red]FAIL[/]")

    if not strike:
        # Fallback: use cached spot for ATM
        spot = get_cached_spot_price(UNDERLYING)
        if spot > 0:
            strike = int(round(spot / STEP) * STEP)
            console.print(f"[yellow]\\[Fallback] Using cached spot {spot:.2f} → ATM {strike}[/]")
        else:
            results.add_row("–", "ABORT", "No strike available", "[red]FAIL[/]")
            console.print(results)
            return

    # Step 2: Fetch expiry list
    sec_id = INDEX_SECURITY_IDS.get(UNDERLYING, 13)
    expiries = fetch_expiry_list(sec_id)
    ok = len(expiries) > 0
    if not ok:
        all_pass = False
    results.add_row("2", "Expiry List",
                    f"{len(expiries)} expiries  (next: {expiries[:2]})" if expiries else "EMPTY",
                    "[green]PASS[/]" if ok else "[red]FAIL[/]")

    if not expiries:
        console.print(results)
        return

    expiry_date = expiries[0]

    # Step 3: Resolve CE/PE from instrument CSV
    idf = _load_instrument_df()
    ce_sym, pe_sym, ce_sec_id, pe_sec_id = None, None, None, None
    if idf is not None:
        ce_sym, pe_sym, ce_sec_id, pe_sec_id = _resolve_ce_pe_symbols(
            idf, UNDERLYING, expiry_date, strike)
    ok = ce_sec_id is not None and pe_sec_id is not None
    if not ok:
        all_pass = False
    results.add_row("3", "Resolve CE/PE Symbols",
                    f"CE={ce_sym}  PE={pe_sym}" if ok else "NOT FOUND",
                    "[green]PASS[/]" if ok else "[red]FAIL[/]")

    if not ok:
        console.print(results)
        return

    # Step 4: Fetch 15-min intraday data
    ce_df = _fetch_option_intraday(ce_sec_id, 15, label=f'CE {strike}')
    pe_df = _fetch_option_intraday(pe_sec_id, 15, label=f'PE {strike}')
    ok = not ce_df.empty and not pe_df.empty
    if not ok:
        all_pass = False
    results.add_row("4", "Fetch 15-min Intraday",
                    f"CE={len(ce_df)} rows, PE={len(pe_df)} rows",
                    "[green]PASS[/]" if ok else "[red]FAIL[/]")

    if not ok:
        console.print(results)
        return

    # Step 5: Filter to latest trading day
    ce_dates = ce_df['timestamp'].astype(str).str[:10]
    today_str = str(_dt.date.today())
    if today_str in set(ce_dates):
        use_date = today_str
    else:
        use_date = ce_dates.max()
        console.print(f"[yellow]No today data, using latest: {use_date}[/]")

    ce_today = ce_df[ce_dates == use_date].copy()
    pe_dates = pe_df['timestamp'].astype(str).str[:10]
    pe_today = pe_df[pe_dates == use_date].copy()
    ok = not ce_today.empty and not pe_today.empty
    if not ok:
        all_pass = False
    results.add_row("5", f"Filter to {use_date}",
                    f"CE={len(ce_today)} candles, PE={len(pe_today)} candles",
                    "[green]PASS[/]" if ok else "[red]FAIL[/]")

    if not ok:
        console.print(results)
        return

    # Step 6: Merge & compute straddle
    merged = pd.merge(
        ce_today[['timestamp', 'open', 'high', 'low', 'close', 'volume']].rename(
            columns={'open': 'ce_o', 'high': 'ce_h', 'low': 'ce_l',
                     'close': 'ce_c', 'volume': 'ce_v'}),
        pe_today[['timestamp', 'open', 'high', 'low', 'close', 'volume']].rename(
            columns={'open': 'pe_o', 'high': 'pe_h', 'low': 'pe_l',
                     'close': 'pe_c', 'volume': 'pe_v'}),
        on='timestamp', how='inner',
    )
    merged['s_close'] = merged['ce_c'] + merged['pe_c']
    merged['s_open'] = merged['ce_o'] + merged['pe_o']

    # Per-leg VWAP
    ce_tp = (merged['ce_h'] + merged['ce_l'] + merged['ce_c']) / 3
    pe_tp = (merged['pe_h'] + merged['pe_l'] + merged['pe_c']) / 3
    ce_cum_tpv = (ce_tp * merged['ce_v'].fillna(0)).cumsum()
    ce_cum_vol = merged['ce_v'].fillna(0).cumsum().replace(0, float('nan'))
    pe_cum_tpv = (pe_tp * merged['pe_v'].fillna(0)).cumsum()
    pe_cum_vol = merged['pe_v'].fillna(0).cumsum().replace(0, float('nan'))
    merged['vwap'] = (ce_cum_tpv / ce_cum_vol) + (pe_cum_tpv / pe_cum_vol)
    merged['rsi'] = _calc_rsi(merged['s_close'], 14)

    opening_straddle = float(merged['s_open'].iloc[0])
    current_straddle = float(merged['s_close'].iloc[-1])
    pnl = current_straddle - opening_straddle
    pnl_pct = (pnl / opening_straddle * 100) if opening_straddle > 0 else 0
    current_rsi = float(merged['rsi'].dropna().iloc[-1]) if not merged['rsi'].dropna().empty else 0

    ok = len(merged) > 0
    if not ok:
        all_pass = False
    results.add_row("6", "Merge + Straddle + VWAP + RSI",
                    f"{len(merged)} merged candles",
                    "[green]PASS[/]" if ok else "[red]FAIL[/]")

    # Step 7: Build Plotly figure
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged['timestamp'], y=merged['s_close'],
        mode='lines+markers', name=f'Straddle {strike}',
        line=dict(color='#4fc3f7', width=3),
    ))
    fig.add_trace(go.Scatter(
        x=merged['timestamp'], y=merged['vwap'],
        mode='lines', name='VWAP',
        line=dict(color='#ff9800', width=2, dash='dot'),
    ))
    fig.add_hline(y=opening_straddle, line_dash='dash', line_color='#ffd700', line_width=2)
    fig.update_layout(
        title=f"15-Min Straddle | Strike {strike} | Exp {expiry_date}",
        paper_bgcolor='#0e1117', plot_bgcolor='#0e1117',
        font=dict(color='#cfd8dc'), height=480,
    )
    ok = len(fig.data) >= 2
    if not ok:
        all_pass = False
    results.add_row("7", "Build Plotly Figure",
                    f"{len(fig.data)} traces, height={fig.layout.height}",
                    "[green]PASS[/]" if ok else "[red]FAIL[/]")

    console.print(results)
    console.print()

    # ── Summary values ──
    summary = Table(title="Straddle Values", box=box.SIMPLE_HEAVY,
                    header_style="bold yellow", expand=False)
    summary.add_column("Metric", style="bold", width=22)
    summary.add_column("Value", width=20, justify="right")
    pnl_clr = "green" if pnl <= 0 else "red"
    summary.add_row("Strike", f"{strike:,}")
    summary.add_row("Expiry", expiry_date)
    summary.add_row("Opening Straddle", f"₹{opening_straddle:,.2f}")
    summary.add_row("Current Straddle", f"₹{current_straddle:,.2f}")
    summary.add_row("PnL", f"[{pnl_clr}]{pnl:+.2f} ({pnl_pct:+.1f}%)[/]")
    summary.add_row("RSI(14)", f"{current_rsi:.1f}")
    summary.add_row("VWAP (last)", f"₹{float(merged['vwap'].iloc[-1]):,.2f}" if not merged['vwap'].dropna().empty else "N/A")
    summary.add_row("Candles", f"{len(merged)}")
    console.print(summary)
    console.print()

    if all_pass:
        console.print(Panel("[bold green]ALL STEPS PASSED[/bold green]",
                            border_style="green", expand=False))
    else:
        console.print(Panel("[bold red]SOME STEPS FAILED — see table above[/bold red]",
                            border_style="red", expand=False))


if __name__ == '__main__':
    run_test()
