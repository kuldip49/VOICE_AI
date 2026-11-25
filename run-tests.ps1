# Backend unit/integration/E2E-API tests + frontend type-check/build.
# Browser tests (Playwright MCP / Chrome DevTools MCP): see e2e\README.md
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\backend"
& ..\.venv\Scripts\python.exe -m pytest -q
Set-Location "$PSScriptRoot\frontend"
npm run build
