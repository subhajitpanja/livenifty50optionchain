"""
Index-level constants for NSE derivatives.

Single source of truth for strike step, DhanHQ security IDs and exchange
segment per index — previously duplicated across optionchain_gradio.py and
oc_data_fetcher.py.
"""

from __future__ import annotations

# Strike increment per index (used to round spot → ATM strike)
INDEX_STEP: dict[str, int] = {
    'NIFTY':     50,
    'BANKNIFTY': 100,
    'FINNIFTY':  50,
    'MIDCPNIFTY': 25,
}

# DhanHQ underlying security IDs for the option-chain/expirylist APIs
INDEX_SECURITY_IDS_OC: dict[str, int] = {
    'NIFTY':     13,
    'BANKNIFTY': 25,
    'FINNIFTY':  27,
    'MIDCPNIFTY': 442,
}

# DhanHQ exchange segment for indices (all IDX_I for now)
INDEX_EXCHANGE_SEG: dict[str, str] = {
    'NIFTY':     'IDX_I',
    'BANKNIFTY': 'IDX_I',
    'FINNIFTY':  'IDX_I',
    'MIDCPNIFTY': 'IDX_I',
}

# Number of historical snapshot tabs (Live + N history) used by the OC and
# OI-distribution history strips in the Gradio UI.
HISTORY_TAB_COUNT: int = 14
