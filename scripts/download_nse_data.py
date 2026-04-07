"""
Unified NSE Data Downloader — Playwright Web Scraper
======================================================
Downloads three datasets from NSE India in a single browser session:

  1. NIFTY Option Chain CSV    → data/source/optionchain/
  2. NIFTY Futures CSV          → data/source/futures/
  3. India VIX CSV              → data/source/vix/

The DATE in every filename is the DATA DATE (the trading day the data
belongs to), NOT the calendar day the script is executed.

Features:
  • Single browser session for all three downloads
  • Extracts data-date from the page itself
  • On Nifty expiry day after 4 PM → switches to next expiry
  • Idempotent: skips download if file already exists
  • Rich console logging

Usage:
  python scripts/download_nse_data.py
"""

import sys
import time
import datetime
import re
from pathlib import Path

# ── Ensure project root is on sys.path ────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from paths import (OPTIONCHAIN_CSV_DIR, FUTURES_DIR, VIX_DIR,   # noqa: E402
                   DOWNLOAD_TEMP_DIR, ensure_dirs)
from rich.console import Console                                 # noqa: E402
from rich.panel import Panel                                      # noqa: E402
from rich.table import Table                                      # noqa: E402

console = Console()

# ── IST timezone ──────────────────────────────────────────────────────────
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except ImportError:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")

# ── Constants ─────────────────────────────────────────────────────────────
NSE_BASE_URL = "https://www.nseindia.com"
NSE_OC_URL = "https://www.nseindia.com/option-chain"
NSE_DERIV_URL = "https://www.nseindia.com/market-data/equity-derivatives-watch"
NSE_VIX_URL = "https://www.nseindia.com/reports-indices-historical-vix"

MARKET_CLOSE_HOUR = 16   # 4:00 PM IST
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15

PAGE_TIMEOUT = 60_000       # ms
DOWNLOAD_TIMEOUT = 30_000   # ms


# ═══════════════════════════════════════════════════════════════════════════
#   UTILITY HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def now_ist() -> datetime.datetime:
    return datetime.datetime.now(IST)


def is_after_market_close(dt: datetime.datetime) -> bool:
    return dt.hour >= MARKET_CLOSE_HOUR


def is_before_market_open(dt: datetime.datetime) -> bool:
    return dt.hour < MARKET_OPEN_HOUR or (
        dt.hour == MARKET_OPEN_HOUR and dt.minute < MARKET_OPEN_MINUTE
    )


def parse_nse_date(text: str) -> datetime.date | None:
    """Parse various NSE date formats to a date object."""
    text = text.strip()
    if not text or text.lower() == 'select':
        return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d %b %Y", "%d %B %Y",
                "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%y",
                "%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M:%S %Z"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # Try "DD-MMM-YYYY" with uppercase month like "02-APR-2026"
    try:
        return datetime.datetime.strptime(text.upper().strip(), "%d-%b-%Y").date()
    except ValueError:
        pass
    return None


def extract_data_date_from_text(text: str) -> datetime.date | None:
    """Extract the data date from page text like
    'As on 02-Apr-2026 15:30:00 IST' or 'Data - from 02-04-2026 to 03-04-2026'."""
    # Pattern: "As on DD-Mon-YYYY"
    m = re.search(r'As\s+on\s+(\d{1,2}-\w{3}-\d{4})', text, re.IGNORECASE)
    if m:
        return parse_nse_date(m.group(1))
    # Pattern: "from DD-MM-YYYY to DD-MM-YYYY" — prefer "to" (end) date
    m = re.search(r'to\s+(\d{1,2}-\d{1,2}-\d{4})', text, re.IGNORECASE)
    if m:
        return parse_nse_date(m.group(1))
    # Fallback: "from DD-MM-YYYY" alone
    m = re.search(r'from\s+(\d{1,2}-\d{1,2}-\d{4})', text, re.IGNORECASE)
    if m:
        return parse_nse_date(m.group(1))
    return None


def clean_download_dir():
    """Remove any leftover files in the temp download directory."""
    if DOWNLOAD_TEMP_DIR.exists():
        for f in DOWNLOAD_TEMP_DIR.iterdir():
            if f.is_file() and f.suffix in ('.csv', '.tmp', '.crdownload'):
                try:
                    f.unlink()
                except OSError:
                    pass


# ═══════════════════════════════════════════════════════════════════════════
#   1. OPTION CHAIN DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════

def _determine_expiry_choice(expiry_options: list[str],
                             current_time: datetime.datetime
                             ) -> tuple[str | None, str]:
    """Decide which expiry to select based on time-of-day logic."""
    today = current_time.date()
    parsed = []
    for opt_text in expiry_options:
        d = parse_nse_date(opt_text)
        if d is not None:
            parsed.append((opt_text, d))
    if not parsed:
        return None, "No valid expiry dates in dropdown"
    parsed.sort(key=lambda x: x[1])

    today_is_expiry = any(d == today for _, d in parsed)

    if today_is_expiry and is_after_market_close(current_time):
        future = [(t, d) for t, d in parsed if d > today]
        if future:
            return future[0][0], (
                f"Expiry day & after 4 PM → next expiry: {future[0][0]}")
        return None, "Expiry day after 4 PM but no future expiry available"

    if is_before_market_open(current_time):
        first_text, first_date = parsed[0]
        if first_date < today:
            future = [(t, d) for t, d in parsed if d >= today]
            if future:
                return future[0][0], (
                    f"Pre-market & first expiry passed → {future[0][0]}")
    return None, "Using default NSE-selected expiry"


def download_option_chain(page) -> bool:
    """Download Option Chain CSV.  Returns True on success."""
    console.print(Panel("[bold magenta]① Option Chain CSV[/bold magenta]",
                        border_style="magenta"))
    current_time = now_ist()

    try:
        page.goto(NSE_OC_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.wait_for_selector("#expirySelect", timeout=PAGE_TIMEOUT)
        time.sleep(3)

        # ── Read data date from page ──────────────────────────────────
        page_text = page.text_content("body") or ""
        data_date = extract_data_date_from_text(page_text)
        if not data_date:
            console.print("[yellow]  Could not extract data date, falling back to page timestamp[/yellow]")
            # Fallback: look for the "As on" line
            try:
                as_on_el = page.query_selector("#wrapper_bt498760 span")
                if as_on_el:
                    as_on_text = as_on_el.text_content() or ""
                    data_date = extract_data_date_from_text(as_on_text)
            except Exception:
                pass
        if not data_date:
            console.print("[bold red]  ERROR: Cannot determine data date[/bold red]")
            return False
        console.print(f"  [bold]Data Date:[/bold] {data_date.isoformat()}")

        # ── Read expiry dates ─────────────────────────────────────────
        expiry_els = page.query_selector_all("#expirySelect option")
        expiry_options = [el.text_content().strip() for el in expiry_els
                         if el.text_content().strip().lower() != 'select'
                         and el.text_content().strip()]
        if not expiry_options:
            console.print("[bold red]  ERROR: No expiry dates found[/bold red]")
            return False

        exp_table = Table(title="Expiry Dates", show_lines=False)
        exp_table.add_column("#", style="dim")
        exp_table.add_column("Expiry", style="bold")
        for i, opt in enumerate(expiry_options, 1):
            exp_table.add_row(str(i), opt)
        console.print(exp_table)

        # ── Determine correct expiry ──────────────────────────────────
        expiry_to_select, reason = _determine_expiry_choice(
            expiry_options, current_time)
        console.print(f"  [dim]{reason}[/dim]")

        expiry_dropdown = page.query_selector("#expirySelect")
        if expiry_to_select:
            console.print(f"  [green]→ Selecting: {expiry_to_select}[/green]")
            expiry_dropdown.select_option(label=expiry_to_select)
            time.sleep(4)
            selected_expiry_text = expiry_to_select
        else:
            val = expiry_dropdown.input_value()
            sel_el = page.query_selector(
                f'#expirySelect option[value="{val}"]')
            selected_expiry_text = (sel_el.text_content().strip()
                                    if sel_el else expiry_options[0])
            console.print(f"  [green]→ Using: {selected_expiry_text}[/green]")

        selected_expiry_date = parse_nse_date(selected_expiry_text)
        if not selected_expiry_date:
            console.print(f"[bold red]  ERROR: Cannot parse expiry: {selected_expiry_text}[/bold red]")
            return False

        # ── Idempotent check ──────────────────────────────────────────
        filename = (f"{data_date.isoformat()}_exp_"
                    f"{selected_expiry_date.isoformat()}.csv")
        output_path = OPTIONCHAIN_CSV_DIR / filename
        if output_path.exists():
            console.print(f"  [green]✅ Already exists:[/green] {filename}")
            return True

        # ── Download ──────────────────────────────────────────────────
        dl_link = page.query_selector('a:has-text("Download (.csv)")')
        if not dl_link:
            dl_link = page.query_selector('#downloadOCTable')
        if not dl_link:
            console.print("[bold red]  ERROR: Download link not found[/bold red]")
            return False

        with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as dl_info:
            dl_link.click()
        download = dl_info.value
        temp_path = DOWNLOAD_TEMP_DIR / download.suggested_filename
        download.save_as(str(temp_path))

        # ── Add metadata rows and save ────────────────────────────────
        with open(temp_path, "r", encoding="utf-8") as f:
            raw = f.read()
        date_display = data_date.strftime("%d-%b-%Y")
        content = (f"Date,{date_display}\n"
                   f"Expiry Date,{selected_expiry_text}\n" + raw)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        temp_path.unlink(missing_ok=True)

        console.print(Panel(
            f"[green]✅ Option Chain saved[/green]\n"
            f"[bold]File:[/bold] {filename}\n"
            f"[bold]Data Date:[/bold] {date_display}\n"
            f"[bold]Expiry:[/bold] {selected_expiry_text}\n"
            f"[bold]Size:[/bold] {output_path.stat().st_size:,} bytes",
            border_style="green"))
        return True

    except Exception as e:
        console.print(f"  [bold red]ERROR:[/bold red] {type(e).__name__}: {e}")
        try:
            page.screenshot(
                path=str(DOWNLOAD_TEMP_DIR / "oc_error.png"))
        except Exception:
            pass
        return False


# ═══════════════════════════════════════════════════════════════════════════
#   2. NIFTY FUTURES DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════

def download_futures(page) -> bool:
    """Download Nifty 50 Futures CSV.  Returns True on success."""
    console.print(Panel("[bold blue]② Nifty 50 Futures CSV[/bold blue]",
                        border_style="blue"))
    try:
        page.goto(NSE_DERIV_URL, wait_until="domcontentloaded",
                  timeout=PAGE_TIMEOUT)
        time.sleep(3)

        # ── Select "Nifty 50 Futures" from dropdown ──────────────────
        dropdown = page.query_selector("select.no-border-radius")
        if not dropdown:
            # Fallback: try first <select> on page
            dropdown = page.query_selector("select")
        if not dropdown:
            console.print("[bold red]  ERROR: Dropdown not found[/bold red]")
            return False

        console.print("  Selecting 'Nifty 50 Futures'...")
        dropdown.select_option(value="nse50_fut")
        time.sleep(4)

        # ── Extract data date from page ───────────────────────────────
        page_text = page.text_content("body") or ""
        data_date = extract_data_date_from_text(page_text)
        if not data_date:
            # Try reading from table first row EXPIRY DATE column
            try:
                first_expiry_cell = page.query_selector(
                    "table tbody tr:first-child td:nth-child(3)")
                if first_expiry_cell:
                    # The "As on" line holds the actual data date
                    pass
            except Exception:
                pass
        if not data_date:
            console.print("[bold red]  ERROR: Cannot determine data date[/bold red]")
            return False
        console.print(f"  [bold]Data Date:[/bold] {data_date.isoformat()}")

        # ── Idempotent check ──────────────────────────────────────────
        filename = f"NIFTY_FUTURE_{data_date.isoformat()}.csv"
        output_path = FUTURES_DIR / filename
        if output_path.exists():
            console.print(f"  [green]✅ Already exists:[/green] {filename}")
            return True

        # ── Download ──────────────────────────────────────────────────
        dl_link = page.query_selector('a:has-text("Download (.csv)")')
        if not dl_link:
            dl_link = page.query_selector('span:has-text("Download (.csv)")')
            if dl_link:
                dl_link = dl_link.evaluate_handle("el => el.closest('a')")
        if not dl_link:
            console.print("[bold red]  ERROR: Download link not found[/bold red]")
            return False

        with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as dl_info:
            dl_link.click()
        download = dl_info.value
        temp_path = DOWNLOAD_TEMP_DIR / download.suggested_filename
        download.save_as(str(temp_path))

        # ── Read downloaded CSV and filter to NIFTY futures only ──────
        with open(temp_path, "r", encoding="utf-8") as f:
            raw = f.read()

        # The full download includes ALL derivatives contracts.
        # Filter to keep only rows where SYMBOL is NIFTY and type is
        # Index Futures (matching the existing file format).
        lines = raw.split("\n")
        header_line = lines[0] if lines else ""
        filtered_lines = [header_line]
        for line in lines[1:]:
            # Match rows containing "Index Futures" and "NIFTY"
            # (but not BANKNIFTY, FINNIFTY etc.)
            if not line.strip():
                continue
            upper = line.upper()
            if ('"INDEX FUTURES"' in upper or 'INDEX FUTURES' in upper):
                # Check it's NIFTY specifically (not BANKNIFTY etc)
                # Split by comma but handle quoted fields
                if ('"NIFTY"' in line and '"BANKNIFTY"' not in line
                        and '"FINNIFTY"' not in line
                        and '"NIFTYNXT50"' not in line
                        and '"MIDCPNIFTY"' not in line):
                    filtered_lines.append(line)

        final_content = "\n".join(filtered_lines)
        if not final_content.strip():
            # If filtering produced nothing, save the full file
            final_content = raw

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_content)
        temp_path.unlink(missing_ok=True)

        console.print(Panel(
            f"[green]✅ Futures saved[/green]\n"
            f"[bold]File:[/bold] {filename}\n"
            f"[bold]Data Date:[/bold] {data_date.isoformat()}\n"
            f"[bold]Size:[/bold] {output_path.stat().st_size:,} bytes",
            border_style="green"))
        return True

    except Exception as e:
        console.print(f"  [bold red]ERROR:[/bold red] {type(e).__name__}: {e}")
        try:
            page.screenshot(
                path=str(DOWNLOAD_TEMP_DIR / "futures_error.png"))
        except Exception:
            pass
        return False


# ═══════════════════════════════════════════════════════════════════════════
#   3. INDIA VIX DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════

def download_vix(page) -> bool:
    """Download India VIX CSV.  Returns True on success.

    Logic:
      1. Navigate to VIX page, click 1D
      2. Check if the table has real data rows
      3. ONLY if 1D is empty → click 1W
      4. Extract the data date from the FIRST table row
      5. Download CSV
    """
    console.print(Panel("[bold yellow]③ India VIX CSV[/bold yellow]",
                        border_style="yellow"))
    try:
        page.goto(NSE_VIX_URL, wait_until="domcontentloaded",
                  timeout=PAGE_TIMEOUT)
        time.sleep(3)

        # ── Click "1D" (daily) ────────────────────────────────────────
        console.print("  Clicking 1D (daily)...")
        d_btn = page.query_selector('a:has-text("1D")')
        if d_btn:
            d_btn.click()
            time.sleep(3)

        # ── Check if daily table has data ─────────────────────────────
        # Use JavaScript to find ANY visible table row with a date-like
        # first cell, since NSE uses various table IDs.
        vix_check = page.evaluate("""() => {
            // Try all tables on the page — return the LAST date row
            // (the latest trading day) rather than the first.
            const tables = document.querySelectorAll('table');
            let lastDate = '';
            let totalRows = 0;
            for (const table of tables) {
                const rows = table.querySelectorAll('tbody tr');
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 4) {
                        const firstCell = cells[0].textContent.trim();
                        if (/\\d{2}-.{3,}-\\d{4}/.test(firstCell) || /\\d{2}-[A-Za-z]{3}-\\d{4}/.test(firstCell)) {
                            lastDate = firstCell;
                            totalRows++;
                        }
                    }
                }
            }
            return {
                hasData: totalRows > 0,
                dateText: lastDate,
                rowCount: totalRows
            };
        }""")

        daily_has_data = vix_check.get('hasData', False)
        data_date = None
        used_weekly = False

        if daily_has_data:
            console.print(f"  [green]1D has data ✓[/green] "
                          f"({vix_check['rowCount']} rows, "
                          f"first date: {vix_check['dateText']})")
            data_date = parse_nse_date(vix_check['dateText'])
        else:
            # ONLY now try weekly
            console.print("  [yellow]1D table is empty, trying 1W...[/yellow]")
            w_btn = page.query_selector('a:has-text("1W")')
            if w_btn:
                w_btn.click()
                time.sleep(3)
                used_weekly = True

            vix_check = page.evaluate("""() => {
                const tables = document.querySelectorAll('table');
                let lastDate = '';
                let totalRows = 0;
                for (const table of tables) {
                    const rows = table.querySelectorAll('tbody tr');
                    for (const row of rows) {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 4) {
                            const firstCell = cells[0].textContent.trim();
                            if (/\\d{2}-.{3,}-\\d{4}/.test(firstCell) || /\\d{2}-[A-Za-z]{3}-\\d{4}/.test(firstCell)) {
                                lastDate = firstCell;
                                totalRows++;
                            }
                        }
                    }
                }
                return {
                    hasData: totalRows > 0,
                    dateText: lastDate,
                    rowCount: totalRows
                };
            }""")

            if vix_check.get('hasData'):
                console.print(f"  [green]1W has data ✓[/green] "
                              f"({vix_check['rowCount']} rows)")
                data_date = parse_nse_date(vix_check['dateText'])
            else:
                console.print("  [yellow]1W also empty[/yellow]")

        # ── Fallback for data date ────────────────────────────────────
        if not data_date:
            page_text = page.text_content("body") or ""
            data_date = extract_data_date_from_text(page_text)
        if not data_date:
            console.print("[bold red]  ERROR: Cannot determine data date[/bold red]")
            return False
        console.print(f"  [bold]Data Date:[/bold] {data_date.isoformat()}"
                      f"{'  (from 1W)' if used_weekly else ''}")

        # ── Idempotent check ──────────────────────────────────────────
        filename = f"indiavix_{data_date.isoformat()}.csv"
        output_path = VIX_DIR / filename
        if output_path.exists():
            console.print(f"  [green]✅ Already exists:[/green] {filename}")
            return True

        # ── Download ──────────────────────────────────────────────────
        dl_link = page.query_selector("#CFanncEquity-download")
        if not dl_link:
            dl_link = page.query_selector('a:has-text("Download (.csv)")')
        if not dl_link:
            console.print("[bold red]  ERROR: Download link not found[/bold red]")
            return False

        with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as dl_info:
            dl_link.click()
        download = dl_info.value
        temp_path = DOWNLOAD_TEMP_DIR / download.suggested_filename
        download.save_as(str(temp_path))

        # ── Save with correct name ────────────────────────────────────
        with open(temp_path, "r", encoding="utf-8") as f:
            raw = f.read()

        # Always keep only the latest date row from the CSV.
        # The downloaded file may contain multiple rows (especially
        # from the 1W tab), but consumers expect header + 1 row.
        lines = raw.split("\n")
        header = lines[0] if lines else ""
        data_lines = [l for l in lines[1:] if l.strip()]

        if data_lines:
            # Parse dates from each row and pick the latest
            best_line = data_lines[-1]  # fallback: last row
            best_date = None
            for line in data_lines:
                first_field = line.split(",")[0].strip().strip('"')
                row_date = parse_nse_date(first_field)
                if row_date and (best_date is None or row_date > best_date):
                    best_date = row_date
                    best_line = line

            # Update data_date if we found a newer date in the CSV
            if best_date and best_date != data_date:
                console.print(f"  [yellow]Adjusting date from {data_date} → {best_date}[/yellow]")
                data_date = best_date
                filename = f"indiavix_{data_date.isoformat()}.csv"
                output_path = VIX_DIR / filename
                # Re-check idempotent
                if output_path.exists():
                    console.print(f"  [green]✅ Already exists:[/green] {filename}")
                    temp_path.unlink(missing_ok=True)
                    return True

            final_content = header + "\n" + best_line + "\n"
        else:
            final_content = raw

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_content)
        temp_path.unlink(missing_ok=True)

        console.print(Panel(
            f"[green]✅ VIX saved[/green]\n"
            f"[bold]File:[/bold] {filename}\n"
            f"[bold]Data Date:[/bold] {data_date.isoformat()}\n"
            f"[bold]Size:[/bold] {output_path.stat().st_size:,} bytes",
            border_style="green"))
        return True

    except Exception as e:
        console.print(f"  [bold red]ERROR:[/bold red] {type(e).__name__}: {e}")
        try:
            page.screenshot(
                path=str(DOWNLOAD_TEMP_DIR / "vix_error.png"))
        except Exception:
            pass
        return False


# ═══════════════════════════════════════════════════════════════════════════
#   MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    console.print(Panel(
        "[bold cyan]NSE Unified Data Downloader[/bold cyan]\n"
        "[dim]Option Chain  •  Futures  •  VIX[/dim]",
        border_style="cyan",
    ))

    ensure_dirs()
    clean_download_dir()

    current_time = now_ist()
    console.print(f"[bold]Current Time (IST):[/bold] "
                  f"{current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    console.print()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        console.print("[bold red]ERROR:[/bold red] playwright not installed!")
        console.print("Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    # ── Launch browser ────────────────────────────────────────────────
    console.print("[yellow]⏳ Launching Chromium…[/yellow]")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"),
            accept_downloads=True,
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        page = context.new_page()

        results = {}
        try:
            # ── Establish cookies ─────────────────────────────────────
            console.print("[cyan]Setting up NSE session…[/cyan]")
            page.goto(NSE_BASE_URL, wait_until="domcontentloaded",
                      timeout=PAGE_TIMEOUT)
            time.sleep(3)

            # ── 1. Option Chain ───────────────────────────────────────
            results['option_chain'] = download_option_chain(page)

            # ── 2. Futures ────────────────────────────────────────────
            results['futures'] = download_futures(page)

            # ── 3. VIX ────────────────────────────────────────────────
            results['vix'] = download_vix(page)

        except Exception as e:
            console.print(f"\n[bold red]FATAL:[/bold red] {e}")
            try:
                page.screenshot(
                    path=str(DOWNLOAD_TEMP_DIR / "fatal_error.png"))
            except Exception:
                pass
        finally:
            browser.close()
            console.print("[dim]Browser closed.[/dim]")

        # ── Summary ───────────────────────────────────────────────────
        console.print()
        summary = Table(title="Download Summary", show_lines=True)
        summary.add_column("Dataset", style="bold")
        summary.add_column("Status")
        for name, ok in results.items():
            status = "[green]✅ Success[/green]" if ok else "[red]❌ Failed[/red]"
            summary.add_row(name.replace('_', ' ').title(), status)
        console.print(summary)


if __name__ == "__main__":
    main()
