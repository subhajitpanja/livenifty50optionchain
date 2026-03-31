@echo off
REM Activate virtual environment and start the dashboard
REM Usage: activate.bat

echo Activating virtual environment...
call ..\\.venv\\Scripts\\activate.bat

echo.
echo Virtual environment activated!
echo.
echo To start the dashboard, run:
echo   python optionchain_gradio.py
echo.
echo Or run the test suite:
echo   python tests/test_all_functions.py
echo.
