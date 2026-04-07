"""
Ngrok Tunnel Setup — Validation Tests
======================================
Run:  pytest tests/test_ngrok_setup.py -v

Validates that the ngrok tunnel infrastructure is properly configured:
  - run_ngrok.py exists and is importable
  - .ngrok/ directory structure is correct
  - pyngrok dependency is available
  - CLI argument parsing works correctly
  - Authtoken file handling behaves as expected
"""

import sys
import subprocess
from pathlib import Path

import pytest

# ── path setup ──────────────────────────────────────────────────────────────
_here = Path(__file__).resolve().parent
_project_root = _here.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── File & directory existence ──────────────────────────────────────────────

class TestNgrokFileStructure:
    """Verify ngrok-related files and directories exist."""

    def test_run_ngrok_script_exists(self):
        script = _project_root / "run_ngrok.py"
        assert script.exists(), "run_ngrok.py not found in project root"

    def test_ngrok_directory_exists(self):
        ngrok_dir = _project_root / ".ngrok"
        assert ngrok_dir.is_dir(), ".ngrok/ directory not found"

    def test_ngrok_binary_exists(self):
        ngrok_bin = _project_root / ".ngrok" / "ngrok.exe"
        assert ngrok_bin.exists(), ".ngrok/ngrok.exe not found (run: python run_ngrok.py once to download)"

    def test_authtoken_file_exists(self):
        authtoken = _project_root / ".ngrok" / "authtoken.txt"
        assert authtoken.exists(), ".ngrok/authtoken.txt not found (see docs/guides/NGROK_SETUP.md)"

    def test_authtoken_not_empty(self):
        authtoken = _project_root / ".ngrok" / "authtoken.txt"
        if authtoken.exists():
            content = authtoken.read_text(encoding="utf-8").strip()
            assert len(content) > 0, "authtoken.txt is empty"

    def test_authtoken_is_utf8(self):
        """Ensure authtoken is valid UTF-8 (not UTF-16 from Windows echo)."""
        authtoken = _project_root / ".ngrok" / "authtoken.txt"
        if authtoken.exists():
            raw = authtoken.read_bytes()
            assert not raw.startswith(b"\xff\xfe"), "authtoken.txt is UTF-16 encoded — re-save as UTF-8"
            assert not raw.startswith(b"\xef\xbb\xbf"), "authtoken.txt has BOM — re-save without BOM"

    def test_ngrok_setup_guide_exists(self):
        guide = _project_root / "docs" / "guides" / "NGROK_SETUP.md"
        assert guide.exists(), "docs/guides/NGROK_SETUP.md not found"


# ── Dependency check ────────────────────────────────────────────────────────

class TestNgrokDependency:
    """Verify pyngrok is installed and importable."""

    def test_pyngrok_importable(self):
        import pyngrok  # noqa: F401

    def test_pyngrok_conf_importable(self):
        from pyngrok.conf import PyngrokConfig  # noqa: F401

    def test_pyngrok_ngrok_importable(self):
        from pyngrok import ngrok  # noqa: F401


# ── CLI argument parsing ────────────────────────────────────────────────────

class TestNgrokCLI:
    """Verify run_ngrok.py CLI argument handling."""

    def test_help_flag(self):
        """--help should exit 0 and show usage."""
        result = subprocess.run(
            [sys.executable, str(_project_root / "run_ngrok.py"), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower()

    def test_missing_password_exits_nonzero(self):
        """Running without --pass should fail with error."""
        result = subprocess.run(
            [sys.executable, str(_project_root / "run_ngrok.py")],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0

    def test_short_password_exits_nonzero(self):
        """Password shorter than 8 chars should fail."""
        result = subprocess.run(
            [sys.executable, str(_project_root / "run_ngrok.py"), "--pass", "short"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0


# ── .gitignore & .code-review-graphignore ───────────────────────────────────

class TestNgrokIgnoreRules:
    """Verify ngrok artifacts are excluded from VCS and code review graph."""

    def test_gitignore_excludes_ngrok(self):
        gitignore = (_project_root / ".gitignore").read_text(encoding="utf-8")
        assert ".ngrok/" in gitignore, ".ngrok/ not found in .gitignore"

    def test_code_review_graphignore_excludes_ngrok(self):
        ignore_file = _project_root / ".code-review-graphignore"
        if ignore_file.exists():
            content = ignore_file.read_text(encoding="utf-8")
            assert ".ngrok/" in content, ".ngrok/ not found in .code-review-graphignore"
