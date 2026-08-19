<#
.SYNOPSIS
  Start the bluntly.ph stack — exactly one API and one web server, every time.

.DESCRIPTION
  Idempotent by design. Each port is freed before anything is started, so
  running this twice replaces the running stack rather than leaving a second
  copy behind. That matters here: Next silently falls back to the next free
  port when 3000 is taken, which is how you end up with one server on 3000 and
  another on 3001, each talking to a different backend state.

  Only processes *listening on our ports* are stopped. Nothing else is touched.

.PARAMETER Stop
  Free the ports and exit without starting anything.

.EXAMPLE
  npm run dev:all
  npm run dev:stop
#>
[CmdletBinding()]
param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 3000,
    [switch]$Stop,
    # Deliberately run local development against PRODUCTION. Off by default,
    # never persisted, and announced loudly every time it is used.
    [switch]$AllowProduction
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Stop-Port {
    param([int]$Port, [string]$Label)
    $owners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    if (-not $owners) {
        Write-Host "  $Label`: port $Port already free"
        return
    }
    foreach ($processId in $owners) {
        try {
            $name = (Get-Process -Id $processId -ErrorAction Stop).ProcessName
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Host "  $Label`: stopped $name (pid $processId) on $Port"
        } catch {
            Write-Warning "  $Label`: could not stop pid $processId on $Port - $_"
        }
    }
    # Windows holds the socket briefly after the process dies.
    Start-Sleep -Milliseconds 800
}

function Wait-Healthy {
    param([string]$Url, [string]$Label, [int]$TimeoutSeconds = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing | Out-Null
            Write-Host "  $Label ready -> $Url" -ForegroundColor Green
            return $true
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    Write-Warning "  $Label did not become ready within ${TimeoutSeconds}s"
    return $false
}

Write-Host "Freeing ports..." -ForegroundColor Cyan
Stop-Port -Port $ApiPort -Label 'api'
Stop-Port -Port $WebPort -Label 'web'

if ($Stop) {
    Write-Host "Stopped. Nothing is running." -ForegroundColor Cyan
    exit 0
}

$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw "Backend virtualenv not found at $python. Create it before running this."
}

# --- Refuse to start against production -------------------------------------
# `npm run dev:all` reads the repo-root .env, which is production. Clicking
# around the local app therefore wrote to the live database, and no automated
# guard covered it because starting the app is a deliberate act rather than an
# automated command. It is guarded here, at the launcher, rather than in the
# application: the deployed production function must obviously still boot with
# production configuration.
#
# Both processes are checked as ONE environment. A frontend on test with a
# backend on production (or the reverse) is worse than either alone, because
# every symptom points at the wrong half.
# Load backend/.env.test into THIS process, so both child processes inherit it.
# Without this the probe could report "test" while uvicorn still read the
# repo-root .env and connected to production - the two must be one environment,
# and a frontend on test with a backend on production is worse than either
# alone because every symptom points at the wrong half.
$envTest = Join-Path $root 'backend/.env.test'
if (Test-Path $envTest) {
    Get-Content $envTest | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
            $k, $v = $line.Split('=', 2)
            # A variable already exported wins, so CI and one-off overrides hold.
            if (-not [Environment]::GetEnvironmentVariable($k.Trim())) {
                Set-Item -Path "env:$($k.Trim())" -Value $v.Trim()
            }
        }
    }
    Write-Host "  loaded backend/.env.test into the dev environment" -ForegroundColor DarkGray
}

$probeScript = Join-Path $root 'backend\scripts\print_env_target.py'
$targetProbe = & $python $probeScript 2>&1

$targetLine = ($targetProbe | Select-Object -First 1)
$verdict = ($targetProbe | Select-Object -Last 1)

Write-Host ""
Write-Host "  environment -> $targetLine" -ForegroundColor DarkGray

if ($verdict -eq 'PRODUCTION' -and -not $AllowProduction) {
    Write-Host ""
    Write-Host "  ====================================================" -ForegroundColor Red
    Write-Host "  REFUSING TO START - local dev is pointed at PRODUCTION" -ForegroundColor Red
    Write-Host "  ====================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Anything you click in the local app would write to the live" -ForegroundColor Yellow
    Write-Host "  database that serves www.bluntly.ph." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Point it at the test project instead:" -ForegroundColor Cyan
    Write-Host "    1. cp backend/.env.test.example backend/.env.test" -ForegroundColor Cyan
    Write-Host "    2. fill in the test project's credentials" -ForegroundColor Cyan
    Write-Host "    3. npm run dev:all" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  If you genuinely need production (read-only debugging):" -ForegroundColor DarkGray
    Write-Host "    powershell -File scripts/dev.ps1 -AllowProduction" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  See docs/ENVIRONMENTS.md." -ForegroundColor DarkGray
    exit 1
}

if ($verdict -eq 'PRODUCTION' -and $AllowProduction) {
    Write-Host ""
    Write-Host "  !! RUNNING LOCAL DEV AGAINST PRODUCTION !!" -ForegroundColor Red
    Write-Host "  Every write you make here lands on the live site." -ForegroundColor Red
    Write-Host ""
}

Write-Host "Starting API on $ApiPort..." -ForegroundColor Cyan
# The frontend calls the API server-side, but CORS still has to allow the web
# origin for anything the browser reaches directly.
$env:CORS_ORIGINS = "http://localhost:$WebPort"
# --reload matters more than it looks: without it uvicorn holds the modules it
# imported at boot, so editing a service or template changes nothing until the
# process is restarted — and the symptom is silent (the old code just keeps
# running). The web server already hot-reloads; the API should too.
Start-Process -FilePath $python `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--port', "$ApiPort",
                    '--log-level', 'info', '--reload', '--reload-dir', 'app') `
    -WorkingDirectory (Join-Path $root 'backend') `
    -WindowStyle Minimized | Out-Null

Write-Host "Starting web on $WebPort..." -ForegroundColor Cyan
# --port is explicit so Next fails loudly on a busy port instead of silently
# moving to 3001 and creating the duplicate this script exists to prevent.
Start-Process -FilePath 'cmd.exe' `
    -ArgumentList @('/c', 'npm', 'run', 'dev', '--', '--port', "$WebPort") `
    -WorkingDirectory $root `
    -WindowStyle Minimized | Out-Null

Write-Host "Waiting for both..." -ForegroundColor Cyan
$apiOk = Wait-Healthy -Url "http://localhost:$ApiPort/health" -Label 'api'
$webOk = Wait-Healthy -Url "http://localhost:$WebPort/welcome" -Label 'web'

Write-Host ''
if ($apiOk -and $webOk) {
    Write-Host "Stack up:  http://localhost:$WebPort" -ForegroundColor Green
    exit 0
}
Write-Warning 'Stack did not come up cleanly. Check the minimized console windows.'
exit 1
