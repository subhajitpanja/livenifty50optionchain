"""
TUI Theme — Rich console theme constants for the terminal dashboard.
=====================================================================
Extends color_constants.py with TUI-specific styles for panels,
borders, sparklines, and status indicators.
"""

from rich.style import Style
from rich.theme import Theme

# ═══════════════════════════════════════════════════════════════════════════
#  NAMED STYLES
# ═══════════════════════════════════════════════════════════════════════════
STYLES = {
    # ── Header / Banner ──
    "banner.title":      Style(color="#e0e0ff", bold=True),
    "banner.subtitle":   Style(color="#b0bec5"),
    "banner.version":    Style(color="#888888", italic=True),

    # ── Market Status ──
    "market.open":       Style(color="#00e676", bold=True),
    "market.closed":     Style(color="#ef5350", bold=True),
    "market.pre":        Style(color="#ffa726", bold=True),
    "market.holiday":    Style(color="#ff6b6b", italic=True),

    # ── Data Status ──
    "status.ok":         Style(color="#00e676"),
    "status.warn":       Style(color="#ffa726"),
    "status.err":        Style(color="#ef5350", bold=True),
    "status.cached":     Style(color="#888888", italic=True),

    # ── Values ──
    "val.price":         Style(color="#e0e0e0", bold=True),
    "val.positive":      Style(color="#69f0ae"),
    "val.negative":      Style(color="#ff6b6b"),
    "val.neutral":       Style(color="#b0bec5"),
    "val.highlight":     Style(color="#ffd700", bold=True),

    # ── Panels ──
    "panel.header":      Style(color="#e0e0ff", bold=True),
    "panel.border":      Style(color="#555555"),

    # ── Table ──
    "tbl.header":        Style(color="#ffd700", bold=True),
    "tbl.key":           Style(color="#42a5f5", bold=True),
    "tbl.val":           Style(color="#e0e0e0"),

    # ── Log Levels ──
    "log.time":          Style(color="#888888"),
    "log.info":          Style(color="#42a5f5"),
    "log.success":       Style(color="#00e676"),
    "log.warning":       Style(color="#ffa726"),
    "log.error":         Style(color="#ef5350", bold=True),
    "log.debug":         Style(color="#888888", dim=True),

    # ── Sparkline / Chart ──
    "spark.up":          Style(color="#00e676"),
    "spark.down":        Style(color="#ef5350"),
    "spark.flat":        Style(color="#888888"),

    # ── OH/OL ──
    "oh":                Style(color="#ff6d00", bold=True),
    "ol":                Style(color="#2979ff", bold=True),

    # ── Tabs ──
    "tab.active":        Style(color="#ffd700", bold=True, underline=True),
    "tab.inactive":      Style(color="#888888"),
    "tab.separator":     Style(color="#555555"),
}

TUI_THEME = Theme(STYLES)

# ═══════════════════════════════════════════════════════════════════════════
#  BORDER STYLES
# ═══════════════════════════════════════════════════════════════════════════
BORDER_MAIN   = "bold #42a5f5"    # main dashboard border
BORDER_HEADER = "bold #ffd700"    # header panel
BORDER_DATA   = "#555555"            # data panels
BORDER_LOG    = "#444444"            # log panel
BORDER_ALERT  = "bold #ef5350"    # error/alert panel

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
