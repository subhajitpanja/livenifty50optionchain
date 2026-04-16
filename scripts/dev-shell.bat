@echo off
REM ══════════════════════════════════════════════════════════════════
REM  dev-shell.bat — one-shot project bootstrap for a new terminal
REM  Run once per fresh terminal: `scripts\dev-shell.bat`
REM  What it does:
REM    1. Activates the project venv
REM    2. Incrementally updates the code-review-graph (fast, silent)
REM    3. Prints graph status so you know the graph is fresh
REM ══════════════════════════════════════════════════════════════════
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
.venv\Scripts\code-review-graph.exe update >nul 2>&1
.venv\Scripts\code-review-graph.exe status
echo.
echo [dev-shell] venv active, graph fresh. Ready.
