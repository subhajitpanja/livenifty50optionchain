"""
Color Constants — Single source of truth for all dashboard colors.
==================================================================
Import into Python files (optionchain_gradio.py, optionchain_streamlit.py).
CSS uses matching :root variables in templates/css/styles.css.
"""

# ═══════════════════════════════════════════════════════════════════════════
#^# HEADING COLORS
# ═══════════════════════════════════════════════════════════════════════════
H1_CLR = '#e0e0ff'     # main dashboard title
H2_CLR = '#ffd700'     # section headings (OI Distribution, Change in OI, etc.)
H3_CLR = '#b0bec5'     # sub-section / table group headings

# ═══════════════════════════════════════════════════════════════════════════
#^# BAR CHART COLORS
# ═══════════════════════════════════════════════════════════════════════════
CALL_BAR = '#ef5350'        # red  — Call OI bars
PUT_BAR = '#26a69a'         # green — Put OI bars
CALL_BAR_NEG = '#ef535055'  # faded red for negative OI change
PUT_BAR_NEG = '#26a69a55'   # faded green for negative OI change

# ═══════════════════════════════════════════════════════════════════════════
#^# SEMANTIC COLORS
# ═══════════════════════════════════════════════════════════════════════════
GREEN = '#00e676'         # bullish / positive / Long Build Up
RED = '#ef5350'           # bearish / negative / Short Build Up
CYAN = '#00bcd4'          # Short Covering (Call)
ORANGE = '#ffa726'        # Long Unwinding / neutral
BLUE = '#42a5f5'          # Short Covering (Futures) / expiry
YELLOW_GREEN = '#adff2f'  # Long Unwinding (Put) / OI rank put #3
GOLD = '#ffd700'          # ATM / SPOT / highlights
LIMEGREEN = '#32cd32'     # MACD bullish / EMA bullish / O=H O=L badges
BRIGHT_RED = '#ff0000'    # MACD bearish / RSI oversold / O=H O=L badges
WHITE = '#FFFFFF'         # OI rank text (Call side)
BLACK = '#000000'         # OI rank text (Put side) / badge text
DEEP_ORANGE = '#ff9800'   # VWAP line / secondary indicator line

# ═══════════════════════════════════════════════════════════════════════════
#^# BUILD-UP COLORS
# ═══════════════════════════════════════════════════════════════════════════
#~# Build Up colors — CALL side
BU_CALL = {'LB': GREEN, 'SC': YELLOW_GREEN, 'SB': RED, 'LU': ORANGE}
#~# Build Up colors — PUT side (reversed: LB=bearish, SB=bullish for puts)
BU_PUT = {'LB': RED, 'SC': ORANGE, 'SB': GREEN, 'LU': YELLOW_GREEN}
#~# Futures uses full names
BU_FUT = {
    'Long Build Up': GREEN, 'Short Covering': YELLOW_GREEN,
    'Short Build Up': RED,  'Long Unwinding': ORANGE,
}

# ═══════════════════════════════════════════════════════════════════════════
#^# OI RANK COLORS — H1/H2/H3 markers for top 3 OI strikes
# ═══════════════════════════════════════════════════════════════════════════
OI_RANK_CALL = {1: '#a50004', 2: '#e60045', 3: '#ff0000'}   # firebrick / red / bright-red
OI_RANK_PUT = {1: '#32cd32', 2: '#00e676', 3: '#adff2f'}    # limegreen / green / yellow-green

# ═══════════════════════════════════════════════════════════════════════════
#^# UI / THEME COLORS
# ═══════════════════════════════════════════════════════════════════════════
MUTED = '#888'            # muted / disabled
MUTED_LIGHT = '#9aa4ad'   # lighter muted — TF indicator no-data, plotly labels
TEXT_DEFAULT = '#e0e0e0'  # default text
TEXT_GREEN = '#69f0ae'    # net positive
TEXT_RED = '#ff6b6b'      # net negative
TEXT_LIGHT = '#cfd8dc'    # plotly font / chart text
ATM_BG = '#000'           # ATM row text color (black on gold)
NEUTRAL_PURPLE = '#ce93d8'  # RSI neutral zone / plotly RSI neutral
RED_BRIGHT = '#ff5252'    # RSI oversold / EMA signal line

# ═══════════════════════════════════════════════════════════════════════════
#^# CHART / PLOTLY COLORS
# ═══════════════════════════════════════════════════════════════════════════
PANEL_BG = '#0e1117'      # plotly paper/plot background, hatch pattern
LIGHT_BLUE = '#4fc3f7'    # straddle chart line, MACD signal
GRID_COLOR = '#1e2530'    # plotly grid lines
BORDER_COLOR = '#2a3140'  # plotly legend border

# ═══════════════════════════════════════════════════════════════════════════
#^# RGBA COLORS — Plotly (opacity/transparency required for overlays/fills)
# ═══════════════════════════════════════════════════════════════════════════
#~# RSI Indicator lines & zones
RSI_OVERBOUGHT_LINE = 'rgba(38,166,154,0.70)'     # PUT_BAR 70% — RSI 70 line
RSI_NEUTRAL_LINE = 'rgba(150,150,150,0.35)'       # Gray 35% — RSI 50 line
RSI_OVERSOLD_LINE = 'rgba(239,83,80,0.70)'        # CALL_BAR 70% — RSI 30 line
RSI_OVERBOUGHT_ZONE = 'rgba(38,166,154,0.07)'     # PUT_BAR 7% — RSI 70-100 fill
RSI_OVERSOLD_ZONE = 'rgba(239,83,80,0.07)'        # CALL_BAR 7% — RSI 0-30 fill

#~# Annotation backgrounds (badges, tooltips)
ANNOTATION_BG_PRIMARY = 'rgba(14,17,23,0.94)'     # PANEL_BG 94% — main annotations
ANNOTATION_BG_SECONDARY = 'rgba(10,10,15,0.95)'   # Darker 95% — PnL badge
ANNOTATION_BG_TERTIARY = 'rgba(10,10,15,0.90)'    # Darker 90% — RSI badge
LEGEND_BG = 'rgba(14,17,23,0.88)'                 # PANEL_BG 88% — chart legend

#~# Candlestick fills
CANDLE_INCREASING_75 = 'rgba(38,166,154,0.75)'    # PUT_BAR 75% — bullish candle
CANDLE_DECREASING_75 = 'rgba(239,83,80,0.75)'     # CALL_BAR 75% — bearish candle
CANDLE_INCREASING_80 = 'rgba(38,166,154,0.80)'    # PUT_BAR 80% — bullish candle (alt)
CANDLE_DECREASING_80 = 'rgba(239,83,80,0.80)'     # CALL_BAR 80% — bearish candle (alt)

#~# Chart elements
SPIKE_COLOR = 'rgba(255,255,255,0.30)'            # White 30% — crosshair spike
GRAY_LINE_25 = 'rgba(180,180,180,0.25)'           # Gray 25% — MACD zero line
GRAY_LINE_35 = 'rgba(180,180,180,0.35)'           # Gray 35% — zero line (alt)
BAND_FILL_BLUE = 'rgba(100,181,246,0.08)'         # LIGHT_BLUE 8% — band fill
GOLD_LINE_60 = 'rgba(255,215,0,0.60)'             # GOLD 60% — ATM line
BLUE_LINE_50 = 'rgba(66,165,245,0.50)'            # BLUE 50% — spot line
BLUE_LINE_40 = 'rgba(66,165,245,0.40)'            # BLUE 40% — border (alt)

#~# OI Rank colors (full opacity RGBA for plotly compatibility)
RANK_PUT_1 = 'rgba(50,205,50,1.0)'                # LIMEGREEN — H1 put
RANK_PUT_2 = 'rgba(0,230,118,1.0)'                # GREEN — H2 put
RANK_PUT_3 = 'rgba(173,255,47,1.0)'               # YELLOW_GREEN — H3 put
RANK_CALL_1 = 'rgba(165,0,4,1.0)'                 # OI_RANK_CALL #1
RANK_CALL_2 = 'rgba(230,0,69,1.0)'                # OI_RANK_CALL #2
RANK_CALL_3 = 'rgba(255,0,0,1.0)'                 # OI_RANK_CALL #3

#~# Bar chart defaults (full opacity RGBA)
DEFAULT_PUT_RGBA = 'rgba(38,166,154,1.0)'         # PUT_BAR 100%
DEFAULT_CALL_RGBA = 'rgba(239,83,80,1.0)'         # CALL_BAR 100%

#~# Utility
TRANSPARENT = 'rgba(0,0,0,0)'                     # Fully transparent
