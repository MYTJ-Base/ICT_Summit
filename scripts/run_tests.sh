#!/usr/bin/env bash

# This script runs the full test suite for the project to validate the system.
# Make sure to run this script from the project root directory.

echo "===================================================="
echo "          RUNNING KNOWME TEST SUITE                 "
echo "===================================================="

# Set the Python Path to the current directory
export PYTHONPATH=.

# Check if the virtual environment is available, otherwise use global pytest
if [ -f ".venv/bin/pytest" ]; then
    echo "Running tests using local virtual environment..."
    .venv/bin/pytest -v
else
    echo "Running tests using global pytest..."
    pytest -v
fi

if [ $? -eq 0 ]; then
    echo "✅ All tests passed successfully!"
else
    echo "❌ Tests failed. Please check the output above."
    exit 1
fi
