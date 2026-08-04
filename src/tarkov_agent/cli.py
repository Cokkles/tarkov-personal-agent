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

from tarkov_agent.api.application import create_app
from tarkov_agent.app_context import AgentContext, build_context
from tarkov_agent.config import AppSettings
from tarkov_agent.domain.recommendations import (
    RecommendationPurpose,
    RecommendationRequest,
    RiskPosture,
)
from tarkov_agent.domain.source_truth import GameScope, MechanicsQuery
from tarkov_agent.integrations.obs import ObsIntegrationError, build_recording_controller
from tarkov_agent.observers.logs import LogTailObserver
from tarkov_agent.observers.process import ProcessObserver
from tarkov_agent.services.diagnostics import DiagnosticCaptureService
from tarkov_agent.services.ppe import PPEDisabledError
from tarkov_agent.services.recommendations import (
    RecommendationDisabledError,
    recommendation_to_markdown,
)
from tarkov_agent.services.source_truth import SourceTruthDisabledError

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

[ppe]
enabled = true
neutral_prior_weight = 1.25
confidence_weight_scale = 2.5
maximum_weight_per_raid_dimension = 1.0
minimum_report_confidence = 0.25
minimum_established_confidence = 0.50
signal_threshold = 0.20
context_difference_threshold = 0.35
minimum_independent_raids = 3
maximum_history = 200

[truth]
enabled = true
seed_default_sources = true
minimum_verification_score = 0.72
minimum_supporting_citations = 1
claim_review_interval_days = 30
source_review_interval_days = 30
stale_grace_days = 14

[recommendations]
enabled = true
minimum_plan_confidence = 0.40
maximum_history = 200

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
    profile = context.ppe.current()
    latest_plan = context.recommendations.latest()
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
        "ppe": {
            "enabled": settings.ppe.enabled,
            "profile_version": profile.version if profile is not None else None,
            "evidence_count": len(context.ppe.evidence(limit=10000)),
            "profile_root": str(settings.paths.ppe_root),
        },
        "source_truth": context.truth.status(),
        "recommendations": {
            "enabled": settings.recommendations.enabled,
            "latest_plan_id": str(latest_plan.id) if latest_plan is not None else None,
            "latest_can_recommend": (
                latest_plan.can_recommend if latest_plan is not None else None
            ),
            "output_root": str(settings.paths.recommendations_root),
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


def _command_ppe_rebuild(args: argparse.Namespace) -> int:
    context = _context(args.config)
    try:
        result = context.ppe.rebuild(
            trigger="cli-force-rebuild" if args.force else "cli-rebuild",
            force=args.force,
        )
    except PPEDisabledError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    snapshot = result.snapshot
    print(
        json.dumps(
            {
                "profile_version": snapshot.version,
                "evidence_count": snapshot.evidence_count,
                "estimate_count": len(snapshot.estimates),
                "established_strengths": snapshot.established_strengths,
                "likely_constraints": snapshot.likely_constraints,
                "report_path": str(context.settings.paths.ppe_root / "profile-report.md"),
            },
            indent=2,
        )
    )
    return 0


def _command_truth_status(args: argparse.Namespace) -> int:
    context = _context(args.config)
    print(json.dumps(context.truth.status(), indent=2))
    return 0


def _command_truth_query(args: argparse.Namespace) -> int:
    context = _context(args.config)
    try:
        result = context.truth.query(
            MechanicsQuery(
                key=args.key,
                game=GameScope(args.game),
                patch_version=args.patch,
                include_stale=args.include_stale,
            )
        )
    except SourceTruthDisabledError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(result.model_dump_json(indent=2))
    return 0 if result.can_recommend else 3


def _command_truth_review_queue(args: argparse.Namespace) -> int:
    context = _context(args.config)
    tasks = context.truth.review_queue()
    print(json.dumps([task.model_dump(mode="json") for task in tasks], indent=2))
    return 0


def _command_truth_export(args: argparse.Namespace) -> int:
    context = _context(args.config)
    try:
        content = (
            context.truth.export_markdown()
            if args.format == "markdown"
            else context.truth.export_json()
        )
    except SourceTruthDisabledError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"Wrote Source-of-Truth export: {output}")
    else:
        print(content, end="" if content.endswith("\n") else "\n")
    return 0


def _command_recommend(args: argparse.Namespace) -> int:
    context = _context(args.config)
    request = RecommendationRequest(
        game=GameScope(args.game),
        patch_version=args.patch,
        objective=args.objective,
        map_name=args.map,
        character_type=args.character,
        group_size=args.group_size,
        purpose=RecommendationPurpose(args.purpose),
        risk_posture=RiskPosture(args.risk),
        mechanic_keys=args.mechanic,
        constraints=args.constraint,
        notes=args.notes,
    )
    try:
        plan = context.recommendations.generate(request)
    except RecommendationDisabledError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    content = (
        recommendation_to_markdown(plan)
        if args.format == "markdown"
        else plan.model_dump_json(indent=2)
    )
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"Wrote recommendation plan: {output}")
    else:
        print(content, end="" if content.endswith("\n") else "\n")
    return 0 if plan.can_recommend else 3


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

    ppe_parser = subparsers.add_parser(
        "ppe-rebuild",
        help="Recalculate the Personal Playstyle Engine profile from stored evidence",
    )
    ppe_parser.add_argument("--config")
    ppe_parser.add_argument("--force", action="store_true")
    ppe_parser.set_defaults(func=_command_ppe_rebuild)

    truth_status_parser = subparsers.add_parser(
        "truth-status",
        help="Show Source-of-Truth source, claim, conflict, and review counts",
    )
    truth_status_parser.add_argument("--config")
    truth_status_parser.set_defaults(func=_command_truth_status)

    truth_query_parser = subparsers.add_parser(
        "truth-query",
        help="Resolve a mechanics claim and refuse unresolved or conflicting values",
    )
    truth_query_parser.add_argument("key")
    truth_query_parser.add_argument(
        "--game",
        choices=[scope.value for scope in GameScope],
        default=GameScope.TARKOV.value,
    )
    truth_query_parser.add_argument("--patch")
    truth_query_parser.add_argument("--include-stale", action="store_true")
    truth_query_parser.add_argument("--config")
    truth_query_parser.set_defaults(func=_command_truth_query)

    truth_queue_parser = subparsers.add_parser(
        "truth-review-queue",
        help="List due source reviews, claim reviews, and blocking conflicts",
    )
    truth_queue_parser.add_argument("--config")
    truth_queue_parser.set_defaults(func=_command_truth_review_queue)

    truth_export_parser = subparsers.add_parser(
        "truth-export",
        help="Export the Source-of-Truth corpus with preserved citations",
    )
    truth_export_parser.add_argument("--config")
    truth_export_parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
    )
    truth_export_parser.add_argument("--output")
    truth_export_parser.set_defaults(func=_command_truth_export)

    recommendation_parser = subparsers.add_parser(
        "recommend",
        help="Generate a traceable primary and fallback plan",
    )
    recommendation_parser.add_argument("objective")
    recommendation_parser.add_argument(
        "--game",
        choices=[scope.value for scope in GameScope],
        default=GameScope.TARKOV.value,
    )
    recommendation_parser.add_argument("--patch")
    recommendation_parser.add_argument("--map")
    recommendation_parser.add_argument("--character", default="PMC")
    recommendation_parser.add_argument("--group-size")
    recommendation_parser.add_argument(
        "--purpose",
        choices=[item.value for item in RecommendationPurpose],
        default=RecommendationPurpose.PROGRESSION.value,
    )
    recommendation_parser.add_argument(
        "--risk",
        choices=[item.value for item in RiskPosture],
        default=RiskPosture.BALANCED.value,
    )
    recommendation_parser.add_argument("--mechanic", action="append", default=[])
    recommendation_parser.add_argument("--constraint", action="append", default=[])
    recommendation_parser.add_argument("--notes")
    recommendation_parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
    )
    recommendation_parser.add_argument("--output")
    recommendation_parser.add_argument("--config")
    recommendation_parser.set_defaults(func=_command_recommend)
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
