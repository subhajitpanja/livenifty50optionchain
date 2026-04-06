#!/bin/bash
################################################################################
# Live NIFTY Option Chain Dashboard - Test Runner Script
################################################################################
# Runs all tests and generates a comprehensive test report
################################################################################

set -e  # Exit on any error

TEST_RESULTS=0

echo ""
echo "================================================================================"
echo " Live NIFTY Option Chain Dashboard - Test Execution"
echo "================================================================================"
echo ""

# Check if virtual environment exists
if [ ! -d .venv ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please run setup.sh first to initialize the environment"
    exit 1
fi

# Activate virtual environment
echo "[1/5] Activating virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate virtual environment"
    exit 1
fi
echo "SUCCESS: Virtual environment activated"
echo ""

# Check if pytest is installed
echo "[2/5] Checking test dependencies..."
if ! command -v pytest &> /dev/null; then
    echo "Test dependencies missing. Installing..."
    pip install pytest pytest-asyncio --quiet
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install test dependencies"
        exit 1
    fi
fi
echo "SUCCESS: Test dependencies verified"
echo ""

# Run pytest with coverage
echo "[3/5] Running test suite with pytest..."
echo ""
if [ -d tests ]; then
    pytest tests/ -v --tb=short --color=yes || TEST_RESULTS=$?
else
    echo "WARNING: tests/ directory not found"
    echo "Attempting to discover and run any test files..."
    pytest --collect-only -q || TEST_RESULTS=$?
fi
echo ""

# Check for syntax errors in main modules
echo "[4/5] Checking Python syntax in main modules..."
echo ""

for module in color_constants.py oc_data_fetcher.py optionchain_gradio.py paths.py tui_components.py tui_theme.py; do
    if [ -f "$module" ]; then
        echo "Checking $module..."
        python -m py_compile "$module"
        if [ $? -ne 0 ]; then
            echo "ERROR: Syntax error in $module"
            TEST_RESULTS=1
        else
            echo "SUCCESS: $module syntax valid"
        fi
    fi
done

echo ""

# Verify imports
echo "[5/5] Verifying Python imports..."
echo ""

python -c "import gradio; print('SUCCESS: gradio imported')" 2>/dev/null || {
    echo "ERROR: Failed to import gradio"
    TEST_RESULTS=1
}

python -c "import pandas; print('SUCCESS: pandas imported')" 2>/dev/null || {
    echo "ERROR: Failed to import pandas"
    TEST_RESULTS=1
}

python -c "import numpy; print('SUCCESS: numpy imported')" 2>/dev/null || {
    echo "ERROR: Failed to import numpy"
    TEST_RESULTS=1
}

python -c "import plotly; print('SUCCESS: plotly imported')" 2>/dev/null || {
    echo "ERROR: Failed to import plotly"
    TEST_RESULTS=1
}

python -c "import requests; print('SUCCESS: requests imported')" 2>/dev/null || {
    echo "ERROR: Failed to import requests"
    TEST_RESULTS=1
}

python -c "import rich; print('SUCCESS: rich imported')" 2>/dev/null || {
    echo "ERROR: Failed to import rich"
    TEST_RESULTS=1
}

echo ""
echo "================================================================================"
echo " Test Execution Summary"
echo "================================================================================"
echo ""

if [ $TEST_RESULTS -eq 0 ]; then
    echo "SUCCESS: All tests passed! ✓"
    echo ""
    echo "Your environment is ready for development."
    echo "You can now run: python optionchain_gradio.py"
else
    echo "WARNING: Some tests or checks failed!"
    echo "Please review the output above and address any errors."
    echo ""
    echo "Common fixes:"
    echo "  1. Run setup.sh again to ensure all dependencies are installed"
    echo "  2. Check that the virtual environment is properly activated"
    echo "  3. Verify Python version (3.12 or later required)"
fi

echo ""
echo "Test Results Code: $TEST_RESULTS"
echo ""

exit $TEST_RESULTS
