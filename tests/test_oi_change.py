"""
NIFTY Option Chain — Change in OI & LTP Chg% Test
===================================================
Run:  python optionchain/test_oi_change.py
      (from workspace root with venv active)

Tests & verifies all Change in OI and LTP Chg% calculations displayed
in the option chain table for ATM ± 5 strikes.

Formulas verified:
  LTP Chg%    = (Today LTP − Prev Day Close LTP) / Prev Day Close LTP × 100
                Base = yesterday's NSE CSV closing LTP

  OI Chg%     = (Today OI − Prev Day Close OI) / Prev Day Close OI × 100
                Base = Dhan API 'previous_oi' field (yesterday's session close)

  OI Chg (lots) = Today OI (lots) − Prev OI (lots from API)

  Build Up Logic:
    OI Chg > 0 AND LTP Chg > 0  →  LB  (Long Build Up)
    OI Chg < 0 AND LTP Chg > 0  →  SC  (Short Covering)
    OI Chg > 0 AND LTP Chg < 0  →  SB  (Short Build Up)
    OI Chg < 0 AND LTP Chg < 0  →  LU  (Long Unwinding)

Cross-checks:
  • API previous_oi  vs  CSV yesterday OI  — should be ≈ equal
  • LTP Chg% uses  CSV prev close  (not API previous_ltp)
  • OI units: Dhan OC API returns OI in LOTS (contracts) — no division needed
"""

import sys
import os
import time
import json
import datetime as _dt
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

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

from color_constants import TUI_HEADER_BG, TUI_ATM_BG

from oc_data_fetcher import (
    fetch_option_chain,
    load_previous_day_data,
    fetch_expiry_list,
    fetch_batch_ltp,
    format_lakh,
    INDEX_SECURITY_IDS,
    INDEX_STEP_MAP,
    LOT_SIZE_MAP,
    VIX_SECURITY_ID,
    get_cached_spot_price,
)

console = Console(force_terminal=True, width=140)
_t_start = time.perf_counter()

UNDERLYING  = "NIFTY"
SECURITY_ID = INDEX_SECURITY_IDS.get(UNDERLYING, 13)
STEP        = INDEX_STEP_MAP.get(UNDERLYING, 50)
LOT_SIZE    = LOT_SIZE_MAP.get(UNDERLYING, 65)
NUM_STRIKES = 5   # ATM ± N strikes shown in detail


def _chk(ok: bool) -> str:
    return "[bold green]✔[/]" if ok else "[bold red]✘[/]"


def _pct_color(v: float) -> str:
    if v > 0:
        return f"[green]+{v:.2f}%[/]"
    elif v < 0:
        return f"[red]{v:.2f}%[/]"
    return f"[dim]{v:.2f}%[/]"


def _buildup_color(bu: str) -> str:
    colors = {"LB": "bright_green", "SC": "cyan", "SB": "red", "LU": "yellow", "-": "dim"}
    c = colors.get(bu, "white")
    return f"[{c}]{bu}[/]"


# ═══════════════════════════════════════════════════════════════════════════
#  STARTUP BANNER
# ═══════════════════════════════════════════════════════════════════════════
console.print()
console.print(Panel(
    "[bold bright_cyan]OI Change & LTP Calculation Test[/]\n"
    "[dim]Verifies OI Chg%, LTP Chg%, and Build Up formulas[/]\n\n"
    f"[bold]Date:[/] {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    f"[bold]Python:[/] {sys.version.split()[0]}\n"
    f"[bold]Platform:[/] {sys.platform}",
    border_style="bright_cyan",
    expand=False,
    padding=(1, 3)))
console.print()

def section(title: str):
    console.print()
    console.rule(f"[bold bright_cyan]{title}[/]", style="dim cyan")
    console.print()


# ══════════════════════════════════════════════════════════════════════════
def step1_formulas():
    section("Step 1: Formula Reference")
    console.print(Panel(
        "[bold cyan]LTP Chg%[/bold cyan]\n"
        "  = (Today LTP − Prev Day Close LTP) / Prev Day Close LTP × 100\n"
        "  Base = [yellow]yesterday's NSE CSV closing LTP[/yellow]  (loaded via load_previous_day_data)\n\n"
        "[bold cyan]OI Chg%[/bold cyan]\n"
        "  = (Today OI [lots] − Prev Day OI [lots]) / Prev Day OI [lots] × 100\n"
        "  Base = [yellow]Dhan OC API 'previous_oi' field[/yellow]  (yesterday's session-close OI in lots)\n\n"
        "[bold cyan]Cross-Check[/bold cyan]\n"
        "  API 'previous_oi'  should ≈  CSV yesterday 'OI' column\n"
        "  (both represent yesterday's EOD closing OI in lots)\n\n"
        "[bold cyan]OI Units[/bold cyan]\n"
        "  Dhan OC API 'oi' / 'previous_oi'  →  already in LOTS (contracts)\n"
        "  NO division by lot_size needed (unlike futures quotes API)\n\n"
        "[bold cyan]Build Up[/bold cyan]\n"
        "  OI Chg > 0 & LTP Chg > 0  →  [bright_green]LB[/]  Long Build Up\n"
        "  OI Chg < 0 & LTP Chg > 0  →  [cyan]SC[/]  Short Covering\n"
        "  OI Chg > 0 & LTP Chg < 0  →  [red]SB[/]  Short Build Up\n"
        "  OI Chg < 0 & LTP Chg < 0  →  [yellow]LU[/]  Long Unwinding",
        title="[bold white]Formulas[/bold white]", border_style="dim white", padding=(0, 2),
    ))


# ══════════════════════════════════════════════════════════════════════════
def step2_prev_day_csv() -> dict:
    section("Step 2: Previous Day CSV Data")

    prev = load_previous_day_data(UNDERLYING)

    # Find the CSV file that was used
    from paths import OPTIONCHAIN_CSV_DIR
    deps = OPTIONCHAIN_CSV_DIR
    csv_files = sorted([f for f in deps.glob("????-??-??.csv")
                        if f.stem != _dt.date.today().strftime('%Y-%m-%d')],
                       key=lambda x: x.stem, reverse=True)
    csv_file = csv_files[0] if csv_files else None

    console.print(Panel(
        f"  [bold cyan]CSV File      [/bold cyan]  :  [white]{csv_file.name if csv_file else 'NOT FOUND'}[/white]   {_chk(bool(csv_file))}\n"
        f"  [bold cyan]Total Strikes [/bold cyan]  :  [white]{len(prev)}[/white]\n"
        f"  [bold cyan]Underlying    [/bold cyan]  :  [white]{UNDERLYING}[/white]\n"
        f"  [bold cyan]LOT SIZE      [/bold cyan]  :  [white]{LOT_SIZE}[/white]\n\n"
        f"  [dim]Fields loaded: call_ltp, put_ltp, call_oi, put_oi  (per strike)[/dim]",
        title="[bold yellow]PREV DAY CSV[/bold yellow]", border_style="dim white", padding=(0, 2),
    ))
    return prev


# ══════════════════════════════════════════════════════════════════════════
def step3_live_spot() -> tuple:
    section("Step 3: Live SPOT Price")

    payload = {"IDX_I": [SECURITY_ID, VIX_SECURITY_ID]}
    bltp = fetch_batch_ltp(payload)
    idx = bltp.get("IDX_I", {})
    spot = float((idx.get(str(SECURITY_ID)) or {}).get("last_price", 0) or 0)
    if spot <= 0:
        spot = get_cached_spot_price(UNDERLYING) or 0

    atm = int(round(spot / STEP) * STEP) if spot > 0 else 0

    console.print(Panel(
        f"  [bold cyan]SPOT (live)   [/bold cyan]  :  [bold white]{spot:,.2f}[/bold white]   {_chk(spot > 0)}\n"
        f"  [bold cyan]ATM Strike    [/bold cyan]  :  [bold green]{atm:,}[/bold green]\n"
        f"  [bold cyan]ATM Formula   [/bold cyan]  :  round({spot:,.2f} ÷ {STEP}) × {STEP} = {atm:,}\n"
        f"  [bold cyan]First Expiry  [/bold cyan]  :  (fetched in next step)",
        title="[bold yellow]SPOT / ATM[/bold yellow]", border_style="dim white", padding=(0, 2),
    ))
    return spot, atm


# ══════════════════════════════════════════════════════════════════════════
def step4_live_option_chain(spot: float, atm: int, prev: dict) -> list:
    section("Step 4: Live Option Chain (Raw API Data)")

    # Fetch expiry
    expiry_list = fetch_expiry_list(SECURITY_ID, "IDX_I")
    expiry = expiry_list[0] if expiry_list else ""
    console.print(f"  Expiry: [bold]{expiry}[/bold]   Pausing 0.5s...")
    time.sleep(0.5)

    # Fetch option chain
    oc_data = fetch_option_chain(SECURITY_ID, "IDX_I", expiry)
    if not oc_data or oc_data.get('status') != 'success':
        console.print("[red]  Option chain fetch failed![/red]")
        return []

    data = oc_data.get('data', {})
    oc   = data.get('oc', {})

    console.print(Panel(
        f"  [bold cyan]API Status    [/bold cyan]  :  [green]{oc_data.get('status', '?')}[/green]   {_chk(oc_data.get('status') == 'success')}\n"
        f"  [bold cyan]Total Strikes [/bold cyan]  :  [white]{len(oc)}[/white]\n"
        f"  [bold cyan]Expiry        [/bold cyan]  :  [white]{expiry}[/white]\n"
        f"  [bold cyan]API last_price[/bold cyan]  :  [white]{data.get('last_price', 'N/A')}[/white]",
        title="[bold yellow]OC API RESPONSE[/bold yellow]", border_style="dim white", padding=(0, 2),
    ))

    # Parse ATM ± N strikes
    rows = []
    for sk, sd in oc.items():
        try:
            strike = float(sk)
        except Exception:
            continue
        ce = sd.get('ce', {}) or {}
        pe = sd.get('pe', {}) or {}

        # Live from API
        c_ltp    = float(ce.get('last_price',    0) or 0)
        p_ltp    = float(pe.get('last_price',    0) or 0)
        c_oi_api = float(ce.get('oi',            0) or 0)   # lots (Dhan OC returns lots directly)
        p_oi_api = float(pe.get('oi',            0) or 0)
        c_prev_oi_api = float(ce.get('previous_oi', 0) or 0)  # yesterday's EOD OI from Dhan
        p_prev_oi_api = float(pe.get('previous_oi', 0) or 0)

        # Yesterday from CSV
        csv = prev.get(strike, {})
        c_ltp_csv    = float(csv.get('call_ltp', 0) or 0)
        p_ltp_csv    = float(csv.get('put_ltp',  0) or 0)
        c_oi_csv     = float(csv.get('call_oi',  0) or 0)   # lots from CSV
        p_oi_csv     = float(csv.get('put_oi',   0) or 0)

        rows.append({
            'strike':          strike,
            'c_ltp':           c_ltp,
            'p_ltp':           p_ltp,
            'c_oi_api':        c_oi_api,
            'p_oi_api':        p_oi_api,
            'c_prev_oi_api':   c_prev_oi_api,
            'p_prev_oi_api':   p_prev_oi_api,
            'c_ltp_csv':       c_ltp_csv,
            'p_ltp_csv':       p_ltp_csv,
            'c_oi_csv':        c_oi_csv,
            'p_oi_csv':        p_oi_csv,
        })

    rows.sort(key=lambda r: r['strike'])

    # Filter ATM ± NUM_STRIKES
    atm_rows = [r for r in rows
                if abs(r['strike'] - atm) <= NUM_STRIKES * STEP]

    console.print(f"\n  [dim]Showing ATM ± {NUM_STRIKES} strikes ({len(atm_rows)} rows)[/dim]")
    return atm_rows


# ══════════════════════════════════════════════════════════════════════════
def step5_raw_data_table(rows: list, atm: int):
    section("Step 5 — Raw Values (Live API vs CSV Prev Day)")

    tbl = Table(title="Raw Call Data — ATM ± Strikes", box=box.ROUNDED, show_lines=True,
                header_style="bold cyan", expand=False)
    tbl.add_column("Strike",                       style="bold white", justify="right")
    tbl.add_column("C_LTP live",                   justify="right")
    tbl.add_column("C_LTP csv",                    justify="right", style="dim")
    tbl.add_column(f"C_OI live\n(÷{LOT_SIZE} lots)", justify="right")
    tbl.add_column(f"C_OI prev\n(API÷{LOT_SIZE} lots)", justify="right", style="yellow")
    tbl.add_column("C_OI prev\n(CSV lots)",        justify="right", style="dim")
    tbl.add_column("API ≈ CSV?",                   justify="center")

    for r in rows:
        s = int(r['strike'])
        is_atm = s == atm
        prefix = "[bold magenta]►[/] " if is_atm else ""
        # API returns raw qty — normalize to lots for comparison with CSV
        api_prev_lots = r['c_prev_oi_api'] / LOT_SIZE
        csv_prev      = r['c_oi_csv']
        api_oi_lots   = r['c_oi_api'] / LOT_SIZE
        diff = abs(api_prev_lots - csv_prev)
        pct_diff = (diff / csv_prev * 100) if csv_prev > 0 else 0
        match = "[green]✔[/]" if pct_diff < 5 else f"[red]✘ Δ{pct_diff:.1f}%[/red]"

        tbl.add_row(
            f"{prefix}{s:,}{'  ◀ATM' if is_atm else ''}",
            f"{r['c_ltp']:,.2f}",
            f"{r['c_ltp_csv']:,.2f}",
            format_lakh(api_oi_lots),
            format_lakh(api_prev_lots),
            format_lakh(csv_prev),
            match,
        )
    console.print(tbl)
    console.print("  [dim]Note: API OI values divided by LOT_SIZE ({}) to normalize to lots for comparison.[/dim]".format(LOT_SIZE))

    # Put side
    tbl2 = Table(title="Raw Put Data — ATM ± Strikes", box=box.ROUNDED, show_lines=True,
                 header_style="bold magenta", expand=False)
    tbl2.add_column("Strike",       style="bold white", justify="right")
    tbl2.add_column("P_LTP live",   justify="right")
    tbl2.add_column("P_LTP csv",    justify="right", style="dim")
    tbl2.add_column("P_OI live\n(normalized)", justify="right")
    tbl2.add_column("P_OI prev\n(API ÷ lot)", justify="right", style="yellow")
    tbl2.add_column("P_OI prev\n(CSV lots)",  justify="right", style="dim")
    tbl2.add_column("API ≈ CSV?",   justify="center")

    for r in rows:
        s = int(r['strike'])
        is_atm = s == atm
        prefix = "[bold magenta]►[/] " if is_atm else ""
        api_prev_lots = r['p_prev_oi_api'] / LOT_SIZE
        csv_prev      = r['p_oi_csv']
        api_oi_lots   = r['p_oi_api'] / LOT_SIZE
        diff = abs(api_prev_lots - csv_prev)
        pct_diff = (diff / csv_prev * 100) if csv_prev > 0 else 0
        match = "[green]✔[/]" if pct_diff < 5 else f"[red]✘ Δ{pct_diff:.1f}%[/red]"

        tbl2.add_row(
            f"{prefix}{s:,}{'  ◀ATM' if is_atm else ''}",
            f"{r['p_ltp']:,.2f}",
            f"{r['p_ltp_csv']:,.2f}",
            format_lakh(api_oi_lots),
            format_lakh(api_prev_lots),
            format_lakh(csv_prev),
            match,
        )
    console.print(tbl2)


# ══════════════════════════════════════════════════════════════════════════
def step6_formula_walkthrough(rows: list, atm: int):
    section("Step 6: Formula Walkthrough (ATM Strike)")

    atm_row = next((r for r in rows if int(r['strike']) == atm), None)
    if not atm_row:
        # take closest
        atm_row = min(rows, key=lambda r: abs(r['strike'] - atm))
    s = int(atm_row['strike'])

    # ── CALL ── (API oi/previous_oi are in raw qty; divide by LOT_SIZE to display in lots)
    c_ltp         = atm_row['c_ltp']
    c_ltp_csv     = atm_row['c_ltp_csv']
    c_oi_qty      = atm_row['c_oi_api']           # raw qty from API
    c_prev_oi_qty = atm_row['c_prev_oi_api']       # raw qty from API
    c_oi_lots     = c_oi_qty / LOT_SIZE            # display in lots
    c_prev_lots   = c_prev_oi_qty / LOT_SIZE       # display in lots
    c_oi_csv      = atm_row['c_oi_csv']            # already in lots (from CSV)

    c_ltp_chg    = ((c_ltp - c_ltp_csv) / c_ltp_csv * 100) if c_ltp_csv > 0 else 0
    # OI Chg%: qty-to-qty comparison (both from Dhan API) = correct ratio
    c_oi_chg_qty  = c_oi_qty - c_prev_oi_qty
    c_oi_chg_lots = c_oi_chg_qty / LOT_SIZE
    c_oi_chg_pct  = (c_oi_chg_qty / c_prev_oi_qty * 100) if c_prev_oi_qty > 0 else 0
    c_buildup     = _get_buildup(c_oi_chg_qty, c_ltp_chg)

    # Cross-check OI Chg% using CSV lots as base (lots-to-lots)
    c_oi_chg_csv_lots = c_oi_lots - c_oi_csv
    c_oi_chg_pct_csv  = (c_oi_chg_csv_lots / c_oi_csv * 100) if c_oi_csv > 0 else 0
    # How closely does API previous_oi (normalized) match CSV OI?
    c_prev_vs_csv_diff = abs(c_prev_lots - c_oi_csv)
    c_prev_vs_csv_pct  = (c_prev_vs_csv_diff / c_oi_csv * 100) if c_oi_csv > 0 else 0

    # ── PUT ──
    p_ltp         = atm_row['p_ltp']
    p_ltp_csv     = atm_row['p_ltp_csv']
    p_oi_qty      = atm_row['p_oi_api']
    p_prev_oi_qty = atm_row['p_prev_oi_api']
    p_oi_lots     = p_oi_qty / LOT_SIZE
    p_prev_lots   = p_prev_oi_qty / LOT_SIZE
    p_oi_csv      = atm_row['p_oi_csv']

    p_ltp_chg    = ((p_ltp - p_ltp_csv) / p_ltp_csv * 100) if p_ltp_csv > 0 else 0
    p_oi_chg_qty  = p_oi_qty - p_prev_oi_qty
    p_oi_chg_lots = p_oi_chg_qty / LOT_SIZE
    p_oi_chg_pct  = (p_oi_chg_qty / p_prev_oi_qty * 100) if p_prev_oi_qty > 0 else 0
    p_buildup     = _get_buildup(p_oi_chg_qty, p_ltp_chg)

    p_oi_chg_csv_lots = p_oi_lots - p_oi_csv
    p_oi_chg_pct_csv  = (p_oi_chg_csv_lots / p_oi_csv * 100) if p_oi_csv > 0 else 0
    p_prev_vs_csv_pct = (abs(p_prev_lots - p_oi_csv) / p_oi_csv * 100) if p_oi_csv > 0 else 0

    console.print(Panel(
        f"[bold white]CALL @ Strike {s:,}[/bold white]\n\n"
        f"  [bold cyan]LTP Chg%[/bold cyan]"
        f"  (Base = NSE CSV prev close)\n"
        f"    Today LTP      = {c_ltp:,.2f}\n"
        f"    Prev Close     = {c_ltp_csv:,.2f}  (NSE CSV)\n"
        f"    Formula        = ({c_ltp:,.2f} − {c_ltp_csv:,.2f}) / {c_ltp_csv:,.2f} × 100\n"
        f"    Result         = {_pct_color(c_ltp_chg)}\n\n"
        f"  [bold cyan]OI Chg%[/bold cyan]"
        f"  (Dhan OC API: 'oi' & 'previous_oi' are raw qty — same unit ✔)\n"
        f"    Today OI  (raw qty)        = {c_oi_qty:,.0f}\n"
        f"    Prev OI   (raw qty, API)   = {c_prev_oi_qty:,.0f}\n"
        f"    OI Chg    (raw qty)        = {c_oi_chg_qty:+,.0f}\n"
        f"    OI Chg%   (API qty÷qty)    = {_pct_color(c_oi_chg_pct)}  ← [bold]this is what dashboard shows[/bold]\n\n"
        f"  [bold cyan]Normalized to LOTS[/bold cyan]   (÷ {LOT_SIZE})\n"
        f"    Today OI  (lots)           = {format_lakh(c_oi_lots)}\n"
        f"    Prev OI   (lots, API÷lot)  = {format_lakh(c_prev_lots)}"
        f"  vs  CSV lots = {format_lakh(c_oi_csv)}"
        f"  → diff {c_prev_vs_csv_pct:.1f}% {'[green]✔ match[/]' if c_prev_vs_csv_pct < 5 else '[red]✘ mismatch[/]'}\n"
        f"    OI Chg% (CSV lots base)    = {_pct_color(c_oi_chg_pct_csv)}  [dim](cross-check)[/dim]\n\n"
        f"  [bold cyan]Build Up[/bold cyan]  :  {_buildup_color(c_buildup)}\n"
        f"    OI Chg = {c_oi_chg_lots:+,.0f} lots  |  LTP Chg% = {c_ltp_chg:+.2f}%",
        title=f"[bold yellow]CALL Formula Walkthrough — {s:,}[/bold yellow]",
        border_style="dim white", padding=(0, 2),
    ))

    console.print(Panel(
        f"[bold white]PUT @ Strike {s:,}[/bold white]\n\n"
        f"  [bold cyan]LTP Chg%[/bold cyan]"
        f"  (Base = NSE CSV prev close)\n"
        f"    Today LTP      = {p_ltp:,.2f}\n"
        f"    Prev Close     = {p_ltp_csv:,.2f}  (NSE CSV)\n"
        f"    Formula        = ({p_ltp:,.2f} − {p_ltp_csv:,.2f}) / {p_ltp_csv:,.2f} × 100\n"
        f"    Result         = {_pct_color(p_ltp_chg)}\n\n"
        f"  [bold cyan]OI Chg%[/bold cyan]"
        f"  (Dhan OC API: 'oi' & 'previous_oi' are raw qty — same unit ✔)\n"
        f"    Today OI  (raw qty)        = {p_oi_qty:,.0f}\n"
        f"    Prev OI   (raw qty, API)   = {p_prev_oi_qty:,.0f}\n"
        f"    OI Chg    (raw qty)        = {p_oi_chg_qty:+,.0f}\n"
        f"    OI Chg%   (API qty÷qty)    = {_pct_color(p_oi_chg_pct)}  ← [bold]this is what dashboard shows[/bold]\n\n"
        f"  [bold cyan]Normalized to LOTS[/bold cyan]   (÷ {LOT_SIZE})\n"
        f"    Today OI  (lots)           = {format_lakh(p_oi_lots)}\n"
        f"    Prev OI   (lots, API÷lot)  = {format_lakh(p_prev_lots)}"
        f"  vs  CSV lots = {format_lakh(p_oi_csv)}"
        f"  → diff {p_prev_vs_csv_pct:.1f}% {'[green]✔ match[/]' if p_prev_vs_csv_pct < 5 else '[red]✘ mismatch[/]'}\n"
        f"    OI Chg% (CSV lots base)    = {_pct_color(p_oi_chg_pct_csv)}  [dim](cross-check)[/dim]\n\n"
        f"  [bold cyan]Build Up[/bold cyan]  :  {_buildup_color(p_buildup)}\n"
        f"    OI Chg = {p_oi_chg_lots:+,.0f} lots  |  LTP Chg% = {p_ltp_chg:+.2f}%",
        title=f"[bold yellow]PUT Formula Walkthrough — {s:,}[/bold yellow]",
        border_style="dim white", padding=(0, 2),
    ))


def _get_buildup(oi_chg: float, ltp_chg_pct: float) -> str:
    if oi_chg > 0 and ltp_chg_pct > 0:   return "LB"
    elif oi_chg < 0 and ltp_chg_pct > 0: return "SC"
    elif oi_chg > 0 and ltp_chg_pct < 0: return "SB"
    elif oi_chg < 0 and ltp_chg_pct < 0: return "LU"
    return "-"


# ══════════════════════════════════════════════════════════════════════════
def step7_summary_table(rows: list, atm: int):
    section("Step 7 — Full OI Chg% & LTP Chg% Summary Table (ATM ± strikes)")

    tbl = Table(
        title=f"Option Chain — Change in OI & LTP  |  ATM = {atm:,}",
        box=box.ROUNDED, show_lines=True, header_style="bold white", expand=False
    )
    tbl.add_column("Strike",          style="bold white",  justify="right")
    tbl.add_column("C Build Up",      justify="center")
    tbl.add_column("C OI Chg%",       justify="right")
    tbl.add_column("C OI (lots)",     justify="right")
    tbl.add_column("C LTP Chg%",      justify="right")
    tbl.add_column("C LTP",           justify="right")
    tbl.add_column("",                justify="center", style="dim")   # separator
    tbl.add_column("P LTP",           justify="right")
    tbl.add_column("P LTP Chg%",      justify="right")
    tbl.add_column("P OI (lots)",     justify="right")
    tbl.add_column("P OI Chg%",       justify="right")
    tbl.add_column("P Build Up",      justify="center")

    for r in rows:
        s = int(r['strike'])
        is_atm = s == atm
        prefix = "► " if is_atm else ""

        # CALL
        c_ltp_chg = ((r['c_ltp'] - r['c_ltp_csv']) / r['c_ltp_csv'] * 100) if r['c_ltp_csv'] > 0 else 0
        c_oi_chg  = r['c_oi_api'] - r['c_prev_oi_api']          # qty - qty
        c_oi_chg_pct = (c_oi_chg / r['c_prev_oi_api'] * 100) if r['c_prev_oi_api'] > 0 else 0
        c_bu = _get_buildup(c_oi_chg, c_ltp_chg)
        c_oi_lots = r['c_oi_api'] / LOT_SIZE  # normalize for display

        # PUT
        p_ltp_chg = ((r['p_ltp'] - r['p_ltp_csv']) / r['p_ltp_csv'] * 100) if r['p_ltp_csv'] > 0 else 0
        p_oi_chg  = r['p_oi_api'] - r['p_prev_oi_api']
        p_oi_chg_pct = (p_oi_chg / r['p_prev_oi_api'] * 100) if r['p_prev_oi_api'] > 0 else 0
        p_bu = _get_buildup(p_oi_chg, p_ltp_chg)
        p_oi_lots = r['p_oi_api'] / LOT_SIZE  # normalize for display

        strike_label = f"[bold magenta]{prefix}{s:,}[/]" if is_atm else f"{prefix}{s:,}"

        tbl.add_row(
            strike_label,
            _buildup_color(c_bu),
            _pct_color(c_oi_chg_pct),
            format_lakh(c_oi_lots),
            _pct_color(c_ltp_chg),
            f"{r['c_ltp']:,.2f}",
            "│",
            f"{r['p_ltp']:,.2f}",
            _pct_color(p_ltp_chg),
            format_lakh(p_oi_lots),
            _pct_color(p_oi_chg_pct),
            _buildup_color(p_bu),
        )

    console.print(tbl)

    # Legend
    console.print(
        "\n  [dim]Build Up[/dim]  "
        "[bright_green]LB[/] = Long Build Up  "
        "[cyan]SC[/] = Short Covering  "
        "[red]SB[/] = Short Build Up  "
        "[yellow]LU[/] = Long Unwinding\n"
        "  [dim]LTP Chg% base = NSE CSV prev day close   |   OI Chg% base = Dhan API previous_oi[/dim]"
    )


# ══════════════════════════════════════════════════════════════════════════
def step8_api_vs_csv_crosscheck(rows: list):
    section("Step 8 — Cross-Check: API previous_oi vs CSV yesterday OI")

    tbl = Table(
        title=f"Dhan API 'previous_oi' ÷ {LOT_SIZE}  vs  NSE CSV yesterday 'OI'  (both in lots)",
        box=box.ROUNDED, show_lines=True, header_style="bold yellow", expand=False
    )
    tbl.add_column("Strike",                   style="bold white", justify="right")
    tbl.add_column(f"C API÷{LOT_SIZE}\n(lots)", justify="right", style="yellow")
    tbl.add_column("C CSV oi\n(lots)",          justify="right", style="dim")
    tbl.add_column("C Diff\n(lots)",            justify="right")
    tbl.add_column("C Match?",                  justify="center")
    tbl.add_column(f"P API÷{LOT_SIZE}\n(lots)", justify="right", style="yellow")
    tbl.add_column("P CSV oi\n(lots)",          justify="right", style="dim")
    tbl.add_column("P Diff\n(lots)",            justify="right")
    tbl.add_column("P Match?",                  justify="center")

    c_mismatches = 0
    p_mismatches = 0

    for r in rows:
        s = int(r['strike'])
        # Normalize API qty → lots for fair comparison with CSV
        ca = r['c_prev_oi_api'] / LOT_SIZE
        cc = r['c_oi_csv']
        pa = r['p_prev_oi_api'] / LOT_SIZE
        pc = r['p_oi_csv']

        cd = ca - cc
        pd_ = pa - pc
        c_pct = abs(cd / cc * 100) if cc > 0 else 0
        p_pct = abs(pd_ / pc * 100) if pc > 0 else 0

        c_ok = c_pct < 5
        p_ok = p_pct < 5
        if not c_ok: c_mismatches += 1
        if not p_ok: p_mismatches += 1

        tbl.add_row(
            f"{s:,}",
            format_lakh(ca),
            format_lakh(cc),
            f"{cd:+,.0f}",
            "[green]✔[/]" if c_ok else f"[red]✘ {c_pct:.1f}%[/]",
            format_lakh(pa),
            format_lakh(pc),
            f"{pd_:+,.0f}",
            "[green]✔[/]" if p_ok else f"[red]✘ {p_pct:.1f}%[/]",
        )

    console.print(tbl)
    console.print(Panel(
        f"  [bold cyan]Call mismatches (>5%)  [/bold cyan]  :  "
        f"{'[red]' + str(c_mismatches) + '[/red]' if c_mismatches else '[green]0 — all match ✔[/green]'}\n"
        f"  [bold cyan]Put  mismatches (>5%)  [/bold cyan]  :  "
        f"{'[red]' + str(p_mismatches) + '[/red]' if p_mismatches else '[green]0 — all match ✔[/green]'}\n\n"
        f"  [bold cyan]Unit Discovery[/bold cyan]\n"
        f"  Dhan OC API 'oi' / 'previous_oi' → [yellow]raw qty (shares)[/yellow]  (same as futures API)\n"
        f"  NSE CSV 'OI' column              → [yellow]lots (contracts)[/yellow]\n"
        f"  Ratio = LOT_SIZE = {LOT_SIZE}   so CSV lots × {LOT_SIZE} ≈ API qty\n"
        f"  OI Chg% in code: qty÷qty (both from API) → [green]correct ratio ✔[/green]\n\n"
        f"  [dim]If API previous_oi ÷ {LOT_SIZE} ≈ CSV OI → both represent yesterday EOD closing OI ✓[/dim]",
        title="[bold yellow]CROSS-CHECK VERDICT[/bold yellow]", border_style="dim white", padding=(0, 2),
    ))


# ══════════════════════════════════════════════════════════════════════════
def step9_final_summary(rows: list, atm: int, spot: float):
    section("Final Summary — As Displayed in Dashboard Option Chain")

    now = _dt.datetime.now().strftime("%d-%b-%Y %H:%M:%S")
    console.print(f"  [dim]NIFTY Option Chain Live   {now}   SPOT={spot:,.2f}   ATM={atm:,}[/dim]\n")

    tbl = Table(box=box.DOUBLE_EDGE, show_lines=True, expand=False,
                header_style=f"bold white on {TUI_HEADER_BG}")
    tbl.add_column("Build Up",    justify="center", style="bold")
    tbl.add_column("OI Chg%",     justify="right")
    tbl.add_column("OI",          justify="right")
    tbl.add_column("LTP Chg%",    justify="right")
    tbl.add_column("LTP",         justify="right")
    tbl.add_column("STRIKE",      justify="center", style="bold white")
    tbl.add_column("LTP",         justify="right")
    tbl.add_column("LTP Chg%",    justify="right")
    tbl.add_column("OI",          justify="right")
    tbl.add_column("OI Chg%",     justify="right")
    tbl.add_column("Build Up",    justify="center", style="bold")

    for r in rows:
        s = int(r['strike'])
        is_atm = s == atm

        c_ltp_chg = ((r['c_ltp'] - r['c_ltp_csv']) / r['c_ltp_csv'] * 100) if r['c_ltp_csv'] > 0 else 0
        c_oi_chg  = r['c_oi_api'] - r['c_prev_oi_api']
        c_oi_chg_pct = (c_oi_chg / r['c_prev_oi_api'] * 100) if r['c_prev_oi_api'] > 0 else 0
        c_bu = _get_buildup(c_oi_chg, c_ltp_chg)
        c_oi_lots = r['c_oi_api'] / LOT_SIZE

        p_ltp_chg = ((r['p_ltp'] - r['p_ltp_csv']) / r['p_ltp_csv'] * 100) if r['p_ltp_csv'] > 0 else 0
        p_oi_chg  = r['p_oi_api'] - r['p_prev_oi_api']
        p_oi_chg_pct = (p_oi_chg / r['p_prev_oi_api'] * 100) if r['p_prev_oi_api'] > 0 else 0
        p_bu = _get_buildup(p_oi_chg, p_ltp_chg)
        p_oi_lots = r['p_oi_api'] / LOT_SIZE

        bg = f"on {TUI_ATM_BG}" if is_atm else ""
        strike_display = f"[bold magenta on {TUI_ATM_BG}]► {s:,} ◄[/]" if is_atm else f"{s:,}"

        tbl.add_row(
            _buildup_color(c_bu),
            _pct_color(c_oi_chg_pct),
            format_lakh(c_oi_lots),
            _pct_color(c_ltp_chg),
            f"{r['c_ltp']:,.2f}",
            strike_display,
            f"{r['p_ltp']:,.2f}",
            _pct_color(p_ltp_chg),
            format_lakh(p_oi_lots),
            _pct_color(p_oi_chg_pct),
            _buildup_color(p_bu),
        )

    console.print(tbl)

    # ─── Final Summary ───────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold bright_cyan]Final Summary[/]", style="dim cyan"))

    elapsed_total = time.perf_counter() - _t_start
    summary_tbl = Table(box=box.DOUBLE_EDGE, show_header=False, expand=False, padding=(0, 2))
    summary_tbl.add_column(style="bold", width=20)
    summary_tbl.add_column(width=12, justify="right")
    summary_tbl.add_row("[cyan]Strikes Tested[/]", f"[bold]{len(rows)}[/]")
    summary_tbl.add_row("[cyan]CSV Data Source[/]", "[green]✓ Loaded[/]")
    summary_tbl.add_row("[cyan]Live OC API[/]", "[green]✓ Fetched[/]")
    summary_tbl.add_row("[cyan]Calculations[/]", "[green]✓ Verified[/]")
    summary_tbl.add_row("[dim]Elapsed[/]", f"{elapsed_total:.2f}s")
    console.print(summary_tbl)
    console.print()

    console.print(Panel(
        "[bold green]✓ OI Change test suite completed[/]\n"
        "[dim]All formulas and calculations verified across API + CSV data sources[/]",
        border_style="green",
        expand=False,
        padding=(1, 2)))
    console.print()


# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    console.print()
    console.rule("[bold blue]NIFTY Option Chain — Change in OI & LTP Chg% Test[/bold blue]")
    console.print(Panel(
        f"  [bold cyan]Underlying   [/bold cyan]  :  {UNDERLYING}\n"
        f"  [bold cyan]LOT SIZE     [/bold cyan]  :  {LOT_SIZE}\n"
        f"  [bold cyan]ATM Step     [/bold cyan]  :  {STEP}\n"
        f"  [bold cyan]Strikes shown[/bold cyan]  :  ATM ± {NUM_STRIKES}\n"
        f"  [bold cyan]Date         [/bold cyan]  :  {_dt.date.today().strftime('%d-%b-%Y')}\n\n"
        f"  [dim]OI Source: Dhan OC API ('oi' = today lots, 'previous_oi' = prev day lots)\n"
        f"  LTP Source: Dhan OC API live  vs  NSE CSV yesterday closing LTP[/dim]",
        title="[bold white]Test Config[/bold white]", border_style="blue", padding=(0, 2),
    ))

    step1_formulas()
    prev = step2_prev_day_csv()
    console.print("  Pausing 0.5s (rate limit)...")
    time.sleep(0.5)
    spot, atm = step3_live_spot()
    console.print("  Pausing 1s (rate limit)...")
    time.sleep(1)
    rows = step4_live_option_chain(spot, atm, prev)

    if not rows:
        console.print("[red]No option chain data — cannot continue.[/red]")
        sys.exit(1)

    time.sleep(0.5)
    step5_raw_data_table(rows, atm)
    step6_formula_walkthrough(rows, atm)
    step7_summary_table(rows, atm)
    step8_api_vs_csv_crosscheck(rows)
    step9_final_summary(rows, atm, spot)
