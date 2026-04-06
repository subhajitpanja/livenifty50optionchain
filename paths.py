"""
Centralized Path Configuration
===============================
All folder paths used across the project are defined here.
Import from this module instead of hardcoding paths.
"""

from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent

# ── Templates ─────────────────────────────────────────────────────────────
TEMPLATES_DIR = PROJECT_ROOT / 'templates'
CSS_DIR = TEMPLATES_DIR / 'css'
HTML_DIR = TEMPLATES_DIR / 'html'

CSS_STYLES_FILE = CSS_DIR / 'styles.css'
CSS_OPTIONCHAIN_FILE = CSS_DIR / 'optionchain_styles.css'

# Backward-compat alias (templates now live directly in html/)
HTML_OPTIONCHAIN_DIR = HTML_DIR

# ── Data ──────────────────────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / 'data'

# Source data (input CSVs organized by type)
SOURCE_DIR = DATA_DIR / 'source'
INSTRUMENTS_DIR = SOURCE_DIR / 'instruments'
VIX_DIR = SOURCE_DIR / 'vix'
FUTURES_DIR = SOURCE_DIR / 'futures'
OPTIONCHAIN_CSV_DIR = SOURCE_DIR / 'optionchain'

# Cache (runtime JSON files)
CACHE_DIR = DATA_DIR / 'cache'

# Output (generated snapshots, exports)
OUTPUT_DIR = DATA_DIR / 'output'

# Logs
LOGS_DIR = DATA_DIR / 'logs'

# Playwright download staging area
DOWNLOAD_TEMP_DIR = DATA_DIR / 'downloads'

# ── Specific cache files ─────────────────────────────────────────────────
SPOT_PRICE_CACHE_FILE = CACHE_DIR / 'spot_price_cache.json'
VIX_CACHE_FILE = CACHE_DIR / 'vix_cache.json'
OI_HISTORY_FILE = CACHE_DIR / 'oi_history.json'
OI_HISTORY_GRADIO_FILE = CACHE_DIR / 'oi_history_gradio.json'
OI_HISTORY_TERMINAL_FILE = CACHE_DIR / 'oi_history_terminal.json'
OI_SNAPSHOTS_FILE = CACHE_DIR / 'oi_snapshots.json'
OC_SNAPSHOTS_FILE = CACHE_DIR / 'oc_snapshots.json'
DAY_OPEN_SYNC_FILE = CACHE_DIR / 'day_open_sync.json'
DAY_OPENING_PRICES_FILE = CACHE_DIR / 'day_opening_prices.json'
DAY_OPENING_STRADDLES_FILE = CACHE_DIR / 'day_opening_straddles.json'
FUTURES_BUILDUP_CACHE_FILE = CACHE_DIR / 'futures_buildup_cache.json'


def ensure_dirs():
    """Create all required directories if they don't exist."""
    for d in [INSTRUMENTS_DIR, VIX_DIR, FUTURES_DIR, OPTIONCHAIN_CSV_DIR,
              CACHE_DIR, OUTPUT_DIR, LOGS_DIR, CSS_DIR, HTML_DIR,
              DOWNLOAD_TEMP_DIR]:
        d.mkdir(parents=True, exist_ok=True)
