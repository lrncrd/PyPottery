#!/bin/bash
# PyPottery Suite Launcher - Linux/macOS
# This script launches the PyPottery Suite GUI

echo ""
echo "========================================"
echo "  PyPottery Suite Launcher"
echo "========================================"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check for Python 3
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python not found"
    echo "Please install Python 3.9+ using your package manager:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv python3-tk"
    echo "  macOS: brew install python python-tk"
    echo "  Fedora: sudo dnf install python3 python3-pip python3-tkinter"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MAJOR_VERSION=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
MINOR_VERSION=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')

if [ "$MAJOR_VERSION" -lt 3 ] || ([ "$MAJOR_VERSION" -eq 3 ] && [ "$MINOR_VERSION" -lt 9 ]); then
    echo "[ERROR] Python 3.9+ required. Found: Python $PYTHON_VERSION"
    exit 1
fi

echo "[OK] Found Python $PYTHON_VERSION"

# Check for tkinter
$PYTHON_CMD -c "import tkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[ERROR] tkinter not found"
    echo "Please install tkinter:"
    echo "  Ubuntu/Debian: sudo apt install python3-tk"
    echo "  macOS: brew install python-tk"
    echo "  Fedora: sudo dnf install python3-tkinter"
    exit 1
fi

# Run the install script
cd "$SCRIPT_DIR"
$PYTHON_CMD install.py "$@"

exit $?
