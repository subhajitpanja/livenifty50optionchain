#!/usr/bin/env python
"""
Live NIFTY Option Chain Dashboard — Startup Script
====================================================

This is the main entry point for the Gradio dashboard.

Usage:
    python run.py

Then navigate to: http://localhost:7860

Requirements:
    - Python 3.10+
    - Virtual environment activated
    - Dependencies installed: pip install -r requirements.txt
    - Dhan API credentials in Credential/Credential.py
"""

if __name__ == '__main__':
    import sys
    from pathlib import Path

    # Ensure we can import from current directory
    sys.path.insert(0, str(Path(__file__).parent))

    # Import and run the Gradio app
    import optionchain_gradio
