"""
TUI Theme — Rich console theme constants for the terminal dashboard.
=====================================================================
Extends color_constants.py with TUI-specific styles for panels,
borders, sparklines, and status indicators.

All hex colors are imported from color_constants.py (single source of truth).
"""

from rich.style import Style
from rich.theme import Theme

from color_constants import (
    H1_CLR, H3_CLR, MUTED_DARK,
    GREEN, RED, ORANGE, TEXT_RED,
    TEXT_DEFAULT, TEXT_GREEN, GOLD, BLUE,
    BORDER_GRAY_DARK, BORDER_GRAY_DARKER,
    OH_MARKER, OL_MARKER,
)

# ═══════════════════════════════════════════════════════════════════════════
#  NAMED STYLES
# ═══════════════════════════════════════════════════════════════════════════
STYLES = {
    # ── Header / Banner ──
    "banner.title":      Style(color=H1_CLR, bold=True),
    "banner.subtitle":   Style(color=H3_CLR),
    "banner.version":    Style(color=MUTED_DARK, italic=True),

    # ── Market Status ──
    "market.open":       Style(color=GREEN, bold=True),
    "market.closed":     Style(color=RED, bold=True),
    "market.pre":        Style(color=ORANGE, bold=True),
    "market.holiday":    Style(color=TEXT_RED, italic=True),

    # ── Data Status ──
    "status.ok":         Style(color=GREEN),
    "status.warn":       Style(color=ORANGE),
    "status.err":        Style(color=RED, bold=True),
    "status.cached":     Style(color=MUTED_DARK, italic=True),

    # ── Values ──
    "val.price":         Style(color=TEXT_DEFAULT, bold=True),
    "val.positive":      Style(color=TEXT_GREEN),
    "val.negative":      Style(color=TEXT_RED),
    "val.neutral":       Style(color=H3_CLR),
    "val.highlight":     Style(color=GOLD, bold=True),

    # ── Panels ──
    "panel.header":      Style(color=H1_CLR, bold=True),
    "panel.border":      Style(color=BORDER_GRAY_DARK),

    # ── Table ──
    "tbl.header":        Style(color=GOLD, bold=True),
    "tbl.key":           Style(color=BLUE, bold=True),
    "tbl.val":           Style(color=TEXT_DEFAULT),

    # ── Log Levels ──
    "log.time":          Style(color=MUTED_DARK),
    "log.info":          Style(color=BLUE),
    "log.success":       Style(color=GREEN),
    "log.warning":       Style(color=ORANGE),
    "log.error":         Style(color=RED, bold=True),
    "log.debug":         Style(color=MUTED_DARK, dim=True),

    # ── Sparkline / Chart ──
    "spark.up":          Style(color=GREEN),
    "spark.down":        Style(color=RED),
    "spark.flat":        Style(color=MUTED_DARK),

    # ── OH/OL ──
    "oh":                Style(color=OH_MARKER, bold=True),
    "ol":                Style(color=OL_MARKER, bold=True),

    # ── Tabs ──
    "tab.active":        Style(color=GOLD, bold=True, underline=True),
    "tab.inactive":      Style(color=MUTED_DARK),
    "tab.separator":     Style(color=BORDER_GRAY_DARK),
}

TUI_THEME = Theme(STYLES)

# ═══════════════════════════════════════════════════════════════════════════
#  BORDER STYLES
# ═══════════════════════════════════════════════════════════════════════════
BORDER_MAIN   = f"bold {BLUE}"              # main dashboard border
BORDER_HEADER = f"bold {GOLD}"              # header panel
BORDER_DATA   = BORDER_GRAY_DARK            # data panels
BORDER_LOG    = BORDER_GRAY_DARKER          # log panel
BORDER_ALERT  = f"bold {RED}"               # error/alert panel

# ═══════════════════════════════════════════════════════════════════════════
#  STATUS ICONS (Unicode)
# ═══════════════════════════════════════════════════════════════════════════
ICON_OK      = "\u2714"   # ✔
ICON_ERR     = "\u2718"   # ✘
ICON_WARN    = "\u26a0"   # ⚠
ICON_BULL    = "\u25b2"   # ▲
ICON_BEAR    = "\u25bc"   # ▼
ICON_FLAT    = "\u25c6"   # ◆
ICON_CLOCK   = "\u231a"   # ⌚
ICON_CHART   = "\U0001f4ca"  # 📊
ICON_FIRE    = "\U0001f525"  # 🔥
ICON_ROCKET  = "\U0001f680"  # 🚀
ICON_REFRESH = "\u21bb"   # ↻
ICON_MARKET  = "\U0001f3e6"  # 🏦
ICON_LIVE    = "\u25cf"   # ●

# ═══════════════════════════════════════════════════════════════════════════
#  SPARKLINE BLOCKS (for mini-charts in terminal)
# ═══════════════════════════════════════════════════════════════════════════
SPARK_BLOCKS = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
#               ▁ ▂ ▃ ▄ ▅ ▆ ▇ █
