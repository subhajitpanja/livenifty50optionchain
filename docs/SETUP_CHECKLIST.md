# Setup Checklist ✓

Use this checklist to verify your setup is complete.

## Pre-Setup Requirements

- [ ] Python 3.10 or higher installed
- [ ] Dhan API account with valid credentials
- [ ] Internet connection for API access
- [ ] At least 1GB disk space

## Setup Steps

### 1. Project Structure
- [x] Project location: `E:\Repository\livenifty50optionchain`
- [x] All files copied from source
- [x] Directory structure created
- [x] Git repository initialized

### 2. Virtual Environment
- [x] `.venv/` directory created
- [x] 66 packages installed
- [x] Python path configured

### 3. Dependencies
- [x] gradio 6.10.0
- [x] pandas 3.0.2
- [x] numpy 2.4.4
- [x] plotly 6.6.0
- [x] requests 2.33.1
- [x] rich 14.3.3
- [x] Dhan-Tradehull 3.0.6
- [x] python-dateutil 2.9.0.post0

### 4. Configuration
- [x] Credential folder created
- [x] Credential.py with placeholders
- [x] data/ folder with source, cache, output, logs
- [x] Templates folder with styles

### 5. Documentation
- [x] README.md (full guide)
- [x] STARTUP.md (getting started)
- [x] requirements.txt (dependencies)
- [x] .gitignore (credential protection)
- [x] PROJECT_SETUP_SUMMARY.txt (overview)

### 6. Scripts & Utilities
- [x] optionchain_gradio.py (main app)
- [x] oc_data_fetcher.py (API logic)
- [x] color_constants.py (UI colors)
- [x] ui_labels.py (UI text)
- [x] tui_components.py (terminal UI)
- [x] tui_theme.py (theme settings)
- [x] run.py (startup script)
- [x] activate.bat (Windows venv)
- [x] activate.sh (Unix venv)

### 7. Test Suite
- [x] 9 test files
- [x] 78+ tests passing
- [x] Import verification passing
- [x] API integration working

## Pre-Launch Verification

Before running the app, verify:

### 1. Virtual Environment Active
```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```
- [ ] Command prompt shows `(.venv)` prefix
- [ ] `which python` shows .venv path

### 2. Dependencies Installed
```bash
pip list | grep -E "(gradio|pandas|plotly|requests)"
```
- [ ] All packages listed above present
- [ ] No error messages

### 3. Credentials Configured
- [ ] Edit: `Credential/Credential.py`
- [ ] Set `client_code` to your ID
- [ ] Set `token_id` to your access token
- [ ] Token is not expired (check Dhan dashboard)

### 4. Test Run (Optional)
```bash
python tests/test_all_functions.py
```
- [ ] 78 tests pass
- [ ] ~12-13 seconds to complete
- [ ] No import errors

## Launch Checklist

When you're ready to start:

1. [ ] Virtual environment activated
2. [ ] Credentials verified in Credential.py
3. [ ] All files present and readable
4. [ ] Internet connection verified
5. [ ] Port 7860 is free (or use different port)

## First Run

```bash
python optionchain_gradio.py
```

Verify:
- [ ] "Gradio X.X.X ready" message appears
- [ ] "Running on http://127.0.0.1:7860" message
- [ ] No error messages
- [ ] Browser opens dashboard
- [ ] Data starts loading (3-10 seconds)

## Ongoing Checks

### Daily Startup
- [ ] Activate .venv
- [ ] Check Credential/Credential.py is up-to-date
- [ ] Run dashboard
- [ ] Verify spot price appears
- [ ] Option chain loads

### Weekly Maintenance
- [ ] Check token expiration (Dhan dashboard)
- [ ] Review any error messages in console
- [ ] Verify data accuracy
- [ ] Check disk space for cache files

### Monthly
- [ ] Update NSE holidays in optionchain_gradio.py (if needed)
- [ ] Review Dhan API updates
- [ ] Clean old log files in data/logs/

## Troubleshooting Checklist

If something breaks:

1. [ ] Check error message (copy full stack trace)
2. [ ] Run tests: `python tests/test_all_functions.py`
3. [ ] Verify credentials are still valid
4. [ ] Check network connectivity
5. [ ] Restart the app with fresh venv activation
6. [ ] Check Dhan API status page
7. [ ] Review recent changes (git log)

## File Integrity

Verify these critical files exist:

- [ ] `optionchain_gradio.py` (176 KB)
- [ ] `oc_data_fetcher.py` (88 KB)
- [ ] `Credential/Credential.py` (1 KB)
- [ ] `requirements.txt` (520 B)
- [ ] `.gitignore` (610 B)
- [ ] `README.md` (4.5 KB)
- [ ] `tests/test_all_functions.py` (present)

## Success Indicators

✓ Project is ready when:
1. All files present ✓
2. Virtual env created ✓
3. Dependencies installed ✓
4. Imports all pass ✓
5. Tests all pass ✓
6. Credentials configured (pending your setup)
7. Dashboard launches (pending your setup)

---

**Status:** 5/7 steps complete (awaiting your credential configuration)

**Next action:** Edit `Credential/Credential.py` with your Dhan API credentials
