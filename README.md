# Live NIFTY Option Chain Dashboard

A real-time option chain analysis dashboard for NIFTY 50 index options using Dhan API and Gradio.

## Features

- **Real-time Data**: Live option chain data from Dhan API
- **Interactive Dashboard**: Gradio-based web interface
- **Technical Analysis**: RSI, MACD, and other indicators
- **Multi-timeframe Analysis**: 5-min, 15-min, and daily charts
- **Build-up Analysis**: Long buildup, short covering, etc.
- **OI Analytics**: Open interest distribution and changes
- **Market Status Detection**: Automatic weekend/holiday detection

## Setup

### 1. Create and Activate Virtual Environment

```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Credentials

Edit `Credential/Credential.py` with your Dhan API credentials:

```python
client_code = "YOUR_CLIENT_CODE"
token_id = "YOUR_ACCESS_TOKEN"
```

### 4. Run the Dashboard

```bash
python optionchain_gradio.py
```

Then open your browser to: **http://localhost:7860**

## Project Structure

```
livenifty50optionchain/
├── optionchain_gradio.py      # Main Gradio app
├── oc_data_fetcher.py         # API data fetching logic
├── color_constants.py         # UI color definitions
├── ui_labels.py               # UI label strings
├── tui_components.py          # Terminal UI components
├── tui_theme.py               # Terminal theme settings
├── paths.py                   # Centralized path configuration
├── run.py                     # Application entry point
├── Credential/
│   └── Credential.py          # API credentials (DO NOT COMMIT)
├── data/                      # All data files
│   ├── source/                # Input data
│   │   ├── instruments/       # Instrument CSVs
│   │   ├── futures/           # Futures CSVs
│   │   ├── optionchain/       # Option chain CSVs
│   │   └── vix/               # VIX CSVs
│   ├── cache/                 # Runtime JSON cache
│   ├── output/                # Generated exports
│   └── logs/                  # Log files
├── templates/                 # HTML templates & CSS
│   ├── css/                   # Stylesheets
│   │   ├── styles.css
│   │   └── optionchain_styles.css
│   └── html/                  # HTML templates (48 files)
├── tests/                     # Test suite (9 test files)
├── docs/                      # Documentation
│   ├── STARTUP.md
│   ├── SETUP_CHECKLIST.md
│   ├── FINAL_REPORT.txt
│   └── PROJECT_SETUP_SUMMARY.txt
├── scripts/                   # Helper scripts
│   ├── activate.bat
│   └── activate.sh
├── requirements.txt           # Python dependencies
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

## Testing

Run the comprehensive test suite:

```bash
python tests/test_all_functions.py
```

Expected output: 78 passed, 3 skipped (templates are optional)

### Test Coverage

- **GROUP 1**: Pure logic functions (RSI, MACD, formatting, etc.)
- **GROUP 2**: Instrument CSV loading and symbol resolution
- **GROUP 3**: Dhan API functions (expiry, spot, VIX, futures)
- **GROUP 4**: Integration tests (full data pipeline)
- **GROUP 5**: HTML rendering and data quality checks

## Dependencies

### Core Libraries
- **gradio** — Web UI framework
- **pandas** — Data processing
- **numpy** — Numerical computing
- **plotly** — Interactive charts
- **requests** — HTTP client
- **rich** — Terminal output formatting
- **Dhan-Tradehull** — Dhan API wrapper

### Optional
- **pytest** — Test framework
- **uvicorn** — ASGI server for production

## Usage

### Basic Dashboard

Simply run:
```bash
python optionchain_gradio.py
```

The dashboard will:
1. Fetch live NIFTY spot price
2. Load available expiry dates
3. Display the option chain with OI, LTP, build-up signals
4. Show technical indicators and charts
5. Auto-refresh every 3 seconds

### API Functions

You can also use the data fetcher standalone:

```python
from oc_data_fetcher import fetch_all_data

data = fetch_all_data(underlying='NIFTY')
print(data['option_df'])  # Option chain DataFrame
print(data['metrics'])     # Calculated metrics
```

## Market Sessions

The app automatically detects:
- **Market Hours**: 09:15 - 15:30 IST (Mon-Fri)
- **Holidays**: NSE official holidays (updated yearly)
- **Weekends**: Saturday & Sunday (mock mode available)

## Troubleshooting

### API Errors
- Verify credentials in `Credential/Credential.py`
- Check Dhan API token expiration
- Ensure network connectivity

### Import Errors
- Confirm virtual environment is activated
- Run: `pip install -r requirements.txt`
- Check Python version ≥ 3.10

### Missing Templates
- Ensure `templates/html/` directory exists with `.html` files
- Ensure `templates/css/` directory exists
- Add HTML template files as needed

## AI Token Optimization

This project ships with a token-reduction pipeline for Claude Code sessions. See [CLAUDE.md](CLAUDE.md) for the rules Claude follows here.

- **claude-mem** — persistent cross-session memory (installed user-scope via Claude Code plugins)
- **caveman** — compresses CLAUDE.md / large docs (~46% savings). Run `/caveman:compress <file>` on demand.
- **code-review-graph** — local SQLite knowledge graph of the repo for ~8× cheaper code Q&A. CLI at `.venv/Scripts/code-review-graph`.

Reinstall (one-time, user scope):
```bash
npx claude-mem install
claude plugin marketplace add JuliusBrussee/caveman && claude plugin install caveman@caveman
```

Note: these apply only inside Claude Code. Copilot / Antigravity use their own context pipelines.

## Performance Notes

- Option chain refreshes every 3 seconds during market hours
- Caches expire after 30-60 seconds (configurable)
- Expiry list cached for 5 minutes
- VIX data cached separately

## License

Internal use only. All credentials and API keys must be kept confidential.

## Support

For issues or questions, check the test output:
```bash
python tests/test_all_functions.py
```

See individual test docstrings for details.
