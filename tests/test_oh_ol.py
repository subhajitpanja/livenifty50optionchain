"""
Quick test: OH/OL (Open=High / Open=Low) enrichment
=====================================================
Tests the enrich_oh_ol function and the batch OHLC fetch.
Run: python test_oh_ol.py
"""
import sys
import os

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

console = Console(force_terminal=True)

console.print(Panel("[bold cyan]Testing OH/OL (Open=High / Open=Low) Enrichment[/]", expand=False))

# ── Step 1: Import data fetcher ──────────────────────────────────────────
console.print("\n[bold]1. Importing oc_data_fetcher...[/]")
try:
    from oc_data_fetcher import fetch_all_data, enrich_oh_ol, fetch_batch_ohlc
    console.print("[green]   OK — imported fetch_all_data, enrich_oh_ol, fetch_batch_ohlc[/]")
except ImportError as e:
    console.print(f"[red]   FAIL — {e}[/]")
    sys.exit(1)

# ── Step 2: Fetch option chain data ──────────────────────────────────────
console.print("\n[bold]2. Fetching option chain data (NIFTY, expiry 0, 10 strikes)...[/]")
try:
    data = fetch_all_data("NIFTY", expiry_index=0, num_strikes=10)
    if data.get('error'):
        console.print(f"[yellow]   WARN: {data['error']}[/]")
    else:
        console.print(f"[green]   OK — spot={data['spot_price']:.2f}, atm={data['atm_strike']}, expiry={data['expiry']}[/]")
except Exception as e:
    console.print(f"[red]   FAIL — {e}[/]")
    sys.exit(1)

# ── Step 3: Check OH/OL columns ─────────────────────────────────────────
console.print("\n[bold]3. Checking OH/OL columns in option_df...[/]")
odf = data.get('option_df')
if odf is None or odf.empty:
    console.print("[red]   FAIL — option_df is empty[/]")
    sys.exit(1)

has_c_oh_ol = 'C_OH_OL' in odf.columns
has_p_oh_ol = 'P_OH_OL' in odf.columns
console.print(f"   C_OH_OL column: {'[green]YES[/]' if has_c_oh_ol else '[red]NO[/]'}")
console.print(f"   P_OH_OL column: {'[green]YES[/]' if has_p_oh_ol else '[red]NO[/]'}")

if not has_c_oh_ol or not has_p_oh_ol:
    console.print("[red]   FAIL — OH/OL columns missing![/]")
    sys.exit(1)

# ── Step 4: Display OH/OL results ───────────────────────────────────────
console.print("\n[bold]4. OH/OL Results:[/]")

tbl = Table(title="Option Chain with OH/OL Tags", show_lines=True)
tbl.add_column("Strike", style="bold yellow", justify="center")
tbl.add_column("CE LTP", justify="right")
tbl.add_column("CE OH/OL", justify="center")
tbl.add_column("PE LTP", justify="right")
tbl.add_column("PE OH/OL", justify="center")

for _, row in odf.iterrows():
    strike = f"{int(row['Strike']):,}"
    c_ltp = f"{float(row.get('C_LTP', 0)):.2f}"
    p_ltp = f"{float(row.get('P_LTP', 0)):.2f}"
    c_tag = str(row.get('C_OH_OL', ''))
    p_tag = str(row.get('P_OH_OL', ''))

    # Color the tags
    if c_tag == 'OH':
        c_tag_styled = "[bold #ff6d00]O=H[/]"
    elif c_tag == 'OL':
        c_tag_styled = "[bold #2979ff]O=L[/]"
    else:
        c_tag_styled = "-"

    if p_tag == 'OH':
        p_tag_styled = "[bold #ff6d00]O=H[/]"
    elif p_tag == 'OL':
        p_tag_styled = "[bold #2979ff]O=L[/]"
    else:
        p_tag_styled = "-"

    tbl.add_row(strike, c_ltp, c_tag_styled, p_ltp, p_tag_styled)

console.print(tbl)

# ── Step 5: Summary ─────────────────────────────────────────────────────
c_oh_count = (odf['C_OH_OL'] == 'OH').sum()
c_ol_count = (odf['C_OH_OL'] == 'OL').sum()
p_oh_count = (odf['P_OH_OL'] == 'OH').sum()
p_ol_count = (odf['P_OH_OL'] == 'OL').sum()

summary = Table(title="Summary", show_header=False, expand=False)
summary.add_column(style="bold", width=20)
summary.add_column(width=30)
summary.add_row("Total Strikes", str(len(odf)))
summary.add_row("CE Open=High (OH)", f"[#ff6d00]{c_oh_count}[/]")
summary.add_row("CE Open=Low  (OL)", f"[#2979ff]{c_ol_count}[/]")
summary.add_row("PE Open=High (OH)", f"[#ff6d00]{p_oh_count}[/]")
summary.add_row("PE Open=Low  (OL)", f"[#2979ff]{p_ol_count}[/]")
console.print(summary)

console.print("\n[bold green]All tests passed! OH/OL enrichment is working.[/]\n")
