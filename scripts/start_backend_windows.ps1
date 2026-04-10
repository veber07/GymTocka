$ErrorActionPreference = "Stop"

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing $python. Create the virtual environment and install backend dependencies first."
}

Write-Host "Starting backend on http://0.0.0.0:8000"
& $python run_backend.py
