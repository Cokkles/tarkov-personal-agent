param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ConfigPath = "",
    [switch]$StartWithWindows,
    [switch]$SkipShortcut
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $ProjectRoot "config.toml"
}
if (-not (Test-Path $ConfigPath)) {
    throw "Configuration file not found: $ConfigPath"
}
$ConfigPath = (Resolve-Path $ConfigPath).Path

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Project virtual environment not found at $Python"
}

Write-Host "Installing Desktop Companion dependencies..."
& $Python -m pip install -e "${ProjectRoot}[desktop]"
if ($LASTEXITCODE -ne 0) {
    throw "Desktop dependency installation failed with exit code $LASTEXITCODE"
}

$Launcher = Join-Path $ProjectRoot ".venv\Scripts\tarkov-agent-desktop.exe"
if (-not (Test-Path $Launcher)) {
    throw "Desktop launcher was not created: $Launcher"
}

if (-not $SkipShortcut) {
    $ShortcutScript = Join-Path $PSScriptRoot "create_desktop_shortcut.ps1"
    & $ShortcutScript `
        -ProjectRoot $ProjectRoot `
        -ConfigPath $ConfigPath `
        -StartWithWindows:$StartWithWindows
    if ($LASTEXITCODE -ne 0) {
        throw "Shortcut creation failed with exit code $LASTEXITCODE"
    }
}

Write-Host "Desktop Companion installed."
Write-Host "Launcher: $Launcher"
Write-Host "Config:   $ConfigPath"
