$ErrorActionPreference = "Stop"

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing $python. Create the virtual environment and install backend dependencies first."
}

Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like '*run_backend.py*' } |
    ForEach-Object {
        Write-Host "Stopping older backend process $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force
    }

$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
if ($listener) {
    foreach ($pid in $listener) {
        Write-Host "Stopping process listening on port 8000: $pid"
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Starting backend on http://0.0.0.0:8000"
& $python run_backend.py
