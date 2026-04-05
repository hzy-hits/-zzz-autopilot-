# ZZZ-Autopilot MCP Server startup script for Windows
# Usage: Right-click -> Run with PowerShell
#   or:  powershell -ExecutionPolicy Bypass -File start.ps1

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
    # Glob for ZenlessZoneZero-OneDragon* pattern (handles versioned folders)
    $SearchDirs += @(Get-ChildItem -Path $ParentDir -Directory -Filter "ZenlessZoneZero-OneDragon*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    # Check inside versioned folders (e.g. .../v2.1.0-Full/zzz/)
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

# --- Sync project dependencies ---
Write-Host "[*] Syncing project dependencies..." -ForegroundColor Cyan
Push-Location $ScriptDir
uv sync --quiet
Pop-Location

# --- Set PYTHONPATH (framework src only, runtime deps come from uv) ---
$env:PYTHONPATH = ""
if ($FrameworkDir -and -not $NoFramework) {
    $env:PYTHONPATH = "$FrameworkDir\src"
    Write-Host "[*] Framework: $FrameworkDir" -ForegroundColor Cyan
}

# --- Start server ---
$UvArgs = @("run", "python", "-m", "zzz_agent.main", "--transport", "sse", "--port", $Port)
if ($NoFramework) {
    $UvArgs += "--no-framework"
    Write-Host "[*] Starting in DEV mode (no framework)..." -ForegroundColor Yellow
} else {
    $UvArgs += @("--framework-src", "$FrameworkDir\src")
    Write-Host "[*] Starting with framework integration..." -ForegroundColor Green
}
Write-Host "[*] MCP Server: http://localhost:${Port}/sse" -ForegroundColor Green
Write-Host ""

uv @UvArgs
