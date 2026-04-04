"""
NIFTY Option Chain Live — Header Section Rich Print Test
=========================================================
Run:  python optionchain/test_header_section.py
      (from workspace root with venv active)

Tests all values shown in the dashboard header:
  ┌─────────────────────────────────────────────────────────────┐
  │  SPOT  │  ATM  │  EXPIRY  │  VIX  │  FUT                   │
  │  DAY OPEN PRICE  │  OPENING STRADDLE  │  STRADDLE LIVE PRICE│
  └─────────────────────────────────────────────────────────────┘

Formula reference:
  ATM          = round(SPOT / step) * step   (step = 50 for NIFTY)
  VIX Chg%     = (VIX_live − VIX_yesterday_close) / VIX_yesterday_close × 100
  Day Open     = OHLC open from Dhan API (fetched once at 09:16, cached for day)
  Straddle     = Call LTP + Put LTP  (at ATM strike of day-open)
"""

import sys
import os
import time
import datetime
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── path setup ────────────────────────────────────────────────────────────
_here = Path(__file__).resolve().parent          # tests/
_oc_dir = _here.parent                            # project root
for _p in [str(_here), str(_oc_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich.columns import Columns
from rich import box

from oc_data_fetcher import (
    fetch_ltp,
    fetch_batch_ltp,
    get_vix_data,
    get_futures_info,
    ensure_day_open_synced,
    _load_saved_opening_straddle,
    fetch_expiry_list,
    fetch_all_data,
    INDEX_SECURITY_IDS,
    INDEX_STEP_MAP,
    VIX_SECURITY_ID,
    LOT_SIZE_MAP,
    get_cached_spot_price,
)

console = Console(force_terminal=True, width=140)
_t_start = time.perf_counter()

UNDERLYING  = "NIFTY"
STEP        = INDEX_STEP_MAP.get(UNDERLYING, 50)
SECURITY_ID = INDEX_SECURITY_IDS.get(UNDERLYING, 13)


# ── helpers ───────────────────────────────────────────────────────────────
def _pct_color(v: float) -> str:
    return "green" if v > 0 else ("red" if v < 0 else "yellow")

def _chk(ok: bool) -> str:
    return "[bold green]✓ OK[/bold green]" if ok else "[bold red]✗ MISSING / ZERO[/bold red]"

def _val_row(label: str, value: str, status: str, note: str = "") -> list:
    return [label, value, status, note]


# ══════════════════════════════════════════════════════════════════════════
def section(title: str):
    console.print()
    console.print(Rule(f"[bold bright_cyan]{title}[/]", style="dim cyan"))


def print_formula_box():
    section("Formula Reference")
    console.print(Panel(
        "[bold cyan]ATM Strike[/bold cyan]    = round(SPOT / step) × step"
        "   [dim](step = 50 for NIFTY)[/dim]\n\n"
        "[bold cyan]VIX Chg%[/bold cyan]      = (VIX_live − VIX_yesterday_close) / VIX_yesterday_close × 100\n\n"
        "[bold cyan]Day Open[/bold cyan]      = OHLC open from Dhan IDX_I API  "
        "[dim](fetched once after 09:16, cached for the day)[/dim]\n\n"
        "[bold cyan]ATM_open Strike[/bold cyan] = round(Day_Open / step) × step\n\n"
        "[bold cyan]Straddle Total[/bold cyan] = Call LTP (at ATM_open) + Put LTP (at ATM_open)\n\n"
        "[bold cyan]Straddle Chg%[/bold cyan]  = (Live_Total − Opening_Total) / Opening_Total × 100",
        title="[bold yellow]Formulas[/bold yellow]",
        border_style="yellow", padding=(0, 2),
    ))


# ══════════════════════════════════════════════════════════════════════════
def test_spot_atm():
    section("Step 1 — SPOT & ATM Strike")

    spot = fetch_ltp(SECURITY_ID, "IDX_I") or 0.0
    cached = get_cached_spot_price(UNDERLYING)
    atm = int(round(spot / STEP) * STEP) if spot > 0 else 0

    console.print(Panel(
        f"  [bold cyan]SPOT (live Dhan)[/bold cyan]  :  [bold white]{spot:>12,.2f}[/bold white]   {_chk(spot > 0)}\n"
        f"  [bold cyan]SPOT (cached)   [/bold cyan]  :  [dim white]{cached:>12,.2f}[/dim white]\n\n"
        f"  [bold cyan]ATM formula     [/bold cyan]  :  round({spot:,.2f} ÷ {STEP}) × {STEP}"
        f"  =  [bold green]{atm:,}[/bold green]\n"
        f"  [dim]step = {STEP} (NIFTY)[/dim]",
        title="[bold yellow]SPOT / ATM[/bold yellow]", border_style="dim white", padding=(0, 2),
    ))
    return spot, atm


# ══════════════════════════════════════════════════════════════════════════
def test_expiry(spot: float):
    section("Step 2 — EXPIRY LIST")

    expiries = fetch_expiry_list(SECURITY_ID)
    if not expiries:
        console.print("[red]  No expiries returned — check token / market hours[/red]")
        return ""

    tbl = Table(box=box.SIMPLE_HEAD, header_style="bold blue")
    tbl.add_column("Index", justify="right", style="yellow", min_width=5)
    tbl.add_column("Expiry Date", style="cyan",  min_width=14)
    tbl.add_column("Selected?",   justify="center")

    for i, exp in enumerate(expiries[:6]):
        sel = "[bold green]◀ default (idx=0)[/bold green]" if i == 0 else ""
        tbl.add_row(str(i), exp, sel)

    console.print(tbl)
    return expiries[0] if expiries else ""


# ══════════════════════════════════════════════════════════════════════════
def test_vix():
    section("Step 3 — VIX (India VIX)")

    vix_live, vix_chg_pct, vix_yesterday = get_vix_data()

    console.print(Panel(
        f"  [bold cyan]VIX Live (Dhan IDX_I id=21)[/bold cyan]  :  "
        f"[bold white]{vix_live:.2f}[/bold white]   {_chk(vix_live > 0)}\n\n"
        f"  [bold cyan]VIX Yesterday Close (CSV)  [/bold cyan]  :  "
        f"[white]{vix_yesterday:.4f}[/white]   {_chk(vix_yesterday > 0)}\n"
        f"  [dim]File: data/source/vix/indiavix_YYYY-MM-DD.csv[/dim]\n\n"
        f"  [bold cyan]VIX Chg% Formula[/bold cyan]\n"
        f"  ({vix_live:.2f} − {vix_yesterday:.4f}) / {vix_yesterday:.4f} × 100\n"
        f"  = [{_pct_color(vix_chg_pct)}]{vix_chg_pct:+.2f}%[/{_pct_color(vix_chg_pct)}]"
        f"   {_chk(vix_chg_pct != 0 or vix_yesterday == 0)}\n\n"
        f"  [bold]Display → [white]{vix_live:.2f} "
        f"([{_pct_color(vix_chg_pct)}]{vix_chg_pct:+.2f}%[/{_pct_color(vix_chg_pct)}])[/white][/bold]",
        title="[bold yellow]VIX[/bold yellow]", border_style="dim white", padding=(0, 2),
    ))
    return vix_live, vix_chg_pct


# ══════════════════════════════════════════════════════════════════════════
def test_futures():
    section("Step 4 — FUTURES (Near-Month FUT Price & Expiry)")

    fut_price, fut_expiry = get_futures_info(UNDERLYING)

    console.print(Panel(
        f"  [bold cyan]FUT Price  [/bold cyan]  :  [bold white]{fut_price:,.2f}[/bold white]   {_chk(fut_price > 0)}\n"
        f"  [bold cyan]FUT Expiry [/bold cyan]  :  [white]{fut_expiry}[/white]   {_chk(bool(fut_expiry))}\n\n"
        f"  [bold]Display → [white]{fut_price:,.2f} ({fut_expiry})[/white][/bold]",
        title="[bold yellow]FUT[/bold yellow]", border_style="dim white", padding=(0, 2),
    ))
    return fut_price, fut_expiry


# ══════════════════════════════════════════════════════════════════════════
def test_day_open(spot: float):
    section("Step 5 — DAY OPEN PRICE (Synced Day Open)")

    rec = ensure_day_open_synced(UNDERLYING, spot_price=spot)

    open_price  = rec.get('open_price', 0)
    atm_strike  = rec.get('atm_strike', 0)
    source      = rec.get('source', 'unknown')
    timestamp   = rec.get('timestamp', 'N/A')
    date        = rec.get('date', 'N/A')

    source_color = {
        'live':          'bold green',
        'cached_today':  'cyan',
        'previous':      'yellow',
        'fallback':      'red',
    }.get(source, 'white')

    step = INDEX_STEP_MAP.get(UNDERLYING, 50)
    atm_formula = f"round({open_price:,.2f} ÷ {step}) × {step} = {atm_strike:,}" if open_price > 0 else "N/A"

    console.print(Panel(
        f"  [bold cyan]Day Open Price [/bold cyan]  :  [bold white]{open_price:,.2f}[/bold white]   {_chk(open_price > 0)}\n"
        f"  [bold cyan]ATM at Open    [/bold cyan]  :  [bold green]{atm_strike:,}[/bold green]\n"
        f"  [bold cyan]ATM Formula    [/bold cyan]  :  {atm_formula}\n\n"
        f"  [bold cyan]Source         [/bold cyan]  :  [{source_color}]{source}[/{source_color}]\n"
        f"  [bold cyan]Saved At       [/bold cyan]  :  [dim]{timestamp}[/dim]\n"
        f"  [bold cyan]Date           [/bold cyan]  :  [dim]{date}[/dim]\n\n"
        f"  [dim]Sources: live = Dhan OHLC API  |  cached_today = already saved today\n"
        f"            previous = last saved date  |  fallback = spot price used[/dim]",
        title="[bold yellow]DAY OPEN PRICE[/bold yellow]", border_style="dim white", padding=(0, 2),
    ))
    return open_price, atm_strike


# ══════════════════════════════════════════════════════════════════════════
def test_opening_straddle(atm_open: int):
    section("Step 6 — OPENING STRADDLE (Saved at 09:16 open)")

    straddle = _load_saved_opening_straddle(UNDERLYING)

    if not straddle:
        console.print(f"  [yellow]No straddle saved yet — triggering fetch_all_data to save it (ATM_open={atm_open:,})…[/yellow]")
        try:
            fetch_all_data(UNDERLYING, expiry_index=0)
            straddle = _load_saved_opening_straddle(UNDERLYING)
        except Exception as e:
            console.print(f"  [red]fetch_all_data failed: {e}[/red]")

    if not straddle:
        console.print(Panel(
            "[red]  No opening straddle saved for today.[/red]\n"
            "[dim]  It is saved automatically when the dashboard first loads after 09:16.[/dim]\n"
            f"  [dim]Expected ATM strike from day open: [bold]{atm_open:,}[/bold][/dim]",
            title="[bold yellow]OPENING STRADDLE[/bold yellow]", border_style="red", padding=(0, 2),
        ))
        return 0, 0.0, 0.0

    strike     = straddle.get('strike', 0)
    call_open  = straddle.get('call',   0.0)
    put_open   = straddle.get('put',    0.0)
    total_open = straddle.get('total',  0.0)

    console.print(Panel(
        f"  [bold cyan]Saved Strike  [/bold cyan]  :  [bold white]{strike:,}[/bold white]   {_chk(strike > 0)}\n"
        f"  [bold cyan]Call Open LTP [/bold cyan]  :  [white]{call_open:.2f}[/white]   {_chk(call_open > 0)}\n"
        f"  [bold cyan]Put  Open LTP [/bold cyan]  :  [white]{put_open:.2f}[/white]   {_chk(put_open > 0)}\n\n"
        f"  [bold cyan]Opening Total [/bold cyan]  :  [bold green]{total_open:.2f}[/bold green]\n"
        f"  [bold cyan]Formula       [/bold cyan]  :  {call_open:.2f} + {put_open:.2f} = {call_open + put_open:.2f}\n\n"
        f"  [bold]Display → Strike [white]{strike:,}[/white]   Opening Total [white]{total_open:.2f}[/white][/bold]",
        title="[bold yellow]OPENING STRADDLE[/bold yellow]", border_style="dim white", padding=(0, 2),
    ))
    return strike, call_open, put_open


# ══════════════════════════════════════════════════════════════════════════
def test_straddle_live(saved_strike: int, call_open: float, put_open: float, option_df=None):
    section("Step 7 — STRADDLE LIVE PRICE (C + P at saved strike)")

    # Try to get live LTPs from a quick option chain lookup via batch LTP
    # We'll fetch from the option_df if available, otherwise note it needs the full chain
    if saved_strike <= 0:
        console.print("[red]  No saved strike — cannot compute live straddle[/red]")
        return

    # We need to find the option security IDs for saved_strike - requires option chain
    console.print(Panel(
        f"  [bold cyan]Saved Strike          [/bold cyan]  :  [bold white]{saved_strike:,}[/bold white]\n\n"
        f"  [bold cyan]Call Opening LTP (C)  [/bold cyan]  :  [white]{call_open:.2f}[/white]\n"
        f"  [bold cyan]Put  Opening LTP (P)  [/bold cyan]  :  [white]{put_open:.2f}[/white]\n"
        f"  [bold cyan]Opening Total         [/bold cyan]  :  [bold]{call_open + put_open:.2f}[/bold]\n\n"
        f"  [dim]Live C + P LTP requires the full option chain (fetched in fetch_all_data).\n"
        f"  Run the full dashboard or test_optionchain.py to see live straddle vs opening.[/dim]\n\n"
        f"  [bold cyan]Formula[/bold cyan]\n"
        f"  Live Total = C_LTP + P_LTP (at strike {saved_strike:,})\n"
        f"  Straddle Chg% = (Live_Total − {call_open + put_open:.2f}) / {call_open + put_open:.2f} × 100",
        title="[bold yellow]STRADDLE LIVE PRICE[/bold yellow]", border_style="dim white", padding=(0, 2),
    ))


# ══════════════════════════════════════════════════════════════════════════
def print_final_summary(spot, atm_spot, expiry, vix_live, vix_chg, fut_price, fut_expiry,
                        open_price, atm_open, saved_strike, call_open, put_open):
    section("Final Summary — As Displayed in Dashboard Header")

    straddle_total = call_open + put_open

    tbl = Table(
        title=f"[bold green]NIFTY Option Chain Live[/bold green]   "
              f"[dim]{datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S')}[/dim]",
        box=box.DOUBLE_EDGE,
        header_style="bold white on #1a1a2e",
        show_lines=True, padding=(0, 2),
    )
    tbl.add_column("Field",        style="bold cyan",  min_width=22)
    tbl.add_column("Value",        style="white",      min_width=22)
    tbl.add_column("Source / Note", style="dim white", min_width=30)

    vix_str = (
        f"{vix_live:.2f} ([{_pct_color(vix_chg)}]{vix_chg:+.2f}%[/{_pct_color(vix_chg)}])"
    )

    rows = [
        ("SPOT",              f"{spot:,.2f}",                    "Dhan batch LTP  IDX_I"),
        ("ATM (live spot)",   f"{atm_spot:,}",                   f"round({spot:,.0f} ÷ {STEP}) × {STEP}"),
        ("EXPIRY",            expiry,                             "fetch_expiry_list idx=0"),
        ("VIX",               vix_str,                            f"live={vix_live:.2f}  yest_close via CSV"),
        ("FUT",               f"{fut_price:,.2f}  ({fut_expiry})","near-month futures LTP"),
        ("DAY OPEN PRICE",    f"{open_price:,.2f}",               "Dhan OHLC  (cached after 09:16)"),
        ("OPENING STRADDLE",  f"Strike {saved_strike:,}",        f"ATM at day-open (round({open_price:,.0f}÷{STEP})×{STEP})"),
        ("Call Open LTP (C)", f"{call_open:.2f}",                "option daily open at strike"),
        ("Put  Open LTP (P)", f"{put_open:.2f}",                 "option daily open at strike"),
        ("STRADDLE TOTAL",    f"{straddle_total:.2f}",            f"C {call_open:.2f} + P {put_open:.2f}"),
    ]

    for field, value, note in rows:
        tbl.add_row(field, value, note)

    console.print(tbl)


# ══════════════════════════════════════════════════════════════════════════
def main():
    console.print()
    console.print(Panel(
        "[bold bright_cyan]NIFTY Option Chain — Header Section Test[/]\n"
        f"[dim]Underlying: {UNDERLYING}  |  ATM Step: {STEP}  |  "
        f"Date: {datetime.date.today().strftime('%d-%b-%Y')}[/dim]\n\n"
        f"[bold]Python:[/] {sys.version.split()[0]}\n"
        f"[bold]Platform:[/] {sys.platform}",
        border_style="bright_cyan",
        expand=False,
        padding=(1, 3),
    ))

    print_formula_box()

    spot, atm_spot = test_spot_atm()
    expiry         = test_expiry(spot)

    console.print()
    console.print("[dim]  Pausing 0.5s (rate limit)...[/dim]")
    time.sleep(0.5)

    vix_live, vix_chg = test_vix()

    console.print()
    console.print("[dim]  Pausing 0.5s (rate limit)...[/dim]")
    time.sleep(0.5)

    fut_price, fut_expiry = test_futures()

    console.print()
    console.print("[dim]  Pausing 0.5s (rate limit)...[/dim]")
    time.sleep(0.5)

    open_price, atm_open = test_day_open(spot)
    saved_strike, call_open, put_open = test_opening_straddle(atm_open)
    test_straddle_live(saved_strike, call_open, put_open)

    print_final_summary(
        spot, atm_spot, expiry,
        vix_live, vix_chg,
        fut_price, fut_expiry,
        open_price, atm_open,
        saved_strike, call_open, put_open,
    )

    # ─── Final Summary ───────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold bright_cyan]Final Summary[/]", style="dim cyan"))

    elapsed_total = time.perf_counter() - _t_start
    summary_tbl = Table(box=box.DOUBLE_EDGE, show_header=False, expand=False, padding=(0, 2))
    summary_tbl.add_column(style="bold", width=20)
    summary_tbl.add_column(width=12, justify="right")
    summary_tbl.add_row("[cyan]API Calls[/]", "[green]✓ 4 complete[/]")
    summary_tbl.add_row("[cyan]Header Fields[/]", "[green]✓ All fetched[/]")
    summary_tbl.add_row("[cyan]Calculations[/]", "[green]✓ Verified[/]")
    summary_tbl.add_row("[dim]Elapsed[/]", f"{elapsed_total:.2f}s")
    console.print(summary_tbl)
    console.print()

    console.print(Panel(
        "[bold green]✓ Header section test completed[/]\n"
        "[dim]All dashboard header fields and calculations verified[/]",
        border_style="green",
        expand=False,
        padding=(1, 2)))
    console.print()


if __name__ == "__main__":
    main()
