$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$database = Join-Path $root "data\forge.db"
if (-not (Test-Path -LiteralPath $database)) { throw "FORGE database was not found: $database" }
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) { throw "Python was not found." }
$stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$target = Join-Path $root "backups\forge_$stamp.db"
New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
& $python.Source -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close(); c=sqlite3.connect(sys.argv[2]); assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; c.close()" $database $target
if ($LASTEXITCODE -ne 0) { Remove-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue; throw "Backup failed integrity verification." }
Write-Host "FORGE verified backup created: $target" -ForegroundColor Green
