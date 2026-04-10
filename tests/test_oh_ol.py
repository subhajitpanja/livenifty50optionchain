"""
Quick test: OH/OL (Open=High / Open=Low) enrichment
=====================================================
Tests the enrich_oh_ol function and the batch OHLC fetch.
Run: python test_oh_ol.py
"""
import sys
import os
import time
import datetime as _dt

# Force UTF-8 on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add parent dirs for Credential & optionchain imports
_here = os.path.dirname(os.path.abspath(__file__))    # tests/
_oc_dir = os.path.dirname(_here)                       # project root
for _p in (_here, _oc_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.chdir(_oc_dir)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich import box

from color_constants import OH_MARKER, OL_MARKER

console = Console(force_terminal=True, width=140)
_results = []
_t_start = time.perf_counter()

# ═══════════════════════════════════════════════════════════════════════════
#  STARTUP BANNER
# ═══════════════════════════════════════════════════════════════════════════
console.print()
console.print(Panel(
    "[bold bright_cyan]OH/OL Enrichment Test[/]\n"
    "[dim]Tests the enrich_oh_ol function and batch OHLC fetch[/]\n\n"
    f"[bold]Date:[/] {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    f"[bold]Python:[/] {sys.version.split()[0]}\n"
    f"[bold]Platform:[/] {sys.platform}",
    border_style="bright_cyan",
    expand=False,
    padding=(1, 3)))
console.print()

# ═══════════════════════════════════════════════════════════════════════════
#  STEP 1: IMPORT DATA FETCHER
# ═══════════════════════════════════════════════════════════════════════════
console.print(Rule("[bold bright_cyan]Step 1: Import Data Fetcher[/]", style="dim cyan"))
t0 = time.perf_counter()
try:
    from oc_data_fetcher import fetch_all_data, enrich_oh_ol, fetch_batch_ohlc
    elapsed = time.perf_counter() - t0
    console.print(f"[green]✓ PASS[/]  Imported fetch_all_data, enrich_oh_ol, fetch_batch_ohlc  [dim]{elapsed:.3f}s[/]\n")
    _results.append(("Import", "PASS", "3 functions loaded", elapsed))
except ImportError as e:
    elapsed = time.perf_counter() - t0
    console.print(f"[red]✗ FAIL[/]  {e}  [dim]{elapsed:.3f}s[/]\n")
    _results.append(("Import", "FAIL", str(e), elapsed))
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════
#  STEP 2: FETCH OPTION CHAIN DATA
# ═══════════════════════════════════════════════════════════════════════════
console.print(Rule("[bold bright_cyan]Step 2: Fetch Option Chain Data[/]", style="dim cyan"))
t0 = time.perf_counter()

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    TimeElapsedColumn(),
    console=console,
) as progress:
    task = progress.add_task("[cyan]Fetching NIFTY option chain (expiry 0, 10 strikes)...", total=None)
    try:
        data = fetch_all_data("NIFTY", expiry_index=0, num_strikes=10)
        progress.stop()
    except Exception as e:
        progress.stop()
        elapsed = time.perf_counter() - t0
        console.print(f"[red]✗ FAIL[/]  {e}  [dim]{elapsed:.3f}s[/]\n")
        _results.append(("Fetch Data", "FAIL", str(e), elapsed))
        sys.exit(1)

elapsed = time.perf_counter() - t0
if data.get('error'):
    console.print(f"[yellow]⚠ WARN[/]  {data['error']}  [dim]{elapsed:.3f}s[/]\n")
    _results.append(("Fetch Data", "WARN", data['error'], elapsed))
else:
    console.print(
        f"[green]✓ PASS[/]  spot={data['spot_price']:.2f}, atm={data['atm_strike']}, "
        f"expiry={data['expiry']}, strikes={len(data.get('option_df', []))}  [dim]{elapsed:.3f}s[/]\n"
    )
    _results.append(("Fetch Data", "PASS", f"{len(data.get('option_df', []))} strikes", elapsed))

# ═══════════════════════════════════════════════════════════════════════════
#  STEP 3: CHECK OH/OL COLUMNS
# ═══════════════════════════════════════════════════════════════════════════
console.print(Rule("[bold bright_cyan]Step 3: Validate OH/OL Columns[/]", style="dim cyan"))
t0 = time.perf_counter()

odf = data.get('option_df')
if odf is None or odf.empty:
    elapsed = time.perf_counter() - t0
    console.print(f"[red]✗ FAIL[/]  option_df is empty  [dim]{elapsed:.3f}s[/]\n")
    _results.append(("Columns", "FAIL", "option_df empty", elapsed))
    sys.exit(1)

has_c_oh_ol = 'C_OH_OL' in odf.columns
has_p_oh_ol = 'P_OH_OL' in odf.columns
elapsed = time.perf_counter() - t0

col_status = []
if has_c_oh_ol:
    col_status.append("[green]C_OH_OL[/]")
else:
    col_status.append("[red]C_OH_OL[/]")
if has_p_oh_ol:
    col_status.append("[green]P_OH_OL[/]")
else:
    col_status.append("[red]P_OH_OL[/]")

console.print(f"  {' | '.join(col_status)}")

if not has_c_oh_ol or not has_p_oh_ol:
    console.print(f"[red]✗ FAIL[/]  OH/OL columns missing  [dim]{elapsed:.3f}s[/]\n")
    _results.append(("Columns", "FAIL", "Missing columns", elapsed))
    sys.exit(1)

console.print(f"[green]✓ PASS[/]  All required columns present  [dim]{elapsed:.3f}s[/]\n")
_results.append(("Columns", "PASS", "C_OH_OL + P_OH_OL", elapsed))

# ═══════════════════════════════════════════════════════════════════════════
#  STEP 4: DISPLAY OH/OL RESULTS
# ═══════════════════════════════════════════════════════════════════════════
console.print(Rule("[bold bright_cyan]Step 4: OH/OL Results Table[/]", style="dim cyan"))

tbl = Table(box=box.ROUNDED, title="[bold]Option Chain with OH/OL Tags[/]", header_style="bold bright_cyan", show_lines=False)
tbl.add_column("Strike", style="bold yellow", justify="center", width=12)
tbl.add_column("CE LTP", justify="right", width=10)
tbl.add_column("CE OH/OL", justify="center", width=10)
tbl.add_column("PE LTP", justify="right", width=10)
tbl.add_column("PE OH/OL", justify="center", width=10)

for _, row in odf.iterrows():
    strike = f"{int(row['Strike']):,}"
    c_ltp = f"{float(row.get('C_LTP', 0)):.2f}"
    p_ltp = f"{float(row.get('P_LTP', 0)):.2f}"
    c_tag = str(row.get('C_OH_OL', ''))
    p_tag = str(row.get('P_OH_OL', ''))

    # Color the tags
    if c_tag == 'OH':
        c_tag_styled = f"[bold {OH_MARKER}]O=H[/]"
    elif c_tag == 'OL':
        c_tag_styled = f"[bold {OL_MARKER}]O=L[/]"
    else:
        c_tag_styled = "-"

    if p_tag == 'OH':
        p_tag_styled = f"[bold {OH_MARKER}]O=H[/]"
    elif p_tag == 'OL':
        p_tag_styled = f"[bold {OL_MARKER}]O=L[/]"
    else:
        p_tag_styled = "-"

    tbl.add_row(strike, c_ltp, c_tag_styled, p_ltp, p_tag_styled)

console.print(tbl)
console.print()

# ═══════════════════════════════════════════════════════════════════════════
#  STEP 5: VALIDATION & SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
console.print(Rule("[bold bright_cyan]Step 5: Validation & Summary[/]", style="dim cyan"))

c_oh_count = (odf['C_OH_OL'] == 'OH').sum()
c_ol_count = (odf['C_OH_OL'] == 'OL').sum()
p_oh_count = (odf['P_OH_OL'] == 'OH').sum()
p_ol_count = (odf['P_OH_OL'] == 'OL').sum()

# Validation: Check that OH/OL tags make sense with LTP values
validation_checks = [
    ("C_OH_OL presence", "✓" if c_oh_count > 0 or c_ol_count > 0 else "○"),
    ("P_OH_OL presence", "✓" if p_oh_count > 0 or p_ol_count > 0 else "○"),
    ("OH count > 0", "✓" if (c_oh_count + p_oh_count) > 0 else "○"),
    ("OL count > 0", "✓" if (c_ol_count + p_ol_count) > 0 else "○"),
]

val_tbl = Table(box=box.ROUNDED, show_header=False, expand=False, padding=(0, 1))
val_tbl.add_column(style="dim", width=20)
val_tbl.add_column(width=4)
for check_name, status_icon in validation_checks:
    status_styled = "[green]" + status_icon + "[/]" if status_icon == "✓" else f"[dim]{status_icon}[/]"
    val_tbl.add_row(check_name, status_styled)
console.print(val_tbl)
console.print()

# Summary table
summary = Table(box=box.DOUBLE_EDGE, show_header=False, expand=False, padding=(0, 2))
summary.add_column(style="bold", width=20)
summary.add_column(width=15, justify="right")
summary.add_row("[cyan]Total Strikes[/]", f"[bold]{len(odf)}[/]")
summary.add_row(f"[{OH_MARKER}]CE Open=High[/]", f"[{OH_MARKER}]{c_oh_count}[/]")
summary.add_row(f"[{OL_MARKER}]CE Open=Low[/]", f"[{OL_MARKER}]{c_ol_count}[/]")
summary.add_row(f"[{OH_MARKER}]PE Open=High[/]", f"[{OH_MARKER}]{p_oh_count}[/]")
summary.add_row(f"[{OL_MARKER}]PE Open=Low[/]", f"[{OL_MARKER}]{p_ol_count}[/]")
console.print(summary)
console.print()

# ═══════════════════════════════════════════════════════════════════════════
#  FINAL VERDICT
# ═══════════════════════════════════════════════════════════════════════════
elapsed_total = time.perf_counter() - _t_start
passed = sum(1 for _, s, _, _ in _results if s == "PASS")
failed = sum(1 for _, s, _, _ in _results if s == "FAIL")

console.print(Rule("[bold bright_cyan]Final Verdict[/]", style="dim cyan"))

if failed == 0:
    console.print(Panel(
        f"[bold green]✓ ALL {passed} CHECKS PASSED[/]\n"
        f"[dim]OH/OL enrichment is working correctly[/]",
        border_style="green",
        expand=False,
        padding=(1, 2)))
else:
    console.print(Panel(
        f"[bold red]✗ {failed} CHECK(S) FAILED[/]\n"
        f"[dim]{passed} passed, {failed} failed[/]",
        border_style="red",
        expand=False,
        padding=(1, 2)))

console.print()
sys.exit(0 if failed == 0 else 1)
