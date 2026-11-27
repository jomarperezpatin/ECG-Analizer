param([Parameter(Mandatory=$true)][string]$Archive,[string]$SourceDatabase='ecg_database')
$ErrorActionPreference='Stop'
if (!(Test-Path -LiteralPath $Archive -PathType Leaf)) { throw 'Respaldo no encontrado.' }
if ($SourceDatabase -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Nombre inválido.' }
$target='ecg_restore_'+[guid]::NewGuid().ToString('N')
$tool=Get-Command mongorestore.exe -ErrorAction Stop
& $tool.Source --host 127.0.0.1 --port 27017 "--archive=$Archive" --gzip "--nsInclude=$SourceDatabase.*" "--nsFrom=$SourceDatabase.*" "--nsTo=$target.*" --stopOnError
if ($LASTEXITCODE) { throw 'Restauración de prueba fallida.' }
Write-Host "Restauración en nueva base: $target. No se borró ni sobrescribió la original. Verifica en Compass antes de usarla."
