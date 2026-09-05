param(
    [string]$InstallRoot = "",
    [string]$ShortcutPath = "",
    [string]$ProcessIdPath = "",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$source = $PSScriptRoot
$installRoot = if ($InstallRoot) { [IO.Path]::GetFullPath($InstallRoot) } else { Join-Path $env:LOCALAPPDATA "FORGE" }
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = if ($ShortcutPath) { [IO.Path]::GetFullPath($ShortcutPath) } else { Join-Path $desktop "FORGE.lnk" }
$rollbackRoot = $null
$preBackup = $null
$upgradeCommitted = $false

trap {
    $failure = $_
    if (-not $upgradeCommitted -and $rollbackRoot -and (Test-Path -LiteralPath $rollbackRoot)) {
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            ($_.Name -in @("python.exe", "pythonw.exe")) -and $_.CommandLine -and $_.CommandLine.Contains((Join-Path $installRoot "forge_app.py"))
        } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Get-ChildItem -LiteralPath $installRoot -Force | Where-Object { $_.Name -notin @("data", "exports", "backups") } | Remove-Item -Recurse -Force
        Get-ChildItem -LiteralPath $rollbackRoot -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $installRoot -Recurse -Force
        }
        if ($preBackup -and (Test-Path -LiteralPath $preBackup.FullName)) {
            Copy-Item -LiteralPath $preBackup.FullName -Destination (Join-Path $installRoot "data\forge.db") -Force
        }
        Write-Host "Upgrade failed; the previous FORGE version and database were restored." -ForegroundColor Yellow
    }
    Write-Error $failure
    exit 1
}

$pythonCommand = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    $pythonConsole = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $pythonConsole) {
        throw 'Python 3.10 or newer was not found. Install Python and enable "Add Python to PATH", then run this installer again.'
    }
    $pythonwCandidate = Join-Path (Split-Path $pythonConsole.Source) "pythonw.exe"
    if (Test-Path $pythonwCandidate) {
        $pythonPath = $pythonwCandidate
    } else {
        $pythonPath = $pythonConsole.Source
    }
} else {
    $pythonPath = $pythonCommand.Source
}

$pythonConsolePath = if ($pythonConsole) { $pythonConsole.Source } else { (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
if (-not $pythonConsolePath) { throw "Python 3.10 or newer was not found." }
$pythonVersionOk = & $pythonConsolePath -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if ($LASTEXITCODE -ne 0) { throw "FORGE requires Python 3.10 or newer." }

# Capture and protect all existing user records before changing application files.
$database = Join-Path $installRoot "data\forge.db"
$preState = $null
if (Test-Path -LiteralPath $database) {
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $installRoot "Backup-FORGE.ps1")
    if ($LASTEXITCODE -ne 0) { throw "The pre-upgrade backup failed. FORGE was not changed." }
    $preBackup = Get-ChildItem (Join-Path $installRoot "backups") -Filter "forge_*.db" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $preState = & $pythonConsolePath -c "import json,sqlite3,sys; c=sqlite3.connect(sys.argv[1]); tables=['missions','timer_sessions','time_adjustments','projects','milestones','daily_notes']; print(json.dumps({t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in tables})); c.close()" $database | ConvertFrom-Json
}

if (Test-Path -LiteralPath $installRoot) {
    $rollbackRoot = Join-Path $env:TEMP ("FORGE_ROLLBACK_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $rollbackRoot -Force | Out-Null
    Get-ChildItem -LiteralPath $installRoot -Force | Where-Object { $_.Name -notin @("data", "exports", "backups") } | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $rollbackRoot -Recurse -Force
    }
}

# Stop only an installed FORGE process, so an upgrade cannot reopen stale code.
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    ($_.Name -in @("python.exe", "pythonw.exe")) -and $_.CommandLine -and
    $_.CommandLine.Contains((Join-Path $installRoot "forge_app.py"))
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 500

New-Item -ItemType Directory -Path $installRoot -Force | Out-Null

# Preserve the user's database, exports and backups during upgrades.
$preserve = @("data", "exports", "backups")
Get-ChildItem -LiteralPath $source -Force | Where-Object {
    $_.Name -notin $preserve -and $_.Name -notin @("build-dev", "__pycache__", ".git", ".github", ".ai", "node_modules", "dist", "test-results", "playwright-report")
} | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $installRoot -Recurse -Force
}

foreach ($folder in $preserve) {
    $destination = Join-Path $installRoot $folder
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    $sourceFolder = Join-Path $source $folder
    if ((Test-Path $sourceFolder) -and -not (Get-ChildItem -LiteralPath $destination -Force -ErrorAction SilentlyContinue)) {
        Copy-Item -Path (Join-Path $sourceFolder "*") -Destination $destination -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonPath
$shortcut.Arguments = '"' + (Join-Path $installRoot "forge_app.py") + '"'
$shortcut.WorkingDirectory = $installRoot
$shortcut.Description = "FORGE daily command board"
$shortcut.IconLocation = $pythonPath + ",0"
$shortcut.Save()

$launchArguments = @('"' + (Join-Path $installRoot "forge_app.py") + '"')
if ($NoBrowser) { $launchArguments += "--no-browser" }
$launchedProcess = Start-Process -FilePath $pythonPath -ArgumentList $launchArguments -WorkingDirectory $installRoot -PassThru
if ($ProcessIdPath) {
    Set-Content -LiteralPath ([IO.Path]::GetFullPath($ProcessIdPath)) -Value $launchedProcess.Id -Encoding ASCII
}

$verifiedUrl = $null
for ($attempt = 0; $attempt -lt 30 -and -not $verifiedUrl; $attempt++) {
    Start-Sleep -Milliseconds 250
    foreach ($port in 8877..8896) {
        try {
            $identity = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/identity" -TimeoutSec 1
            $identityRoot = if ($identity.root) { [IO.Path]::GetFullPath([string]$identity.root) } else { "" }
            if ($identity.app -eq "FORGE" -and $identity.version -eq "0.10.0" -and $identityRoot -eq $installRoot) {
                $verifiedUrl = "http://127.0.0.1:$port"
                break
            }
        } catch { }
    }
}
if (-not $verifiedUrl) { throw "FORGE was copied but version 0.10.0 did not start correctly." }

if ($preState) {
    $postState = & $pythonConsolePath -c "import json,sqlite3,sys; c=sqlite3.connect(sys.argv[1]); assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; tables=['missions','timer_sessions','time_adjustments','projects','milestones','daily_notes']; print(json.dumps({t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in tables})); c.close()" $database | ConvertFrom-Json
    foreach ($table in @('missions','timer_sessions','time_adjustments','projects','milestones','daily_notes')) {
        if ([int]$postState.$table -lt [int]$preState.$table) { throw "Upgrade validation failed: $table records decreased. Your verified backup was preserved." }
    }
}

Write-Host ""
Write-Host "FORGE installed successfully." -ForegroundColor Green
Write-Host "Location: $installRoot"
Write-Host "Desktop shortcut: $shortcutPath"
$upgradeCommitted = $true
if ($rollbackRoot) { Remove-Item -LiteralPath $rollbackRoot -Recurse -Force -ErrorAction SilentlyContinue }
Write-Host "Verified version: 0.10.0 at $verifiedUrl"
if ($preState) { Write-Host "Existing activities and project records validated after upgrade." -ForegroundColor Green }
