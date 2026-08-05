# Phase 6.5 — Desktop Companion

## Purpose

The Desktop Companion provides a native Windows-oriented application for normal daily use while preserving the existing local FastAPI service and browser interfaces as the stable backend and diagnostics layer.

Launching one shortcut can now:

- start the local agent service inside the desktop process;
- display agent, raid, OBS, PPE, and review status;
- start, end, or abort a raid;
- create the seven validated live markers;
- open Raid Review, PPE, Source of Truth, Recommendations, Media, or API documentation;
- remain available in the Windows system tray.

The desktop application is a client of the same local API used by Stream Deck and the browser interface. It does not create a second data model or bypass existing safety checks.

## Installation

From the repository root with the project virtual environment already created:

```powershell
.\scripts\install_desktop_companion.ps1 `
  -ConfigPath "C:\TarkovPersonalAgent\TarkovPersonalAgentCode\config.toml"
```

The script installs the optional PySide6 desktop dependency into the project virtual environment and creates a **Tarkov Personal Agent** shortcut on the Windows desktop.

To create the shortcut in the Windows Startup folder instead:

```powershell
.\scripts\install_desktop_companion.ps1 `
  -ConfigPath "C:\TarkovPersonalAgent\TarkovPersonalAgentCode\config.toml" `
  -StartWithWindows
```

The installation can also be performed manually:

```powershell
python -m pip install -e ".[desktop]"
tarkov-agent-desktop --config config.toml
```

## Native dashboard

The main window contains:

- local service start, stop, and refresh controls;
- lifecycle state;
- active map and character;
- OBS connection and recording state;
- review queue count;
- PPE profile version;
- automatic log-rule count;
- manual Start Raid, End Raid, and Abort Raid controls;
- live marker buttons;
- links to every browser workspace;
- a local activity and error area.

The seven initial marker buttons are:

```text
PMC Heard
Player Seen
Fight Started
Route Changed
Important Loot
Mistake
Good Decision
```

Marker creation still uses the validated `/api/markers` endpoint and therefore attaches only to the current active raid.

## Embedded service ownership

The desktop application first checks whether the configured local service is already available.

- When another service instance is already running, the desktop connects to it and does not claim ownership.
- When no service is running and automatic startup is enabled, the desktop starts Uvicorn in a background thread using the existing application context.
- On exit, the desktop stops only the service instance that it started.
- A service started separately from PowerShell remains running when the desktop closes.

This prevents the GUI from killing an independently managed companion process.

## System tray

When enabled and supported by the desktop environment, closing the window hides it to the system tray instead of stopping the companion. The tray menu can:

- show the main window;
- open Raid Review;
- start the local service;
- quit the desktop application.

A deliberate **Quit** stops the embedded service only when `stop_service_on_exit` is enabled.

## Configuration

```toml
[desktop]
enabled = true
auto_start_service = true
minimize_to_tray = true
stop_service_on_exit = true
poll_interval_seconds = 2.0
request_timeout_seconds = 1.5
service_start_timeout_seconds = 15.0
```

Desktop logs are written locally under:

```text
<data_root>/desktop/desktop.log
```

Command-line overrides:

```powershell
tarkov-agent-desktop --config config.toml --no-auto-start
tarkov-agent-desktop --config config.toml --no-tray
```

## Desktop status API

The desktop uses:

```text
GET /api/desktop/status
```

The response contains:

- application version;
- lifecycle state and active raid;
- review queue count;
- automatic log-rule count;
- OBS enabled, connected, recording, paused, output, and error state;
- PPE enabled state and current profile version;
- Source of Truth, Recommendation Engine, and Media Assistance availability.

Normal raid and marker actions continue to use the established control endpoints.

## Dependency boundary

PySide6 is optional and is not installed by the standard server or development dependency set. Headless CI, the CLI, browser applications, and the local API remain usable without Qt.

The entry point reports a clear installation command when PySide6 is missing.

## Safety boundary

The Desktop Companion:

- does not read Tarkov memory;
- does not inject into the game;
- does not automate gameplay;
- does not introduce an overlay;
- uses the existing loopback API and token rules;
- preserves manual lifecycle controls;
- keeps the browser UI available for diagnostics and detailed review;
- stores logs and configuration locally.

## Exit condition

Phase 6.5 is complete when one native shortcut can start or connect to the local service, display operational status, control the manual raid lifecycle, create validated markers, open every workspace, remain in the system tray, and stop only the service process it owns.
