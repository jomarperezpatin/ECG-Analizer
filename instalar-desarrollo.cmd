@echo off
setlocal
cd /d "%~dp0"
set "ComSpec=%SystemRoot%\System32\cmd.exe"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar-desarrollo.ps1"
if errorlevel 1 pause
