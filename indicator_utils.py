"""
Technical Indicator Utilities
==============================
Reusable indicator calculations (RSI, MACD, EMA, VWAP, etc.) extracted from
optionchain_gradio.py so they can be unit-tested and reused across charts,
tests and future modules.

All functions are pure — they take a pandas Series / DataFrame and return a
pandas Series / DataFrame without side-effects.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ══════════════════════════════════════════════════════════════════════════
# RSI — Relative Strength Index (Wilder's smoothing via EWM)
# ══════════════════════════════════════════════════════════════════════════
def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Compute RSI(period) on a price series using Wilder's smoothing.

    Correctly handles the three degenerate cases that the old implementation
    got wrong:

      1. avg_loss == 0  and avg_gain  > 0  →  RSI = 100  (all gains)
      2. avg_gain == 0  and avg_loss  > 0  →  RSI =   0  (all losses)
      3. avg_gain == 0  and avg_loss == 0  →  RSI =  50  (flat price)

    The previous version did
        rs = avg_gain / avg_loss.replace(0, NaN).fillna(inf)
    which turned case (1) into `rs = gain / inf = 0`, producing **RSI = 0**
    for a rallying series — the exact bug that caused straddle charts to
    display an RSI of 0 during strong trends.

    Parameters
    ----------
    series : pd.Series
        Price series (typically the straddle close).
    period : int
        Lookback window (default 14, the classic RSI period).

    Returns
    -------
    pd.Series
        RSI values in [0, 100], rounded to 2 decimals, aligned with `series`.
    """
    if series is None or len(series) == 0:
        return pd.Series(dtype=float)

    # First diff is NaN — fill with 0 so EWM has a stable starting point.
    delta = series.diff().fillna(0.0)
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)

    # Wilder's smoothing ≡ EWM with alpha = 1/period, adjust=False.
    # min_periods=period makes the first (period-1) rows NaN, which is the
    # textbook behaviour — the UI has an `.dropna().iloc[-1]` fallback for
    # early-session bars.
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    # Compute RS safely; we override edge cases explicitly below.
    with np.errstate(divide='ignore', invalid='ignore'):
        rs  = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

    # Edge cases:
    #   flat  → 50   (no movement either way)
    #   rally → 100  (gains only, no losses)
    flat  = (avg_gain == 0) & (avg_loss == 0)
    rally = (avg_loss == 0) & (avg_gain > 0)

    rsi = rsi.mask(flat,  50.0)
    rsi = rsi.mask(rally, 100.0)

    return rsi.round(2)


# ══════════════════════════════════════════════════════════════════════════
# MACD — 12/26/9 by default (classic Appel parameters)
# ══════════════════════════════════════════════════════════════════════════
def calc_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    Compute MACD line, signal line and histogram.

    Returns
    -------
    (macd_line, signal_line, histogram) : tuple[pd.Series, pd.Series, pd.Series]
    """
    ema_fast    = series.ewm(span=fast,  adjust=False).mean()
    ema_slow    = series.ewm(span=slow,  adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


# ══════════════════════════════════════════════════════════════════════════
# OHLCV resampling helper
# ══════════════════════════════════════════════════════════════════════════
def resample_ohlcv(df: pd.DataFrame, target_minutes: int) -> pd.DataFrame:
    """
    Resample a lower-timeframe OHLCV DataFrame up to a higher timeframe.

    Expects columns: `timestamp, open, high, low, close, volume`. Returns a
    DataFrame with the same columns, indexed 0..N-1, dropping empty buckets.
    """
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    rule = f'{target_minutes}min'
    resampled = df.resample(rule, origin='start').agg({
        'open':   'first',
        'high':   'max',
        'low':    'min',
        'close':  'last',
        'volume': 'sum',
    }).dropna(subset=['open'])
    return resampled.reset_index()


# ══════════════════════════════════════════════════════════════════════════
# Convenience: current (latest non-NaN) RSI with sensible fallback
# ══════════════════════════════════════════════════════════════════════════
def latest_rsi(series: pd.Series, period: int = 14, fallback: float = 50.0) -> float:
    """
    Return the most recent valid RSI value, or `fallback` if the series is
    too short / empty to produce one.
    """
    rsi = calc_rsi(series, period=period).dropna()
    if rsi.empty:
        return float(fallback)
    return float(rsi.iloc[-1])
