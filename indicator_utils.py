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
    Compute RSI(period) matching TradingView's exact algorithm:

      Phase 1 (bar 1 .. period):  SMA seed — simple average of gains/losses
                                  over the first `period` changes.
      Phase 2 (bar period+1 ..):  Wilder's smoothing —
                                  avg = (prev_avg * (period-1) + current) / period

    This two-phase approach prevents the early-bar overshoot that a pure EWM
    produces (e.g. RSI spiking above 70 when TradingView stays below 60).

    Edge cases:
      avg_loss == 0 and avg_gain > 0  →  RSI = 100  (all gains)
      avg_gain == 0 and avg_loss > 0  →  RSI =   0  (all losses)
      avg_gain == 0 and avg_loss == 0 →  RSI =  50  (flat / no movement)

    Parameters
    ----------
    series : pd.Series
        Price series (typically the straddle close).
    period : int
        Lookback window (default 14).

    Returns
    -------
    pd.Series
        RSI values in [0, 100], rounded to 2 decimals, aligned with `series`.
    """
    if series is None or len(series) == 0:
        return pd.Series(dtype=float)

    delta = series.diff()
    gain  = delta.clip(lower=0).fillna(0.0)
    loss  = (-delta.clip(upper=0)).fillna(0.0)

    n = len(series)
    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)

    gain_vals = gain.values
    loss_vals = loss.values

    if n <= period:
        # Not enough bars for a full SMA seed — use running SMA so RSI is
        # available from bar 2 onward (critical for early-session charts).
        cum_g = 0.0
        cum_l = 0.0
        for i in range(n):
            cum_g += gain_vals[i]
            cum_l += loss_vals[i]
            count = i + 1
            if count >= 2:  # need at least 1 price change
                avg_gain[i] = cum_g / count
                avg_loss[i] = cum_l / count
    else:
        # Phase 1: SMA seed over first `period` bars
        avg_gain[period] = np.mean(gain_vals[1:period + 1])
        avg_loss[period] = np.mean(loss_vals[1:period + 1])

        # Phase 2: Wilder's smoothing
        for i in range(period + 1, n):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain_vals[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss_vals[i]) / period

    avg_gain = pd.Series(avg_gain, index=series.index)
    avg_loss = pd.Series(avg_loss, index=series.index)

    # Compute RSI; handle edge cases explicitly
    with np.errstate(divide='ignore', invalid='ignore'):
        rs  = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

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
