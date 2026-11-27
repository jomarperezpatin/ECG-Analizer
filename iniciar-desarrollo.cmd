@echo off
setlocal
cd /d "%~dp0"
set "ComSpec=%SystemRoot%\System32\cmd.exe"
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\WindowsPowerShell\v1.0;%PATH%"
set "ELECTRON_RUN_AS_NODE="
call npm.cmd run dev:desktop
if errorlevel 1 pause
