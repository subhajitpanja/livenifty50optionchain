# Project Structure Guide

## Directory Organization

```
livenifty50optionchain/
│
├── 📋 Configuration & Setup
│   ├── requirements.txt              # Python dependencies
│   ├── setup.bat                     # Windows setup script
│   ├── setup.sh                      # Linux/Mac setup script
│   ├── run_tests.bat                 # Windows test runner
│   └── run_tests.sh                  # Linux/Mac test runner
│
├── 📚 Documentation
│   ├── README.md                     # Project overview
│   ├── agents.md                     # AI agents & code-review-graph config
│   └── PROJECT_STRUCTURE.md          # This file
│
├── 🔧 Configuration Directories
│   ├── .vscode/                      # VS Code settings
│   │   └── settings.json             # Python interpreter & formatting config
│   │
│   ├── .code-review-graph/           # Code review graph database (auto-generated)
│   │   ├── config.yaml               # Graph configuration
│   │   ├── graph.db                  # SQLite knowledge graph
│   │   └── cache/                    # Temporary cache files
│   │
│   └── .git/                         # Git repository data
│
├── 🔐 Credentials & Secrets (EXCLUDED from version control)
│   └── Credential/                   # API keys, tokens, auth credentials
│       ├── __init__.py
│       ├── dhan_credentials.py       # Dhan API credentials
│       └── .gitignore                # Prevents credential leakage
│
├── 📦 Core Application Modules
│   ├── optionchain_gradio.py        # Main Gradio web interface
│   ├── oc_data_fetcher.py           # Data fetching & API calls
│   ├── paths.py                     # Path configuration & constants
│   └── color_constants.py           # UI color definitions
│
├── 🎨 UI & Theme Components
│   ├── tui_components.py            # Terminal UI components
│   └── tui_theme.py                 # Terminal UI theming & styles
│
├── ✅ Testing Suite
│   ├── tests/                       # Test directory
│   │   ├── __init__.py
│   │   ├── test_*.py                # Individual test modules
│   │   └── conftest.py              # Pytest configuration
│   │
│   └── pytest.ini                   # Pytest settings
│
├── 🐍 Virtual Environment
│   └── .venv/                       # Python virtual environment (auto-generated)
│       ├── Scripts/                 # Executables (Windows)
│       ├── bin/                     # Executables (Linux/Mac)
│       └── Lib/                     # Installed packages
│
└── 📖 Environment Files
    └── .env.example                 # Example environment variables (if needed)

```

## File Purpose Reference

### Setup & Execution
- **setup.bat** - Windows automatic environment setup
- **setup.sh** - Linux/Mac automatic environment setup
- **run_tests.bat** - Windows test execution
- **run_tests.sh** - Linux/Mac test execution
- **requirements.txt** - All Python package dependencies with pinned versions

### Core Application
- **optionchain_gradio.py** - Main Gradio web UI application
- **oc_data_fetcher.py** - Handles API calls and data retrieval
- **paths.py** - Centralized path management
- **color_constants.py** - UI color definitions for consistency

### UI & Theming
- **tui_components.py** - Reusable terminal UI components
- **tui_theme.py** - Terminal theming and styling system

### Configuration
- **.vscode/settings.json** - Python interpreter path, formatting, linting
- **.code-review-graph/config.yaml** - Code-review-graph settings
- **.gitignore** - Git exclusion rules (Credential/, .venv/, etc.)

### Testing
- **tests/** - Test suite directory
- **pytest.ini** - Pytest configuration

## Setup Workflow

### 1. Initial Setup (One-time)
```bash
# Windows
.\setup.bat

# Linux/Mac
bash setup.sh
```

This will:
- ✅ Create Python virtual environment
- ✅ Install all dependencies from requirements.txt
- ✅ Install code-review-graph for code review optimization
- ✅ Initialize code-review-graph knowledge graph
- ✅ Setup git hooks for automatic updates

### 2. Run Tests
```bash
# Windows
.\run_tests.bat

# Linux/Mac
bash run_tests.sh
```

This will:
- ✅ Verify virtual environment
- ✅ Check all dependencies
- ✅ Run pytest on test suite
- ✅ Check Python syntax in main modules
- ✅ Verify critical imports

### 3. Development
```bash
# Activate virtual environment (if not already active)
.venv\Scripts\activate.bat    # Windows
source .venv/bin/activate     # Linux/Mac

# Run main application
python optionchain_gradio.py
```

## Dependency Categories

### Runtime Dependencies
- **Web**: gradio (UI framework)
- **Data**: pandas, numpy (data processing)
- **Visualization**: plotly (charts)
- **API**: requests, httpx, dhanhq, Dhan_Tradehull (trading APIs)
- **Analysis**: TA-Lib (technical indicators)
- **UI**: rich, colorama (terminal output)
- **Utilities**: python-dateutil, pytz, mibian, tqdm
- **Server**: uvicorn (production deployment)

### Development Dependencies
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Code Review**: code-review-graph (AI-assisted reviews with reduced tokens)
- **Code Quality**: black (formatting), flake8 (linting), mypy (type checking)

### Optional Dependencies
- **Browser Automation**: playwright (NSE CSV downloads)

## Security Notes

⚠️ **Sensitive Data**
- `Credential/` directory contains API keys and auth tokens
- Never commit credential files to version control
- Use `.env` files for local configuration (not in repo)
- Environment variables for production secrets

✅ **Safety Measures**
- `.gitignore` excludes `Credential/` directory
- Virtual environment in `.venv` (not committed)
- `code-review-graph` runs locally (no cloud upload)
- No credentials exposed in logs or configuration

## CI/CD Integration

For automated testing in CI/CD pipelines:

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests with coverage
pytest tests/ --cov=. --cov-report=xml

# Check code quality
flake8 .
mypy .
black --check .
```

## Troubleshooting

### Virtual Environment Issues
```bash
# Recreate virtual environment
rm -rf .venv
.\setup.bat          # or bash setup.sh
```

### Dependency Issues
```bash
# Upgrade pip and reinstall
python -m pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### Code-Review-Graph Issues
```bash
# Reinitialize code-review-graph
rm -rf .code-review-graph
code-review-graph init
code-review-graph install-hooks
```

### Python Interpreter Issues
- Check `.vscode/settings.json` for correct interpreter path
- Verify Python version: `python --version` (requires 3.12+)
- Update VSCode Python extension to latest version

## Version Control

### Files to Commit
✅ Source code (*.py)
✅ Configuration (requirements.txt, setup scripts)
✅ Tests (tests/)
✅ Documentation (*.md)
✅ .gitignore, .vscode/settings.json

### Files to Ignore
❌ .venv/ (virtual environment)
❌ Credential/ (API keys)
❌ .code-review-graph/ (generated database)
❌ __pycache__/ (compiled Python)
❌ *.pyc (compiled modules)
❌ .pytest_cache/ (test cache)
❌ .mypy_cache/ (type checker cache)
❌ build/, dist/ (build artifacts)

---

**Last Updated**: 2026-04-06
**Version**: 1.0
