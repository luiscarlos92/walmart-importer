@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer.ps1"
endlocal
