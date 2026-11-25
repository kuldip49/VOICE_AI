# Deletes the local SQLite database and reloads the sample knowledge base (stop the backend first).
Set-Location "$PSScriptRoot\backend"
& ..\.venv\Scripts\python.exe -m app.seed --reset
