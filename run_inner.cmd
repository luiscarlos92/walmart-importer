@echo off
setlocal EnableExtensions
REM Inner execution script - activates venv and runs the pipeline

set "HERE=%~dp0"
cd /d "%HERE%"

REM Check if venv exists
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found
    echo Please run install.cmd first
    pause
    exit /b 1
)

REM Activate venv
call .venv\Scripts\activate.bat

REM Run the pipeline
python -m importer.main --period %1

REM Keep window open if run directly
if "%2"=="" (
    echo.
    pause
)

endlocal
