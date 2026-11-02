# Run from PowerShell: .\start.ps1
[CmdletBinding()]
param(
    [string]$PythonExe,
    [switch]$NoBrowser,
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$children = @()
$logDirectory = Join-Path $projectRoot '.local-logs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed (exit $LASTEXITCODE). See the output above." }
}

function Start-AppProcess {
    param([string]$Command, [string]$Directory, [string]$Name)
    $escapedDirectory = $Directory.Replace("'", "''")
    $script = "Set-Location -LiteralPath '$escapedDirectory'; $Command; exit " + '$LASTEXITCODE'
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
    Start-Process -FilePath powershell.exe -WindowStyle Hidden -PassThru `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded) `
        -RedirectStandardOutput (Join-Path $logDirectory "$Name.log") `
        -RedirectStandardError (Join-Path $logDirectory "$Name.error.log")
}

function Wait-App {
    param([string]$Url, [System.Diagnostics.Process]$Process, [string]$Name)
    $deadline = (Get-Date).AddMinutes(3)
    while ((Get-Date) -lt $deadline) {
        if ($Process.HasExited) { throw "$Name exited. Check .local-logs\$Name.error.log and $Name.log." }
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Seconds 2
    }
    throw "Timed out waiting for $Name. Check .local-logs."
}

function Find-FreePort {
    param([int]$Preferred)
    for ($candidate = $Preferred; $candidate -lt ($Preferred + 20); $candidate++) {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $candidate)
        $listener.Server.ExclusiveAddressUse = $true
        try {
            $listener.Start()
            return $candidate
        } catch [System.Net.Sockets.SocketException] {
            # Another app or a Windows reservation owns this port.
        } finally {
            $listener.Stop()
        }
    }
    throw "No available port near $Preferred. Close an existing app and try again."
}

Push-Location -LiteralPath $projectRoot
try {
    foreach ($tool in @('docker', 'node', 'npm.cmd')) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            throw "$tool is missing. Install Docker Desktop, Node.js and standard Windows Python first."
        }
    }

    # Prefer a normal Windows venv; keep an existing MSYS venv untouched.
    $projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $projectPython)) {
        $venvDirectory = if (Test-Path -LiteralPath '.venv') { '.venv-windows' } else { '.venv' }
        $projectPython = Join-Path $projectRoot "$venvDirectory\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $projectPython)) {
            if (-not $PythonExe) {
                $candidates = @(Get-Command python.exe -All -ErrorAction SilentlyContinue |
                    Where-Object { $_.Source -notmatch 'msys|WindowsApps' })
                if ($candidates.Count) { $PythonExe = $candidates[0].Source }
            }
            if (-not $PythonExe) { throw 'Windows Python not found. Run .\start.ps1 -PythonExe "C:\path\to\python.exe".' }
            Invoke-Checked $PythonExe @('-c', "import sys; assert sys.platform == 'win32' and sys.version_info >= (3,11), 'Use standard Windows Python 3.11+'")
            Invoke-Checked $PythonExe @('-m', 'venv', $venvDirectory)
        }
    }

    if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
    Write-Host 'Checking Python packages...' -ForegroundColor Cyan
    Invoke-Checked $projectPython @('-m', 'pip', 'install', '-r', 'backend/requirements.txt')
    if (-not (Test-Path -LiteralPath 'frontend/node_modules/.package-lock.json')) {
        Push-Location frontend
        try { Invoke-Checked 'npm.cmd' @('ci') } finally { Pop-Location }
    }

    Write-Host 'Starting databases (Docker Desktop must be running)...' -ForegroundColor Cyan
    Invoke-Checked 'docker' @('compose', 'up', '-d')
    # Verify both configured connections before applying the schema.
    $probe = @'
import sys
try:
    from backend.db import connect
    from backend.graph import driver
    with connect() as conn:
        conn.execute('SELECT 1')
    with driver() as db:
        db.verify_connectivity()
except Exception:
    sys.exit(1)
'@
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        & $projectPython -c $probe 2>$null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw 'Databases did not become ready. Check docker compose logs and the connection settings in .env.' }

    Invoke-Checked $projectPython @('-m', 'backend.setup_db')
    $userProbe = "from backend.db import connect; c = connect(); conn = c.__enter__(); row = conn.execute('SELECT count(DISTINCT role) AS n FROM users WHERE active').fetchone(); c.__exit__(None, None, None); print(row['n'])"
    $roleCount = & $projectPython -c $userProbe
    if ($LASTEXITCODE -ne 0) { throw 'Could not check demo accounts.' }
    if ([int]$roleCount -lt 2) {
        Write-Host 'Preparing default local demo accounts...' -ForegroundColor Cyan
        Invoke-Checked $projectPython @('-m', 'backend.seed_users', '--defaults')
    }
    Invoke-Checked $projectPython @('-m', 'backend.sync_graph')

    $apiPort = Find-FreePort 8000
    $webPort = Find-FreePort 3000
    Write-Host "Starting API on $apiPort and web app on $webPort..." -ForegroundColor Cyan
    $pythonCommand = "& '" + $projectPython.Replace("'", "''") + "' -m uvicorn backend.main:app --host 127.0.0.1 --port $apiPort"
    $apiProcess = Start-AppProcess $pythonCommand $projectRoot 'api'
    $children += $apiProcess
    Wait-App "http://127.0.0.1:$apiPort/api/health" $apiProcess 'api'
    $webCommand = '$env:BACKEND_URL = ' + "'http://127.0.0.1:$apiPort'; & npm.cmd run dev -- --hostname 127.0.0.1 --port $webPort"
    $webProcess = Start-AppProcess $webCommand (Join-Path $projectRoot 'frontend') 'web'
    $children += $webProcess
    Wait-App "http://127.0.0.1:$webPort/login" $webProcess 'web'

    Write-Host "`nApp ready: http://127.0.0.1:$webPort" -ForegroundColor Green
    Write-Host 'Demo logins: admin / admin123 or analyst / analyst123. Logs: .local-logs'
    Write-Host 'Keep this terminal open. Press Ctrl+C to stop the API and web app.'
    Write-Host 'Databases stay running; stop them later with: docker compose stop'
    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$webPort" }
    while ($true) {
        foreach ($child in $children) {
            if ($child.HasExited) { throw 'An application process exited. Check .local-logs.' }
        }
        Start-Sleep -Seconds 2
    }
} catch {
    $failure = $_
    $failure | Format-List * -Force | Out-String | Out-File -LiteralPath (Join-Path $logDirectory 'startup.error.log') -Encoding utf8
    Write-Host "`nStartup failed: $($failure.Exception.Message)" -ForegroundColor Red
    Write-Host "Details saved to: $logDirectory\startup.error.log"
    if (-not $NoPause) { Read-Host 'Press Enter to close' | Out-Null }
    exit 1
} finally {
    foreach ($child in $children) {
        if (-not $child.HasExited) { & taskkill.exe /PID $child.Id /T /F 2>$null | Out-Null }
    }
    Pop-Location
}
