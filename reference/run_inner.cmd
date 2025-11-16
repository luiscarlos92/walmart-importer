@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Walmart Importer Pipeline (Inner)

echo =========================================
echo   Walmart Importer - Pipeline Runner
echo   Script: %~f0
echo   Folder: %~dp0
echo =========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PERIOD=%~1"
if "%PERIOD%"=="" (
  set /p PERIOD=Enter period YYYY-MM ^>: 
)

if not exist "%SCRIPT_DIR%.venv\Scripts\activate.bat" (
  echo [ERROR] venv not found. Run installer.cmd first.
  goto ENDPAUSE
)

call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
python --version

echo.
echo [INFO] Running pipeline for period: %PERIOD%
python "%SCRIPT_DIR%main.py" --period %PERIOD% --pipeline

:ENDPAUSE
echo.
echo =========================================
echo   Finished. Press any key to close ...
echo =========================================
pause >nul
endlocal
