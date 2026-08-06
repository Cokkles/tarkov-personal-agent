from __future__ import annotations

import argparse
import logging
from pathlib import Path
from uuid import uuid4

from tarkov_agent.config import AppSettings
from tarkov_agent.desktop.client import DesktopApiClient, DesktopApiError
from tarkov_agent.domain.models import MarkerCommand, MarkerType


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tarkov-marker",
        description="Create a Tarkov Personal Agent marker without a console window",
    )
    parser.add_argument("marker_type", choices=[item.value for item in MarkerType])
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--details", default=None)
    parser.add_argument("--source", default="marker_exe")
    return parser


def _logger(settings: AppSettings) -> logging.Logger:
    settings.paths.desktop_root.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("tarkov_agent.marker_app")
    if not logger.handlers:
        handler = logging.FileHandler(
            settings.paths.desktop_root / "markers.log",
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def main() -> None:
    args = _parser().parse_args()
    config_path = Path(args.config).expanduser().resolve()
    try:
        settings = AppSettings.from_toml(config_path)
    except (OSError, ValueError) as exc:
        raise SystemExit(2) from exc

    settings.prepare()
    logger = _logger(settings)
    command = MarkerCommand(
        marker_type=MarkerType(args.marker_type),
        details=args.details,
        source=args.source,
        request_id=str(uuid4()),
    )
    try:
        DesktopApiClient(settings, timeout_seconds=3.0).add_marker(command)
    except DesktopApiError as exc:
        logger.error("Marker failed: %s (%s)", command.marker_type, exc)
        raise SystemExit(2) from exc
    logger.info("Marker created: %s", command.marker_type)


if __name__ == "__main__":
    main()
