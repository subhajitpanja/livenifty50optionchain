"""
Rich-print validation script for NIFTY Multi-Timeframe RSI & MACD/Signal values.

Fetches OHLCV data from Dhan API, computes RSI(14) and MACD(12,26,9) locally,
and logs them with rich formatting for visual comparison.

Runs every 60s for 5 minutes (5 iterations) so you can compare side-by-side
with the Gradio dashboard values.

Usage:
    cd "D:\Algo trading mentorship"
    python optionchain/test_mtf_indicators_richprint.py
"""

import sys, os, time, datetime as _dt

# ── path setup ──────────────────────────────────────────────────────────────
_here = os.path.dirname(os.path.abspath(__file__))   # tests/
_oc_dir = os.path.dirname(_here)                      # project root
for p in (_here, _oc_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

import pandas as pd
import requests

# ── rich imports ────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.text import Text
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("[WARN] 'rich' not installed — falling back to plain print.")

# ── credentials & API config ───────────────────────────────────────────────
from Credential.Credential import client_code, token_id

INDEX_SECURITY_IDS = {'NIFTY': 13, 'BANKNIFTY': 25, 'FINNIFTY': 27, 'MIDCPNIFTY': 442}
API_HEADERS = {
    'access-token': token_id,
    'client-id':    str(client_code),
    'Content-Type': 'application/json',
}

UNDERLYING = 'NIFTY'
ITERATIONS = 5          # run 5 cycles
INTERVAL_S = 60         # seconds between cycles


# ════════════════════════════════════════════════════════════════════════════
# Indicator helpers (same formulas as optionchain_gradio.py)
# ════════════════════════════════════════════════════════════════════════════

def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Standard Wilder-smoothed RSI."""
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=1).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan')).fillna(float('inf'))
    return (100 - (100 / (1 + rs))).round(2)


def calc_macd(series: pd.Series, fast=12, slow=26, signal=9):
    """MACD line, signal line, histogram."""
    ema_fast    = series.ewm(span=fast, adjust=False).mean()
    ema_slow    = series.ewm(span=slow, adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


# ════════════════════════════════════════════════════════════════════════════
# Data fetchers
# ════════════════════════════════════════════════════════════════════════════

def fetch_intraday(underlying: str, interval: int) -> pd.DataFrame:
    """Fetch 5-day intraday OHLCV from Dhan /charts/intraday."""
    sec_id = INDEX_SECURITY_IDS.get(underlying, 0)
    if not sec_id:
        return pd.DataFrame()
    to_date   = _dt.date.today().strftime('%Y-%m-%d')
    from_date = (_dt.date.today() - _dt.timedelta(days=7)).strftime('%Y-%m-%d')
    try:
        r = requests.post(
            "https://api.dhan.co/v2/charts/intraday",
            json={
                'securityId': str(sec_id), 'exchangeSegment': 'IDX_I',
                'instrument': 'INDEX', 'interval': interval,
                'fromDate': from_date, 'toDate': to_date,
            },
            headers=API_HEADERS, timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if 'open' in data and 'close' in data and 'timestamp' in data:
                df = pd.DataFrame(data)
                df['timestamp'] = (pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
                                   .dt.tz_localize('UTC')
                                   .dt.tz_convert('Asia/Kolkata')
                                   .dt.tz_localize(None))
                df.columns = [c.lower() for c in df.columns]
                return df
    except Exception as e:
        print(f"[ERR] Intraday ({interval}m) fetch: {e}")
    return pd.DataFrame()


def fetch_daily(underlying: str) -> pd.DataFrame:
    """Fetch 1-year daily OHLCV from Dhan /charts/historical + today partial."""
    sec_id = INDEX_SECURITY_IDS.get(underlying, 0)
    if not sec_id:
        return pd.DataFrame()
    to_date   = _dt.date.today().strftime('%Y-%m-%d')
    from_date = (_dt.date.today() - _dt.timedelta(days=365)).strftime('%Y-%m-%d')
    try:
        r = requests.post(
            "https://api.dhan.co/v2/charts/historical",
            json={
                'securityId': str(sec_id), 'exchangeSegment': 'IDX_I',
                'instrument': 'INDEX', 'expiryCode': 0,
                'fromDate': from_date, 'toDate': to_date,
            },
            headers=API_HEADERS, timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if 'open' in data and 'close' in data and 'timestamp' in data:
                df = pd.DataFrame(data)
                df['timestamp'] = (pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
                                   .dt.tz_localize('UTC')
                                   .dt.tz_convert('Asia/Kolkata')
                                   .dt.tz_localize(None))
                df.columns = [c.lower() for c in df.columns]

                # Append today's partial candle from 5-min intraday
                try:
                    intra = fetch_intraday(underlying, 5)
                    if intra is not None and not intra.empty:
                        today = _dt.date.today()
                        tc = intra[intra['timestamp'].dt.date == today]
                        if not tc.empty:
                            today_row = pd.DataFrame([{
                                'timestamp': pd.Timestamp(today),
                                'open':   float(tc.iloc[0]['open']),
                                'high':   float(tc['high'].max()),
                                'low':    float(tc['low'].min()),
                                'close':  float(tc.iloc[-1]['close']),
                                'volume': int(tc['volume'].sum()),
                            }])
                            df = pd.concat([df, today_row], ignore_index=True)
                except Exception:
                    pass
                return df
    except Exception as e:
        print(f"[ERR] Daily fetch: {e}")
    return pd.DataFrame()


def resample_ohlcv(df: pd.DataFrame, target_minutes: int) -> pd.DataFrame:
    """Resample lower-TF OHLCV to higher TF."""
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    resampled = df.resample(f'{target_minutes}min', origin='start').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum',
    }).dropna(subset=['open']).reset_index()
    return resampled


# ════════════════════════════════════════════════════════════════════════════
# Main validation loop
# ════════════════════════════════════════════════════════════════════════════

TIMEFRAMES = [
    ('5 Min',   5,    None, None),
    ('10 Min',  None, 5,    10),
    ('15 Min',  15,   None, None),
    ('30 Min',  None, 15,   30),
    ('60 Min',  60,   None, None),
    ('Daily',   None, None, None),
]


def _compute_indicators(label, api_interval, resample_src, resample_min):
    """Return dict with candle_count, last_close, rsi, macd, signal, zone, ema34, ema61."""
    if label == 'Daily':
        df = fetch_daily(UNDERLYING)
    elif resample_src and resample_min:
        base = fetch_intraday(UNDERLYING, resample_src)
        df = resample_ohlcv(base, resample_min) if base is not None and not base.empty else pd.DataFrame()
    else:
        df = fetch_intraday(UNDERLYING, api_interval)

    if df is None or df.empty:
        return None

    close = df['close'].astype(float)
    n = len(close)

    rsi_series = calc_rsi(close, 14)
    rsi_val    = float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else 0

    macd_l, sig_l, hist_l = calc_macd(close)
    macd_val   = float(macd_l.dropna().iloc[-1]) if not macd_l.dropna().empty else 0
    signal_val = float(sig_l.dropna().iloc[-1])  if not sig_l.dropna().empty else 0

    if macd_val > 0 and signal_val > 0:
        zone = 'Positive'
    elif macd_val < 0 and signal_val < 0:
        zone = 'Negative'
    else:
        zone = 'Transition'

    ema34 = float(close.ewm(span=34, adjust=False).mean().iloc[-1])
    ema61 = float(close.ewm(span=61, adjust=False).mean().iloc[-1])

    # Also compute RSI/MACD on today-only data to show the difference
    if label != 'Daily' and 'timestamp' in df.columns:
        today_str = str(_dt.date.today())
        today_df = df[df['timestamp'].dt.date.astype(str) == today_str]
        if not today_df.empty:
            tc = today_df['close'].astype(float)
            rsi_today = float(calc_rsi(tc, 14).dropna().iloc[-1]) if len(tc) > 14 else None
            ml, sl, _ = calc_macd(tc)
            macd_today = float(ml.dropna().iloc[-1]) if not ml.dropna().empty else None
            sig_today  = float(sl.dropna().iloc[-1]) if not sl.dropna().empty else None
        else:
            rsi_today = macd_today = sig_today = None
    else:
        rsi_today = macd_today = sig_today = None

    # Show last 5 close values for debugging
    last5 = close.tail(5).tolist()

    return {
        'candles':     n,
        'last_close':  float(close.iloc[-1]),
        'last5':       last5,
        'rsi':         rsi_val,
        'macd':        macd_val,
        'signal':      signal_val,
        'zone':        zone,
        'ema34':       ema34,
        'ema61':       ema61,
        'rsi_today_only':  rsi_today,
        'macd_today_only': macd_today,
        'sig_today_only':  sig_today,
    }


def run_one_cycle(cycle_num: int):
    """Run one validation cycle and print results."""
    now_ist = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=5, minutes=30)))
    ts = now_ist.strftime('%Y-%m-%d %H:%M:%S IST')

    if HAS_RICH:
        console = Console()
        table = Table(
            title=f"[bold cyan]NIFTY Multi-TF Indicator Validation — Cycle {cycle_num}[/]  "
                  f"[dim]{ts}[/]",
            box=box.HEAVY_EDGE,
            show_lines=True,
            header_style="bold magenta",
            border_style="blue",
            expand=True,
        )

        table.add_column("TF",         justify="center", style="bold white",  width=8)
        table.add_column("Candles",     justify="center", style="dim",         width=8)
        table.add_column("Close",       justify="right",  style="yellow",      width=12)
        table.add_column("RSI(14)\nFull Data", justify="center", width=12)
        table.add_column("RSI(14)\nToday Only", justify="center", width=12)
        table.add_column("RSI\nDiff",   justify="center", width=8)
        table.add_column("MACD\nFull",  justify="center", width=12)
        table.add_column("Signal\nFull", justify="center", width=12)
        table.add_column("MACD\nToday", justify="center", width=12)
        table.add_column("Signal\nToday", justify="center", width=12)
        table.add_column("Zone",        justify="center", width=12)
        table.add_column("34-EMA",      justify="right",  width=12)
        table.add_column("61-EMA",      justify="right",  width=12)

        for label, api_int, rsrc, rmin in TIMEFRAMES:
            res = _compute_indicators(label, api_int, rsrc, rmin)
            if res is None:
                table.add_row(label, "—", *["—"] * 11)
                continue

            # Color RSI
            rsi = res['rsi']
            if rsi > 70:
                rsi_style = "bold green"
            elif rsi > 50:
                rsi_style = "green_yellow"
            elif rsi >= 30:
                rsi_style = "dark_orange"
            else:
                rsi_style = "bold red"

            # RSI diff
            rsi_today = res['rsi_today_only']
            if rsi_today is not None:
                diff = abs(rsi - rsi_today)
                diff_str = f"{diff:.2f}"
                diff_style = "bold red" if diff > 2 else ("yellow" if diff > 0.5 else "green")
            else:
                diff_str = "N/A"
                diff_style = "dim"

            # MACD color
            macd_style = "green" if res['macd'] > res['signal'] else "red"

            # Zone color
            zone_style = "green" if res['zone'] == 'Positive' else ("red" if res['zone'] == 'Negative' else "yellow")

            # EMA color
            ema_style = "green" if res['ema34'] > res['ema61'] else "red"

            table.add_row(
                label,
                str(res['candles']),
                f"₹{res['last_close']:,.2f}",
                f"[{rsi_style}]{rsi:.2f}[/]",
                f"[{rsi_style}]{rsi_today:.2f}[/]" if rsi_today is not None else "[dim]N/A[/]",
                f"[{diff_style}]{diff_str}[/]",
                f"[{macd_style}]{res['macd']:.2f}[/]",
                f"[{macd_style}]{res['signal']:.2f}[/]",
                f"[{macd_style}]{res['macd_today_only']:.2f}[/]" if res['macd_today_only'] is not None else "[dim]N/A[/]",
                f"[{macd_style}]{res['sig_today_only']:.2f}[/]" if res['sig_today_only'] is not None else "[dim]N/A[/]",
                f"[{zone_style}]{res['zone']}[/]",
                f"[{ema_style}]{res['ema34']:,.2f}[/]",
                f"[{ema_style}]{res['ema61']:,.2f}[/]",
            )

        console.print()
        console.print(table)

        # Also print last-5 close values per TF for forensic check
        detail_table = Table(
            title="[bold]Last 5 Close Values per Timeframe[/]",
            box=box.SIMPLE, header_style="bold", show_lines=False,
        )
        detail_table.add_column("TF", width=8)
        detail_table.add_column("Last 5 Closes", style="cyan")

        for label, api_int, rsrc, rmin in TIMEFRAMES:
            res = _compute_indicators(label, api_int, rsrc, rmin)
            if res is None:
                detail_table.add_row(label, "—")
            else:
                vals = ', '.join(f'{v:.2f}' for v in res['last5'])
                detail_table.add_row(label, vals)

        console.print(detail_table)

        # Highlight warning if RSI diff > 2 for any TF
        console.print()
        console.print(Panel(
            "[bold yellow]⚠  RSI Diff > 2.0 means today-only calculation is significantly off.\n"
            "   The 'Full Data' column uses all 5 days for EWM warm-up (CORRECT).\n"
            "   The 'Today Only' column uses only today's candles (INACCURATE for short sessions).\n\n"
            "   MACD(12,26,9) needs ≥26 candles to warm up; RSI(14) needs ≥14+ candles.\n"
            "   The Gradio dashboard EMA chart has been FIXED to use full multi-day data.[/]",
            title="[bold]Interpretation Guide[/]",
            border_style="yellow",
        ))
    else:
        # Plain print fallback
        print(f"\n{'='*100}")
        print(f"  NIFTY Multi-TF Indicator Validation — Cycle {cycle_num}  |  {ts}")
        print(f"{'='*100}")
        print(f"{'TF':<8} {'Candles':>8} {'Close':>12} {'RSI(Full)':>10} {'RSI(Today)':>11} "
              f"{'Diff':>6} {'MACD':>10} {'Signal':>10} {'Zone':>12} {'34-EMA':>12} {'61-EMA':>12}")
        print('-' * 120)
        for label, api_int, rsrc, rmin in TIMEFRAMES:
            res = _compute_indicators(label, api_int, rsrc, rmin)
            if res is None:
                print(f"{label:<8} {'No data':>8}")
                continue
            rt = f"{res['rsi_today_only']:.2f}" if res['rsi_today_only'] is not None else "N/A"
            diff = abs(res['rsi'] - res['rsi_today_only']) if res['rsi_today_only'] is not None else 0
            print(f"{label:<8} {res['candles']:>8} {res['last_close']:>12,.2f} {res['rsi']:>10.2f} "
                  f"{rt:>11} {diff:>6.2f} {res['macd']:>10.2f} {res['signal']:>10.2f} "
                  f"{res['zone']:>12} {res['ema34']:>12,.2f} {res['ema61']:>12,.2f}")


def main():
    if HAS_RICH:
        Console().print(Panel(
            f"[bold cyan]NIFTY Multi-Timeframe RSI & MACD Validation[/]\n\n"
            f"Underlying: [bold]{UNDERLYING}[/]\n"
            f"Iterations: {ITERATIONS} × {INTERVAL_S}s = {ITERATIONS * INTERVAL_S // 60} min\n"
            f"Timeframes: 5m, 10m, 15m, 30m, 60m, Daily\n\n"
            f"Compares: RSI(14) and MACD(12,26,9) from FULL data vs TODAY-only data.\n"
            f"Large 'RSI Diff' = warm-up error when using only today's candles.",
            title="[bold white]Test Configuration[/]",
            border_style="cyan",
        ))

    for i in range(1, ITERATIONS + 1):
        run_one_cycle(i)
        if i < ITERATIONS:
            if HAS_RICH:
                Console().print(f"\n[dim]⏳ Waiting {INTERVAL_S}s before next cycle... "
                                f"({ITERATIONS - i} remaining)[/]\n")
            else:
                print(f"\n⏳ Waiting {INTERVAL_S}s... ({ITERATIONS - i} remaining)\n")
            time.sleep(INTERVAL_S)

    if HAS_RICH:
        Console().print(Panel("[bold green]✅ Validation complete — all cycles finished.[/]",
                              border_style="green"))
    else:
        print("\n✅ Validation complete.")


if __name__ == '__main__':
    main()
