# Opens backend and frontend in two PowerShell windows, then the browser.
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\start-backend.ps1"
Start-Sleep -Seconds 3
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\start-frontend.ps1"
Start-Sleep -Seconds 4
Start-Process "http://localhost:5173/agent"
