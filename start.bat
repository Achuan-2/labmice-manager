@echo off
setlocal

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
set "exitCode=%ERRORLEVEL%"

if not "%exitCode%"=="0" pause
exit /b %exitCode%
