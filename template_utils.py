"""
HTML / CSS template loader with in-process caching.

Loads files from `templates/html/*.html` and `templates/css/styles.css`,
caches them after the first read and returns safe-substituted strings so
HTML builders in the rest of the codebase stay free of disk I/O on the
hot path.

Usage:
    from template_utils import render, load_css

    html = render('nse_status_badge', state='ok', label='Option Chain')
    css  = load_css()
"""

from __future__ import annotations

from string import Template

from paths import CSS_STYLES_FILE, HTML_DIR


# ── module-private caches ─────────────────────────────────────────────────
_template_cache: dict[str, str] = {}
_css_cache: str = ''


# ══════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════
def load_css() -> str:
    """Load and cache the shared stylesheet (`templates/css/styles.css`)."""
    global _css_cache
    if not _css_cache:
        _css_cache = CSS_STYLES_FILE.read_text(encoding='utf-8')
    return _css_cache


def load_template(tpl_name: str) -> Template:
    """
    Load an HTML template by name (without the `.html` suffix) and return a
    `string.Template` instance. Subsequent calls return the cached copy.
    """
    if tpl_name not in _template_cache:
        path = HTML_DIR / f'{tpl_name}.html'
        _template_cache[tpl_name] = path.read_text(encoding='utf-8')
    return Template(_template_cache[tpl_name])


def render(tpl_name: str, **kwargs) -> str:
    """
    Render a template with the given variables using `safe_substitute`
    (missing keys are left as `$placeholder` rather than raising).
    """
    return load_template(tpl_name).safe_substitute(**kwargs)
