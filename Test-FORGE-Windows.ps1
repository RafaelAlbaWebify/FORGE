param([switch]$KeepSandbox)

$ErrorActionPreference = "Stop"
$source = $PSScriptRoot
$sandbox = Join-Path $env:TEMP ("FORGE_ACCEPTANCE_" + [guid]::NewGuid().ToString("N"))
$install = Join-Path $sandbox "installed"
$shortcut = Join-Path $sandbox "FORGE.lnk"
$badSource = Join-Path $sandbox "bad-release"
$database = Join-Path $install "data\forge.db"
$processIdFile = Join-Path $sandbox "forge.pid"
$marker = "acceptance-" + [guid]::NewGuid().ToString("N")
$releaseFiles = @(
    "forge_app.py", "README.md", "VERSION.txt", "INSTALL_FORGE.bat",
    "Install-FORGE.ps1", "START_FORGE.bat", "Start-FORGE.ps1",
    "BACKUP_FORGE.bat", "Backup-FORGE.ps1"
)

$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$validationPort = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
$listener.Stop()

function Stop-AcceptanceForge {
    if (Test-Path -LiteralPath $processIdFile) {
        $launchedId = [int](Get-Content -LiteralPath $processIdFile -Raw)
        Stop-Process -Id $launchedId -Force -ErrorAction SilentlyContinue
        try { Wait-Process -Id $launchedId -Timeout 10 -ErrorAction SilentlyContinue } catch { }
        Remove-Item -LiteralPath $processIdFile -Force -ErrorAction SilentlyContinue
    }
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        ($_.Name -in @("python.exe", "pythonw.exe")) -and $_.CommandLine -and
        $_.CommandLine.Contains((Join-Path $install "forge_app.py"))
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Invoke-Installer([string]$installerSource) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $installerSource "Install-FORGE.ps1") `
        -InstallRoot $install -ShortcutPath $shortcut -ProcessIdPath $processIdFile -NoBrowser `
        -AcceptanceValidation -ValidationPort $validationPort
    if ($LASTEXITCODE -ne 0) { throw "Installer returned exit code $LASTEXITCODE." }
}

try {
    New-Item -ItemType Directory -Path $sandbox -Force | Out-Null
    Write-Host "Acceptance health-check port: $validationPort" -ForegroundColor DarkGray
    Write-Host "[1/5] Clean isolated installation" -ForegroundColor Cyan
    Invoke-Installer $source
    if (-not (Test-Path -LiteralPath $database)) { throw "Clean install did not create forge.db." }
    if (-not (Test-Path -LiteralPath $shortcut)) { throw "Installer did not create the shortcut." }
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($shortcut)
    $shortcutArgument = [IO.Path]::GetFullPath($link.Arguments.Trim().Trim('"'))
    $expectedArgument = [IO.Path]::GetFullPath((Join-Path $install "forge_app.py"))
    if ($shortcutArgument -ne $expectedArgument) {
        throw "Shortcut target mismatch. Expected '$expectedArgument'; found '$shortcutArgument'."
    }

    Write-Host "[2/5] Seed preservation marker and upgrade" -ForegroundColor Cyan
    $python = (Get-Command python.exe).Source
    & $python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute('INSERT OR REPLACE INTO app_meta(key,value) VALUES (?,?)',('acceptance_marker',sys.argv[2])); c.commit(); c.close()" $database $marker
    Stop-AcceptanceForge
    Invoke-Installer $source
    $savedMarker = & $python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('SELECT value FROM app_meta WHERE key=?',('acceptance_marker',)).fetchone()[0]); c.close()" $database
    if ($savedMarker.Trim() -ne $marker) { throw "Upgrade did not preserve the database marker." }

    Write-Host "[3/5] Verified backup and disposable restore" -ForegroundColor Cyan
    Stop-AcceptanceForge
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $install "Backup-FORGE.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Backup command failed." }
    $backup = Get-ChildItem (Join-Path $install "backups") -Filter "forge_*.db" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $backup) { throw "No verified backup was created." }
    $restore = Join-Path $sandbox "restored.db"
    Copy-Item -LiteralPath $backup.FullName -Destination $restore -Force
    $restoreResult = & $python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('PRAGMA integrity_check').fetchone()[0]+'|'+c.execute('SELECT value FROM app_meta WHERE key=?',('acceptance_marker',)).fetchone()[0]); c.close()" $restore
    if ($restoreResult.Trim() -ne ("ok|" + $marker)) { throw "Restored backup failed integrity or content verification." }

    Write-Host "[4/5] Forced failed upgrade and rollback" -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $badSource -Force | Out-Null
    foreach ($name in $releaseFiles) { Copy-Item -LiteralPath (Join-Path $source $name) -Destination $badSource -Force }
    Copy-Item -LiteralPath (Join-Path $source "static") -Destination $badSource -Recurse -Force
    $badApp = Join-Path $badSource "forge_app.py"
    (Get-Content -LiteralPath $badApp -Raw).Replace('APP_VERSION = "0.10.0"', 'APP_VERSION = "0.0.0-acceptance-failure"') | Set-Content -LiteralPath $badApp -Encoding UTF8
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $badSource "Install-FORGE.ps1") `
        -InstallRoot $install -ShortcutPath $shortcut -ProcessIdPath $processIdFile -NoBrowser `
        -AcceptanceValidation -ValidationPort $validationPort
    if ($LASTEXITCODE -eq 0) { throw "The deliberately invalid upgrade unexpectedly succeeded." }
    $rolledBackMarker = & $python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('PRAGMA integrity_check').fetchone()[0]+'|'+c.execute('SELECT value FROM app_meta WHERE key=?',('acceptance_marker',)).fetchone()[0]); c.close()" $database
    if ($rolledBackMarker.Trim() -ne ("ok|" + $marker)) { throw "Rollback did not preserve the prior database." }
    if ((Get-Content -LiteralPath (Join-Path $install "forge_app.py") -Raw) -notmatch 'APP_VERSION = "0.10.0"') { throw "Rollback did not restore the prior application." }

    Write-Host "[5/5] PASS - install, shortcut, upgrade, backup/restore and rollback" -ForegroundColor Green
    Write-Host "Acceptance sandbox: $sandbox"
} finally {
    Stop-AcceptanceForge
    if (-not $KeepSandbox -and (Test-Path -LiteralPath $sandbox)) {
        for ($attempt = 0; $attempt -lt 10 -and (Test-Path -LiteralPath $sandbox); $attempt++) {
            try { Remove-Item -LiteralPath $sandbox -Recurse -Force -ErrorAction Stop } catch { Start-Sleep -Milliseconds 300 }
        }
        if (Test-Path -LiteralPath $sandbox) { Write-Warning "Acceptance sandbox remains for inspection: $sandbox" }
    }
}
