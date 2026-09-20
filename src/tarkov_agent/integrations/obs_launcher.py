from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from tarkov_agent.config import ObsSettings

LOGGER = logging.getLogger(__name__)

_DEFAULT_LOCATIONS = (
    r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    r"C:\Program Files (x86)\obs-studio\bin\64bit\obs64.exe",
    r"C:\Program Files (x86)\Steam\steamapps\common\OBS Studio\bin\64bit\obs64.exe",
)


def find_obs_executable(configured: Path | None, extra: Iterable[str] = ()) -> Path | None:
    candidates = [str(configured)] if configured else []
    candidates.extend(_DEFAULT_LOCATIONS)
    candidates.extend(extra)
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


class ObsLauncher:
    """Starts OBS hidden in the tray, reuses one that is already running, and cleans up.

    OBS must be started with its own folder as the working directory or it cannot find its
    locale files. The agent never closes an OBS it did not start itself.
    """

    def __init__(
        self,
        settings: ObsSettings,
        *,
        spawn: Callable[..., Any] = subprocess.Popen,
        port_open: Callable[[str, int], bool] = _port_open,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._spawn = spawn
        self._port_open = port_open
        self._sleep = sleep
        self._clock = clock
        self._process: Any = None

    @property
    def owns_process(self) -> bool:
        return self._process is not None

    def ensure_running(self) -> str:
        """Return one of: disabled, already_running, launched, not_found, timeout."""
        cfg = self._settings
        if not (cfg.enabled and cfg.auto_launch):
            return "disabled"
        if self._port_open(cfg.host, cfg.port):
            return "already_running"
        executable = find_obs_executable(cfg.executable)
        if executable is None:
            LOGGER.warning("OBS auto-launch: obs64.exe not found; set obs.executable in config")
            return "not_found"
        kwargs: dict[str, Any] = {"cwd": str(executable.parent)}
        if sys.platform == "win32" or os.name == "nt":
            kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_PROCESS_GROUP
        args = list(cfg.launch_args)
        if cfg.profile:
            args += ["--profile", cfg.profile]
        if cfg.scene_collection:
            args += ["--collection", cfg.scene_collection]
        self._process = self._spawn([str(executable), *args], **kwargs)
        deadline = self._clock() + cfg.launch_wait_seconds
        while self._clock() < deadline:
            if self._port_open(cfg.host, cfg.port):
                return "launched"
            self._sleep(1.0)
        LOGGER.warning(
            "OBS started but WebSocket %s:%s did not open. Enable it in OBS: "
            "Tools > WebSocket Server Settings.",
            cfg.host,
            cfg.port,
        )
        return "timeout"

    def close_if_owned(self) -> bool:
        if self._process is None or not self._settings.close_on_exit:
            return False
        try:
            self._process.terminate()
        except OSError:
            return False
        finally:
            self._process = None
        return True
