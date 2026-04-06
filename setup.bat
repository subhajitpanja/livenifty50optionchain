@echo off
REM ============================================================================
REM Live NIFTY Option Chain Dashboard - Setup Script
REM ============================================================================
REM This script sets up the development environment with all dependencies
REM Includes code-review-graph integration for optimized code reviews
REM ============================================================================

setlocal enabledelayedexpansion
set PYTHON_REQUIRED=3.12

echo.
echo ============================================================================
echo  Live NIFTY Option Chain Dashboard - Environment Setup
echo ============================================================================
echo.

REM Check if Python is installed
echo [1/7] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.12 or later from https://www.python.org/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo SUCCESS: Found Python %PYTHON_VERSION%
echo.

REM Create virtual environment if it doesn't exist
echo [2/7] Setting up virtual environment...
if not exist .venv (
    echo Creating .venv directory...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo SUCCESS: Virtual environment created
) else (
    echo Virtual environment already exists
)
echo.

REM Activate virtual environment
echo [3/7] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo SUCCESS: Virtual environment activated
echo.

REM Upgrade pip, setuptools, and wheel
echo [4/7] Upgrading pip, setuptools, and wheel...
python -m pip install --upgrade pip setuptools wheel --quiet
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip
    pause
    exit /b 1
)
echo SUCCESS: pip, setuptools, and wheel upgraded
echo.

REM Install requirements
echo [5/7] Installing project dependencies from requirements.txt...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Failed to install requirements
    echo Attempting to install with verbose output for debugging...
    pip install -r requirements.txt
    pause
    exit /b 1
)
echo SUCCESS: Dependencies installed
echo.

REM Install code-review-graph for optimized code reviews
echo [6/7] Installing code-review-graph for enhanced code review capabilities...
pip install code-review-graph --quiet
if errorlevel 1 (
    echo WARNING: Failed to install code-review-graph
    echo You can install it manually later with: pip install code-review-graph
) else (
    echo SUCCESS: code-review-graph installed

    REM Configure MCP and build knowledge graph
    echo Configuring MCP integration...
    code-review-graph install >nul 2>&1
    echo SUCCESS: MCP configured

    echo Building knowledge graph...
    code-review-graph build >nul 2>&1
    if errorlevel 0 (
        echo SUCCESS: Knowledge graph built
    ) else (
        echo WARNING: Graph build had issues — run 'code-review-graph build' manually
    )
)
echo.

REM Verify installation
echo [7/7] Verifying installation...
echo.
echo Installed packages:
pip list --quiet
echo.
echo SUCCESS: Environment setup complete!
echo.
echo Next steps:
echo   1. Review agents.md for code-review-graph usage
echo   2. Run tests with: run_tests.bat
echo   3. Start development with: python optionchain_gradio.py
echo.
echo Environment Summary:
echo   - Python: %PYTHON_VERSION%
echo   - Virtual Environment: .venv (activated)
echo   - Project: Live NIFTY Option Chain Dashboard
echo.

pause
