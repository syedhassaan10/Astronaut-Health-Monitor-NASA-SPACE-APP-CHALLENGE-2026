@echo off
rem OrbitFit launcher for Windows. Double-click to start.
rem The first start creates a Python environment in .venv and installs the packages (needs internet once).
rem After that, OrbitFit runs fully offline.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Setting up OrbitFit for the first time. This takes a few minutes...
    py -3 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo Could not create a Python environment. Install Python 3.11 or 3.12 from python.org and try again.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Installing the packages failed. Check the internet connection and try again.
        pause
        exit /b 1
    )
)

echo Starting OrbitFit at http://localhost:8501 (close this window to stop it)
".venv\Scripts\python.exe" -m streamlit run app.py
pause
