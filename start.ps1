# ZZZ-Autopilot MCP Server startup script for Windows
# Usage: Right-click -> Run with PowerShell
#   or:  powershell -ExecutionPolicy Bypass -File start.ps1

param(
    [int]$Port = 8399,
    [switch]$NoFramework
)

$ErrorActionPreference = "Stop"

# --- Auto-detect paths ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Find the framework (sibling directory or parent)
$FrameworkCandidates = @(
    (Join-Path (Split-Path $ScriptDir -Parent) "ZenlessZoneZero-OneDragon"),
    (Join-Path $ScriptDir ".." "ZenlessZoneZero-OneDragon")
)
$FrameworkDir = $null
foreach ($candidate in $FrameworkCandidates) {
    if (Test-Path (Join-Path $candidate "src\zzz_od")) {
        $FrameworkDir = (Resolve-Path $candidate).Path
        break
    }
}

if (-not $FrameworkDir -and -not $NoFramework) {
    Write-Host "[!] ZenlessZoneZero-OneDragon not found." -ForegroundColor Yellow
    Write-Host "    Expected at: $(Split-Path $ScriptDir -Parent)\ZenlessZoneZero-OneDragon"
    Write-Host "    Starting in --no-framework mode..."
    $NoFramework = $true
}

# --- Find Python ---
# Try framework's .venv first, then system python
$PythonCandidates = @()
if ($FrameworkDir) {
    $PythonCandidates += Join-Path $FrameworkDir ".venv\Scripts\python.exe"
}
$PythonCandidates += (Join-Path $ScriptDir ".venv\Scripts\python.exe")
$PythonCandidates += "python"
$PythonCandidates += "python3"

$Python = $null
foreach ($candidate in $PythonCandidates) {
    try {
        $version = & $candidate --version 2>&1
        if ($version -match "3\.11") {
            $Python = $candidate
            break
        }
    } catch {}
}

if (-not $Python) {
    Write-Host "[ERROR] Python 3.11 not found. Install it or check your PATH." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[*] Python: $Python" -ForegroundColor Cyan

# --- Install extra dependencies ---
Write-Host "[*] Installing MCP server dependencies..." -ForegroundColor Cyan
& $Python -m pip install fastapi uvicorn mcp pydantic --quiet 2>&1 | Out-Null

# --- Set PYTHONPATH ---
$env:PYTHONPATH = "$ScriptDir\src"
if ($FrameworkDir -and -not $NoFramework) {
    $env:PYTHONPATH = "$ScriptDir\src;$FrameworkDir\src"
    Write-Host "[*] Framework: $FrameworkDir" -ForegroundColor Cyan
}

# --- Start server ---
$Args = @("-m", "zzz_agent.main", "--port", $Port)
if ($NoFramework) {
    $Args += "--no-framework"
    Write-Host "[*] Starting in DEV mode (no framework)..." -ForegroundColor Yellow
} else {
    Write-Host "[*] Starting with framework integration..." -ForegroundColor Green
}
Write-Host "[*] MCP Server: http://localhost:$Port/sse" -ForegroundColor Green
Write-Host ""

& $Python @Args
