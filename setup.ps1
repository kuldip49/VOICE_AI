# SalesPilot AI - one-time setup for Windows (PowerShell).
# Usage:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Checking tools..." -ForegroundColor Cyan
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw "Python 3.11+ not found. Install from https://www.python.org/downloads/ (tick 'Add to PATH')." }
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { throw "Node.js 20+ not found. Install from https://nodejs.org/" }
python --version; node --version

Write-Host "Creating Python virtual environment (.venv)..." -ForegroundColor Cyan
if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

if (-not (Test-Path backend\.env)) {
  Copy-Item backend\.env.example backend\.env
  Write-Host "Created backend\.env (demo mode). Add GEMINI_API_KEY later for real LLM answers." -ForegroundColor Yellow
}

Write-Host "Initialising database + sample knowledge base..." -ForegroundColor Cyan
Push-Location backend
& ..\.venv\Scripts\python.exe -m app.seed
Pop-Location

Write-Host "Installing frontend packages..." -ForegroundColor Cyan
Push-Location frontend
npm install
Pop-Location

Write-Host "`nSetup complete. Next: .\start-all.ps1" -ForegroundColor Green
