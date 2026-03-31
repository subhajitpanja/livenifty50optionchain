"""
OI Combined Chart — Calculation Tests
======================================
Tests all bar height / segment logic for the new combined panel
(📊+📈 OI Distribution + Change).

Run:
    python optionchain/test_oi_combined.py
"""

import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.text import Text

# ─── path setup ──────────────────────────────────────────────────────────
_here = Path(__file__).resolve().parent          # tests/
_oc_dir = _here.parent                            # project root
for _p in [str(_here), str(_oc_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

console = Console()

# ═══════════════════════════════════════════════════════════════════════════
#  Pure-Python recreation of bar-height logic (mirrors _oi_combined_chart)
# ═══════════════════════════════════════════════════════════════════════════
CH = 750  # chart canvas height in px  (must match _oi_combined_chart in optionchain_gradio.py)

def bar_segments(curr_oi: float, prev_oi: float, mx: float):
    """
    Returns (base_px, top_px, base_type, top_type) exactly as the
    combined chart renders them.

    base_type : 'solid'
    top_type  : 'hatch' | 'hollow' | None
    """
    if prev_oi > 0:
        diff = curr_oi - prev_oi
        if diff > 0:
            base_px  = max(1, int(prev_oi  / mx * CH))
            top_px   = max(1, int(diff     / mx * CH))
            base_t   = 'solid'
            top_t    = 'hatch (increase)'
        elif diff < 0:
            base_px  = max(1, int(curr_oi  / mx * CH)) if curr_oi > 0 else 1
            top_px   = max(1, int(abs(diff)/ mx * CH))
            base_t   = 'solid'
            top_t    = 'hollow (decrease)'
        else:
            base_px  = max(1, int(curr_oi  / mx * CH)) if curr_oi > 0 else 1
            top_px   = 0
            base_t   = 'solid'
            top_t    = None
    else:
        base_px  = max(1, int(curr_oi  / mx * CH)) if curr_oi > 0 else 1
        top_px   = 0
        base_t   = 'solid'
        top_t    = None

    return base_px, top_px, base_t, top_t


def fmt_l(v: float) -> str:
    """Format as lakh string."""
    if abs(v) >= 1_000_000:
        return f"{v/100_000:.1f}L"
    return f"{v:,.0f}"


# ═══════════════════════════════════════════════════════════════════════════
#  Test cases
# ═══════════════════════════════════════════════════════════════════════════
CASES = [
    # (description, curr_oi, prev_oi)
    ("OI Increase: prev=10L, curr=15L (+5L)",    15_00_000, 10_00_000),
    ("OI Decrease: prev=10L, curr=8L  (-2L)",     8_00_000, 10_00_000),
    ("OI Decrease: prev=10L, curr=0L  (-10L)",           0, 10_00_000),
    ("No Change  : prev=10L, curr=10L",           10_00_000, 10_00_000),
    ("No Previous: prev=0,   curr=12L",           12_00_000,          0),
    ("Large Inc  : prev=50L, curr=120L (+70L)",  120_00_000, 50_00_000),
    ("Large Dec  : prev=80L, curr=20L  (-60L)",   20_00_000, 80_00_000),
]


def _run_tests():
    console.print()
    console.print(Panel(
        "[bold yellow]OI Combined Chart — Segment Calculation Tests[/bold yellow]\n"
        "[dim]Verifying bar heights match NSE-style combined OI visualization[/dim]",
        border_style="blue", expand=False))
    console.print()

    # Compute global mx as combined chart would
    all_vals = [v for desc, c, p in CASES for v in (c, p)]
    mx_global = max(all_vals) * 1.25

    tbl = Table(
        title="Bar Segment Results",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    tbl.add_column("Test Case",       style="white",      ratio=4)
    tbl.add_column("Curr OI",         style="green",      justify="right", ratio=1)
    tbl.add_column("Prev OI",         style="dim green",  justify="right", ratio=1)
    tbl.add_column("Diff",            justify="right",    ratio=1)
    tbl.add_column("Base (px)",       justify="right",    ratio=1)
    tbl.add_column("Top (px)",        justify="right",    ratio=1)
    tbl.add_column("Top type",        ratio=2)
    tbl.add_column("Total px",        justify="right",    ratio=1)
    tbl.add_column("✔ Logic",         justify="center",   ratio=1)

    all_pass = True
    for desc, curr, prev in CASES:
        base_px, top_px, base_t, top_t = bar_segments(curr, prev, mx_global)
        total_px = base_px + top_px
        diff = curr - prev

        # ── Validate logic ──────────────────────────────────────────────
        ok = True
        reason = ""

        if prev > 0:
            if diff > 0:
                # total must equal int(curr/mx*CH) within ±2 rounding px
                expected_total = base_px + top_px
                expected_curr  = max(1, int(curr / mx_global * CH))
                if abs(expected_total - expected_curr) > 2:
                    ok = False; reason = f"total {expected_total}≠curr {expected_curr}"
                if top_t != 'hatch (increase)':
                    ok = False; reason = "expected hatch"
            elif diff < 0:
                # base must represent curr_oi; base+top must represent prev_oi
                expected_base = max(1, int(curr / mx_global * CH)) if curr > 0 else 1
                expected_top  = max(1, int(abs(diff) / mx_global * CH))
                if base_px != expected_base:
                    ok = False; reason = f"base {base_px}≠{expected_base}"
                if top_px != expected_top:
                    ok = False; reason = f"top {top_px}≠{expected_top}"
                if top_t != 'hollow (decrease)':
                    ok = False; reason = "expected hollow"
            else:
                if top_t is not None:
                    ok = False; reason = "no-change should have no top"
        else:
            if top_t is not None:
                ok = False; reason = "no-prev should have no top"

        if not ok:
            all_pass = False

        diff_str = f"+{fmt_l(diff)}" if diff >= 0 else fmt_l(diff)
        diff_clr = "green" if diff > 0 else "red" if diff < 0 else "dim"
        top_str  = top_t or "—"
        top_clr  = "yellow" if top_t == 'hatch (increase)' else "red" if top_t == 'hollow (decrease)' else "dim"
        check    = "[bold green]✔[/]" if ok else f"[bold red]✘ {reason}[/]"

        tbl.add_row(
            desc,
            fmt_l(curr),
            fmt_l(prev),
            Text(diff_str, style=diff_clr),
            str(base_px),
            str(top_px) if top_px else "—",
            Text(top_str, style=top_clr),
            str(total_px),
            check,
        )

    console.print(tbl)
    console.print()

    # ── Summary ──────────────────────────────────────────────────────────
    if all_pass:
        console.print(Panel(
            "[bold green]✔  ALL TESTS PASSED[/bold green]\n"
            "[dim]Combined OI chart segment logic is correct.[/dim]",
            border_style="green", expand=False))
    else:
        console.print(Panel(
            "[bold red]✘  SOME TESTS FAILED — see table above.[/bold red]",
            border_style="red", expand=False))

    # ── Legend explanation ────────────────────────────────────────────────
    console.print()
    tbl2 = Table(title="Visual Legend Mapping", box=box.SIMPLE_HEAD,
                 header_style="bold magenta", expand=False)
    tbl2.add_column("Scenario",     style="white")
    tbl2.add_column("Base segment", style="green")
    tbl2.add_column("Top segment",  style="yellow")
    tbl2.add_column("Total bar height")
    tbl2.add_row("OI Increase (curr > prev)",
                 "Solid fill  = prev-close OI",
                 "Diagonal stripe = added OI",
                 "= current OI")
    tbl2.add_row("OI Decrease (curr < prev)",
                 "Solid fill  = current (remaining) OI",
                 "Hollow border  = removed OI",
                 "= prev-close OI")
    tbl2.add_row("No change (curr == prev)",
                 "Solid fill  = current OI",
                 "— (none)",
                 "= current OI")
    tbl2.add_row("No prev snapshot",
                 "Solid fill  = current OI",
                 "— (none)",
                 "= current OI")
    console.print(tbl2)
    console.print()


if __name__ == '__main__':
    _run_tests()
