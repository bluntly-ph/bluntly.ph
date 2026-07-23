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
    [switch]$Stop
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

Write-Host "Starting API on $ApiPort..." -ForegroundColor Cyan
# The frontend calls the API server-side, but CORS still has to allow the web
# origin for anything the browser reaches directly.
$env:CORS_ORIGINS = "http://localhost:$WebPort"
Start-Process -FilePath $python `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--port', "$ApiPort", '--log-level', 'info') `
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
