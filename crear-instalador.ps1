$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:ComSpec = "$env:SystemRoot\System32\cmd.exe"
$env:Path = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\WindowsPowerShell\v1.0;$env:Path"
if (!(Test-Path '.venv\Scripts\python.exe') -or !(Test-Path 'node_modules')) { throw 'Ejecuta instalar-desarrollo.ps1 primero.' }
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements-build.txt
if ($LASTEXITCODE) { throw 'No se pudo instalar PyInstaller.' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --name ecg-backend --distpath build-python --workpath build-tmp --specpath build-tmp --paths backend --collect-submodules uvicorn --hidden-import matplotlib.backends.backend_agg --hidden-import matplotlib.backends.backend_pdf backend\launch.py
if ($LASTEXITCODE) { throw 'Error empaquetando Python.' }
npm.cmd run build
if ($LASTEXITCODE) { throw 'Error compilando frontend.' }
npm.cmd run dist:win
if ($LASTEXITCODE) { throw 'Error generando instalador.' }
Write-Host 'Revisa release/ para el instalador NSIS. MongoDB Community debe instalarse por separado.'
