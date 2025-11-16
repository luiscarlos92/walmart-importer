@echo off
setlocal EnableExtensions
REM Usage: run_fetch.cmd 2025-10 [limit]
set "SCRIPT_DIR=%~dp0"
set "PERIOD=%1"
set "LIMIT=%2"
if "%PERIOD%"=="" (
  set /p PERIOD=Enter period YYYY-MM ^>: 
)
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
if "%LIMIT%"=="" (
  python "%SCRIPT_DIR%main.py" --period %PERIOD% --fetch
) else (
  python "%SCRIPT_DIR%main.py" --period %PERIOD% --fetch --limit %LIMIT%
)
echo.
echo =========================================
echo   Finished. Press any key to close ...
echo =========================================
pause >nul
endlocal
