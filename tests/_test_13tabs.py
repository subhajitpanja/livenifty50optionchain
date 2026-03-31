"""Quick test: 15 cycles through all 13 tabs with mock OC data."""
import sys, os
_here = os.path.dirname(os.path.abspath(__file__))    # tests/
_oc_dir = os.path.dirname(_here)                       # project root
for _p in (_here, _oc_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.chdir(_oc_dir)

import pandas as pd
from tui_components import tui_dashboard

# Create mock option chain DataFrame
strikes = list(range(23200, 23600, 50))
data_rows = []
for s in strikes:
    data_rows.append({
        'Strike': s,
        'C_OI': 1500000 + (23400 - s) * 100,
        'C_OI_Chg': -5000 + (s % 100) * 10,
        'C_LTP': max(5, 23360 - s + 50),
        'C_IV': 14.5 + (s - 23200) * 0.1,
        'C_BuildUp': 'Long Buildup' if s < 23350 else 'Short Buildup',
        'C_OH_OL': 'OH' if s < 23300 else ('OL' if s > 23450 else ''),
        'P_OI': 800000 + (s - 23200) * 80,
        'P_OI_Chg': 3000 - (s % 100) * 5,
        'P_LTP': max(5, s - 23360 + 50),
        'P_IV': 15.0 + (23500 - s) * 0.08,
        'P_BuildUp': 'Short Covering' if s > 23400 else 'Long Buildup',
        'P_OH_OL': 'OH' if s > 23450 else ('OL' if s < 23250 else ''),
    })
option_df = pd.DataFrame(data_rows)

mock_data = {
    'spot_price': 23360.10, 'vix_current': 24.47,
    'fut_price': 23358.60, 'atm_strike': 23350,
    'underlying': 'NIFTY', 'error': None,
    'expiry': '27-Mar-2026',
}

# Run 15 cycles
for cycle in range(1, 16):
    mock_data['spot_price'] = 23360.10 + cycle * 0.5
    tab_num = (cycle - 1) % 13
    tab_name = tui_dashboard.tab_bar.TABS[tab_num]
    print(f"--- Cycle {cycle} -> Tab {tab_num}: {tab_name} ---")

    tui_dashboard.update(
        cycle=cycle,
        dt_oc=1.2 + cycle * 0.05,
        dt_total=1.8 + cycle * 0.07,
        data=mock_data,
        market_open=True,
        market_status='Wednesday - Market OPEN',
        option_df=option_df,
    )

print(f"\nSnapshots in history: {len(tui_dashboard.oc_history.snapshots)}")
cycles_list = [s["cycle"] for s in tui_dashboard.oc_history.snapshots]
print(f"Snapshot cycles: {cycles_list}")

import json, pathlib
from paths import OC_SNAPSHOTS_FILE
snap_file = OC_SNAPSHOTS_FILE
if snap_file.exists():
    with open(snap_file) as f:
        saved = json.load(f)
    print(f"JSON file has {len(saved)} snapshots")
    saved_cycles = [s["cycle"] for s in saved]
    print(f"JSON cycles: {saved_cycles}")
else:
    print("JSON file NOT found!")

print("\nAll 13 tabs rendered successfully!")
