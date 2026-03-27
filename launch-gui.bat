@echo off
REM Bing Rewards GUI Launcher for Windows
REM This script installs dependencies and launches the web GUI

echo ================================================================
echo Bing Rewards Web GUI - Windows Launcher
echo ================================================================
echo.

echo [1/2] Installing GUI dependencies...
pip install flask flask-cors --quiet

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to install dependencies
    echo Please run: pip install flask flask-cors
    pause
    exit /b 1
)

echo [OK] Dependencies installed
echo.

echo [2/2] Launching GUI...
echo.
echo The GUI will open in your browser at: http://localhost:5000
echo.
echo Press Ctrl+C to stop the GUI server
echo ================================================================
echo.

python -m bing_rewards.gui

pause
