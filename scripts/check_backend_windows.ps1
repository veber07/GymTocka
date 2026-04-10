param(
    [string]$BackendUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

$health = Invoke-WebRequest -Uri "$BackendUrl/health" -UseBasicParsing
Write-Host $health.Content
