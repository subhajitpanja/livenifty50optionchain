# Getting Started — Live NIFTY50 Option Chain Dashboard

## First-Time Setup (5 minutes)

### Step 1: Activate Virtual Environment

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### Step 2: Verify Credentials

Open `Credential/Credential.py` and verify your Dhan API credentials are correct:

```python
client_code = "YOUR_CLIENT_CODE"
token_id = "YOUR_ACCESS_TOKEN"
```

⚠️ **WARNING:** Never commit this file to version control!

### Step 3: Run the Dashboard

```bash
python optionchain_gradio.py
```

You should see:
```
[OK] Gradio 6.10.0 ready  (3.2s)
...
Running on http://127.0.0.1:7860
```

### Step 4: Open in Browser

Navigate to: **http://localhost:7860**

## Daily Usage

Once setup, just run:
```bash
# Activate (if not already active)
.venv\Scripts\activate

# Start the app
python optionchain_gradio.py
```

## Testing

Verify everything is working:

```bash
python tests/test_all_functions.py
```

Expected: **78 passed, 3 skipped**

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'gradio'"

**Solution:** Activate virtual environment and reinstall dependencies
```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

### Issue: "HTTP 401: Invalid credentials"

**Solution:** Check Credential/Credential.py and verify:
- `client_code` is correct
- `token_id` is not expired
- Token has market data permissions

### Issue: "Port 7860 already in use"

**Solution:** Kill the process or use different port
```bash
# Windows
netstat -ano | findstr :7860
taskkill /PID <PID> /F

# Linux/macOS
lsof -i :7860
kill -9 <PID>
```

Or run on different port:
```bash
python optionchain_gradio.py --server_port 7861
```

### Issue: "FileNotFoundError: templates/..."

**Solution:** Already included in setup. If missing:
```bash
mkdir -p templates/html/optionchain templates/css
```

## Project Layout

```
livenifty50optionchain/
├── .venv/                      ← Virtual environment (auto-created)
├── optionchain_gradio.py       ← Main application
├── tests/                      ← Test suite
│   └── test_all_functions.py   ← Run this: python tests/test_all_functions.py
├── Credential/
│   └── Credential.py           ← Edit with your API keys (DON'T COMMIT!)
├── data/                       ← Data files (source, cache, output, logs)
│   ├── source/                 ← Input CSVs (instruments, futures, vix, optionchain)
│   ├── cache/                  ← Runtime JSON cache
│   ├── output/                 ← Generated exports
│   └── logs/                   ← Log files
├── templates/                  ← HTML templates & CSS
│   ├── css/
│   └── html/optionchain/
├── requirements.txt            ← Python dependencies
├── README.md                   ← Full documentation
└── STARTUP.md                  ← This file
```

## Dependencies

All installed automatically via `requirements.txt`:
- **gradio** — Web UI framework
- **pandas** — Data processing  
- **plotly** — Charts
- **Dhan-Tradehull** — Dhan API wrapper
- **rich** — Terminal output
- And more...

Total: **66 packages**, ~500MB

## Features at a Glance

| Feature | Details |
|---------|---------|
| **Real-time Data** | Option chain updates every 3s |
| **Live Charts** | Plotly interactive visualizations |
| **Technical Analysis** | RSI, MACD, support/resistance |
| **Build-up Signals** | LB, SC, SB, LU classifications |
| **OI Analytics** | Distribution, ranking, changes |
| **Multi-expiry** | All NSE options expirations |
| **Market Status** | Auto detects open/closed hours |

## Performance Tips

1. **Faster Startup:** First run loads all data (~10s). Subsequent refreshes are faster (3s).

2. **Reduce Data Volume:** For slower internet, edit refresh interval in code.

3. **Use Test Mode:** On weekends/holidays, use mock mode to test without live data.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+C` | Stop the app |
| `Ctrl+L` | Clear terminal |
| `Ctrl+S` | Save current view (browser dependent) |

## API Rate Limits

Dhan API limits:
- Option chain: ~20 req/sec
- Batch requests: 10-20 req/sec

The app handles throttling automatically with backoff/retry logic.

## Logs & Debugging

Check terminal output for debug info:
- API requests and responses
- Data fetch timing
- Calculation results
- Error details

Enable more verbose logging in `optionchain_gradio.py` by adjusting `_logging` levels.

## Next Steps

1. ✅ Verify credentials work
2. ✅ Run test suite to confirm setup
3. ✅ Explore the dashboard UI
4. ✅ Check live data accuracy
5. ✅ Customize colors/labels as needed

## Help & Support

- **Test Coverage:** `python tests/test_all_functions.py`
- **Full Docs:** See `README.md`
- **Code Comments:** Check `optionchain_gradio.py` for detailed docs
- **API Reference:** See Dhan API documentation

## Security Reminders

⚠️ **CRITICAL:**
- Never share `Credential/Credential.py`
- Never commit credentials to Git
- Never paste your token in chats/forums
- Rotate tokens regularly (at least annually)

## License & Usage

This project is for personal/educational use with valid Dhan API credentials.

---

**Ready to start?** Run:
```bash
python optionchain_gradio.py
```

Happy trading! 📈
