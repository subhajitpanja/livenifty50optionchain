"""
Master Test Suite Runner
====================================
Run: python tests/run_all_tests.py

Executes all test files in sequence and displays a live-updating
results table with grand totals.

Tests are run as subprocesses to isolate errors. Results are aggregated
across all test files with pass/fail/skip counts.
"""
import sys
import os
import subprocess
import time
import datetime as _dt
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

console = Console(force_terminal=True, width=160)

# Test manifest: (display_name, filename, category, timeout_sec)
TEST_MANIFEST = [
    ("Download Pipeline", "test_download_pipeline.py", "DATA", 60),
    ("Pure Logic + All Functions", "test_all_functions.py", "CORE", 120),
    ("OI Combined Chart", "test_oi_combined.py", "CORE", 30),
    ("OH/OL Enrichment", "test_oh_ol.py", "API", 60),
    ("Header Section", "test_header_section.py", "API", 60),
    ("Analytics Verification", "test_analytics.py", "API", 90),
    ("Futures Build-Up", "test_futures_buildup.py", "API", 60),
    ("OI Change Calculation", "test_oi_change.py", "API", 90),
    ("Straddle Chart Pipeline", "test_straddle_chart.py", "API", 60),
    ("13 Tab TUI Cycle", "test_13tabs.py", "TUI", 30),
    # Excluded by default (300+ seconds):
    # ("MTF Indicators", "test_mtf_indicators_richprint.py", "API", 360),
]

# ═══════════════════════════════════════════════════════════════════════════
#  FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def run_one_test(script_path, timeout_sec):
    """Execute one test file as subprocess. Returns (returncode, stdout, stderr, elapsed)."""
    t0 = time.perf_counter()
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout_sec,
            cwd=str(script_path.parent.parent),
            env=env,
        )
        elapsed = time.perf_counter() - t0
        return result.returncode, result.stdout, result.stderr, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - t0
        return -1, "", f"TIMEOUT after {timeout_sec}s", elapsed
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return -1, "", str(e), elapsed

def count_in_output(text, keyword):
    """Count occurrences of a keyword in test output."""
    return text.upper().count(keyword.upper())

def parse_test_result(returncode, stdout):
    """Extract pass/fail/skip counts from test output."""
    passed = count_in_output(stdout, "PASS") // 2  # Divide by 2 because headers + results both have "PASS"
    failed = count_in_output(stdout, "FAIL") // 2
    skipped = count_in_output(stdout, "SKIP") // 2
    warned = count_in_output(stdout, "WARN")

    # Fallback: if returncode indicates failure but no explicit counts, mark as 1 failed
    if returncode != 0 and failed == 0:
        failed = 1

    return passed, failed, skipped, warned

# ═══════════════════════════════════════════════════════════════════════════
#  STARTUP BANNER
# ═══════════════════════════════════════════════════════════════════════════
console.print()
console.print(Panel(
    "[bold bright_cyan]NIFTY Option Chain — Master Test Suite[/]\n"
    "[dim]Run all tests with real-time progress tracking[/]\n\n"
    f"[bold]Date:[/] {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    f"[bold]Python:[/] {sys.version.split()[0]}\n"
    f"[bold]Platform:[/] {sys.platform}\n"
    f"[bold]Tests:[/] {len(TEST_MANIFEST)} test files",
    border_style="bright_cyan",
    expand=False,
    padding=(1, 3)))
console.print()

# ═══════════════════════════════════════════════════════════════════════════
#  BUILD STATUS TABLE (function for live updates)
# ═══════════════════════════════════════════════════════════════════════════

def build_status_table(results):
    """Build the live-updating results table."""
    tbl = Table(
        box=box.ROUNDED,
        title="[bold]Test Suite Progress[/]",
        header_style="bold bright_cyan",
        padding=(0, 1),
    )
    tbl.add_column("#", width=3, justify="right", style="dim")
    tbl.add_column("Category", width=8, style="dim")
    tbl.add_column("Test Name", width=36)
    tbl.add_column("Status", width=10, justify="center")
    tbl.add_column("PASS", width=6, justify="right")
    tbl.add_column("FAIL", width=6, justify="right")
    tbl.add_column("SKIP", width=6, justify="right")
    tbl.add_column("Time", width=8, justify="right", style="dim")

    for i, r in enumerate(results, 1):
        status_map = {
            'PENDING': "[dim]⏳ pending[/]",
            'RUNNING': "[bold yellow]▶ running[/]",
            'PASS': "[bold green]✓ PASS[/]",
            'FAIL': "[bold red]✗ FAIL[/]",
        }

        p_str = f"[green]{r.get('passed', '')}[/]" if r.get('passed') else "[dim]-[/]"
        f_str = f"[red]{r.get('failed', '')}[/]" if r.get('failed') else "[dim]-[/]"
        s_str = f"[yellow]{r.get('skipped', '')}[/]" if r.get('skipped') else "[dim]-[/]"
        t_str = f"{r.get('elapsed', 0):.1f}s" if r.get('elapsed') else "[dim]...[/]"

        tbl.add_row(
            str(i),
            r['category'],
            r['name'],
            status_map.get(r['status'], r['status']),
            p_str, f_str, s_str,
            t_str,
        )

    return tbl

# ═══════════════════════════════════════════════════════════════════════════
#  RUN TESTS WITH LIVE DISPLAY
# ═══════════════════════════════════════════════════════════════════════════

results = []
for i, (name, script_name, category, timeout) in enumerate(TEST_MANIFEST):
    results.append({
        'name': name,
        'category': category,
        'script': script_name,
        'timeout': timeout,
        'status': 'PENDING',
        'elapsed': 0,
        'passed': 0,
        'failed': 0,
        'skipped': 0,
    })

t_suite_start = time.perf_counter()

with Live(console=console, refresh_per_second=4, vertical_overflow="visible") as live:
    for i, r in enumerate(results):
        # Mark as running
        r['status'] = 'RUNNING'
        live.update(build_status_table(results))

        # Run test
        script_path = Path(__file__).parent / r['script']
        t0 = time.perf_counter()
        rc, stdout, stderr, elapsed = run_one_test(script_path, r['timeout'])
        r['elapsed'] = elapsed

        # Parse results
        p, f, s, w = parse_test_result(rc, stdout)
        r['passed'] = p
        r['failed'] = f
        r['skipped'] = s + w

        # Determine status
        if rc == 0 and f == 0:
            r['status'] = 'PASS'
        else:
            r['status'] = 'FAIL'

        # Update live display
        live.update(build_status_table(results))

suite_elapsed = time.perf_counter() - t_suite_start

# ═══════════════════════════════════════════════════════════════════════════
#  FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
console.print()
console.print(Rule("[bold bright_cyan]Grand Summary[/]", style="dim cyan"))

# Overall counts
total_passed = sum(r['passed'] for r in results)
total_failed = sum(r['failed'] for r in results)
total_skipped = sum(r['skipped'] for r in results)
tests_passed = sum(1 for r in results if r['status'] == 'PASS')
tests_failed = sum(1 for r in results if r['status'] == 'FAIL')

# Summary stats
summary_tbl = Table(box=box.DOUBLE_EDGE, show_header=False, expand=False, padding=(0, 2))
summary_tbl.add_column(style="bold", width=20)
summary_tbl.add_column(width=12, justify="right")

summary_tbl.add_row("[bold cyan]Test Files Passed[/]", f"[bold green]{tests_passed}/{len(results)}[/]")
summary_tbl.add_row("[bold cyan]Test Files Failed[/]", f"[bold red]{tests_failed}/{len(results)}[/]")
summary_tbl.add_row()
summary_tbl.add_row("[bold cyan]Total Checks Passed[/]", f"[bold green]{total_passed}[/]")
summary_tbl.add_row("[bold cyan]Total Checks Failed[/]", f"[bold red]{total_failed}[/]")
summary_tbl.add_row("[bold cyan]Total Checks Skipped[/]", f"[bold yellow]{total_skipped}[/]")
summary_tbl.add_row()
summary_tbl.add_row("[dim]Total Suite Time[/]", f"{suite_elapsed:.2f}s")

console.print(summary_tbl)
console.print()

# Breakdown by category
console.print(Rule("[bold bright_cyan]Results by Category[/]", style="dim cyan"))
categories = set(r['category'] for r in results)
cat_tbl = Table(box=box.ROUNDED, show_header=True, header_style="bold bright_cyan")
cat_tbl.add_column("Category", width=12)
cat_tbl.add_column("Tests", width=8, justify="right")
cat_tbl.add_column("Passed", width=8, justify="right")
cat_tbl.add_column("Failed", width=8, justify="right")

for cat in sorted(categories):
    cat_results = [r for r in results if r['category'] == cat]
    cat_passed = sum(1 for r in cat_results if r['status'] == 'PASS')
    cat_failed = sum(1 for r in cat_results if r['status'] == 'FAIL')
    cat_tbl.add_row(
        cat,
        str(len(cat_results)),
        f"[green]{cat_passed}[/]" if cat_failed == 0 else str(cat_passed),
        f"[red]{cat_failed}[/]" if cat_failed > 0 else "[dim]0[/]",
    )
console.print(cat_tbl)
console.print()

# Timing analysis
console.print(Rule("[bold bright_cyan]Timing Analysis[/]", style="dim cyan"))
sorted_by_time = sorted(results, key=lambda r: r['elapsed'], reverse=True)
timing_tbl = Table(box=box.ROUNDED, show_header=True, header_style="bold bright_cyan")
timing_tbl.add_column("Test", width=36)
timing_tbl.add_column("Time", width=10, justify="right")
for r in sorted_by_time[:5]:
    timing_tbl.add_row(r['name'], f"[dim]{r['elapsed']:.2f}s[/]")
console.print(timing_tbl)
console.print()

# Verdict panel
if tests_failed == 0:
    verdict_msg = f"[bold green]✓ ALL {tests_passed} TEST FILES PASSED[/]\n[dim]{total_passed} total checks passed[/]"
    verdict_border = "green"
else:
    verdict_msg = (
        f"[bold red]✗ {tests_failed} TEST FILE(S) FAILED[/]\n"
        f"[dim]{tests_passed} passed, {tests_failed} failed"
        f" | {total_passed} checks passed, {total_failed} failed[/]"
    )
    verdict_border = "red"

console.print(Panel(
    verdict_msg,
    border_style=verdict_border,
    expand=False,
    padding=(1, 2)))

console.print()
sys.exit(0 if tests_failed == 0 else 1)
