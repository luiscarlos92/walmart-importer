@echo off
setlocal EnableExtensions
REM Installation script for Walmart Importer

echo ========================================
echo  Walmart Importer - Installation
echo ========================================
echo.

set "HERE=%~dp0"
cd /d "%HERE%"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.13.9 or later
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
if not exist ".venv" (
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

echo.
echo [2/4] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

echo.
echo [3/4] Installing Python packages...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements
    pause
    exit /b 1
)

echo.
echo [4/4] Installing Playwright Chromium browser...
python -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] Failed to install Playwright browser
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Installation completed successfully!
echo ========================================
echo.
echo Next steps:
echo   1. Configure your Outlook folder path in .env (copy from .env.example)
echo   2. Run 'run_all.cmd' to start importing orders
echo.
pause
endlocal
