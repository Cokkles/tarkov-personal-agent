from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from tarkov_agent.config import AppSettings
from tarkov_agent.integrations.obs import ObsIntegrationError, build_recording_controller
from tarkov_agent.observers.process import ProcessObserver
from tarkov_agent.runtime import CompanionRuntime
from tarkov_agent.services.coordinator import RaidCoordinator
from tarkov_agent.services.markers import MarkerService
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.storage.database import RaidRepository

_CONFIG_TEMPLATE = """# Tarkov Personal Agent configuration

[paths]
data_root = "~/TarkovPersonalAgent"
# Add one or more verified Tarkov log directories for your installation.
tarkov_log_roots = []

[process]
executable_names = [
  "EscapeFromTarkov.exe",
  "EscapeFromTarkov_BE.exe",
  "EscapeFromTarkovArena.exe",
]
poll_interval_seconds = 2.0

[logs]
file_globs = ["*.log", "*.txt"]
poll_interval_seconds = 1.0
start_at_end = true
minimum_auto_signal_confidence = 0.90
# No automatic rules ship enabled. Add rules only after validating them against current logs.
rules = []

[obs]
enabled = false
host = "127.0.0.1"
port = 4455
password = ""
timeout_seconds = 3.0
start_recording_on_raid_start = true
stop_recording_on_raid_end = true

[runtime]
auto_create_raid_package = true
auto_complete_raid_on_end = true
copy_evidence_into_package = false
graceful_shutdown_seconds = 10.0
"""


def _load_settings(path: str | None) -> AppSettings:
    return AppSettings.from_toml(path) if path else AppSettings()


def _build_runtime(settings: AppSettings) -> CompanionRuntime:
    settings.prepare()
    repository = RaidRepository(settings.paths.database_path)
    repository.initialize()
    packages = RaidPackageBuilder(settings.paths.raids_root)
    recording = build_recording_controller(settings.obs)
    markers = MarkerService(repository, packages)
    coordinator = RaidCoordinator(settings, repository, packages, markers, recording)
    return CompanionRuntime(settings, coordinator)


def _command_init(args: argparse.Namespace) -> int:
    path = Path(args.output).expanduser().resolve()
    if path.exists() and not args.force:
        print(f"Refusing to overwrite existing file: {path}", file=sys.stderr)
        return 2
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_CONFIG_TEMPLATE, encoding="utf-8")
    print(f"Wrote configuration template: {path}")
    return 0


def _command_doctor(args: argparse.Namespace) -> int:
    settings = _load_settings(args.config)
    settings.prepare()
    repository = RaidRepository(settings.paths.database_path)
    repository.initialize()

    process = ProcessObserver(
        settings.process.executable_names,
        settings.process.poll_interval_seconds,
    ).snapshot()
    report: dict[str, object] = {
        "data_root": str(settings.paths.data_root),
        "database_path": str(settings.paths.database_path),
        "database_initialized": settings.paths.database_path.exists(),
        "process": {
            "running": process.running,
            "executable_name": process.executable_name,
            "pid": process.pid,
        },
        "log_roots": [
            {
                "path": str(path),
                "exists": path.exists(),
                "is_directory": path.is_dir(),
            }
            for path in settings.paths.tarkov_log_roots
        ],
        "automatic_log_rules": len(settings.logs.rules),
        "obs": {"enabled": settings.obs.enabled},
    }

    if settings.obs.enabled:
        try:
            status = build_recording_controller(settings.obs).status()
            report["obs"] = {
                "enabled": True,
                "connected": status.connected,
                "recording_active": status.active,
                "recording_paused": status.paused,
            }
        except ObsIntegrationError as exc:
            report["obs"] = {"enabled": True, "connected": False, "error": str(exc)}

    print(json.dumps(report, indent=2))
    return 0


def _command_run(args: argparse.Namespace) -> int:
    settings = _load_settings(args.config)
    runtime = _build_runtime(settings)
    try:
        asyncio.run(runtime.run())
    except KeyboardInterrupt:
        print("Shutdown requested.")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tarkov-agent",
        description="Passive local raid companion for Tarkov Personal Agent",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a configuration template")
    init_parser.add_argument("--output", default="config.toml")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=_command_init)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check local configuration and integrations",
    )
    doctor_parser.add_argument("--config")
    doctor_parser.set_defaults(func=_command_doctor)

    run_parser = subparsers.add_parser("run", help="Run passive process and log observers")
    run_parser.add_argument("--config")
    run_parser.set_defaults(func=_command_run)
    return parser


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
