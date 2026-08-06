param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$PluginName = "com.cokkles.tarkov-personal-agent.sdPlugin"
$Source = Join-Path $ProjectRoot "streamdeck\$PluginName"
$PluginsRoot = Join-Path $env:APPDATA "Elgato\StreamDeck\Plugins"
$Destination = Join-Path $PluginsRoot $PluginName

if (-not (Test-Path $Source)) {
    throw "Stream Deck plugin source was not found at $Source"
}

$Manifest = Join-Path $Source "manifest.json"
$PluginCode = Join-Path $Source "bin\plugin.js"
if (-not (Test-Path $Manifest) -or -not (Test-Path $PluginCode)) {
    throw "The plugin source is incomplete. Pull the latest project files and try again."
}

$StreamDeckProcesses = Get-Process -Name "StreamDeck" -ErrorAction SilentlyContinue
if ($StreamDeckProcesses) {
    Write-Host "Stopping Stream Deck..."
    $StreamDeckProcesses | Stop-Process -Force
    Start-Sleep -Milliseconds 900
}

New-Item -ItemType Directory -Path $PluginsRoot -Force | Out-Null
if (Test-Path $Destination) {
    Remove-Item -Path $Destination -Recurse -Force
}
Copy-Item -Path $Source -Destination $Destination -Recurse -Force

Write-Host "Installed Tarkov Personal Agent Stream Deck plugin:"
Write-Host "  $Destination"

if (-not $NoRestart) {
    $Candidates = @(
        (Join-Path $env:ProgramFiles "Elgato\StreamDeck\StreamDeck.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Elgato\StreamDeck\StreamDeck.exe")
    ) | Where-Object { $_ -and (Test-Path $_) }

    if ($Candidates.Count -gt 0) {
        Write-Host "Starting Stream Deck..."
        Start-Process $Candidates[0]
    }
    else {
        Write-Warning "Stream Deck executable was not found automatically. Start Stream Deck manually."
    }
}

Write-Host "Add actions from the 'Tarkov Personal Agent' category to your profile."
