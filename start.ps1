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
    # Search sibling directories for any folder containing src\zzz_od
    $SearchDirs = @(
        (Join-Path $ParentDir "ZenlessZoneZero-OneDragon")
    )
    # Also glob for ZenlessZoneZero-OneDragon* pattern (handles versioned folders)
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

# --- Install extra dependencies (skip if pip unavailable) ---
$HasPip = $false
try { & $Python -m pip --version 2>&1 | Out-Null; $HasPip = $true } catch {}
if ($HasPip) {
    Write-Host "[*] Installing MCP server dependencies..." -ForegroundColor Cyan
    & $Python -m pip install fastapi uvicorn mcp pydantic --quiet 2>&1 | Out-Null
} else {
    Write-Host "[*] pip not available, checking if deps exist..." -ForegroundColor Yellow
    $MissingDeps = @()
    foreach ($mod in @("fastapi", "uvicorn", "mcp", "pydantic")) {
        try { & $Python -c "import $mod" 2>&1 | Out-Null } catch { $MissingDeps += $mod }
    }
    if ($MissingDeps.Count -gt 0) {
        Write-Host "[!] Missing: $($MissingDeps -join ', '). Install manually or use: uv pip install $($MissingDeps -join ' ')" -ForegroundColor Red
    }
}

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
