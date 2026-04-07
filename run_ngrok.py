#!/usr/bin/env python
"""
Ngrok Tunnel for Live NIFTY Option Chain Dashboard
====================================================

Starts a secure ngrok tunnel with basic auth to expose the
Gradio dashboard (port 7860) to the public internet.

Setup (one-time):
    1. Sign up at https://dashboard.ngrok.com/signup
    2. Copy your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
    3. Create a file:  .ngrok/authtoken.txt
       containing ONLY your authtoken (one line, no spaces)

Usage:
    python run_ngrok.py                          # uses default user/pass
    python run_ngrok.py --user admin --pass secret123

IMPORTANT: Run this AFTER starting the Gradio dashboard (python run.py).
"""

import argparse
import os
import sys
from pathlib import Path

# ─── Project paths ───────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent.resolve()
NGROK_DIR = PROJECT_DIR / ".ngrok"
NGROK_BIN = NGROK_DIR / "ngrok.exe"
AUTHTOKEN_FILE = NGROK_DIR / "authtoken.txt"


def load_authtoken() -> str:
    """Load authtoken from .ngrok/authtoken.txt"""
    if not AUTHTOKEN_FILE.exists():
        print(f"\n[ERROR] Authtoken file not found: {AUTHTOKEN_FILE}")
        print(f"\nSetup steps:")
        print(f"  1. Sign up at https://dashboard.ngrok.com/signup")
        print(f"  2. Copy your authtoken")
        print(f"  3. Save it to: {AUTHTOKEN_FILE}")
        print(f'     echo YOUR_TOKEN > "{AUTHTOKEN_FILE}"')
        sys.exit(1)

    token = AUTHTOKEN_FILE.read_text().strip()
    if not token:
        print(f"[ERROR] Authtoken file is empty: {AUTHTOKEN_FILE}")
        sys.exit(1)
    return token


def main():
    parser = argparse.ArgumentParser(description="Ngrok tunnel for NIFTY Option Chain Dashboard")
    parser.add_argument("--user", default="nifty", help="Basic auth username (default: nifty)")
    parser.add_argument("--pass", dest="password", default=None, help="Basic auth password (required)")
    parser.add_argument("--port", type=int, default=7860, help="Local port to tunnel (default: 7860)")
    args = parser.parse_args()

    # Validate password
    if not args.password:
        print("\n[ERROR] Password is required for security.")
        print("  Usage: python run_ngrok.py --user nifty --pass YOUR_STRONG_PASSWORD")
        sys.exit(1)

    if len(args.password) < 8:
        print("\n[ERROR] Password must be at least 8 characters for security.")
        sys.exit(1)

    # Check ngrok binary exists locally
    if not NGROK_BIN.exists():
        print(f"[INFO] Ngrok binary not found at {NGROK_BIN}, downloading...")
        from pyngrok.conf import PyngrokConfig
        from pyngrok import installer
        installer.install_ngrok(str(NGROK_BIN))
        print("[INFO] Download complete.")

    # Load authtoken
    authtoken = load_authtoken()

    # Configure pyngrok to use project-local binary
    from pyngrok.conf import PyngrokConfig
    from pyngrok import ngrok, conf

    config = PyngrokConfig(
        ngrok_path=str(NGROK_BIN),
        auth_token=authtoken,
    )
    conf.set_default(config)

    # Open tunnel with basic auth
    print(f"\n{'='*60}")
    print(f"  NIFTY Option Chain — Ngrok Tunnel")
    print(f"{'='*60}")
    print(f"  Local server : http://localhost:{args.port}")
    print(f"  Auth user    : {args.user}")
    print(f"  Auth pass    : {'*' * len(args.password)}")
    print(f"{'='*60}\n")

    try:
        tunnel = ngrok.connect(
            addr=str(args.port),
            proto="http",
            bind_tls=True,
            auth=f"{args.user}:{args.password}",
        )
        public_url = tunnel.public_url
        print(f"  PUBLIC URL : {public_url}")
        print(f"\n  Share this URL — users must enter:")
        print(f"    Username: {args.user}")
        print(f"    Password: {args.password}")
        print(f"\n  Press Ctrl+C to stop the tunnel.\n")

        # Keep alive
        ngrok.get_ngrok_process().proc.wait()

    except KeyboardInterrupt:
        print("\n\n[INFO] Shutting down ngrok tunnel...")
        ngrok.kill()
        print("[INFO] Tunnel closed.")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        ngrok.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()
