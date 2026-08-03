from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

from tarkov_agent.api.app import create_app
from tarkov_agent.app_context import AgentContext, build_context
from tarkov_agent.config import AppSettings
from tarkov_agent.integrations.obs import ObsIntegrationError, build_recording_controller
from tarkov_agent.observers.logs import LogTailObserver
from tarkov_agent.observers.process import ProcessObserver
from tarkov_agent.services.diagnostics import DiagnosticCaptureService

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
# No automatic rules ship enabled. Add rules only after validating current logs.
rules = []

[obs]
enabled = false
host = "127.0.0.1"
port = 4455
password = ""
timeout_seconds = 3.0
start_recording_on_raid_start = true
stop_recording_on_raid_end = true

[api]
enabled = true
host = "127.0.0.1"
port = 8765
token = ""
open_browser = true
# Files outside data_root can only be referenced when their parent is listed here.
allowed_evidence_roots = []

[diagnostics]
default_capture_seconds = 120.0
maximum_lines = 10000

[runtime]
auto_create_raid_package = true
auto_complete_raid_on_end = false
copy_evidence_into_package = false
recover_interrupted_sessions = true
graceful_shutdown_seconds = 10.0
"""


def _load_settings(path: str | None) -> AppSettings:
    return AppSettings.from_toml(path) if path else AppSettings()


def _context(path: str | None) -> AgentContext:
    return build_context(_load_settings(path))


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
    context = build_context(settings)
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
        "review_queue_count": len(context.recovery.pending(limit=1000)),
        "api": {
            "enabled": settings.api.enabled,
            "host": settings.api.host,
            "port": settings.api.port,
            "token_required": bool(settings.api.token),
        },
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
    context = _context(args.config)
    context.recover_interrupted_session()
    try:
        asyncio.run(context.runtime.run())
    except KeyboardInterrupt:
        print("Shutdown requested.")
    return 0


def _command_serve(args: argparse.Namespace) -> int:
    context = _context(args.config)
    settings = context.settings
    host = args.host or settings.api.host
    port = args.port or settings.api.port
    if settings.api.open_browser and not args.no_browser:
        url = f"http://{host}:{port}/"
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(
        create_app(context, start_runtime=not args.api_only),
        host=host,
        port=port,
        log_level="debug" if args.verbose else "info",
    )
    return 0


def _command_capture_logs(args: argparse.Namespace) -> int:
    settings = _load_settings(args.config)
    settings.prepare()
    if not settings.paths.tarkov_log_roots:
        print("No paths.tarkov_log_roots are configured.", file=sys.stderr)
        return 2
    observer = LogTailObserver(
        settings.paths.tarkov_log_roots,
        settings.logs.file_globs,
        start_at_end=True,
        poll_interval_seconds=settings.logs.poll_interval_seconds,
    )
    service = DiagnosticCaptureService(settings.paths.diagnostics_root)
    seconds = args.seconds or settings.diagnostics.default_capture_seconds
    result = asyncio.run(
        service.capture(
            observer,
            duration_seconds=seconds,
            label=args.label,
            maximum_lines=settings.diagnostics.maximum_lines,
        )
    )
    print(f"Captured {result.line_count} redacted lines in {result.folder}")
    print("Review the files manually before sharing or committing them.")
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

    serve_parser = subparsers.add_parser(
        "serve",
        help="Run the companion with the local raid-review web application",
    )
    serve_parser.add_argument("--config")
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)
    serve_parser.add_argument("--no-browser", action="store_true")
    serve_parser.add_argument("--api-only", action="store_true")
    serve_parser.set_defaults(func=_command_serve)

    capture_parser = subparsers.add_parser(
        "capture-logs",
        help="Capture a short, redacted diagnostic sample from configured log folders",
    )
    capture_parser.add_argument("--config")
    capture_parser.add_argument("--seconds", type=float)
    capture_parser.add_argument("--label", default="log-capture")
    capture_parser.set_defaults(func=_command_capture_logs)
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
