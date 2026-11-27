param([string]$Database = 'ecg_database', [string]$Output = '')
$ErrorActionPreference = 'Stop'
if ($Database -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Nombre de base no válido.' }
if (!$Output) { $Output = Join-Path $HOME ('ECG-respaldo-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.archive.gz') }
if (Test-Path $Output) { throw 'El archivo de destino ya existe.' }
$tool = Get-Command mongodump.exe -ErrorAction Stop
# Default local service only; for authenticated installations use MongoDB tools manually.
& $tool.Source --host 127.0.0.1 --port 27017 --db $Database "--archive=$Output" --gzip
if ($LASTEXITCODE) { throw 'El respaldo falló; no utilizar el archivo parcial.' }
Write-Host "Respaldo creado: $Output. Contiene datos sin cifrar; mantenlo protegido."
