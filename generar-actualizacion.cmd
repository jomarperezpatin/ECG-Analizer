@echo off
setlocal
cd /d "%~dp0"
set "ComSpec=%SystemRoot%\System32\cmd.exe"
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\WindowsPowerShell\v1.0;%PATH%"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0generar-actualizacion.ps1"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo Error al generar la actualizacion. Revisa los mensajes anteriores.
pause
exit /b %RESULT%
