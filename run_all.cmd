@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Main launcher for Walmart Importer

echo ========================================
echo  Walmart Importer - Pipeline Runner
echo ========================================
echo.

REM Prompt for period
set /p PERIOD="Enter period (YYYY-MM, e.g., 2025-10): "

if "%PERIOD%"=="" (
    echo [ERROR] No period specified
    pause
    exit /b 1
)

echo.
echo Starting pipeline for period: %PERIOD%
echo.

REM Get script directory
set "HERE=%~dp0"

REM Call inner script
call "%HERE%run_inner.cmd" %PERIOD%

endlocal
