# Ngrok Setup Guide — Secure Remote Access

Share your Live NIFTY50 Option Chain Dashboard with anyone over the internet,
protected by username + password authentication.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [One-Time Setup](#one-time-setup)
4. [Running the Tunnel](#running-the-tunnel)
5. [Changing Username & Password](#changing-username--password)
6. [Sharing with Others](#sharing-with-others)
7. [Stopping the Tunnel](#stopping-the-tunnel)
8. [Troubleshooting](#troubleshooting)
9. [Security Notes](#security-notes)

---

## Overview

```
Your PC                          Internet                     Viewer's Browser
+-----------------------+        +----------+        +-------------------------+
| Gradio Dashboard      |  <-->  |  Ngrok   |  <-->  | https://xxxx.ngrok.app  |
| http://localhost:7860 |        |  Cloud   |        | (username + password)   |
+-----------------------+        +----------+        +-------------------------+
```

- **What ngrok does**: Creates a secure HTTPS tunnel from your local machine to the internet.
- **What basic auth does**: Requires a username + password before anyone can view the dashboard.
- **Everything stays local**: Your Dhan API credentials, data, and code never leave your machine.

---

## Prerequisites

- Python 3.10+ with the project virtual environment (`.venv`) activated
- The Gradio dashboard running (`python run.py`)
- Internet connection

---

## One-Time Setup

### Step 1: Create a Free Ngrok Account

1. Go to **https://dashboard.ngrok.com/signup**
2. Sign up with email or Google/GitHub account
3. Verify your email if prompted

### Step 2: Get Your Authtoken

1. After login, go to **https://dashboard.ngrok.com/get-started/your-authtoken**
2. Click **Copy** to copy the token (it looks like: `2kJ8x9AbCdEf...`)

### Step 3: Save the Authtoken in the Project

Open a terminal in the project directory and run:

**PowerShell:**
```powershell
Set-Content -Path ".ngrok\authtoken.txt" -Value "PASTE_YOUR_TOKEN_HERE" -Encoding UTF8
```

**Command Prompt:**
```cmd
echo PASTE_YOUR_TOKEN_HERE > .ngrok\authtoken.txt
```

**Manually:**
1. Open the folder: `E:\Repository\livenifty50optionchain\.ngrok\`
2. Open `authtoken.txt` in Notepad
3. Paste your authtoken (just the token, nothing else)
4. Save the file

> The `.ngrok/` folder is git-ignored, so your authtoken will never be committed.

### Step 4: Verify Setup

```bash
python -c "print(open('.ngrok/authtoken.txt').read().strip()[:8] + '...')"
```

You should see the first 8 characters of your token followed by `...`

---

## Running the Tunnel

### Step 1: Start the Dashboard (Terminal 1)

```bash
python run.py
```

Wait until you see: `Running on http://0.0.0.0:7860`

### Step 2: Start the Ngrok Tunnel (Terminal 2)

```bash
python run_ngrok.py --user subhajit --pass MySecurePass123
```

You will see output like:

```
============================================================
  NIFTY Option Chain — Ngrok Tunnel
============================================================
  Local server : http://localhost:7860
  Auth user    : subhajit
  Auth pass    : ***************
============================================================

  PUBLIC URL : https://a1b2-c3d4-e5f6.ngrok-free.app

  Share this URL -- users must enter:
    Username: subhajit
    Password: MySecurePass123

  Press Ctrl+C to stop the tunnel.
```

The **PUBLIC URL** is what you share with others.

---

## Changing Username & Password

The username and password are **not stored anywhere** — you choose them each time
you start the tunnel. This means you can change them every session.

### Examples:

**Default username (`nifty`), custom password:**
```bash
python run_ngrok.py --pass TradingView2026
```
> Username will be `nifty` (the default)

**Custom username and password:**
```bash
python run_ngrok.py --user admin --pass SuperSecret99
```

**Another example:**
```bash
python run_ngrok.py --user viewer --pass NiftyLive@2026
```

### Rules:
- `--user` : Any text you want (no spaces). Default is `nifty` if not provided.
- `--pass` : **Required**. Must be at least 8 characters. Use a mix of letters, numbers, and symbols.
- You can use different credentials for different sessions.
- Share the username + password only with people you trust.

---

## Sharing with Others

Once the tunnel is running, share these three pieces of information:

1. **URL**: The `https://xxxx.ngrok-free.app` link shown in the terminal
2. **Username**: The `--user` value you chose
3. **Password**: The `--pass` value you chose

### What the viewer sees:

1. They open the URL in any browser
2. A **ngrok interstitial page** appears (free tier) — they click "Visit Site"
3. A **login popup** asks for username and password
4. After entering correct credentials, they see the live dashboard

---

## Stopping the Tunnel

Press **Ctrl+C** in the terminal where `run_ngrok.py` is running.

```
[INFO] Shutting down ngrok tunnel...
[INFO] Tunnel closed.
```

The public URL immediately stops working. Your local dashboard continues to run.

---

## Troubleshooting

### "Authtoken file not found"
```
[ERROR] Authtoken file not found
```
You haven't saved your authtoken yet. Follow [Step 3 of One-Time Setup](#step-3-save-the-authtoken-in-the-project).

### "Password is required"
```
[ERROR] Password is required for security.
```
You must provide `--pass`. Example:
```bash
python run_ngrok.py --pass YourPassword123
```

### "Password must be at least 8 characters"
Choose a longer password. Example: `MyNifty@2026`

### "ERR_NGROK_108" or authentication error
Your authtoken may be invalid or expired.
1. Go to https://dashboard.ngrok.com/get-started/your-authtoken
2. Copy a fresh token
3. Save it to `.ngrok/authtoken.txt` again

### Tunnel URL changed after restart
On the free tier, ngrok gives a **new random URL** each time you restart.
Share the new URL with viewers. Paid plans offer fixed custom domains.

### Dashboard not loading through ngrok
Make sure the Gradio dashboard is running FIRST (`python run.py`) before
starting the tunnel. The dashboard must be active on port 7860.

### Encoding error with authtoken
If you saved the token using Windows `echo`, it may have wrong encoding.
Fix it by opening `.ngrok/authtoken.txt` in **Notepad**, deleting everything,
pasting the token cleanly, and saving as **UTF-8**.

---

## Security Notes

| Layer             | Protection                                               |
|-------------------|----------------------------------------------------------|
| HTTPS (TLS)       | All traffic between viewer and ngrok is encrypted        |
| Basic Auth         | Username + password required before viewing dashboard   |
| Local credentials | Dhan API keys stay on your PC, never transmitted         |
| Git-ignored       | `.ngrok/` folder excluded from version control           |
| Session-based     | Tunnel dies when you press Ctrl+C, URL stops working     |
| No persistence    | Password is not stored — chosen fresh each run           |

### Best Practices:
- Use a **strong password** (8+ chars, mix of letters/numbers/symbols)
- **Don't reuse** your Dhan or bank passwords for ngrok auth
- **Stop the tunnel** when not in use
- Only share credentials with **trusted people**
- For production/long-term sharing, consider ngrok's paid plans with fixed domains and IP restrictions

---

## Quick Reference

```bash
# Start dashboard
python run.py

# Start tunnel (separate terminal)
python run_ngrok.py --user USERNAME --pass PASSWORD

# Examples
python run_ngrok.py --pass MyPassword123              # user defaults to "nifty"
python run_ngrok.py --user admin --pass Admin@2026    # custom user + pass
python run_ngrok.py --user demo --pass LiveDemo99     # for demo sharing

# Stop tunnel
Ctrl+C
```
