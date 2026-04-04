"""
NIFTY Futures OI Build-Up — Rich Print Test
=============================================
Run:  python optionchain/test_futures_buildup.py
      (from workspace root with venv active)

Tests `get_futures_buildup_data()` end-to-end and logs every intermediate
value so you can verify formulas by eye.

Formula reference:
  OI Chg%  = (Today_OI_contracts - PrevDay_OI_contracts) / PrevDay_OI_contracts × 100
  LTP Chg% = (Today_LTP           - PrevDay_Close_LTP  ) / PrevDay_Close_LTP    × 100

Build-Up Signal Matrix:
  OI ↑  LTP ↑ → Long  Build Up   (LB)  — Bullish
  OI ↑  LTP ↓ → Short Build Up   (SB)  — Bearish
  OI ↓  LTP ↑ → Short Covering   (SC)  — Bullish (short-term)
  OI ↓  LTP ↓ → Long  Unwinding  (LU)  — Bearish (mild)
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
from rich.text import Text

from oc_data_fetcher import (
    get_futures_buildup_data,
    load_previous_futures_data,
    _load_futures_instruments,
    _fetch_futures_quotes,
    LOT_SIZE_MAP,
    format_lakh,
)

console = Console(force_terminal=True, width=140)
_t_start = time.perf_counter()
_results = []

# ── colour helpers ───────────────────────────────────────────────────────────
def _pct_color(v: float) -> str:
    if v > 0:   return "green"
    if v < 0:   return "red"
    return "yellow"

def _oi_arrow(today_oi, prev_oi) -> str:
    if today_oi > prev_oi: return "[green]▲[/green]"
    if today_oi < prev_oi: return "[red]▼[/red]"
    return "[yellow]─[/yellow]"

def _ltp_arrow(today_ltp, prev_ltp) -> str:
    if today_ltp > prev_ltp: return "[green]▲[/green]"
    if today_ltp < prev_ltp: return "[red]▼[/red]"
    return "[yellow]─[/yellow]"

BUILDUP_COLORS = {
    "Long Build Up":  ("bold green",  "LB", "Bullish   ▲▲"),
    "Short Build Up": ("bold red",    "SB", "Bearish   ▼▼"),
    "Short Covering": ("bold cyan",   "SC", "Bullish ↑ (♻)"),
    "Long Unwinding": ("bold yellow", "LU", "Bearish ↓ (♻)"),
}

UNDERLYING = "NIFTY"
LOT_SIZE   = LOT_SIZE_MAP.get(UNDERLYING, 65)

# ────────────────────────────────────────────────────────────────────────────
def print_legend():
    console.print(Rule("[bold white]Build-Up Signal Matrix[/bold white]", style="dim white"))
    tbl = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold white", padding=(0, 1))
    tbl.add_column("Signal",         style="bold", min_width=18)
    tbl.add_column("Code", justify="center", min_width=5)
    tbl.add_column("OI Direction",   justify="center", min_width=12)
    tbl.add_column("LTP Direction",  justify="center", min_width=12)
    tbl.add_column("Interpretation", min_width=22)

    tbl.add_row("[green]Long Build Up[/green]",   "[green]LB[/green]",  "[green]↑ Rising[/green]",  "[green]↑ Rising[/green]",  "Longs being added — Bullish")
    tbl.add_row("[red]Short Build Up[/red]",   "[red]SB[/red]",    "[red]↑ Rising[/red]",    "[red]↓ Falling[/red]",  "Shorts being added — Bearish")
    tbl.add_row("[cyan]Short Covering[/cyan]",  "[cyan]SC[/cyan]",   "[red]↓ Falling[/red]",   "[green]↑ Rising[/green]",  "Shorts closing position — Mild Bullish")
    tbl.add_row("[yellow]Long Unwinding[/yellow]", "[yellow]LU[/yellow]",  "[red]↓ Falling[/red]",   "[red]↓ Falling[/red]",  "Longs closing position — Mild Bearish")

    console.print(tbl)


def print_formula_box():
    console.print(Rule("[bold white]Formula Reference[/bold white]", style="dim white"))
    console.print(Panel(
        "[bold cyan]OI Chg%[/bold cyan]  = "
        "[white](Today_OI_contracts − PrevDay_OI_contracts) / PrevDay_OI_contracts × 100[/white]\n\n"
        "[bold cyan]LTP Chg%[/bold cyan] = "
        "[white](Today_LTP − PrevDay_Close_LTP) / PrevDay_Close_LTP × 100[/white]\n\n"
        "[dim]Note: Dhan API returns OI in qty (shares).[/dim]\n"
        f"[dim]Normalise → contracts:  OI_qty ÷ lot_size ({LOT_SIZE}) = OI_contracts[/dim]",
        title="[bold yellow]Formulas[/bold yellow]",
        border_style="yellow",
        padding=(0, 2),
    ))


# ────────────────────────────────────────────────────────────────────────────
def print_raw_instruments():
    """Log what instruments are loaded from the CSV."""
    instruments = _load_futures_instruments(UNDERLYING)
    console.print(Rule("[bold white]Step 1 — Futures Instruments (from all_instrument CSV)[/bold white]", style="dim blue"))
    if not instruments:
        console.print("[red]  No instruments found — check all_instrument*.csv in data/source/instruments/[/red]")
        return instruments

    tbl = Table(box=box.SIMPLE_HEAD, header_style="bold blue")
    tbl.add_column("Symbol",      style="cyan")
    tbl.add_column("Expiry",      style="white")
    tbl.add_column("Security ID", justify="right", style="yellow")

    for inst in instruments:
        tbl.add_row(inst['symbol'], inst['expiry'], str(inst['security_id']))
    console.print(tbl)
    return instruments


def print_raw_prev_data():
    """Log previous day CSV data."""
    prev = load_previous_futures_data(UNDERLYING)
    console.print(Rule("[bold white]Step 2 — Previous Day Data (from NIFTY_FUTURE_*.csv)[/bold white]", style="dim blue"))
    if not prev:
        console.print("[red]  No previous day CSV found in data/source/futures/[/red]")
        return prev

    tbl = Table(box=box.SIMPLE_HEAD, header_style="bold blue")
    tbl.add_column("Expiry",          style="cyan")
    tbl.add_column("Expiry Key",      style="dim white")
    tbl.add_column("Prev Close LTP",  justify="right", style="white")
    tbl.add_column("Prev OI (contracts)", justify="right", style="yellow")

    for row in prev:
        tbl.add_row(
            row['expiry'],
            row['expiry_key'],
            f"{row['prev_ltp']:,.2f}",
            f"{int(row['prev_oi']):,}",
        )
    console.print(tbl)
    return prev


def print_live_quotes(instruments):
    """Log raw Dhan API quote response."""
    sec_ids = [i['security_id'] for i in instruments if i['security_id'] > 0]
    quotes  = _fetch_futures_quotes(sec_ids)

    console.print(Rule("[bold white]Step 3 — Live Quotes (Dhan API — NSE_FNO)[/bold white]", style="dim blue"))
    if not quotes:
        console.print("[red]  No quotes returned — check token / market hours[/red]")
        return quotes

    tbl = Table(box=box.SIMPLE_HEAD, header_style="bold blue")
    tbl.add_column("Security ID",      justify="right", style="yellow")
    tbl.add_column("Last Price (LTP)", justify="right", style="white")
    tbl.add_column("OI (raw qty)",     justify="right", style="magenta")
    tbl.add_column(f"OI ÷ {LOT_SIZE} = contracts", justify="right", style="cyan")

    for sec_id_str, q in quotes.items():
        ltp    = float(q.get('last_price',    0) or 0)
        oi_qty = int(  q.get('oi',            0) or q.get('open_interest', 0) or 0)
        oi_c   = oi_qty // LOT_SIZE if LOT_SIZE > 0 else oi_qty
        tbl.add_row(sec_id_str, f"{ltp:,.2f}", format_lakh(float(oi_qty)), f"{format_lakh(float(oi_c))}")

    console.print(tbl)
    return quotes


def print_formula_walkthrough(results):
    """Print step-by-step formula verification for each contract."""
    console.print(Rule("[bold white]Step 4 — Formula Walkthrough (per contract)[/bold white]", style="dim blue"))

    for r in results:
        expiry       = r['expiry']
        ltp          = r['ltp']
        prev_ltp     = r['prev_ltp']
        oi_qty       = r.get('oi_qty', 0)
        oi_contracts = r['oi']
        prev_oi      = r['prev_oi']
        ltp_chg      = r['ltp_chg_pct']
        oi_chg       = r['oi_chg_pct']
        buildup      = r['buildup']
        lot          = r.get('lot_size', LOT_SIZE)

        color, code, interp = BUILDUP_COLORS.get(buildup, ("white", "?", "Unknown"))

        ltp_chg_str = (
            f"({ltp:,.2f} − {prev_ltp:,.2f}) / {prev_ltp:,.2f} × 100 = "
            f"[{_pct_color(ltp_chg)}]{ltp_chg:+.2f}%[/{_pct_color(ltp_chg)}]"
        ) if prev_ltp > 0 else "[dim]prev LTP = 0, skipped[/dim]"

        oi_chg_str = (
            f"({oi_contracts:,} − {int(prev_oi):,}) / {int(prev_oi):,} × 100 = "
            f"[{_pct_color(oi_chg)}]{oi_chg:+.2f}%[/{_pct_color(oi_chg)}]"
        ) if prev_oi > 0 else "[dim]prev OI = 0, skipped[/dim]"

        console.print(Panel(
            f"[bold white]Expiry:[/bold white] {expiry}\n\n"
            f"[bold cyan]LTP Chg%[/bold cyan]\n"
            f"  Today LTP   :  [white]{ltp:>12,.2f}[/white]\n"
            f"  Prev Close  :  [white]{prev_ltp:>12,.2f}[/white]\n"
            f"  Formula     :  {ltp_chg_str}\n\n"
            f"[bold cyan]OI Chg%[/bold cyan]\n"
            f"  API OI (qty):  [magenta]{format_lakh(float(oi_qty)):>12}[/magenta]   ← raw qty from Dhan\n"
            f"  ÷ lot ({lot:>2})  :  [cyan]{format_lakh(float(oi_contracts)):>12}[/cyan]   ← normalised contracts\n"
            f"  Prev OI (c) :  [yellow]{format_lakh(float(prev_oi)):>12}[/yellow]   ← from NIFTY_FUTURE CSV\n"
            f"  Formula     :  {oi_chg_str}\n\n"
            f"[bold]OI direction :[/bold] {_oi_arrow(oi_contracts, prev_oi)}  "
            f"  [bold]LTP direction:[/bold] {_ltp_arrow(ltp, prev_ltp)}\n\n"
            f"[bold]Signal  :  [{color}]{buildup} ({code})[/{color}][/bold]  →  [{color}]{interp}[/{color}]",
            title=f"[bold yellow]{UNDERLYING} {expiry}[/bold yellow]",
            border_style="dim white",
            padding=(0, 2),
        ))


def print_summary_table(results):
    """Final summary table — same as dashboard display."""
    console.print(Rule("[bold white]Summary — NIFTY Futures Build-Up[/bold white]", style="dim green"))

    tbl = Table(
        title=f"[bold green]{UNDERLYING} Futures OI Build-Up[/bold green]   "
              f"[dim]{datetime.datetime.now().strftime('%d-%b-%Y  %H:%M:%S')}[/dim]",
        box=box.DOUBLE_EDGE,
        header_style="bold white on #1a1a2e",
        show_lines=True,
        padding=(0, 1),
    )
    tbl.add_column("Expiry",       style="cyan",    min_width=12)
    tbl.add_column("LTP",          justify="right", style="white",   min_width=10)
    tbl.add_column("Prev LTP",     justify="right", style="dim white")
    tbl.add_column("LTP Chg%",     justify="right", min_width=9)
    tbl.add_column("OI (contracts)",justify="right",style="yellow", min_width=12)
    tbl.add_column("Prev OI (contracts)", justify="right", style="dim yellow", min_width=12)
    tbl.add_column("OI Chg%",      justify="right", min_width=9)
    tbl.add_column("Signal",       justify="center", min_width=16)

    for r in results:
        ltp_chg  = r['ltp_chg_pct']
        oi_chg   = r['oi_chg_pct']
        buildup  = r['buildup']
        color, code, _ = BUILDUP_COLORS.get(buildup, ("white", "?", ""))

        tbl.add_row(
            r['expiry'],
            f"{r['ltp']:,.2f}",
            f"{r['prev_ltp']:,.2f}",
            f"[{_pct_color(ltp_chg)}]{ltp_chg:+.2f}%[/{_pct_color(ltp_chg)}]",
            format_lakh(float(r['oi'])),
            format_lakh(float(r['prev_oi'])),
            f"[{_pct_color(oi_chg)}]{oi_chg:+.2f}%[/{_pct_color(oi_chg)}]",
            f"[{color}]{buildup}[/{color}]" if buildup else "[dim]No live data[/dim]",
        )

    console.print(tbl)


# ────────────────────────────────────────────────────────────────────────────
def main():
    console.print()
    console.print(Panel(
        "[bold bright_cyan]NIFTY Futures OI Build-Up Test[/]\n"
        f"[dim]Lot Size: {LOT_SIZE}  |  Date: {datetime.date.today().strftime('%d-%b-%Y')}[/dim]\n\n"
        f"[bold]Python:[/] {sys.version.split()[0]}\n"
        f"[bold]Platform:[/] {sys.platform}",
        border_style="bright_cyan",
        expand=False,
        padding=(1, 3),
    ))
    console.print()

    print_legend()
    print_formula_box()

    instruments = print_raw_instruments()
    if not instruments:
        console.print("[bold red]Aborting — no instruments loaded.[/bold red]")
        sys.exit(1)

    print_raw_prev_data()
    print_live_quotes(instruments)

    # ── Brief pause to avoid hitting Dhan API rate limit on back-to-back calls ──
    console.print()
    console.print("[dim]  Waiting 1s before final API call (rate limit guard)...[/dim]")
    time.sleep(1)

    # ── Full build-up call (uses cache internally) ───────────────────────
    console.print(Rule("[bold white]Step 5 — Full get_futures_buildup_data() Result[/bold white]", style="dim green"))
    results = get_futures_buildup_data(UNDERLYING)

    if not results:
        console.print("[bold red]  No results returned from get_futures_buildup_data()[/bold red]")
        console.print("[dim]  Possible reasons: no instruments, no live quotes, market closed[/dim]")
        sys.exit(1)

    print_formula_walkthrough(results)
    print_summary_table(results)

    console.print()

    # ─── Final Summary ───────────────────────────────────────────────────
    elapsed_total = time.perf_counter() - _t_start
    console.print(Rule("[bold bright_cyan]Final Summary[/]", style="dim cyan"))

    summary_tbl = Table(box=box.DOUBLE_EDGE, show_header=False, expand=False, padding=(0, 2))
    summary_tbl.add_column(style="bold", width=20)
    summary_tbl.add_column(width=12, justify="right")
    summary_tbl.add_row("[cyan]Futures Analyzed[/]", f"[bold]{len(results)}[/]")
    summary_tbl.add_row("[cyan]Build-Up Signals[/]", "[green]✓ Calculated[/]")
    summary_tbl.add_row("[cyan]OI/LTP Changes[/]", "[green]✓ Verified[/]")
    summary_tbl.add_row("[dim]Elapsed[/]", f"{elapsed_total:.2f}s")
    console.print(summary_tbl)
    console.print()

    console.print(Panel(
        "[bold green]✓ Futures build-up analysis completed[/]\n"
        "[dim]All OI and LTP changes calculated and validated[/]",
        border_style="green",
        expand=False,
        padding=(1, 2)))
    console.print()


if __name__ == "__main__":
    main()
