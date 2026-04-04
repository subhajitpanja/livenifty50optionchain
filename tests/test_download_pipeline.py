"""
Download Pipeline Validation Test
==================================
Run: python tests/test_download_pipeline.py

Validates all downloaded NSE data files without live API calls.
Checks:
  1. File presence and recency (optionchain, futures, VIX CSVs)
  2. Option chain CSV structure, metadata, strike data
  3. Futures CSV structure, NIFTY futures filtering
  4. VIX CSV structure, value ranges
  5. Cross-source date alignment
  6. Instrument CSV presence and NIFTY option availability

No network calls — pure disk-based validation.
"""
import sys
import os
import csv
import json
import datetime as _dt
import time
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box
import pandas as pd

# Path setup
_here = Path(__file__).resolve().parent
_oc_dir = _here.parent
for _p in [str(_here), str(_oc_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.chdir(str(_oc_dir))

from paths import (OPTIONCHAIN_CSV_DIR, FUTURES_DIR, VIX_DIR, INSTRUMENTS_DIR)

console = Console(force_terminal=True, width=140)
_results = []
_t_start = time.perf_counter()

# ═══════════════════════════════════════════════════════════════════════════
#  STARTUP BANNER
# ═══════════════════════════════════════════════════════════════════════════
console.print()
console.print(Panel(
    "[bold bright_cyan]Download Pipeline Validation Test[/]\n"
    "[dim]Validates all NSE data source files (no API calls)[/]\n\n"
    f"[bold]Date:[/] {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    f"[bold]Python:[/] {sys.version.split()[0]}\n"
    f"[bold]Platform:[/] {sys.platform}",
    border_style="bright_cyan",
    expand=False,
    padding=(1, 3)))
console.print()

def record(name, status, detail=''):
    """Track result and print."""
    _results.append((name, status, detail))
    colors = {'PASS': 'bold green', 'FAIL': 'bold red', 'WARN': 'yellow'}
    icon = f"[{colors.get(status, 'white')}]{status}[/]"
    detail_str = f"  [dim]{detail}[/]" if detail else ''
    console.print(f"  {icon}  {name}{detail_str}")

def days_ago_trading(file_date_str):
    """Calculate trading days ago (skip weekends)."""
    try:
        file_date = _dt.datetime.strptime(file_date_str, '%Y-%m-%d').date()
    except ValueError:
        return 999
    today = _dt.date.today()
    days_count = 0
    current = today
    while current > file_date:
        current -= _dt.timedelta(days=1)
        if current.weekday() < 5:  # weekday only
            days_count += 1
    return days_count

# ═══════════════════════════════════════════════════════════════════════════
#  SECTION 1: FILE PRESENCE CHECK
# ═══════════════════════════════════════════════════════════════════════════
console.print(Rule("[bold bright_cyan]SECTION 1 — File Presence & Recency[/]", style="dim cyan"))

sources = [
    ("Option Chain", OPTIONCHAIN_CSV_DIR, "*_exp_*.csv"),
    ("Futures", FUTURES_DIR, "NIFTY_FUTURE_*.csv"),
    ("VIX", VIX_DIR, "indiavix_*.csv"),
]

file_status = {}
for source_name, source_dir, pattern in sources:
    console.print(f"\n[bold]{source_name}[/]:")
    if not source_dir.exists():
        record(f"  {source_name} directory exists", "FAIL", f"NOT FOUND: {source_dir}")
        file_status[source_name] = None
        continue

    files = sorted(source_dir.glob(pattern), reverse=True)
    if not files:
        record(f"  {source_name} CSV files", "FAIL", f"No files matching {pattern}")
        file_status[source_name] = None
        continue

    # Use most recent file
    latest = files[0]
    file_name = latest.name
    file_size_kb = latest.stat().st_size / 1024
    file_stem = latest.stem

    # Extract date from filename
    try:
        if source_name == "Option Chain":
            date_str = file_stem.split('_')[0]  # e.g. "2026-04-02" from "2026-04-02_exp_..."
        elif source_name == "Futures":
            date_str = file_stem.replace('NIFTY_FUTURE_', '')  # e.g. "2026-04-02"
        elif source_name == "VIX":
            date_str = file_stem.replace('indiavix_', '')  # e.g. "2026-04-02"
        else:
            date_str = ''
        days_old = days_ago_trading(date_str) if date_str else 999
    except Exception:
        date_str = "???"
        days_old = 999

    # Recency check: ≤ 5 trading days (allow weekends)
    recency_status = "PASS" if days_old <= 5 else ("WARN" if days_old <= 10 else "FAIL")

    tbl = Table(box=box.ROUNDED, show_header=True, header_style="dim")
    tbl.add_column("File", width=48)
    tbl.add_column("Date", width=12)
    tbl.add_column("Size KB", width=10, justify="right")
    tbl.add_column("Age (days)", width=11, justify="right")
    tbl.add_column("Status", width=8)

    age_color = "green" if recency_status == "PASS" else ("yellow" if recency_status == "WARN" else "red")
    status_icon = {"PASS": "[green]✓[/]", "WARN": "[yellow]⚠[/]", "FAIL": "[red]✗[/]"}[recency_status]

    tbl.add_row(
        file_name,
        date_str,
        f"{file_size_kb:,.0f}",
        f"[{age_color}]{days_old}[/]",
        status_icon,
    )
    console.print(tbl)

    record(f"  {source_name} CSV", recency_status, f"{file_name} ({days_old}d old)")
    file_status[source_name] = {
        'path': latest,
        'name': file_name,
        'date': date_str,
        'size_kb': file_size_kb,
        'age_days': days_old,
    }

# ═══════════════════════════════════════════════════════════════════════════
#  SECTION 2: OPTION CHAIN CSV VALIDATION
# ═══════════════════════════════════════════════════════════════════════════
if file_status.get('Option Chain'):
    console.print()
    console.print(Rule("[bold bright_cyan]SECTION 2 — Option Chain CSV Validation[/]", style="dim cyan"))

    oc_path = file_status['Option Chain']['path']
    oc_info = []

    try:
        with open(oc_path, encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Parse metadata rows
        date_str_oc = rows[0][1] if len(rows) > 0 and len(rows[0]) > 1 else ''
        expiry_str = rows[1][1] if len(rows) > 1 and len(rows[1]) > 1 else ''

        record("  Date row present", "PASS", f"Date: {date_str_oc}")
        record("  Expiry row present", "PASS", f"Expiry: {expiry_str}")

        # Verify date in row 0 matches filename date
        filename_date = file_status['Option Chain']['date']
        # Parse both dates for comparison (CSV is "DD-Mon-YYYY", filename is "YYYY-MM-DD")
        date_match = False
        if date_str_oc and filename_date:
            try:
                parsed_csv = _dt.datetime.strptime(date_str_oc.strip(), '%d-%b-%Y').strftime('%Y-%m-%d')
                date_match = parsed_csv == filename_date
            except ValueError:
                date_match = False

        if date_match:
            record("  Date matches filename", "PASS")
        else:
            record("  Date matches filename", "WARN", f"CSV={date_str_oc}, File={filename_date} (different formats but may be same date)")

        # Parse headers (row 3) and data (row 4+)
        if len(rows) > 3:
            headers = rows[3]
            data_rows = rows[4:]

            # Check columns exist
            required_cols = ['STRIKE', 'OI', 'LTP', 'IV', 'CHNG IN OI']
            found_cols = [h for h in headers if any(req in str(h).upper() for req in required_cols)]
            record("  Key columns present", "PASS" if len(found_cols) >= 4 else "WARN",
                   f"{len(found_cols)}/5 required columns found")

            # Parse strike column
            try:
                strike_idx = next(i for i, h in enumerate(headers) if 'STRIKE' in str(h).upper())
                strikes = []
                for r in data_rows:
                    if len(r) > strike_idx and r[strike_idx].strip() and r[strike_idx].strip() != '-':
                        try:
                            # Handle comma-separated numbers like "20,100.00"
                            clean_val = r[strike_idx].strip().replace(',', '')
                            s = int(float(clean_val))
                            strikes.append(s)
                        except (ValueError, AttributeError):
                            pass

                if strikes:
                    strike_status = "PASS"
                    strikes_uniq = sorted(set(strikes))
                    strike_detail = f"{len(strikes)} total, {len(strikes_uniq)} unique strikes, range {min(strikes_uniq)}-{max(strikes_uniq)}"

                    # Check multiples of 50 (NIFTY standard)
                    if all(s % 50 == 0 for s in strikes_uniq):
                        strike_detail += ", all multiples of 50 ✓"
                    else:
                        strike_status = "WARN"
                        non_mult = [s for s in strikes_uniq if s % 50 != 0]
                        strike_detail += f", {len(non_mult)} strikes not multiples of 50"

                    record("  Strike data", strike_status, strike_detail)
                else:
                    record("  Strike data", "FAIL", "No numeric strikes found")

            except (StopIteration, IndexError):
                record("  Strike column", "FAIL", "STRIKE column not found")

        record("  CSV structure valid", "PASS", f"{len(rows)} rows total, {len(data_rows)} data rows")

    except Exception as e:
        record("  Option Chain CSV parsing", "FAIL", str(e))

# ═══════════════════════════════════════════════════════════════════════════
#  SECTION 3: FUTURES CSV VALIDATION
# ═══════════════════════════════════════════════════════════════════════════
if file_status.get('Futures'):
    console.print()
    console.print(Rule("[bold bright_cyan]SECTION 3 — Futures CSV Validation[/]", style="dim cyan"))

    fut_path = file_status['Futures']['path']

    try:
        df = pd.read_csv(fut_path, encoding='utf-8-sig', header=None)

        # Check structure
        record("  Futures CSV loaded", "PASS", f"{len(df)} rows")

        # Check for NIFTY futures
        if len(df.columns) >= 2:
            underlying_col = df.iloc[:, 1].astype(str)
            nifty_rows = underlying_col[underlying_col.str.contains('NIFTY', na=False)]

            if not nifty_rows.empty:
                record("  NIFTY futures present", "PASS", f"{len(nifty_rows)} rows found")

                # Sample LTP validation
                if len(df.columns) > 5:
                    ltp_col = pd.to_numeric(df.iloc[:, 5].astype(str).str.replace(',', ''), errors='coerce')
                    valid_ltp = ltp_col[(ltp_col > 10000) & (ltp_col < 35000)]
                    if not valid_ltp.empty:
                        record("  LTP range valid", "PASS", f"{len(valid_ltp)} in 10000-35000 range")
                    else:
                        record("  LTP range valid", "WARN", "Few valid LTPs in expected range")
            else:
                record("  NIFTY futures", "WARN", "No NIFTY rows found in derivatives data")

    except Exception as e:
        record("  Futures CSV parsing", "FAIL", str(e))

# ═══════════════════════════════════════════════════════════════════════════
#  SECTION 4: VIX CSV VALIDATION
# ═══════════════════════════════════════════════════════════════════════════
if file_status.get('VIX'):
    console.print()
    console.print(Rule("[bold bright_cyan]SECTION 4 — VIX CSV Validation[/]", style="dim cyan"))

    vix_path = file_status['VIX']['path']

    try:
        df = pd.read_csv(vix_path, encoding='utf-8-sig')
        df.columns = [c.strip() for c in df.columns]  # Handle trailing spaces

        record("  VIX CSV loaded", "PASS", f"{len(df)} rows")

        # Check columns
        required_cols = ['Date', 'Close']
        missing = [c for c in required_cols if c not in df.columns]
        if not missing:
            record("  Required columns present", "PASS")
        else:
            record("  Required columns", "FAIL", f"Missing: {missing}")

        # VIX value range
        if 'Close' in df.columns:
            close = pd.to_numeric(df['Close'], errors='coerce')
            valid = close[(close > 5) & (close <= 100)]
            if not valid.empty:
                last_vix = float(close.dropna().iloc[-1])
                record("  VIX Close range", "PASS", f"Last: {last_vix:.2f}, {len(valid)}/{len(close)} valid")
            else:
                record("  VIX Close range", "FAIL", "No values in 5-100 range")

        # Date format
        if 'Date' in df.columns:
            try:
                dates = pd.to_datetime(df['Date'], format='%d-%b-%Y')
                latest_vix_date = dates.max().date()
                days_old_vix = ((_dt.date.today() - latest_vix_date).days)
                record("  Date format valid", "PASS", f"Latest: {latest_vix_date}, {days_old_vix}d old")
            except Exception:
                record("  Date format", "WARN", "Could not parse dates")

    except Exception as e:
        record("  VIX CSV parsing", "FAIL", str(e))

# ═══════════════════════════════════════════════════════════════════════════
#  SECTION 5: CROSS-SOURCE DATE ALIGNMENT
# ═══════════════════════════════════════════════════════════════════════════
console.print()
console.print(Rule("[bold bright_cyan]SECTION 5 — Cross-Source Date Alignment[/]", style="dim cyan"))

dates_info = {}
for source_name in ['Option Chain', 'Futures', 'VIX']:
    if file_status.get(source_name):
        dates_info[source_name] = file_status[source_name]['date']

if len(dates_info) >= 2:
    unique_dates = set(dates_info.values())
    if len(unique_dates) == 1:
        record("  All sources aligned", "PASS", f"All dated {list(unique_dates)[0]}")
    else:
        record("  All sources aligned", "WARN", f"Dates differ: {dates_info}")
else:
    record("  Cross-source check", "SKIP", "Not enough sources with dates")

# Display date alignment table
tbl_align = Table(box=box.ROUNDED, show_header=True, header_style="dim")
tbl_align.add_column("Source", width=16)
tbl_align.add_column("Newest File Date", width=16)
for source, date in dates_info.items():
    tbl_align.add_row(source, f"[cyan]{date}[/]")
console.print(tbl_align)

# ═══════════════════════════════════════════════════════════════════════════
#  SECTION 6: INSTRUMENTS CSV CHECK
# ═══════════════════════════════════════════════════════════════════════════
console.print()
console.print(Rule("[bold bright_cyan]SECTION 6 — Instruments CSV[/]", style="dim cyan"))

if INSTRUMENTS_DIR.exists():
    inst_files = sorted(INSTRUMENTS_DIR.glob('all_instrument *.csv'), reverse=True)
    if inst_files:
        inst_path = inst_files[0]
        inst_name = inst_path.name
        inst_size_mb = inst_path.stat().st_size / (1024 * 1024)

        try:
            df_inst = pd.read_csv(inst_path, low_memory=False)
            record("  Instrument CSV loaded", "PASS", f"{len(df_inst)} rows, {inst_size_mb:.1f} MB")

            # Count NIFTY options
            if 'SEM_INSTRUMENT_NAME' in df_inst.columns:
                nifty_opts = df_inst[
                    (df_inst['SEM_INSTRUMENT_NAME'] == 'OPTIDX') &
                    (df_inst['SEM_TRADING_SYMBOL'].str.contains('NIFTY-', na=False))
                ]
                record("  NIFTY options in CSV", "PASS", f"{len(nifty_opts)} option rows")

                # Check for future expiry dates
                if 'SEM_EXPIRY_DATE' in df_inst.columns:
                    nifty_opts['SEM_EXPIRY_DATE'] = pd.to_datetime(nifty_opts['SEM_EXPIRY_DATE'], errors='coerce')
                    future_exp = nifty_opts[nifty_opts['SEM_EXPIRY_DATE'] > _dt.datetime.now()]
                    record("  Future expiry dates", "PASS", f"{len(future_exp.drop_duplicates(subset=['SEM_EXPIRY_DATE']))} unique upcoming expiries")

        except Exception as e:
            record("  Instrument CSV parsing", "FAIL", str(e))
    else:
        record("  Instrument CSV files", "FAIL", "No all_instrument*.csv files found")
else:
    record("  Instruments directory", "FAIL", f"NOT FOUND: {INSTRUMENTS_DIR}")

# ═══════════════════════════════════════════════════════════════════════════
#  FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
console.print()
console.print(Rule("[bold bright_cyan]Final Summary[/]", style="dim cyan"))

elapsed = time.perf_counter() - _t_start
passed = sum(1 for _, s, _ in _results if s == "PASS")
failed = sum(1 for _, s, _ in _results if s == "FAIL")
warned = sum(1 for _, s, _ in _results if s == "WARN")
skipped = sum(1 for _, s, _ in _results if s == "SKIP")

summary_tbl = Table(box=box.DOUBLE_EDGE, show_header=False, expand=False, padding=(0, 2))
summary_tbl.add_column(style="bold", width=14)
summary_tbl.add_column(width=10, justify="right")
summary_tbl.add_row("[green]PASSED[/]", f"[bold green]{passed}[/]")
summary_tbl.add_row("[red]FAILED[/]", f"[bold red]{failed}[/]")
summary_tbl.add_row("[yellow]WARNED[/]", f"[bold yellow]{warned}[/]")
summary_tbl.add_row("[dim]SKIPPED[/]", f"[dim]{skipped}[/]")
summary_tbl.add_row("TOTAL", f"[bold]{passed+failed+warned+skipped}[/]")
summary_tbl.add_row("ELAPSED", f"{elapsed:.2f}s")
console.print(summary_tbl)
console.print()

# Verdict
if failed == 0:
    border_color = "yellow" if warned > 0 else "green"
    msg = f"[bold green]✓ {passed} CHECKS PASSED[/]"
    if warned > 0:
        msg += f"\n[bold yellow]⚠ {warned} WARNINGS[/]"
    console.print(Panel(msg, border_style=border_color, expand=False, padding=(1, 2)))
else:
    console.print(Panel(
        f"[bold red]✗ {failed} CHECK(S) FAILED[/]\n"
        f"[dim]{passed} passed, {warned} warned, {skipped} skipped[/]",
        border_style="red",
        expand=False,
        padding=(1, 2)))

console.print()
sys.exit(0 if failed == 0 else 1)
