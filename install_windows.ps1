<#
.SYNOPSIS
    QuantX Deployer - Windows Installer
.DESCRIPTION
    Sets up Python venv, installs dependencies, creates launcher.
    Works on Windows 10/11 with Python 3.11+.
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host "    QUANTX DEPLOYER - WINDOWS INSTALLER" -ForegroundColor Cyan
Write-Host "  ================================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# -- 1. Check Python 3.11+ ------------------------------------------------

function Find-Python {
    foreach ($cmd in @("python", "python3", "py -3.12", "py -3.11")) {
        try {
            $ver = & cmd /c "$cmd --version 2>&1"
            if ($ver -match "Python 3\.1[1-9]|Python 3\.[2-9]") {
                if ($cmd -match "^py ") { return $cmd }
                return $cmd
            }
        } catch {}
    }
    return $null
}

$pythonCmd = Find-Python
if (-not $pythonCmd) {
    Write-Host "[!] Python 3.11+ is required but not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "    Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "    IMPORTANT: Check 'Add Python to PATH' during install." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
Write-Host "[OK] Python found: $pythonCmd" -ForegroundColor Green

# -- 2. Create virtual environment ----------------------------------------

if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating virtual environment..." -ForegroundColor Yellow
    & cmd /c "$pythonCmd -m venv .venv 2>&1"
    Write-Host "[OK] Virtual environment created at .venv\" -ForegroundColor Green
} else {
    Write-Host "[OK] Virtual environment already exists at .venv\" -ForegroundColor Green
}

# -- 3. Install dependencies ----------------------------------------------

Write-Host "[*] Installing Python dependencies..." -ForegroundColor Yellow
& .venv\Scripts\pip install --upgrade pip -q
& .venv\Scripts\pip install -r requirements.txt
Write-Host "[OK] Dependencies installed." -ForegroundColor Green

# -- 4. Create .env if missing --------------------------------------------

if (-not (Test-Path ".env")) {
    Write-Host "[*] Creating default .env file..." -ForegroundColor Yellow
    @"
PORT=8080
HOSTING=vps
# CENTRAL_API_URL=https://quantx-deploy.up.railway.app
# DEV_MODE=1
"@ | Out-File -Encoding utf8 -FilePath ".env"
    Write-Host "[OK] .env created with defaults." -ForegroundColor Green
} else {
    Write-Host "[OK] .env already exists." -ForegroundColor Green
}

# -- 5. Create launcher batch file ----------------------------------------

@"
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
python run.py
pause
"@ | Out-File -Encoding ascii -FilePath "Start QuantX.bat"
Write-Host "[OK] Created 'Start QuantX.bat' (double-click to launch)" -ForegroundColor Green

# -- 6. Done --------------------------------------------------------------

Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Green
Write-Host "    QUANTX DEPLOYER INSTALLED SUCCESSFULLY" -ForegroundColor Green
Write-Host "  ================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  To start QuantX:" -ForegroundColor White
Write-Host "    Option 1: Double-click 'Start QuantX.bat'" -ForegroundColor Cyan
Write-Host "    Option 2: Run in terminal:" -ForegroundColor White
Write-Host "              .venv\Scripts\activate && python run.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "  The app will open at http://localhost:8080" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Yellow
Write-Host "    1. Open http://localhost:8080 in your browser" -ForegroundColor White
Write-Host "    2. Register with your email" -ForegroundColor White
Write-Host "    3. Connect your broker (LongPort or IBKR)" -ForegroundColor White
Write-Host "    4. Add and deploy trading strategies" -ForegroundColor White
Write-Host ""
