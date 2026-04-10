param(
    [string]$ApkPath = "",
    [string]$AdbPath = "adb"
)

$ErrorActionPreference = "Stop"

if (-not $ApkPath) {
    $latestApk = Get-ChildItem -Path ".\bin" -Filter "*.apk" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $latestApk) {
        throw "No APK found in .\bin. Pass -ApkPath explicitly or copy the APK there first."
    }

    $ApkPath = $latestApk.FullName
}

& $AdbPath devices | Out-Host
& $AdbPath install -r $ApkPath

Write-Host ""
Write-Host "Installed APK:" $ApkPath
