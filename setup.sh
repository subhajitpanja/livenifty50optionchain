#!/bin/bash
################################################################################
# Live NIFTY Option Chain Dashboard - Setup Script
################################################################################
# This script sets up the development environment with all dependencies
# Includes code-review-graph integration for optimized code reviews
################################################################################

set -e  # Exit on any error

PYTHON_REQUIRED="3.12"

echo ""
echo "================================================================================"
echo " Live NIFTY Option Chain Dashboard - Environment Setup"
echo "================================================================================"
echo ""

# Check if Python is installed
echo "[1/7] Checking Python installation..."
if ! command -v python &> /dev/null; then
    echo "ERROR: Python is not installed or not in PATH"
    echo "Please install Python 3.12 or later from https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "SUCCESS: Found Python $PYTHON_VERSION"
echo ""

# Create virtual environment if it doesn't exist
echo "[2/7] Setting up virtual environment..."
if [ ! -d .venv ]; then
    echo "Creating .venv directory..."
    python -m venv .venv
    echo "SUCCESS: Virtual environment created"
else
    echo "Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "[3/7] Activating virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate virtual environment"
    exit 1
fi
echo "SUCCESS: Virtual environment activated"
echo ""

# Upgrade pip, setuptools, and wheel
echo "[4/7] Upgrading pip, setuptools, and wheel..."
python -m pip install --upgrade pip setuptools wheel --quiet
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to upgrade pip"
    exit 1
fi
echo "SUCCESS: pip, setuptools, and wheel upgraded"
echo ""

# Install requirements
echo "[5/7] Installing project dependencies from requirements.txt..."
pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install requirements"
    echo "Attempting to install with verbose output for debugging..."
    pip install -r requirements.txt
    exit 1
fi
echo "SUCCESS: Dependencies installed"
echo ""

# Install code-review-graph for optimized code reviews
echo "[6/7] Installing code-review-graph for enhanced code review capabilities..."
pip install code-review-graph --quiet
if [ $? -ne 0 ]; then
    echo "WARNING: Failed to install code-review-graph"
    echo "You can install it manually later with: pip install code-review-graph"
else
    echo "SUCCESS: code-review-graph installed"

    # Configure MCP and build knowledge graph
    echo "Configuring MCP integration..."
    code-review-graph install > /dev/null 2>&1
    echo "SUCCESS: MCP configured"

    echo "Building knowledge graph..."
    code-review-graph build > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "SUCCESS: Knowledge graph built"
    else
        echo "WARNING: Graph build had issues — run 'code-review-graph build' manually"
    fi
fi
echo ""

# Verify installation
echo "[7/7] Verifying installation..."
echo ""
echo "Installed packages:"
pip list --quiet
echo ""
echo "SUCCESS: Environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Review agents.md for code-review-graph usage"
echo "  2. Run tests with: bash run_tests.sh"
echo "  3. Start development with: python optionchain_gradio.py"
echo ""
echo "Environment Summary:"
echo "  - Python: $PYTHON_VERSION"
echo "  - Virtual Environment: .venv (activated)"
echo "  - Project: Live NIFTY Option Chain Dashboard"
echo ""
