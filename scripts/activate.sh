#!/bin/bash
# Activate virtual environment and start the dashboard
# Usage: source activate.sh

echo "Activating virtual environment..."
source ../.venv/bin/activate

echo ""
echo "Virtual environment activated!"
echo ""
echo "To start the dashboard, run:"
echo "  python optionchain_gradio.py"
echo ""
echo "Or run the test suite:"
echo "  python tests/test_all_functions.py"
echo ""
