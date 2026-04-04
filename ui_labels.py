"""
UI Labels — Single source of truth for all dashboard string constants.
======================================================================
Import into Python files (optionchain_gradio.py, optionchain_streamlit.py).
Keeps all user-visible text in one place for consistency.
"""

# ═══════════════════════════════════════════════════════════════════════════
#^# HEADER BOX LABELS
# ═══════════════════════════════════════════════════════════════════════════
LBL_SPOT = 'SPOT'
LBL_ATM = 'ATM'
LBL_EXPIRY = 'EXPIRY'
LBL_VIX = 'VIX'
LBL_FUT = 'FUT'
LBL_CALL_OI = 'CALL OI'
LBL_PUT_OI = 'PUT OI'
LBL_NET_OI = 'NET OI'
LBL_PCR = 'PCR'
LBL_MAX_CE = 'Max CE'
LBL_MAX_PE = 'Max PE'

# ═══════════════════════════════════════════════════════════════════════════
#^# ANALYTICS SECTION TITLES
# ═══════════════════════════════════════════════════════════════════════════
SEC_TOTALS = '📊 Totals'
SEC_SENTIMENT = '💡 Sentiment'
SEC_OTM = '📤 OTM Analysis'
SEC_ITM = '📥 ITM Analysis'
SEC_CALL_OI = '📞 CALL OI'
SEC_PUT_OI = '📉 PUT OI'

# ═══════════════════════════════════════════════════════════════════════════
#^# ANALYTICS ROW LABELS — Totals section
# ═══════════════════════════════════════════════════════════════════════════
LBL_TOTAL_OI = 'Total OI'
LBL_TOTAL_OI_CHG = 'Total OI Chg'
LBL_TOTAL_VOL = 'Total Volume'
LBL_TOTAL_LB_OI = 'Total LB [Price ↑ + OI ↑] OI'
LBL_TOTAL_SC_OI = 'Total SC [Price ↑ + OI ↓] OI'
LBL_TOTAL_SB_OI = 'Total SB [Price ↓ + OI ↑] OI'
LBL_TOTAL_LU_OI = 'Total LU [Price ↓ + OI ↓] OI'
LBL_TOTAL_LB_OI_CHG = 'Total LB [Price ↑ + OI ↑] OI Chg'
LBL_TOTAL_SC_OI_CHG = 'Total SC [Price ↑ + OI ↓] OI Chg'
LBL_TOTAL_SB_OI_CHG = 'Total SB [Price ↓ + OI ↑] OI Chg'
LBL_TOTAL_LU_OI_CHG = 'Total LU [Price ↓ + OI ↓] OI Chg'

# ═══════════════════════════════════════════════════════════════════════════
#^# ANALYTICS ROW LABELS — Sentiment section
# ═══════════════════════════════════════════════════════════════════════════
LBL_BULLISH_OI = 'Total Bullish OI'
LBL_BEARISH_OI = 'Total Bearish OI'
LBL_BULLISH_OI_CHG = 'Total Bullish OI Chg'
LBL_BEARISH_OI_CHG = 'Total Bearish OI Chg'
LBL_CALL_PREMIUM = 'Total Calls Premium'
LBL_PUT_PREMIUM = 'Total Puts Premium'
LBL_CALL_PREM_CHG = 'Tot Call Premium Chg'
LBL_PUT_PREM_CHG = 'Tot Put Premium Chg'
LBL_PE_CE_OI_CHG = 'PE-CE OI Chg'
LBL_PCR_OI = 'PCR OI'
LBL_PCR_OI_CHG = 'PCR OI Chg'
LBL_PCR_VOL = 'PCR Volume'

# ═══════════════════════════════════════════════════════════════════════════
#^# ANALYTICS ROW LABELS — OTM / ITM Analysis
# ═══════════════════════════════════════════════════════════════════════════
LBL_OTM_OI = 'Total OTM OI'
LBL_OTM_OI_CHG = 'Total OTM OI Chg'
LBL_OTM_VOL = 'Total OTM Volume'
LBL_PCR_OTM_OI = 'PCR OTM OI'
LBL_PCR_OTM_OI_CHG = 'PCR OTM OI Chg'
LBL_ITM_OI = 'Total ITM OI'
LBL_ITM_OI_CHG = 'Total ITM OI Chg'
LBL_ITM_VOL = 'Total ITM Volume'
LBL_PCR_ITM_OI = 'PCR ITM OI'
LBL_PCR_ITM_OI_CHG = 'PCR ITM OI Chg'

# ═══════════════════════════════════════════════════════════════════════════
#^# TF INDICATORS
# ═══════════════════════════════════════════════════════════════════════════
LBL_NO_DATA = 'No data'
LBL_ZONE_POSITIVE = 'Positive'
LBL_ZONE_NEGATIVE = 'Negative'
LBL_ZONE_TRANSITION = 'Transition'
