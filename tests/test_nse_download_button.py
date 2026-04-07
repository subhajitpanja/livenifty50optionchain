"""
NSE Data Download Button -- Integration Tests
==============================================
Verifies:
  1. Data status check correctly detects existing/missing files
  2. Status HTML renders with proper badges
  3. Auto-download trigger logic (9 PM IST gate)
  4. Download function doesn't crash (mocked subprocess)
  5. Concurrent download guard works

Run:  python -m pytest tests/test_nse_download_button.py -v
"""
import sys
import os
import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =========================================================================
# 1. Data status detection
# =========================================================================

class TestDataStatusCheck:
    """Verify _check_nse_data_status finds/misses files correctly."""

    def test_returns_dict_with_required_keys(self):
        from optionchain_gradio import _check_nse_data_status
        result = _check_nse_data_status()
        assert isinstance(result, dict)
        assert 'date' in result
        assert 'option_chain' in result
        assert 'futures' in result
        assert 'vix' in result

    def test_date_is_iso_format(self):
        from optionchain_gradio import _check_nse_data_status
        result = _check_nse_data_status()
        # Should be YYYY-MM-DD format
        datetime.date.fromisoformat(result['date'])

    def test_values_are_boolean(self):
        from optionchain_gradio import _check_nse_data_status
        result = _check_nse_data_status()
        assert isinstance(result['option_chain'], bool)
        assert isinstance(result['futures'], bool)
        assert isinstance(result['vix'], bool)

    def test_detects_existing_futures_file(self):
        """If a NIFTY_FUTURE_{date}.csv exists, futures should be True."""
        from optionchain_gradio import _check_nse_data_status, _get_last_trading_date
        from paths import FUTURES_DIR
        data_date = _get_last_trading_date()
        fut_file = FUTURES_DIR / f"NIFTY_FUTURE_{data_date.isoformat()}.csv"
        if fut_file.exists():
            result = _check_nse_data_status()
            assert result['futures'] is True


# =========================================================================
# 2. Status HTML rendering
# =========================================================================

class TestStatusHtml:
    """Verify _nse_data_status_html produces valid HTML."""

    def test_returns_non_empty_html(self):
        from optionchain_gradio import _nse_data_status_html
        html = _nse_data_status_html()
        assert isinstance(html, str)
        assert len(html) > 50
        assert '<div' in html

    def test_contains_badges(self):
        from optionchain_gradio import _nse_data_status_html
        html = _nse_data_status_html()
        assert 'Option Chain' in html
        assert 'Futures' in html
        assert 'VIX' in html

    def test_contains_date(self):
        from optionchain_gradio import _nse_data_status_html, _get_last_trading_date
        html = _nse_data_status_html()
        data_date = _get_last_trading_date()
        assert data_date.isoformat() in html

    def test_shows_checkmark_or_cross(self):
        from optionchain_gradio import _nse_data_status_html
        html = _nse_data_status_html()
        # Should have either checkmark (&#10003;) or cross (&#10007;) for each badge
        assert '&#10003;' in html or '&#10007;' in html


# =========================================================================
# 3. Auto-download trigger logic
# =========================================================================

class TestAutoDownloadTrigger:
    """Verify _should_auto_download respects 9 PM IST gate."""

    def test_returns_boolean(self):
        from optionchain_gradio import _should_auto_download
        result = _should_auto_download()
        assert isinstance(result, bool)

    def test_before_9pm_returns_false(self):
        """Before 9 PM IST, auto-download should never trigger."""
        from optionchain_gradio import _should_auto_download
        # Mock time to 3 PM IST
        fake_now = datetime.datetime(2026, 4, 7, 15, 0, 0,
                                     tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        with mock.patch('optionchain_gradio._dt') as mock_dt:
            mock_dt.datetime.now.return_value = fake_now
            mock_dt.timezone = datetime.timezone
            mock_dt.timedelta = datetime.timedelta
            mock_dt.time = datetime.time
            result = _should_auto_download()
            assert result is False

    def test_after_9pm_with_all_data_returns_false(self):
        """After 9 PM IST, if all data exists, should return False."""
        from optionchain_gradio import _should_auto_download
        with mock.patch('optionchain_gradio._check_nse_data_status') as mock_check:
            mock_check.return_value = {
                'date': '2026-04-07',
                'option_chain': True, 'futures': True, 'vix': True,
            }
            fake_now = datetime.datetime(2026, 4, 7, 21, 30, 0,
                                         tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
            with mock.patch('optionchain_gradio._dt') as mock_dt:
                mock_dt.datetime.now.return_value = fake_now
                mock_dt.timezone = datetime.timezone
                mock_dt.timedelta = datetime.timedelta
                mock_dt.time = datetime.time
                result = _should_auto_download()
                assert result is False


# =========================================================================
# 4. Download function safety
# =========================================================================

class TestDownloadFunction:
    """Verify _run_nse_download handles errors gracefully."""

    def test_returns_html_string(self):
        """Even if subprocess fails, should return status HTML."""
        from optionchain_gradio import _run_nse_download
        with mock.patch('subprocess.run', side_effect=FileNotFoundError("no python")):
            result = _run_nse_download()
            assert isinstance(result, str)
            assert '<div' in result

    def test_concurrent_guard(self):
        """If download is already running, should return immediately."""
        import optionchain_gradio as og
        og._nse_download_running = True
        try:
            result = og._run_nse_download()
            assert isinstance(result, str)
            assert '<div' in result
        finally:
            og._nse_download_running = False


# =========================================================================
# 5. Last trading date logic
# =========================================================================

class TestLastTradingDate:
    """Verify _get_last_trading_date skips weekends."""

    def test_returns_date(self):
        from optionchain_gradio import _get_last_trading_date
        result = _get_last_trading_date()
        assert isinstance(result, datetime.date)

    def test_never_returns_weekend(self):
        from optionchain_gradio import _get_last_trading_date
        result = _get_last_trading_date()
        assert result.weekday() < 5, f"Got weekend day: {result} (weekday={result.weekday()})"

    def test_not_future_date(self):
        from optionchain_gradio import _get_last_trading_date
        result = _get_last_trading_date()
        assert result <= datetime.date.today()
