"""
TUI Components â€” Rich-based Terminal Dashboard for Option Chain Gradio.
========================================================================
Provides an enhanced, interactive terminal display that runs alongside
the Gradio web UI.  Uses Rich library (already installed) with Live
display, Layout, Panels, Tables, and Sparklines.

Usage in optionchain_gradio.py:
    from tui_components import tui_dashboard
    tui_dashboard.update(data_dict)   # called from smart_refresh()

Components:
    TUIHeader        â€” App banner with market status
    TUIRefreshPanel  â€” Live refresh metrics with sparkline history
    TUIMarketData    â€” Spot / VIX / Future with change arrows
    TUIOHOLPanel     â€” OH/OL counts for CE/PE
    TUIAPIHealth     â€” API success/fail tracker with sparkline
    TUILogStream     â€” Rolling log with color-coded categories    TUIPanelTracker  â€" Per-panel staleness monitor with auto-alert
    TUIDataPipeline  â€" API→Parse→Render→Deliver timing breakdown    TUIDashboard     â€” Main orchestrator that renders the full layout
"""

from __future__ import annotations

import os
import sys
import time
import datetime
from collections import deque
from typing import Any

from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.columns import Columns
from rich.rule import Rule
from rich.align import Align

from tui_theme import (
    TUI_THEME,
    BORDER_MAIN, BORDER_HEADER, BORDER_DATA, BORDER_LOG, BORDER_ALERT,
    ICON_OK, ICON_ERR, ICON_WARN, ICON_BULL, ICON_BEAR, ICON_FLAT,
    ICON_CLOCK, ICON_CHART, ICON_REFRESH, ICON_MARKET, ICON_LIVE,
    ICON_FIRE, ICON_ROCKET,
    SPARK_BLOCKS,
)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  HELPER: Sparkline renderer
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def _sparkline(values: list[float], width: int = 20) -> Text:
    """Render a list of floats as a Unicode sparkline."""
    if not values:
        return Text("â”€" * width, style="dim")
    recent = values[-width:]
    mn, mx = min(recent), max(recent)
    rng = mx - mn if mx != mn else 1.0
    txt = Text()
    for v in recent:
        idx = int((v - mn) / rng * (len(SPARK_BLOCKS) - 1))
        idx = max(0, min(idx, len(SPARK_BLOCKS) - 1))
        color = "spark.up" if v >= (mn + rng * 0.5) else "spark.down"
        txt.append(SPARK_BLOCKS[idx], style=color)
    return txt


def _status_icon(ok: bool) -> str:
    """Return a colored status icon."""
    return f"[status.ok]{ICON_OK}[/]" if ok else f"[status.err]{ICON_ERR}[/]"


def _change_arrow(val: float) -> str:
    """Return a colored arrow based on positive/negative value."""
    if val > 0:
        return f"[val.positive]{ICON_BULL} +{val:.2f}[/]"
    elif val < 0:
        return f"[val.negative]{ICON_BEAR} {val:.2f}[/]"
    return f"[val.neutral]{ICON_FLAT} 0.00[/]"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  TUI HEADER â€” banner with app info and market status
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class TUIHeader:
    """Renders the top banner: app name, market status, underlying."""

    def render(self, market_open: bool, market_status: str,
               underlying: str, cycle: int) -> Panel:
        now = datetime.datetime.now().strftime("%H:%M:%S")

        title_line = Text()
        title_line.append(f" {ICON_CHART} ", style="banner.title")
        title_line.append("NIFTY Option Chain ", style="banner.title")
        title_line.append("LIVE ", style="market.open" if market_open else "market.closed")
        title_line.append(f"| {underlying} ", style="val.highlight")
        title_line.append(f"| #{cycle} ", style="banner.subtitle")
        title_line.append(f"@ {now}", style="log.time")

        status_line = Text()
        status_line.append("  ", style="banner.subtitle")
        status_line.append(ICON_LIVE, style="status.ok" if market_open else "status.err")
        status_line.append(f" {ICON_MARKET} ", style="banner.subtitle")
        status_line.append(market_status, style="market.open" if market_open else "market.closed")

        return Panel(
            Group(title_line, status_line),
            border_style=BORDER_HEADER,
            padding=(0, 1),
        )


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  TUI REFRESH PANEL â€” timing metrics with sparkline history
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class TUIRefreshPanel:
    """Tracks and displays refresh cycle timing history."""

    def __init__(self, max_history: int = 30):
        self.oc_times: deque[float] = deque(maxlen=max_history)
        self.total_times: deque[float] = deque(maxlen=max_history)
        self.max_history = max_history

    def record(self, oc_time: float, total_time: float):
        self.oc_times.append(oc_time)
        self.total_times.append(total_time)

    def render(self, dt_oc: float, dt_total: float) -> Panel:
        self.record(dt_oc, dt_total)

        tbl = Table(show_header=True, expand=True, border_style="dim",
                    header_style="tbl.header", padding=(0, 1))
        tbl.add_column("Metric", style="tbl.key", width=12)
        tbl.add_column("Value", style="tbl.val", width=10)
        tbl.add_column("Avg", style="val.neutral", width=8)
        tbl.add_column("Trend (last 20)", width=22, no_wrap=True)

        # OC Fetch
        oc_avg = sum(self.oc_times) / len(self.oc_times) if self.oc_times else 0
        oc_color = "status.ok" if dt_oc < 2.0 else ("status.warn" if dt_oc < 4.0 else "status.err")
        tbl.add_row(
            f"{ICON_REFRESH} OC Fetch",
            f"[{oc_color}]{dt_oc:.2f}s[/]",
            f"{oc_avg:.2f}s",
            _sparkline(list(self.oc_times)),
        )

        # Total
        tot_avg = sum(self.total_times) / len(self.total_times) if self.total_times else 0
        tot_color = "status.ok" if dt_total < 3.0 else ("status.warn" if dt_total < 5.0 else "status.err")
        tbl.add_row(
            f"{ICON_CLOCK} Total",
            f"[{tot_color}]{dt_total:.2f}s[/]",
            f"{tot_avg:.2f}s",
            _sparkline(list(self.total_times)),
        )

        tbl.add_row(
            "Interval", "3s", "", Text("fixed", style="dim"),
        )

        return Panel(tbl, title=f"[tbl.header]{ICON_REFRESH} Performance[/]",
                     border_style=BORDER_DATA, padding=(0, 0))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  TUI MARKET DATA â€” Spot, VIX, Future with live values
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class TUIMarketData:
    """Displays live market data: Spot, VIX, Future prices."""

    def __init__(self, max_history: int = 30):
        self.spot_history: deque[float] = deque(maxlen=max_history)
        self.vix_history: deque[float] = deque(maxlen=max_history)
        self.fut_history: deque[float] = deque(maxlen=max_history)

    def render(self, data: dict) -> Panel:
        spot = data.get('spot_price', 0)
        vix = data.get('vix_current', 0)
        fut = data.get('fut_price', 0)
        atm = data.get('atm_strike', 0)

        spot_ok = spot > 0
        vix_ok = vix > 0
        fut_ok = fut > 0

        if spot_ok:
            self.spot_history.append(spot)
        if vix_ok:
            self.vix_history.append(vix)
        if fut_ok:
            self.fut_history.append(fut)

        # Compute change from previous
        spot_chg = spot - self.spot_history[-2] if len(self.spot_history) >= 2 else 0
        vix_chg = vix - self.vix_history[-2] if len(self.vix_history) >= 2 else 0
        fut_chg = fut - self.fut_history[-2] if len(self.fut_history) >= 2 else 0

        tbl = Table(show_header=True, expand=True, border_style="dim",
                    header_style="tbl.header", padding=(0, 1))
        tbl.add_column("Metric", style="tbl.key", width=10)
        tbl.add_column("Status", width=3, justify="center")
        tbl.add_column("Value", style="val.price", width=12, justify="right")
        tbl.add_column("Change", width=14)
        tbl.add_column("Trend", width=22, no_wrap=True)

        tbl.add_row(
            "SPOT", _status_icon(spot_ok),
            f"{spot:,.2f}", _change_arrow(spot_chg),
            _sparkline(list(self.spot_history)),
        )
        tbl.add_row(
            "VIX", _status_icon(vix_ok),
            f"{vix:.2f}", _change_arrow(vix_chg),
            _sparkline(list(self.vix_history)),
        )
        tbl.add_row(
            "FUTURE", _status_icon(fut_ok),
            f"{fut:,.2f}", _change_arrow(fut_chg),
            _sparkline(list(self.fut_history)),
        )
        tbl.add_row(
            "ATM", _status_icon(atm > 0),
            f"[val.highlight]{atm:,.0f}[/]", "", Text("", style="dim"),
        )

        return Panel(tbl, title=f"[tbl.header]{ICON_MARKET} Market Data[/]",
                     border_style=BORDER_DATA, padding=(0, 0))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  TUI OH/OL PANEL â€” Opening High / Opening Low tracker
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class TUIOHOLPanel:
    """Displays OH / OL counts for Calls and Puts."""

    def render(self, option_df) -> Panel:
        c_oh = c_ol = p_oh = p_ol = 0
        has_data = False

        if option_df is not None and not option_df.empty:
            if 'C_OH_OL' in option_df.columns:
                has_data = True
                c_oh = (option_df['C_OH_OL'] == 'OH').sum()
                c_ol = (option_df['C_OH_OL'] == 'OL').sum()
            if 'P_OH_OL' in option_df.columns:
                has_data = True
                p_oh = (option_df['P_OH_OL'] == 'OH').sum()
                p_ol = (option_df['P_OH_OL'] == 'OL').sum()

        if not has_data:
            return Panel(
                Text("No OH/OL data available", style="status.cached"),
                title="[tbl.header]OH/OL[/]",
                border_style=BORDER_DATA,
            )

        tbl = Table(show_header=True, expand=True, border_style="dim",
                    header_style="tbl.header", padding=(0, 1))
        tbl.add_column("Side", style="tbl.key", width=6)
        tbl.add_column("OH", width=6, justify="center")
        tbl.add_column("OL", width=6, justify="center")
        tbl.add_column("Visual", width=24, no_wrap=True)

        # CE Row
        ce_total = c_oh + c_ol or 1
        ce_bar_oh = "\u2588" * max(1, int(c_oh / ce_total * 16))
        ce_bar_ol = "\u2588" * max(1, int(c_ol / ce_total * 16))
        ce_visual = Text()
        ce_visual.append(ce_bar_oh, style="oh")
        ce_visual.append(" ", style="dim")
        ce_visual.append(ce_bar_ol, style="ol")

        tbl.add_row("CE", f"[oh]{c_oh}[/]", f"[ol]{c_ol}[/]", ce_visual)

        # PE Row
        pe_total = p_oh + p_ol or 1
        pe_bar_oh = "\u2588" * max(1, int(p_oh / pe_total * 16))
        pe_bar_ol = "\u2588" * max(1, int(p_ol / pe_total * 16))
        pe_visual = Text()
        pe_visual.append(pe_bar_oh, style="oh")
        pe_visual.append(" ", style="dim")
        pe_visual.append(pe_bar_ol, style="ol")

        tbl.add_row("PE", f"[oh]{p_oh}[/]", f"[ol]{p_ol}[/]", pe_visual)

        return Panel(tbl, title="[tbl.header]OH / OL[/]",
                     border_style=BORDER_DATA, padding=(0, 0))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  TUI API HEALTH â€” success/fail tracker with visual sparkline
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class TUIAPIHealth:
    """Tracks API call success/failure across refresh cycles."""

    def __init__(self, max_history: int = 40):
        self.history: deque[bool] = deque(maxlen=max_history)
        self.error_count: int = 0
        self.success_count: int = 0

    def record(self, success: bool):
        self.history.append(success)
        if success:
            self.success_count += 1
        else:
            self.error_count += 1

    def render(self) -> Panel:
        total = self.success_count + self.error_count
        rate = (self.success_count / total * 100) if total > 0 else 0

        # Health bar: colored blocks for last N cycles
        bar = Text()
        for ok in self.history:
            bar.append("\u2588", style="status.ok" if ok else "status.err")
        if not self.history:
            bar = Text("\u2500" * 20, style="dim")

        # Rate color
        rate_style = "status.ok" if rate >= 95 else ("status.warn" if rate >= 80 else "status.err")

        content = Text()
        content.append(f"  Success: {self.success_count}  ", style="status.ok")
        content.append(f"Errors: {self.error_count}  ", style="status.err")
        content.append("Rate: ", style="tbl.val")
        content.append(f"{rate:.1f}%", style=rate_style)
        content.append("\n  ")
        content.append_text(bar)

        return Panel(content, title="[tbl.header]\U0001f525 API Health[/]",
                     border_style=BORDER_DATA, padding=(0, 0))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  TUI LOG STREAM â€” rolling log with categories
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class TUILogStream:
    """Maintains a rolling log of messages with color-coded levels."""

    def __init__(self, max_lines: int = 12):
        self.entries: deque[tuple[str, str, str]] = deque(maxlen=max_lines)

    def log(self, level: str, message: str):
        """Add a log entry. Level: INFO, OK, WARN, ERR, DEBUG."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.entries.append((ts, level, message))

    def info(self, msg: str):
        self.log("INFO", msg)

    def ok(self, msg: str):
        self.log("OK", msg)

    def warn(self, msg: str):
        self.log("WARN", msg)

    def error(self, msg: str):
        self.log("ERR", msg)

    def debug(self, msg: str):
        self.log("DEBUG", msg)

    def render(self) -> Panel:
        level_styles = {
            "INFO":  "log.info",
            "OK":    "log.success",
            "WARN":  "log.warning",
            "ERR":   "log.error",
            "DEBUG": "log.debug",
        }
        level_icons = {
            "INFO":  "\u2139",   # â„¹
            "OK":    ICON_OK,
            "WARN":  ICON_WARN,
            "ERR":   ICON_ERR,
            "DEBUG": "\u2022",  # â€¢
        }

        lines = Text()
        if not self.entries:
            lines.append("  Waiting for data...", style="dim")
        for ts, level, msg in self.entries:
            icon = level_icons.get(level, "\u2022")
            style = level_styles.get(level, "tbl.val")
            lines.append(f"  {ts} ", style="log.time")
            lines.append(f"{icon} {level:<5} ", style=style)
            lines.append(f"{msg}\n", style="tbl.val")

        return Panel(lines, title=f"[tbl.header]{ICON_CHART} Activity Log[/]",
                     border_style=BORDER_LOG, padding=(0, 0))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  TUI TAB BAR â€” switchable tabs for different views
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class TUITabBar:
    """Renders a tab bar with active/inactive states.

    3 tabs: Dashboard + Performance + Logs.
    """

    TABS = [
        "Dashboard", "Performance", "Logs",
    ]

    def __init__(self):
        self.active: int = 0

    def set_active(self, idx: int):
        self.active = max(0, min(idx, len(self.TABS) - 1))

    def render(self) -> Text:
        bar = Text()
        bar.append("  ")
        for i, name in enumerate(self.TABS):
            if i > 0:
                bar.append(" \u2502 ", style="tab.separator")  # â”‚
            if i == self.active:
                bar.append(f" {name} ", style="tab.active")
            else:
                bar.append(f" {name} ", style="tab.inactive")
        bar.append("  ")
        return bar


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  TUI CHARTS STATUS â€” background chart build status
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class TUIChartsStatus:
    """Displays the status of background chart builds."""

    def __init__(self):
        self.chart_states: dict[str, str] = {
            "15-Min Straddle (W0)": "pending",
            "15-Min Straddle (W1)": "pending",
            "5-Min Straddle (W0)":  "pending",
            "5-Min Straddle (W1)":  "pending",
            "ATM -1 Strike":        "pending",
            "ATM Strike":           "pending",
            "ATM +1 Strike":        "pending",
            "EMA Candlestick":      "pending",
            "OI + Candle":          "pending",
        }

    def update(self, name: str, state: str):
        """State: pending, building, cached, error."""
        if name in self.chart_states:
            self.chart_states[name] = state

    def set_all(self, state: str):
        for k in self.chart_states:
            self.chart_states[k] = state

    def render(self) -> Panel:
        state_icons = {
            "pending":  f"[dim]\u25cb[/]",     # â—‹
            "building": f"[status.warn]\u25d4[/]",  # â—”
            "cached":   f"[status.ok]{ICON_OK}[/]",
            "error":    f"[status.err]{ICON_ERR}[/]",
        }

        tbl = Table(show_header=False, expand=True, border_style="dim",
                    padding=(0, 1))
        tbl.add_column("Chart", style="tbl.val", width=24)
        tbl.add_column("Status", width=8, justify="center")

        for name, state in self.chart_states.items():
            icon = state_icons.get(state, "[dim]?[/]")
            tbl.add_row(name, icon)

        return Panel(tbl, title=f"[tbl.header]{ICON_CHART} Charts[/]",
                     border_style=BORDER_DATA, padding=(0, 0))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# ═══════════════════════════════════════════════════════════════════════════
#  TUI PANEL TRACKER — per-panel staleness monitor
# ═══════════════════════════════════════════════════════════════════════════
class TUIPanelTracker:
    """Tracks last-update timestamp per panel and detects stale ones.

    Panels that haven't updated within `stale_threshold` seconds are flagged.
    This catches cases where the browser tab is unfocused or a render stalls.
    """

    PANEL_NAMES = [
        "Header", "OI History", "OI Charts", "Option Chain",
        "Futures", "Straddle 15m", "Straddle 5m", "ATM Charts",
        "EMA Candle", "OI Candle", "TF Indicators", "History Tabs",
    ]

    def __init__(self, stale_threshold: float = 15.0):
        self.stale_threshold = stale_threshold
        self._last_update: dict[str, float] = {}
        self._stale_alerts: deque[tuple[str, str, float]] = deque(maxlen=20)

    def touch(self, panel_name: str):
        """Mark a panel as just-updated."""
        self._last_update[panel_name] = time.time()

    def touch_many(self, names: list[str]):
        """Mark multiple panels as just-updated."""
        now = time.time()
        for n in names:
            self._last_update[n] = now

    def get_stale_panels(self) -> list[tuple[str, float]]:
        """Return list of (panel_name, seconds_since_update) for stale panels."""
        now = time.time()
        stale = []
        for name in self.PANEL_NAMES:
            last = self._last_update.get(name)
            if last is None:
                continue
            age = now - last
            if age > self.stale_threshold:
                stale.append((name, age))
        return stale

    def check_and_alert(self, log_stream: 'TUILogStream') -> list[str]:
        """Check for stale panels, log alerts, return list of stale panel names."""
        stale = self.get_stale_panels()
        stale_names = []
        for name, age in stale:
            stale_names.append(name)
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._stale_alerts.append((ts, name, age))
            log_stream.warn(f"STALE: {name} not updated for {age:.0f}s")
        return stale_names

    def render(self) -> Panel:
        """Render panel health status table."""
        now = time.time()
        tbl = Table(show_header=True, expand=True, border_style="dim",
                    header_style="tbl.header", padding=(0, 1))
        tbl.add_column("Panel", style="tbl.key", width=16)
        tbl.add_column("Age", width=8, justify="right")
        tbl.add_column("Status", width=8, justify="center")

        for name in self.PANEL_NAMES:
            last = self._last_update.get(name)
            if last is None:
                tbl.add_row(name, "\u2014", "[dim]\u25cb[/]")
                continue
            age = now - last
            if age < 5:
                icon = f"[status.ok]{ICON_OK}[/]"
                age_str = f"[status.ok]{age:.1f}s[/]"
            elif age < self.stale_threshold:
                icon = f"[status.warn]{ICON_WARN}[/]"
                age_str = f"[status.warn]{age:.1f}s[/]"
            else:
                icon = f"[status.err]{ICON_ERR}[/]"
                age_str = f"[status.err]{age:.0f}s[/]"
            tbl.add_row(name, age_str, icon)

        return Panel(tbl, title=f"[tbl.header]{ICON_LIVE} Panel Health[/]",
                     border_style=BORDER_DATA, padding=(0, 0))


# ═══════════════════════════════════════════════════════════════════════════
#  TUI DATA PIPELINE — API → Parse → Render → Deliver timing
# ═══════════════════════════════════════════════════════════════════════════
class TUIDataPipeline:
    """Tracks timing through the data pipeline stages:
    API Fetch → Data Parse → HTML Render → Chart Build → Total.

    Each cycle records a breakdown dict and shows the latest + history.
    """

    STAGES = ["api_fetch", "data_parse", "html_render", "chart_build", "total"]
    STAGE_LABELS = {
        "api_fetch":   f"{ICON_REFRESH} API Fetch",
        "data_parse":  f"{ICON_CHART} Parse",
        "html_render": "\u2261 Render",
        "chart_build": f"{ICON_CHART} Charts",
        "total":       f"{ICON_CLOCK} Total",
    }
    # Thresholds (seconds): green < warn < red
    THRESHOLDS = {
        "api_fetch":   (1.5, 3.0),
        "data_parse":  (0.3, 1.0),
        "html_render": (0.5, 1.5),
        "chart_build": (2.0, 5.0),
        "total":       (3.0, 6.0),
    }

    def __init__(self, max_history: int = 30):
        self._history: dict[str, deque[float]] = {
            s: deque(maxlen=max_history) for s in self.STAGES
        }
        self._latest: dict[str, float] = {}
        self._slow_count: int = 0

    def record(self, timings: dict[str, float]):
        """Record a pipeline cycle. timings keys should match STAGES."""
        self._latest = timings
        for stage in self.STAGES:
            val = timings.get(stage, 0.0)
            self._history[stage].append(val)
        # Count slow cycles (total > red threshold)
        total = timings.get("total", 0.0)
        if total > self.THRESHOLDS["total"][1]:
            self._slow_count += 1

    def render(self) -> Panel:
        tbl = Table(show_header=True, expand=True, border_style="dim",
                    header_style="tbl.header", padding=(0, 1))
        tbl.add_column("Stage", style="tbl.key", width=14)
        tbl.add_column("Time", width=8, justify="right")
        tbl.add_column("Avg", width=8, justify="right")
        tbl.add_column("Trend", width=22, no_wrap=True)

        for stage in self.STAGES:
            label = self.STAGE_LABELS[stage]
            val = self._latest.get(stage, 0.0)
            hist = list(self._history[stage])
            avg = sum(hist) / len(hist) if hist else 0.0
            warn_th, err_th = self.THRESHOLDS[stage]
            if val < warn_th:
                color = "status.ok"
            elif val < err_th:
                color = "status.warn"
            else:
                color = "status.err"
            tbl.add_row(
                label,
                f"[{color}]{val:.2f}s[/]",
                f"{avg:.2f}s",
                _sparkline(hist),
            )

        # Show slow cycle count
        if self._slow_count > 0:
            tbl.add_row(
                f"{ICON_WARN} SlowCycles",
                f"[status.err]{self._slow_count}[/]",
                "", Text("", style="dim"),
            )

        return Panel(tbl, title=f"[tbl.header]{ICON_ROCKET} Data Pipeline[/]",
                     border_style=BORDER_DATA, padding=(0, 0))


# ═══════════════════════════════════════════════════════════════════════════
#  TUI DASHBOARD — main orchestrator
# ═══════════════════════════════════════════════════════════════════════════

class TUIDashboard:
    """
    Main TUI dashboard that composes all panels into a structured layout.
    Called from smart_refresh() on each cycle.

    Usage:
        tui = TUIDashboard()
        tui.update(cycle, dt_oc, dt_total, data, market_open, market_status, option_df)
    """

    def __init__(self):
        self.console = Console(
            force_terminal=True,
            theme=TUI_THEME,
            highlight=False,
            width=120,
        )
        self.header = TUIHeader()
        self.refresh_panel = TUIRefreshPanel()
        self.market_data = TUIMarketData()
        self.ohohl_panel = TUIOHOLPanel()
        self.api_health = TUIAPIHealth()
        self.log_stream = TUILogStream()
        self.tab_bar = TUITabBar()
        self.charts_status = TUIChartsStatus()
        self.panel_tracker = TUIPanelTracker()
        self.pipeline = TUIDataPipeline()
        self._started = False

    def _render_dashboard_tab(self, cycle: int, dt_oc: float, dt_total: float,
                               data: dict, market_open: bool, market_status: str,
                               option_df: Any) -> Group:
        """Render the Dashboard tab (tab 0)."""
        return Group(
            self.header.render(market_open, market_status,
                               data.get('underlying', 'NIFTY'), cycle),
            self.tab_bar.render(),
            Rule(style="dim"),
            Columns([
                self.market_data.render(data),
                self.ohohl_panel.render(option_df),
            ], expand=True, equal=True),
            Columns([
                self.pipeline.render(),
                self.panel_tracker.render(),
            ], expand=True, equal=True),
            Columns([
                self.api_health.render(),
            ], expand=True),
            self.log_stream.render(),
        )

    def _render_performance_tab(self, cycle: int, dt_oc: float, dt_total: float,
                                 data: dict, market_open: bool, market_status: str,
                                 option_df: Any) -> Group:
        """Render the Performance tab (tab 1)."""
        return Group(
            self.header.render(market_open, market_status,
                               data.get('underlying', 'NIFTY'), cycle),
            self.tab_bar.render(),
            Rule(style="dim"),
            Columns([
                self.pipeline.render(),
                self.refresh_panel.render(dt_oc, dt_total),
            ], expand=True, equal=True),
            Columns([
                self.panel_tracker.render(),
                self.charts_status.render(),
            ], expand=True, equal=True),
            self.api_health.render(),
        )

    def _render_logs_tab(self, cycle: int, dt_oc: float, dt_total: float,
                          data: dict, market_open: bool, market_status: str,
                          option_df: Any) -> Group:
        """Render the Logs tab (tab 2)."""
        return Group(
            self.header.render(market_open, market_status,
                               data.get('underlying', 'NIFTY'), cycle),
            self.tab_bar.render(),
            Rule(style="dim"),
            self.log_stream.render(),
        )

    def update(self, cycle: int, dt_oc: float, dt_total: float,
               data: dict, market_open: bool, market_status: str,
               option_df: Any = None, error: str | None = None,
               pipeline_timings: dict[str, float] | None = None,
               panels_updated: list[str] | None = None):
        """
        Main entry point - called from smart_refresh() on each cycle.
        Renders the full TUI dashboard to the terminal.
        Auto-cycles through 3 tabs: Dashboard, Performance, Logs.

        Args:
            pipeline_timings: dict with keys from TUIDataPipeline.STAGES
            panels_updated: list of panel names that were updated this cycle
        """
        # Record API health
        self.api_health.record(error is None)

        # Record pipeline timings
        if pipeline_timings:
            self.pipeline.record(pipeline_timings)

        # Track which panels were updated
        if panels_updated:
            self.panel_tracker.touch_many(panels_updated)

        # Check for stale panels during market hours
        if market_open:
            stale_names = self.panel_tracker.check_and_alert(self.log_stream)
            if stale_names:
                self.log_stream.warn(
                    f"#{cycle} {len(stale_names)} stale panel(s): {', '.join(stale_names)}")

        # Auto-log this cycle — structured pipeline summary
        if error:
            self.log_stream.error(f"Cycle #{cycle}: {error}")
        else:
            spot = data.get('spot_price', 0)
            vix = data.get('vix_current', 0)
            if pipeline_timings:
                api_t = pipeline_timings.get('api_fetch', 0)
                render_t = pipeline_timings.get('html_render', 0)
                self.log_stream.ok(
                    f"#{cycle} API:{api_t:.2f}s Render:{render_t:.2f}s "
                    f"Total:{dt_total:.2f}s | Spot:{spot:,.2f} VIX:{vix:.2f}"
                )
            else:
                self.log_stream.ok(
                    f"#{cycle} | OC: {dt_oc:.2f}s | Spot: {spot:,.2f} | VIX: {vix:.2f} | Total: {dt_total:.2f}s"
                )

        # Update chart status based on market hours
        if market_open:
            self.charts_status.set_all("building")
        else:
            self.charts_status.set_all("cached")

        # Auto-rotate tabs: cycle 1 -> tab 0, cycle 2 -> tab 1, ...
        num_tabs = len(TUITabBar.TABS)
        active_tab = (cycle - 1) % num_tabs
        self.tab_bar.set_active(active_tab)

        # Select renderer based on active tab
        if active_tab == 0:
            content = self._render_dashboard_tab(
                cycle, dt_oc, dt_total, data, market_open, market_status, option_df)
        elif active_tab == 1:
            content = self._render_performance_tab(
                cycle, dt_oc, dt_total, data, market_open, market_status, option_df)
        else:
            content = self._render_logs_tab(
                cycle, dt_oc, dt_total, data, market_open, market_status, option_df)

        # Clear terminal and render
        self._started = True

        self.console.print()  # blank line separator
        self.console.print(
            Panel(
                content,
                border_style=BORDER_MAIN,
                title=f"[banner.title]{ICON_ROCKET} Option Chain Terminal Dashboard[/]",
                subtitle=f"[log.time]Refresh every 3s | Tab: {TUITabBar.TABS[active_tab]}[/]",
                padding=(0, 0),
            )
        )

    def log_info(self, msg: str):
        """Add an info log entry."""
        self.log_stream.info(msg)

    def log_ok(self, msg: str):
        """Add a success log entry."""
        self.log_stream.ok(msg)

    def log_warn(self, msg: str):
        """Add a warning log entry."""
        self.log_stream.warn(msg)

    def log_error(self, msg: str):
        """Add an error log entry."""
        self.log_stream.error(msg)

    def log_debug(self, msg: str):
        """Add a debug log entry."""
        self.log_stream.debug(msg)

    def set_tab(self, tab: int | str):
        """Switch active tab by index or name."""
        if isinstance(tab, str):
            try:
                idx = [t.lower() for t in TUITabBar.TABS].index(tab.lower())
                self.tab_bar.set_active(idx)
            except ValueError:
                pass
        else:
            self.tab_bar.set_active(tab)

    def update_chart_status(self, name: str, state: str):
        """Update individual chart build status."""
        self.charts_status.update(name, state)

    def touch_panel(self, name: str):
        """Mark a panel as just-updated (delegates to panel_tracker)."""
        self.panel_tracker.touch(name)

    def touch_panels(self, names: list[str]):
        """Mark multiple panels as just-updated."""
        self.panel_tracker.touch_many(names)

    def record_pipeline(self, timings: dict[str, float]):
        """Record pipeline stage timings (delegates to pipeline)."""
        self.pipeline.record(timings)

    def get_stale_panels(self) -> list[str]:
        """Return names of panels that are stale (exceeded threshold)."""
        return [name for name, _ in self.panel_tracker.get_stale_panels()]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  MODULE-LEVEL SINGLETON
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
tui_dashboard = TUIDashboard()
