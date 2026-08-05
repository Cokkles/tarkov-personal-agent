param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ConfigPath = "",
    [string]$ShortcutPath = "",
    [switch]$StartWithWindows
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $ProjectRoot "config.toml"
}
$ConfigPath = (Resolve-Path $ConfigPath).Path

$Launcher = Join-Path $ProjectRoot ".venv\Scripts\tarkov-agent-desktop.exe"
if (-not (Test-Path $Launcher)) {
    throw "Desktop launcher not found at $Launcher. Run scripts\install_desktop_companion.ps1 first."
}

if ([string]::IsNullOrWhiteSpace($ShortcutPath)) {
    if ($StartWithWindows) {
        $ShortcutPath = Join-Path ([Environment]::GetFolderPath("Startup")) "Tarkov Personal Agent.lnk"
    }
    else {
        $ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Tarkov Personal Agent.lnk"
    }
}

$ShortcutDirectory = Split-Path -Parent $ShortcutPath
if (-not (Test-Path $ShortcutDirectory)) {
    New-Item -ItemType Directory -Path $ShortcutDirectory -Force | Out-Null
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.Arguments = "--config `"$ConfigPath`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = "Launch the Tarkov Personal Agent desktop companion"
$Shortcut.IconLocation = "$Launcher,0"
$Shortcut.Save()

Write-Host "Created shortcut: $ShortcutPath"
