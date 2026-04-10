"""
NSE data-file status badge + auto-downloader helpers.

- check_nse_data_status()   → which CSVs exist for the last trading date
- nse_data_status_html()    → rendered HTML badge for the Gradio UI
- run_nse_download()        → spawn scripts/download_nse_data.py
- should_auto_download()    → True after 9 PM IST when any file is missing

Logging/TUI is injected via `set_logger` so this module stays detached from
optionchain_gradio.py.
"""

from __future__ import annotations

import datetime as _dt
import subprocess
import sys
from typing import Callable

from nse_calendar import get_last_trading_date
from paths import FUTURES_DIR, OPTIONCHAIN_CSV_DIR, PROJECT_ROOT, VIX_DIR
from template_utils import render


# ──────────────────────────────────────────────────────────────────────────
# Logger injection (so we don't import tui_components here)
# ──────────────────────────────────────────────────────────────────────────
def _noop(_msg: str) -> None:  # pragma: no cover
    return None


_log_info:  Callable[[str], None] = _noop
_log_warn:  Callable[[str], None] = _noop
_log_error: Callable[[str], None] = _noop


def set_logger(info, warn, error) -> None:
    """Install logging callbacks. Each callable takes a single `msg` string."""
    global _log_info, _log_warn, _log_error
    _log_info, _log_warn, _log_error = info, warn, error


# ══════════════════════════════════════════════════════════════════════════
# Status check
# ══════════════════════════════════════════════════════════════════════════
def check_nse_data_status() -> dict:
    """
    Check which NSE data files exist for the last trading date.
    Returns dict with keys: `date, option_chain, futures, vix`.
    """
    data_date = get_last_trading_date()
    date_str = data_date.isoformat()

    oc_files = list(OPTIONCHAIN_CSV_DIR.glob(f"{date_str}_exp_*.csv"))
    fut_file = FUTURES_DIR / f"NIFTY_FUTURE_{date_str}.csv"
    vix_file = VIX_DIR / f"indiavix_{date_str}.csv"

    return {
        'date': date_str,
        'option_chain': len(oc_files) > 0,
        'futures': fut_file.exists(),
        'vix': vix_file.exists(),
    }


def nse_data_status_html() -> str:
    """Render a styled status bar showing per-file availability."""
    st = check_nse_data_status()
    all_ok = st['option_chain'] and st['futures'] and st['vix']

    def _badge(ok: bool, label: str) -> str:
        return render(
            'nse_status_badge',
            state='ok' if ok else 'err',
            icon_entity='10003' if ok else '10007',
            label=label,
        )

    return render(
        'nse_status_bar',
        state='ok' if all_ok else 'warn',
        status_icon_entity='10003' if all_ok else '9888',
        status_text='All Data Available' if all_ok else 'Missing Data',
        date=st['date'],
        oc_badge=_badge(st['option_chain'], 'Option Chain'),
        fut_badge=_badge(st['futures'], 'Futures'),
        vix_badge=_badge(st['vix'], 'VIX'),
    )


# ══════════════════════════════════════════════════════════════════════════
# Downloader (subprocess — blocks caller for up to 5 min)
# ══════════════════════════════════════════════════════════════════════════
_nse_download_running = False


def run_nse_download() -> str:
    """
    Run `scripts/download_nse_data.py` in a subprocess and return the
    refreshed status HTML. A concurrent call short-circuits.
    """
    global _nse_download_running
    if _nse_download_running:
        return nse_data_status_html()

    _nse_download_running = True
    try:
        _log_info("NSE data download started...")
        script = str(PROJECT_ROOT / 'scripts' / 'download_nse_data.py')
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True, timeout=300,
            cwd=str(PROJECT_ROOT),
            encoding='utf-8', errors='replace',
        )
        if result.returncode == 0:
            _log_info("NSE data download completed successfully")
        else:
            _log_error(f"NSE data download failed (exit {result.returncode})")
            if result.stderr:
                _log_error(result.stderr[:500])
    except subprocess.TimeoutExpired:
        _log_error("NSE data download timed out (5 min)")
    except Exception as e:
        _log_error(f"NSE data download error: {e}")
    finally:
        _nse_download_running = False

    return nse_data_status_html()


def should_auto_download() -> bool:
    """True when it's after 21:00 IST and at least one data file is missing."""
    try:
        now_ist = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=5, minutes=30)))
    except Exception:
        now_ist = _dt.datetime.now()
    if now_ist.hour < 21:
        return False
    st = check_nse_data_status()
    return not (st['option_chain'] and st['futures'] and st['vix'])
