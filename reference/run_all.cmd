@echo off
setlocal EnableExtensions
REM Outer wrapper: double-click THIS. It opens a new console that stays open.
set "HERE=%~dp0"
start "Walmart Importer Pipeline" cmd.exe /k "%HERE%run_inner.cmd" %*
endlocal
