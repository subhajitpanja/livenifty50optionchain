#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  dev-shell.sh — one-shot project bootstrap for a new terminal
#  Run once per fresh terminal: `source scripts/dev-shell.sh`
#  What it does:
#    1. Activates the project venv
#    2. Incrementally updates the code-review-graph (fast, silent)
#    3. Prints graph status so you know the graph is fresh
# ══════════════════════════════════════════════════════════════════
cd "$(dirname "${BASH_SOURCE[0]}")/.."
# shellcheck disable=SC1091
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
.venv/Scripts/code-review-graph update >/dev/null 2>&1 || .venv/bin/code-review-graph update >/dev/null 2>&1
.venv/Scripts/code-review-graph status 2>/dev/null || .venv/bin/code-review-graph status
echo
echo "[dev-shell] venv active, graph fresh. Ready."
