"""
NSE Market Calendar
====================
NSE holiday list and market-session helpers.

Extracted from optionchain_gradio.py so that any module needing to know
"is the market open right now?" can import from a single source of truth.

Update `NSE_HOLIDAYS` once per year.
"""

from __future__ import annotations

import datetime as _dt


# ══════════════════════════════════════════════════════════════════════════
# NSE holidays (yyyy-mm-dd) — covers 2025 and 2026
# ══════════════════════════════════════════════════════════════════════════
NSE_HOLIDAYS: set[str] = {
    # 2025
    '2025-02-26', '2025-03-14', '2025-03-31', '2025-04-10', '2025-04-14',
    '2025-04-18', '2025-05-01',
    '2025-08-15', '2025-08-27', '2025-10-02', '2025-10-20', '2025-10-21',
    '2025-10-22', '2025-11-05', '2025-11-26', '2025-12-25',
    # 2026
    '2026-01-26', '2026-02-17', '2026-03-10', '2026-03-17',
    '2026-03-30', '2026-04-03', '2026-04-14', '2026-05-01', '2026-05-25',
    '2026-07-17', '2026-08-15', '2026-08-17', '2026-10-02', '2026-10-09',
    '2026-10-19', '2026-10-20', '2026-11-09', '2026-11-24', '2026-12-25',
}

# IST timezone (UTC+5:30) — Python 3.9+ has zoneinfo but this stays dep-free.
IST = _dt.timezone(_dt.timedelta(hours=5, minutes=30))


def _now_ist() -> _dt.datetime:
    try:
        return _dt.datetime.now(IST)
    except Exception:
        return _dt.datetime.now()


# ══════════════════════════════════════════════════════════════════════════
# Public helpers
# ══════════════════════════════════════════════════════════════════════════
def is_weekend(d: _dt.date | None = None) -> bool:
    """True when `d` (default today) falls on Saturday or Sunday."""
    d = d or _dt.date.today()
    return d.weekday() >= 5


def is_nse_holiday(d: _dt.date | None = None) -> bool:
    """True when `d` (default today) is in the NSE holiday list."""
    d = d or _dt.date.today()
    return str(d) in NSE_HOLIDAYS


def is_market_open() -> bool:
    """
    True when NSE is likely open right now.

    Checks (in order): not weekend, not NSE holiday, current IST time is
    within 09:00 – 15:40 (40-minute post-close buffer for settlement).
    """
    now_ist = _now_ist()
    d = now_ist.date()
    if d.weekday() >= 5:
        return False
    if str(d) in NSE_HOLIDAYS:
        return False
    t = now_ist.time()
    if t < _dt.time(9, 0) or t > _dt.time(15, 40):
        return False
    return True


def market_status_str() -> str:
    """Short human-readable market status string for UI badges."""
    now_ist = _now_ist()
    d = now_ist.date()
    t = now_ist.time()
    day_name = d.strftime('%A')
    if d.weekday() >= 5:
        return f"{day_name} — Weekend (market closed)"
    if str(d) in NSE_HOLIDAYS:
        return f"{day_name} — NSE Holiday (market closed)"
    if t < _dt.time(9, 0):
        return f"{day_name} — Pre-market (opens 09:15)"
    if t > _dt.time(15, 40):
        return f"{day_name} — Post-market (closed 15:30)"
    return f"{day_name} — Market OPEN"


def get_last_trading_date() -> _dt.date:
    """
    Return the most recent trading date.

    Rule: if it's before 16:00 IST we haven't finished today's session yet,
    so roll back to yesterday; then skip weekends AND NSE holidays so the
    returned date is always a real trading session for which CSV files
    could plausibly exist.
    """
    now_ist = _now_ist()
    d = now_ist.date()
    t = now_ist.time()
    if t < _dt.time(16, 0):
        d -= _dt.timedelta(days=1)
    while d.weekday() >= 5 or str(d) in NSE_HOLIDAYS:
        d -= _dt.timedelta(days=1)
    return d
