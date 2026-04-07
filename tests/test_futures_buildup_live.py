"""
Futures Buildup Live Data Diagnostic
=====================================
Professional diagnostic to verify the NIFTY FUTURE OI Build Up pipeline
fetches and displays LIVE data from the Dhan API -- not stale cache.

Checks:
  1. Instrument CSV -> futures security_ids are resolved correctly
  2. Dhan /v2/marketfeed/quote -> raw API response (field names, OI, LTP)
  3. Previous-day CSV -> prev_ltp / prev_oi loaded correctly
  4. Buildup calculation -> live vs cache comparison
  5. End-to-end fetch_all_data -> futures_buildup populated with live values
  6. All other live data feeds (spot, VIX, option chain) verified

Run:  python -m pytest tests/test_futures_buildup_live.py -s
  or: python tests/test_futures_buildup_live.py
"""
import sys
import os
import json
import time
import datetime
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
import io

# Force UTF-8 output to avoid Windows cp1252 encoding errors
_out = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
console = Console(file=_out, force_terminal=True)

# ===========================================================================
# Helpers
# ===========================================================================

def _section(title: str):
    console.print()
    console.rule(f"[bold cyan]{title}[/]", style="cyan")


def _pass(msg: str):
    console.print(f"  [green]PASS[/]  {msg}")


def _fail(msg: str):
    console.print(f"  [red]FAIL[/]  {msg}")


def _warn(msg: str):
    console.print(f"  [yellow]WARN[/]  {msg}")


def _info(msg: str):
    console.print(f"  [dim]INFO[/]  {msg}")


# ===========================================================================
# 1. Instrument Resolution
# ===========================================================================

def check_instruments():
    _section("1. Futures Instrument Resolution")
    from oc_data_fetcher import _load_futures_instruments, _futures_instruments_cache
    import oc_data_fetcher
    # Reset cache to force fresh load
    oc_data_fetcher._futures_instruments_cache = None

    instruments = _load_futures_instruments("NIFTY")
    if not instruments:
        _fail("No futures instruments found -- check instrument CSV exists")
        return []

    _pass(f"Found {len(instruments)} futures contracts")

    tbl = Table(title="Futures Instruments", box=box.SIMPLE_HEAVY, show_lines=False)
    tbl.add_column("Symbol", style="cyan")
    tbl.add_column("Expiry", style="yellow")
    tbl.add_column("Expiry Key", style="dim")
    tbl.add_column("Security ID", style="green", justify="right")
    for inst in instruments:
        sid = inst['security_id']
        sid_style = "green" if sid > 0 else "red bold"
        tbl.add_row(inst['symbol'], inst['expiry'], inst['expiry_key'],
                     f"[{sid_style}]{sid}[/]")
        if sid <= 0:
            _fail(f"Security ID = {sid} for {inst['symbol']} -- API calls will fail")

    console.print(tbl)
    return instruments


# ===========================================================================
# 2. Raw API Response
# ===========================================================================

def check_raw_api(instruments: list):
    _section("2. Raw Dhan /v2/marketfeed/quote API Response")
    from Credential.Credential import client_code, token_id

    security_ids = [inst['security_id'] for inst in instruments if inst['security_id'] > 0]
    if not security_ids:
        _fail("No valid security IDs to query")
        return {}

    url = "https://api.dhan.co/v2/marketfeed/quote"
    headers = {
        'access-token': token_id,
        'client-id': str(client_code),
        'Content-Type': 'application/json'
    }
    payload = {"NSE_FNO": security_ids}

    _info(f"POST {url}")
    _info(f"Payload: {json.dumps(payload)}")

    try:
        t0 = time.time()
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        dt = time.time() - t0
        _info(f"HTTP {resp.status_code} in {dt:.2f}s")
    except Exception as e:
        _fail(f"Request failed: {e}")
        return {}

    if resp.status_code != 200:
        _fail(f"Non-200 response: {resp.text[:500]}")
        return {}

    data = resp.json()
    _info(f"Top-level keys: {list(data.keys())}")

    if 'data' not in data:
        _fail(f"No 'data' key in response -- full response: {json.dumps(data, indent=2)[:1000]}")
        return {}

    _info(f"data keys: {list(data['data'].keys())}")

    if 'NSE_FNO' not in data['data']:
        _fail(f"No 'NSE_FNO' in data -- available: {list(data['data'].keys())}")
        _info(f"Full data: {json.dumps(data['data'], indent=2)[:1000]}")
        return {}

    quotes = data['data']['NSE_FNO']
    _pass(f"Got {len(quotes)} quote entries")

    # Show raw fields for each security_id
    tbl = Table(title="Raw API Quote Fields", box=box.SIMPLE_HEAVY)
    tbl.add_column("Security ID", style="cyan", justify="right")
    tbl.add_column("Fields", style="dim", max_width=80)
    tbl.add_column("last_price", style="green", justify="right")
    tbl.add_column("oi", justify="right")
    tbl.add_column("open_interest", justify="right")
    tbl.add_column("OI", justify="right")

    for sid_str, quote_data in quotes.items():
        if isinstance(quote_data, dict):
            fields = list(quote_data.keys())
            lp = quote_data.get('last_price', '--')
            oi = quote_data.get('oi', '--')
            open_interest = quote_data.get('open_interest', '--')
            OI = quote_data.get('OI', '--')
            tbl.add_row(sid_str, ", ".join(fields), str(lp), str(oi),
                        str(open_interest), str(OI))
        else:
            tbl.add_row(sid_str, f"type={type(quote_data).__name__}", str(quote_data),
                        "--", "--", "--")

    console.print(tbl)

    # Diagnose: which field actually holds OI?
    for sid_str, quote_data in quotes.items():
        if not isinstance(quote_data, dict):
            continue
        found_oi = False
        for key, val in quote_data.items():
            if 'oi' in key.lower() or 'interest' in key.lower():
                found_oi = True
                if val and val != 0:
                    _pass(f"  SID {sid_str}: {key} = {val} (live OI detected)")
                else:
                    _warn(f"  SID {sid_str}: {key} = {val} (zero -- market closed or stale)")
        if not found_oi:
            _fail(f"  SID {sid_str}: NO OI-related field found -- fields: {list(quote_data.keys())}")
        # Check LTP
        lp = quote_data.get('last_price', 0)
        if lp and float(lp) > 0:
            _pass(f"  SID {sid_str}: last_price = {lp} (live)")
        else:
            _warn(f"  SID {sid_str}: last_price = {lp} (zero or missing)")

    return quotes


# ===========================================================================
# 3. Previous Day Data
# ===========================================================================

def check_previous_data():
    _section("3. Previous Day Futures Data (CSV)")
    from oc_data_fetcher import load_previous_futures_data
    from paths import FUTURES_DIR

    prev = load_previous_futures_data("NIFTY")
    if not prev:
        _fail(f"No previous futures CSV found in {FUTURES_DIR}")
        return []

    _pass(f"Loaded {len(prev)} previous-day entries")

    tbl = Table(title="Previous Day Data", box=box.SIMPLE_HEAVY)
    tbl.add_column("Expiry", style="yellow")
    tbl.add_column("Expiry Key", style="dim")
    tbl.add_column("Prev LTP", style="green", justify="right")
    tbl.add_column("Prev OI", style="cyan", justify="right")

    for p in prev:
        ltp_style = "green" if p.get('prev_ltp', 0) > 0 else "red"
        oi_style = "cyan" if p.get('prev_oi', 0) > 0 else "red"
        tbl.add_row(
            p.get('expiry', '?'),
            p.get('expiry_key', '?'),
            f"[{ltp_style}]{p.get('prev_ltp', 0):,.2f}[/]",
            f"[{oi_style}]{p.get('prev_oi', 0):,}[/]",
        )
    console.print(tbl)
    return prev


# ===========================================================================
# 4. File Cache vs Live Comparison
# ===========================================================================

def check_cache_vs_live():
    _section("4. Futures Buildup: Cache vs Live")
    from oc_data_fetcher import (
        _load_futures_buildup_cache, get_futures_buildup_data,
        _last_valid_futures_buildup, LOT_SIZE_MAP
    )
    import oc_data_fetcher
    from paths import FUTURES_BUILDUP_CACHE_FILE

    # Load file cache
    cached = _load_futures_buildup_cache()
    if cached:
        _info(f"File cache: {FUTURES_BUILDUP_CACHE_FILE}")
        _pass(f"File cache has {len(cached)} entries")
        for c in cached:
            _info(f"  {c.get('expiry', '?')}: LTP={c.get('ltp', 0):,.2f}  "
                  f"OI={c.get('oi', 0):,}  buildup={c.get('buildup', '?')}")
    else:
        _warn("No file cache exists")

    # Reset in-memory cache to force fresh API call
    oc_data_fetcher._last_valid_futures_buildup = None
    oc_data_fetcher._prev_futures_cache = None

    _info("Forcing fresh API call (cleared in-memory caches)...")
    live = get_futures_buildup_data("NIFTY")

    if not live:
        _fail("get_futures_buildup_data returned empty")
        return

    _pass(f"Live result has {len(live)} entries")

    # Compare
    tbl = Table(title="Cache vs Live Comparison", box=box.DOUBLE_EDGE)
    tbl.add_column("Expiry", style="yellow")
    tbl.add_column("Field", style="dim")
    tbl.add_column("Cached", justify="right")
    tbl.add_column("Live", justify="right")
    tbl.add_column("Match?", justify="center")

    any_diff = False
    for i, entry in enumerate(live):
        cache_entry = cached[i] if (cached and i < len(cached)) else {}
        for field in ('ltp', 'oi', 'oi_chg_pct', 'ltp_chg_pct', 'buildup'):
            c_val = cache_entry.get(field, '--')
            l_val = entry.get(field, '--')
            if isinstance(c_val, float):
                c_str = f"{c_val:,.2f}"
            elif isinstance(c_val, int):
                c_str = f"{c_val:,}"
            else:
                c_str = str(c_val)
            if isinstance(l_val, float):
                l_str = f"{l_val:,.2f}"
            elif isinstance(l_val, int):
                l_str = f"{l_val:,}"
            else:
                l_str = str(l_val)

            match = c_val == l_val if cache_entry else False
            match_str = "[green]YES[/]" if match else "[red]DIFF[/]" if cache_entry else "[dim]N/A[/]"
            if not match and cache_entry:
                any_diff = True
            tbl.add_row(
                entry.get('expiry', '?') if field == 'ltp' else "",
                field, c_str, l_str, match_str
            )

    console.print(tbl)

    if any_diff:
        _pass("Live data DIFFERS from cache -- live updates are working")
    else:
        _warn("Live data is IDENTICAL to cache -- data may not be updating live")
        _warn("This is expected when market is closed (weekend/holiday/after hours)")

    # Show raw OI debug info
    lot_size = LOT_SIZE_MAP.get("NIFTY", 65)
    _info(f"Lot size (NIFTY): {lot_size}")
    for entry in live:
        _info(f"  {entry.get('expiry', '?')}: "
              f"oi_qty(raw)={entry.get('oi_qty', '?')}  "
              f"oi(contracts)={entry.get('oi', '?')}  "
              f"prev_oi={entry.get('prev_oi', '?')}  "
              f"lot_size={entry.get('lot_size', '?')}")


# ===========================================================================
# 5. End-to-End fetch_all_data
# ===========================================================================

def check_fetch_all_data():
    _section("5. End-to-End: fetch_all_data -> futures_buildup")
    from oc_data_fetcher import fetch_all_data

    _info("Calling fetch_all_data('NIFTY', 0, 15)...")
    t0 = time.time()
    data = fetch_all_data("NIFTY", 0, 15)
    dt = time.time() - t0
    _info(f"Completed in {dt:.2f}s")

    if data.get('error'):
        _fail(f"Error: {data['error']}")
        return data

    fb = data.get('futures_buildup', [])
    if not fb:
        _fail("futures_buildup is EMPTY in fetch_all_data result")
        return data

    _pass(f"futures_buildup has {len(fb)} entries")

    tbl = Table(title="fetch_all_data -> futures_buildup", box=box.DOUBLE_EDGE)
    tbl.add_column("Build Up", style="bold")
    tbl.add_column("OI Chg%", justify="right")
    tbl.add_column("OI (contracts)", justify="right")
    tbl.add_column("LTP Chg%", justify="right")
    tbl.add_column("LTP", justify="right", style="green")
    tbl.add_column("Expiry", style="yellow")

    for entry in fb:
        bu = entry.get('buildup', '?')
        bu_color = {
            'Long Build Up': 'green',
            'Short Build Up': 'red',
            'Short Covering': 'yellow',
            'Long Unwinding': 'magenta',
            'Market Closed': 'dim',
        }.get(bu, 'white')

        oi_c = entry.get('oi', 0)
        if oi_c >= 100_000:
            oi_disp = f"{oi_c/100_000:.2f} L"
        elif oi_c >= 1_000:
            oi_disp = f"{oi_c/1_000:.1f}K"
        else:
            oi_disp = f"{oi_c:,}"

        tbl.add_row(
            f"[{bu_color}]{bu}[/]",
            f"{entry.get('oi_chg_pct', 0):+.2f}%",
            oi_disp,
            f"{entry.get('ltp_chg_pct', 0):+.2f}%",
            f"{entry.get('ltp', 0):,.2f}",
            entry.get('expiry', '?'),
        )

    console.print(tbl)
    return data


# ===========================================================================
# 6. All Live Data Feeds Verification
# ===========================================================================

def check_all_feeds(data: dict):
    _section("6. All Live Data Feeds Verification")

    tbl = Table(title="Live Data Feed Status", box=box.DOUBLE_EDGE)
    tbl.add_column("Feed", style="cyan", min_width=25)
    tbl.add_column("Value", justify="right", min_width=15)
    tbl.add_column("Status", justify="center", min_width=10)
    tbl.add_column("Detail", style="dim", max_width=50)

    # Spot Price
    spot = data.get('spot_price', 0)
    tbl.add_row("Spot Price", f"{spot:,.2f}",
                "[green]LIVE[/]" if spot > 0 else "[red]DEAD[/]",
                "IDX_I segment via LTP API")

    # VIX
    vix = data.get('vix_current', 0)
    vix_chg = data.get('vix_change_pct', 0)
    tbl.add_row("India VIX", f"{vix:.2f} ({vix_chg:+.2f}%)",
                "[green]LIVE[/]" if vix > 0 else "[red]DEAD[/]",
                "IDX_I segment via LTP API")

    # Futures Price
    fut = data.get('fut_price', 0)
    fut_exp = data.get('fut_expiry', '')
    tbl.add_row("Futures LTP", f"{fut:,.2f}",
                "[green]LIVE[/]" if fut > 0 else "[red]DEAD[/]",
                f"Expiry: {fut_exp}")

    # Option Chain
    odf = data.get('option_df')
    if odf is not None and not odf.empty:
        num_strikes = len(odf)
        total_c_oi = int(odf['C_OI'].sum()) if 'C_OI' in odf.columns else 0
        total_p_oi = int(odf['P_OI'].sum()) if 'P_OI' in odf.columns else 0
        tbl.add_row("Option Chain", f"{num_strikes} strikes",
                     "[green]LIVE[/]",
                     f"Call OI: {total_c_oi:,} | Put OI: {total_p_oi:,}")
    else:
        tbl.add_row("Option Chain", "0 strikes", "[red]DEAD[/]", "DataFrame empty")

    # ATM Strike
    atm = data.get('atm_strike', 0)
    tbl.add_row("ATM Strike", f"{atm:,}",
                "[green]OK[/]" if atm > 0 else "[red]MISSING[/]",
                f"Nearest to spot {spot:,.2f}")

    # Expiry List
    exp_list = data.get('expiry_list', [])
    tbl.add_row("Expiry List", f"{len(exp_list)} expiries",
                "[green]OK[/]" if exp_list else "[red]EMPTY[/]",
                f"Current: {data.get('expiry', '?')}")

    # Futures Buildup
    fb = data.get('futures_buildup', [])
    fb_status = "[green]LIVE[/]"
    fb_detail = ""
    if not fb:
        fb_status = "[red]EMPTY[/]"
    else:
        all_closed = all(e.get('buildup') == 'Market Closed' for e in fb)
        all_zero_ltp = all(e.get('ltp', 0) == 0 for e in fb)
        if all_closed:
            fb_status = "[yellow]CACHE[/]"
            fb_detail = "All entries show 'Market Closed'"
        elif all_zero_ltp:
            fb_status = "[yellow]STALE[/]"
            fb_detail = "All LTP = 0"
        else:
            fb_detail = f"{len(fb)} contracts with live data"
    tbl.add_row("Futures Buildup", f"{len(fb)} entries", fb_status, fb_detail)

    # Metrics
    metrics = data.get('metrics', {})
    pcr = metrics.get('pcr', 0)
    tbl.add_row("PCR (Put/Call Ratio)", f"{pcr:.2f}",
                "[green]OK[/]" if pcr > 0 else "[yellow]ZERO[/]",
                "From option chain OI")

    # Update Time
    ut = data.get('update_time', '?')
    tbl.add_row("Update Timestamp", ut, "[dim]--[/]", "Server time")

    console.print(tbl)


# ===========================================================================
# 7. Timestamp Freshness Check
# ===========================================================================

def check_data_freshness():
    _section("7. Data Freshness -- Consecutive Fetches")
    from oc_data_fetcher import get_futures_buildup_data
    import oc_data_fetcher

    # Reset caches
    oc_data_fetcher._last_valid_futures_buildup = None
    oc_data_fetcher._prev_futures_cache = None
    oc_data_fetcher._futures_instruments_cache = None

    _info("Fetching futures buildup twice with 3s gap to check for changes...")

    t1 = time.time()
    result1 = get_futures_buildup_data("NIFTY")
    dt1 = time.time() - t1
    _info(f"Fetch 1: {dt1:.2f}s -- {len(result1)} entries")

    time.sleep(3)

    t2 = time.time()
    result2 = get_futures_buildup_data("NIFTY")
    dt2 = time.time() - t2
    _info(f"Fetch 2: {dt2:.2f}s -- {len(result2)} entries")

    if not result1 or not result2:
        _fail("One or both fetches returned empty")
        return

    tbl = Table(title="Freshness: Fetch 1 vs Fetch 2 (3s apart)", box=box.DOUBLE_EDGE)
    tbl.add_column("Expiry", style="yellow")
    tbl.add_column("LTP #1", justify="right")
    tbl.add_column("LTP #2", justify="right")
    tbl.add_column("OI #1", justify="right")
    tbl.add_column("OI #2", justify="right")
    tbl.add_column("Changed?", justify="center")

    any_changed = False
    for i in range(min(len(result1), len(result2))):
        r1, r2 = result1[i], result2[i]
        ltp_diff = r1.get('ltp', 0) != r2.get('ltp', 0)
        oi_diff = r1.get('oi', 0) != r2.get('oi', 0)
        changed = ltp_diff or oi_diff
        if changed:
            any_changed = True
        tbl.add_row(
            r1.get('expiry', '?'),
            f"{r1.get('ltp', 0):,.2f}",
            f"{r2.get('ltp', 0):,.2f}",
            f"{r1.get('oi', 0):,}",
            f"{r2.get('oi', 0):,}",
            "[green]YES[/]" if changed else "[dim]NO[/]",
        )

    console.print(tbl)

    if any_changed:
        _pass("Data changed between fetches -- live updates confirmed")
    else:
        _warn("Data identical between fetches -- "
              "expected during market closed or low-frequency updates")


# ===========================================================================
# Main
# ===========================================================================

def main():
    console.print(Panel(
        "[bold white]NIFTY Futures Buildup -- Live Data Diagnostic[/]\n"
        f"[dim]{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]",
        border_style="cyan", box=box.DOUBLE,
    ))

    instruments = check_instruments()
    quotes = check_raw_api(instruments) if instruments else {}
    check_previous_data()
    check_cache_vs_live()
    data = check_fetch_all_data()
    if data and not data.get('error'):
        check_all_feeds(data)
    check_data_freshness()

    console.print()
    console.rule("[bold cyan]Diagnostic Complete[/]", style="cyan")
    console.print()


if __name__ == "__main__":
    main()
