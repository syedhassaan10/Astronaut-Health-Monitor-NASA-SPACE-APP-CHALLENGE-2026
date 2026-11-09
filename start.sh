#!/usr/bin/env bash
# OrbitFit launcher for macOS and Linux: bash start.sh
# The first start creates a Python environment in .venv and installs the packages (needs internet once).
# After that, OrbitFit runs fully offline.
set -e
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "Setting up OrbitFit for the first time. This takes a few minutes..."
    PY=$(command -v python3.12 || command -v python3.11 || command -v python3 || true)
    if [ -z "$PY" ]; then
        echo "Python 3.11 or 3.12 is needed. Install it from python.org and try again."
        exit 1
    fi
    "$PY" -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

echo "Starting OrbitFit at http://localhost:8501 (press Ctrl+C to stop it)"
# --server.address localhost: only this computer can open the app; health data is never served to the network.
.venv/bin/python -m streamlit run app.py --server.address localhost
