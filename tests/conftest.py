"""Pytest configuration for the test suite."""
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Standalone integration scripts — run them directly with
# `python tests/<script>.py`, not via pytest.
# These either use sys.exit() at module level or have chained
# test functions with non-fixture parameters.
collect_ignore = [
    "test_download_pipeline.py",
    "test_oh_ol.py",
    "test_header_section.py",
    "run_all_tests.py",
    "_test_13tabs.py",
    "test_runner_playwright.py",
    "test_panel_spacing.py",
]
