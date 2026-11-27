$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:ComSpec = "$env:SystemRoot\System32\cmd.exe"
$env:Path = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\WindowsPowerShell\v1.0;$env:Path"
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File .\instalar-desarrollo.ps1
if ($LASTEXITCODE -ne 0) { throw 'Error preparando dependencias.' }
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File .\crear-instalador.ps1
if ($LASTEXITCODE -ne 0) { throw 'Error generando el instalador.' }
$installer = Join-Path $PSScriptRoot 'release\ECG-Analyzer-Setup-1.0.0-x64.exe'
if (!(Test-Path $installer -PathType Leaf)) { throw 'No se encontro el instalador esperado. Revisa release y los mensajes del build.' }
Write-Host "Instalador generado: $installer"
