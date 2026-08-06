from __future__ import annotations

import argparse
import contextlib
import ctypes
import logging
import sys
import traceback
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


def _bootstrap_log_path() -> Path:
    return Path.home() / "TarkovPersonalAgent" / "desktop" / "bootstrap.log"


def _show_native_error(message: str) -> None:
    print(message, file=sys.stderr)
    if sys.platform != "win32":
        return
    with contextlib.suppress(Exception):
        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0,
            message,
            "Tarkov Personal Agent — Startup Error",
            0x10,
        )


def _report_startup_failure(message: str, exc: BaseException) -> None:
    log_path = _bootstrap_log_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        log_path.write_text(details, encoding="utf-8")
        suffix = f"\n\nDiagnostic details were written to:\n{log_path}"
    except OSError:
        suffix = ""
    _show_native_error(f"{message}\n\n{exc}{suffix}")


def main() -> None:
    args = _parser().parse_args()
    config_path = Path(args.config).expanduser().resolve()
    try:
        settings = AppSettings.from_toml(config_path)
    except (OSError, ValueError) as exc:
        _report_startup_failure("Unable to load the desktop configuration.", exc)
        raise SystemExit(2) from exc
    if not settings.desktop.enabled:
        _show_native_error("Desktop Companion is disabled in configuration.")
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
            _report_startup_failure(
                "PySide6 is required for the desktop application. Install the desktop "
                'extra with: python -m pip install -e ".[desktop]"',
                exc,
            )
            raise SystemExit(2) from exc
        _report_startup_failure("The desktop application could not be imported.", exc)
        raise SystemExit(2) from exc
    except Exception as exc:
        _report_startup_failure("The desktop application could not be imported.", exc)
        raise SystemExit(2) from exc

    try:
        exit_code = run_desktop(settings, config_path=config_path)
    except Exception as exc:
        _report_startup_failure("The Operations Center failed during startup.", exc)
        raise SystemExit(1) from exc
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
