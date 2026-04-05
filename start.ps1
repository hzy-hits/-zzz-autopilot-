# ZZZ-Autopilot MCP Server startup script for Windows
# Usage: Right-click -> Run with PowerShell
#   or:  powershell -ExecutionPolicy Bypass -File start.ps1
#
# Strategy: run inside the framework's venv (which has all game deps),
#           install only our few MCP deps there via uv pip.

param(
    [int]$Port = 8399,
    [string]$FrameworkPath = "",
    [switch]$NoFramework
)

$ErrorActionPreference = "Stop"

# --- Auto-detect paths ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Find the framework: explicit path > sibling dirs > glob search
$FrameworkDir = $null

if ($FrameworkPath -and (Test-Path (Join-Path $FrameworkPath "src\zzz_od"))) {
    $FrameworkDir = (Resolve-Path $FrameworkPath).Path
}

if (-not $FrameworkDir) {
    $ParentDir = Split-Path $ScriptDir -Parent
    $SearchDirs = @(
        (Join-Path $ParentDir "ZenlessZoneZero-OneDragon")
    )
    $SearchDirs += @(Get-ChildItem -Path $ParentDir -Directory -Filter "ZenlessZoneZero-OneDragon*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    $SearchDirs += @(Get-ChildItem -Path $ParentDir -Directory -Filter "ZenlessZoneZero-OneDragon*" -ErrorAction SilentlyContinue |
        Get-ChildItem -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })

    foreach ($candidate in $SearchDirs) {
        if ($candidate -and (Test-Path (Join-Path $candidate "src\zzz_od"))) {
            $FrameworkDir = (Resolve-Path $candidate).Path
            break
        }
    }
}

if (-not $FrameworkDir -and -not $NoFramework) {
    Write-Host "[!] ZenlessZoneZero-OneDragon not found." -ForegroundColor Yellow
    Write-Host "    Pass -FrameworkPath 'D:\path\to\zzz' or place it as a sibling directory."
    Write-Host "    Starting in --no-framework mode..."
    $NoFramework = $true
}

# --- Check uv ---
try {
    uv --version 2>&1 | Out-Null
} catch {
    Write-Host "[ERROR] uv not found. Install it: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# --- Resolve Python ---
if ($NoFramework) {
    # Dev mode: use project's own venv
    Write-Host "[*] Syncing project dependencies..." -ForegroundColor Cyan
    Push-Location $ScriptDir
    uv sync --quiet
    Pop-Location
    $Python = Join-Path $ScriptDir ".venv\Scripts\python.exe"
    $env:PYTHONPATH = "$ScriptDir\src"
    Write-Host "[*] Starting in DEV mode (no framework)..." -ForegroundColor Yellow
} else {
    # Production: use framework's venv, install our few deps into it
    $Python = Join-Path $FrameworkDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $Python)) {
        Write-Host "[ERROR] Framework venv not found at: $Python" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "[*] Framework: $FrameworkDir" -ForegroundColor Cyan
    Write-Host "[*] Python: $Python" -ForegroundColor Cyan

    # Install only MCP bridge deps into framework venv
    Write-Host "[*] Ensuring MCP deps in framework venv..." -ForegroundColor Cyan
    uv pip install --python $Python fastapi "uvicorn[standard]" "mcp[cli]" pydantic --quiet

    $env:PYTHONPATH = "$ScriptDir\src;$FrameworkDir\src"
    Write-Host "[*] Starting with framework integration..." -ForegroundColor Green
}

# --- Start server ---
$ServerArgs = @("-m", "zzz_agent.main", "--transport", "sse", "--port", $Port)
if (-not $NoFramework) {
    $ServerArgs += @("--framework-src", "$FrameworkDir\src")
}
if ($NoFramework) {
    $ServerArgs += "--no-framework"
}

Write-Host "[*] MCP Server: http://localhost:${Port}/sse" -ForegroundColor Green
Write-Host ""

& $Python @ServerArgs
