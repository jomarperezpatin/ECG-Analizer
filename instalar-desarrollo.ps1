$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:ComSpec = "$env:SystemRoot\System32\cmd.exe"
$env:Path = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\WindowsPowerShell\v1.0;$env:Path"
if (!(Test-Path '.venv\Scripts\python.exe')) { py -3.12 -m venv .venv; if ($LASTEXITCODE) { throw 'No se pudo crear .venv (instala Python 3.12 x64).' } }
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if ($LASTEXITCODE) { throw 'Error instalando dependencias Python.' }
npm.cmd install
if ($LASTEXITCODE) { throw 'Error instalando dependencias Node.' }
Write-Host 'Listo. Ejecuta npm.cmd run dev:desktop.'
