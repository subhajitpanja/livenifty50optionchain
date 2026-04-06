@echo off
REM ============================================================================
REM Live NIFTY Option Chain Dashboard - Test Runner Script
REM ============================================================================
REM Runs all tests and generates a comprehensive test report
REM ============================================================================

setlocal enabledelayedexpansion
set TEST_RESULTS=0

echo.
echo ============================================================================
echo  Live NIFTY Option Chain Dashboard - Test Execution
echo ============================================================================
echo.

REM Check if virtual environment exists
if not exist .venv (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first to initialize the environment
    pause
    exit /b 1
)

REM Activate virtual environment
echo [1/5] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo SUCCESS: Virtual environment activated
echo.

REM Check if pytest is installed
echo [2/5] Checking test dependencies...
pytest --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pytest not found. Installing test dependencies...
    pip install pytest pytest-asyncio --quiet
    if errorlevel 1 (
        echo ERROR: Failed to install test dependencies
        pause
        exit /b 1
    )
)
echo SUCCESS: Test dependencies verified
echo.

REM Run pytest with coverage
echo [3/5] Running test suite with pytest...
echo.
if exist tests (
    pytest tests/ -v --tb=short --color=yes
    set TEST_RESULTS=!ERRORLEVEL!
) else (
    echo WARNING: tests/ directory not found
    echo Attempting to discover and run any test files...
    pytest --collect-only -q
    set TEST_RESULTS=!ERRORLEVEL!
)
echo.

REM Check for syntax errors in main modules
echo [4/5] Checking Python syntax in main modules...
echo.

if exist color_constants.py (
    echo Checking color_constants.py...
    python -m py_compile color_constants.py
    if errorlevel 1 (
        echo ERROR: Syntax error in color_constants.py
        set TEST_RESULTS=1
    ) else (
        echo SUCCESS: color_constants.py syntax valid
    )
)

if exist oc_data_fetcher.py (
    echo Checking oc_data_fetcher.py...
    python -m py_compile oc_data_fetcher.py
    if errorlevel 1 (
        echo ERROR: Syntax error in oc_data_fetcher.py
        set TEST_RESULTS=1
    ) else (
        echo SUCCESS: oc_data_fetcher.py syntax valid
    )
)

if exist optionchain_gradio.py (
    echo Checking optionchain_gradio.py...
    python -m py_compile optionchain_gradio.py
    if errorlevel 1 (
        echo ERROR: Syntax error in optionchain_gradio.py
        set TEST_RESULTS=1
    ) else (
        echo SUCCESS: optionchain_gradio.py syntax valid
    )
)

if exist paths.py (
    echo Checking paths.py...
    python -m py_compile paths.py
    if errorlevel 1 (
        echo ERROR: Syntax error in paths.py
        set TEST_RESULTS=1
    ) else (
        echo SUCCESS: paths.py syntax valid
    )
)

if exist tui_components.py (
    echo Checking tui_components.py...
    python -m py_compile tui_components.py
    if errorlevel 1 (
        echo ERROR: Syntax error in tui_components.py
        set TEST_RESULTS=1
    ) else (
        echo SUCCESS: tui_components.py syntax valid
    )
)

if exist tui_theme.py (
    echo Checking tui_theme.py...
    python -m py_compile tui_theme.py
    if errorlevel 1 (
        echo ERROR: Syntax error in tui_theme.py
        set TEST_RESULTS=1
    ) else (
        echo SUCCESS: tui_theme.py syntax valid
    )
)

echo.

REM Verify imports
echo [5/5] Verifying Python imports...
echo.

python -c "import gradio; print('SUCCESS: gradio imported')" 2>nul || (
    echo ERROR: Failed to import gradio
    set TEST_RESULTS=1
)

python -c "import pandas; print('SUCCESS: pandas imported')" 2>nul || (
    echo ERROR: Failed to import pandas
    set TEST_RESULTS=1
)

python -c "import numpy; print('SUCCESS: numpy imported')" 2>nul || (
    echo ERROR: Failed to import numpy
    set TEST_RESULTS=1
)

python -c "import plotly; print('SUCCESS: plotly imported')" 2>nul || (
    echo ERROR: Failed to import plotly
    set TEST_RESULTS=1
)

python -c "import requests; print('SUCCESS: requests imported')" 2>nul || (
    echo ERROR: Failed to import requests
    set TEST_RESULTS=1
)

python -c "import rich; print('SUCCESS: rich imported')" 2>nul || (
    echo ERROR: Failed to import rich
    set TEST_RESULTS=1
)

echo.
echo ============================================================================
echo  Test Execution Summary
echo ============================================================================
echo.

if %TEST_RESULTS% equ 0 (
    echo SUCCESS: All tests passed! ✓
    echo.
    echo Your environment is ready for development.
    echo You can now run: python optionchain_gradio.py
) else (
    echo WARNING: Some tests or checks failed!
    echo Please review the output above and address any errors.
    echo.
    echo Common fixes:
    echo   1. Run setup.bat again to ensure all dependencies are installed
    echo   2. Check that the virtual environment is properly activated
    echo   3. Verify Python version (3.12 or later required)
)

echo.
echo Test Results Code: %TEST_RESULTS%
echo.

pause
