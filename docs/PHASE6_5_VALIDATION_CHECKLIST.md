# Phase 6.5 Validation Checklist

- Ruff passes without new exclusions.
- Strict mypy passes for all `tarkov_agent` modules.
- Pytest passes on Windows and Ubuntu with Python 3.12.
- Standard development installation remains headless and does not require PySide6.
- The desktop extra installs PySide6 and creates the `tarkov-agent-desktop` entry point.
- A missing PySide6 installation produces a clear actionable error.
- The desktop status endpoint reports lifecycle, active raid, queue, OBS, PPE, Truth, Recommendation, and Media state.
- The desktop starts an embedded service when none is available.
- The desktop connects without ownership when an independent service is already running.
- Quit stops only the embedded service owned by the desktop session.
- Start Raid, End Raid, Abort Raid, and marker actions use the existing local API.
- The seven validated marker buttons are available only during an active raid.
- Browser workspaces open through the configured local service URL.
- The system tray can restore and deliberately quit the desktop application.
- The shortcut script points to the project virtual-environment launcher and configured TOML file.
- Desktop logs remain under the local data root.
- No game-memory access, injection, gameplay automation, or overlay is introduced.
