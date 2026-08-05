from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from tarkov_agent.config import AppSettings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tarkov-agent-desktop",
        description="Launch the native Tarkov Personal Agent desktop companion",
    )
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--no-auto-start", action="store_true")
    parser.add_argument("--no-tray", action="store_true")
    return parser


def _configure_logging(settings: AppSettings) -> None:
    settings.paths.desktop_root.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(
                settings.paths.desktop_root / "desktop.log",
                encoding="utf-8",
            )
        ],
    )


def main() -> None:
    args = _parser().parse_args()
    config_path = Path(args.config).expanduser().resolve()
    try:
        settings = AppSettings.from_toml(config_path)
    except (OSError, ValueError) as exc:
        print(f"Unable to load desktop configuration: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    if not settings.desktop.enabled:
        print("Desktop Companion is disabled in configuration.", file=sys.stderr)
        raise SystemExit(2)
    if args.no_auto_start:
        settings.desktop.auto_start_service = False
    if args.no_tray:
        settings.desktop.minimize_to_tray = False
    settings.prepare()
    _configure_logging(settings)
    try:
        from tarkov_agent.desktop.qt_app import run_desktop
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("PySide6"):
            print(
                "PySide6 is required for the desktop application. Install "
                "the desktop extra with: python -m pip install -e \".[desktop]\"",
                file=sys.stderr,
            )
            raise SystemExit(2) from exc
        raise
    raise SystemExit(run_desktop(settings, config_path=config_path))


if __name__ == "__main__":
    main()
