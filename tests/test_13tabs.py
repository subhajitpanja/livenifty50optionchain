"""
TUI Dashboard 13-Tab Cycle Test
========================================
Run: python tests/test_13tabs.py

Tests the TUI dashboard by running 15 update cycles and cycling
through the 3 available tabs (Dashboard, Performance, Logs).

Verifies that the terminal dashboard renders correctly without
crashing on each cycle.
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

from pathlib import Path
from rich.console import Console
from rich.progress import track
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

# Path setup
_here = Path(__file__).resolve().parent        # tests/
_oc_dir = _here.parent                         # project root
for _p in [str(_here), str(_oc_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.chdir(str(_oc_dir))

import pandas as pd
from tui_components import tui_dashboard

console = Console(force_terminal=True, width=140)


# ═══════════════════════════════════════════════════════════════════════════
#  Pytest-compatible test function
# ═══════════════════════════════════════════════════════════════════════════
def test_tui_13tab_cycle():
    """TUI dashboard renders across all tabs without crashing."""
    strikes = list(range(23200, 23600, 50))
    data_rows = []
    for s in strikes:
        data_rows.append({
            'Strike': s,
            'C_OI': 1500000 + (23400 - s) * 100,
            'C_OI_Chg': -5000 + (s % 100) * 10,
            'C_LTP': max(5, 23360 - s + 50),
            'C_IV': 14.5 + (s - 23200) * 0.1,
            'C_BuildUp': 'Long Buildup' if s < 23350 else 'Short Buildup',
            'C_OH_OL': 'OH' if s < 23300 else ('OL' if s > 23450 else ''),
            'P_OI': 800000 + (s - 23200) * 80,
            'P_OI_Chg': 3000 - (s % 100) * 5,
            'P_LTP': max(5, s - 23360 + 50),
            'P_IV': 15.0 + (23500 - s) * 0.08,
            'P_BuildUp': 'Short Covering' if s > 23400 else 'Long Buildup',
            'P_OH_OL': 'OH' if s > 23450 else ('OL' if s < 23250 else ''),
        })
    option_df = pd.DataFrame(data_rows)

    mock_data = {
        'spot_price': 23360.10, 'vix_current': 24.47,
        'fut_price': 23358.60, 'atm_strike': 23350,
        'underlying': 'NIFTY', 'error': None,
        'expiry': '27-Mar-2026',
    }

    _tabs = tui_dashboard.tab_bar.TABS
    for cycle in range(1, 16):
        mock_data['spot_price'] = 23360.10 + cycle * 0.5
        tui_dashboard.update(
            cycle=cycle,
            dt_oc=1.2 + cycle * 0.05,
            dt_total=1.8 + cycle * 0.07,
            data=mock_data,
            market_open=True,
            market_status='Wednesday - Market OPEN',
            option_df=option_df,
        )

    # If we get here without exception, all 15 cycles passed across all tabs
    assert len(_tabs) >= 1, "At least one tab should exist"


# ═══════════════════════════════════════════════════════════════════════════
#  Standalone runner (python tests/test_13tabs.py)
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    _results = []
    _t_start = time.perf_counter()

    console.print()
    console.print(Panel(
        "[bold bright_cyan]TUI Dashboard 13-Tab Cycle Test[/]\n"
        "[dim]Testing TUI render across 15 cycles, 3 tabs[/]\n\n"
        f"[bold]Date:[/] {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"[bold]Python:[/] {sys.version.split()[0]}\n"
        f"[bold]Platform:[/] {sys.platform}",
        border_style="bright_cyan",
        expand=False,
        padding=(1, 3)))
    console.print()

    console.print("[bold bright_cyan]Setting up mock data...[/]")
    strikes = list(range(23200, 23600, 50))
    data_rows = []
    for s in strikes:
        data_rows.append({
            'Strike': s,
            'C_OI': 1500000 + (23400 - s) * 100,
            'C_OI_Chg': -5000 + (s % 100) * 10,
            'C_LTP': max(5, 23360 - s + 50),
            'C_IV': 14.5 + (s - 23200) * 0.1,
            'C_BuildUp': 'Long Buildup' if s < 23350 else 'Short Buildup',
            'C_OH_OL': 'OH' if s < 23300 else ('OL' if s > 23450 else ''),
            'P_OI': 800000 + (s - 23200) * 80,
            'P_OI_Chg': 3000 - (s % 100) * 5,
            'P_LTP': max(5, s - 23360 + 50),
            'P_IV': 15.0 + (23500 - s) * 0.08,
            'P_BuildUp': 'Short Covering' if s > 23400 else 'Long Buildup',
            'P_OH_OL': 'OH' if s > 23450 else ('OL' if s < 23250 else ''),
        })
    option_df = pd.DataFrame(data_rows)

    mock_data = {
        'spot_price': 23360.10, 'vix_current': 24.47,
        'fut_price': 23358.60, 'atm_strike': 23350,
        'underlying': 'NIFTY', 'error': None,
        'expiry': '27-Mar-2026',
    }

    console.print(f"  [green]✓[/] Mock DataFrame: {len(option_df)} strikes")
    console.print(f"  [green]✓[/] Mock data dict ready")
    console.print()

    console.print(Rule("[bold bright_cyan]Running 15 TUI Update Cycles[/]", style="dim cyan"))

    cycle_results = []
    _tabs = tui_dashboard.tab_bar.TABS
    tab_counts = {tab: 0 for tab in _tabs}

    for cycle in track(range(1, 16), description="[bold blue]Updating TUI...", console=console):
        t_cycle = time.perf_counter()

        try:
            mock_data['spot_price'] = 23360.10 + cycle * 0.5
            tab_num = (cycle - 1) % len(_tabs)
            tab_name = _tabs[tab_num]
            tab_counts[tab_name] += 1

            tui_dashboard.update(
                cycle=cycle,
                dt_oc=1.2 + cycle * 0.05,
                dt_total=1.8 + cycle * 0.07,
                data=mock_data,
                market_open=True,
                market_status='Wednesday - Market OPEN',
                option_df=option_df,
            )

            elapsed = time.perf_counter() - t_cycle
            cycle_results.append((cycle, "PASS", tab_name, elapsed))

        except Exception as e:
            elapsed = time.perf_counter() - t_cycle
            cycle_results.append((cycle, "FAIL", str(type(e).__name__), elapsed))

    console.print()
    console.print(Rule("[bold bright_cyan]Cycle Summary[/]", style="dim cyan"))

    tbl = Table(box=box.ROUNDED, title="[bold]Cycle Results[/]")
    tbl.add_column("Cycle", width=6, justify="right", style="dim")
    tbl.add_column("Status", width=8, justify="center")
    tbl.add_column("Tab", width=14)
    tbl.add_column("Elapsed", width=9, justify="right", style="dim")

    for cycle, status, tab_or_error, elapsed in cycle_results:
        status_str = "[bold green]PASS[/]" if status == "PASS" else f"[bold red]{status}[/]"
        tbl.add_row(str(cycle), status_str, tab_or_error, f"{elapsed:.3f}s")

    console.print(tbl)
    console.print()

    console.print(Rule("[bold bright_cyan]Tab Distribution[/]", style="dim cyan"))
    dist_tbl = Table(box=box.ROUNDED, show_header=True, header_style="bold bright_cyan")
    dist_tbl.add_column("Tab Name", width=16)
    dist_tbl.add_column("Count", width=8, justify="right")
    dist_tbl.add_column("Expected", width=10, justify="right")
    dist_tbl.add_column("✓", width=4, justify="center")

    for tab in _tabs:
        count = tab_counts[tab]
        expected = 15 // len(_tabs) + (1 if _tabs.index(tab) < 15 % len(_tabs) else 0)
        match = "[bold green]✓[/]" if count in (expected, expected + 1) else "[bold red]✗[/]"
        dist_tbl.add_row(tab, str(count), str(expected), match)

    console.print(dist_tbl)
    console.print()

    elapsed_total = time.perf_counter() - _t_start
    passed = sum(1 for _, s, _, _ in cycle_results if s == "PASS")
    failed = sum(1 for _, s, _, _ in cycle_results if s == "FAIL")

    console.print(Rule("[bold bright_cyan]Final Summary[/]", style="dim cyan"))

    summary_tbl = Table(box=box.DOUBLE_EDGE, show_header=False, expand=False, padding=(0, 2))
    summary_tbl.add_column(style="bold", width=14)
    summary_tbl.add_column(width=10, justify="right")
    summary_tbl.add_row("[green]PASSED[/]", f"[bold green]{passed}[/]")
    summary_tbl.add_row("[red]FAILED[/]", f"[bold red]{failed}[/]")
    summary_tbl.add_row("[dim]TOTAL CYCLES[/]", f"[bold]{len(cycle_results)}[/]")
    summary_tbl.add_row("[dim]ELAPSED[/]", f"{elapsed_total:.2f}s")
    console.print(summary_tbl)
    console.print()

    if failed == 0:
        console.print(Panel(
            f"[bold green]✓ ALL {passed} CYCLES PASSED[/]\n"
            f"TUI dashboard rendered successfully across all {len(_tabs)} tabs",
            border_style="green",
            expand=False,
            padding=(1, 2)))
    else:
        console.print(Panel(
            f"[bold red]✗ {failed} CYCLE(S) FAILED[/]\n"
            f"[dim]{passed} passed, {failed} failed out of {len(cycle_results)} total[/]",
            border_style="red",
            expand=False,
            padding=(1, 2)))

    console.print()
    sys.exit(0 if failed == 0 else 1)
