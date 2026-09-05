$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw 'Python was not found. Install Python 3.10+ and enable "Add Python to PATH".'
}
& $python.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if ($LASTEXITCODE -ne 0) { throw "FORGE requires Python 3.10 or newer." }
& $python.Source "$PSScriptRoot\forge_app.py"
