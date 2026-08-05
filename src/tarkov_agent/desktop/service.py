from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import uvicorn

from tarkov_agent.api.application import create_app
from tarkov_agent.app_context import build_context
from tarkov_agent.config import AppSettings
from tarkov_agent.desktop.client import DesktopApiClient

LOGGER = logging.getLogger(__name__)


class EmbeddedServiceError(RuntimeError):
    pass


class EmbeddedServiceManager:
    """Owns a loopback Uvicorn service only when the desktop app starts it."""

    def __init__(
        self,
        settings: AppSettings,
        client: DesktopApiClient,
        *,
        config_path: Path,
    ) -> None:
        self.settings = settings
        self.client = client
        self.config_path = config_path
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def owns_service(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def start(self) -> bool:
        """Start the service and return True only when this manager owns it."""
        with self._lock:
            if self.owns_service:
                return True
            if self.client.is_available():
                return False
            context = build_context(self.settings)
            app = create_app(context, start_runtime=True)
            config = uvicorn.Config(
                app,
                host=self.settings.api.host,
                port=self.settings.api.port,
                log_level="warning",
                access_log=False,
            )
            self._server = uvicorn.Server(config)
            self._thread = threading.Thread(
                target=self._run,
                name="tarkov-agent-embedded-service",
                daemon=True,
            )
            self._thread.start()

        deadline = (
            time.monotonic()
            + self.settings.desktop.service_start_timeout_seconds
        )
        while time.monotonic() < deadline:
            if self.client.is_available():
                return True
            thread = self._thread
            if thread is None or not thread.is_alive():
                break
            time.sleep(0.1)
        self.stop()
        raise EmbeddedServiceError(
            "The local agent service did not become available before the "
            "configured startup timeout."
        )

    def stop(self) -> bool:
        """Stop the service only when this manager started it."""
        with self._lock:
            server = self._server
            thread = self._thread
            if server is None or thread is None:
                return False
            server.should_exit = True
        thread.join(timeout=self.settings.runtime.graceful_shutdown_seconds + 2.0)
        if thread.is_alive():
            LOGGER.warning("Embedded service did not stop before timeout")
        with self._lock:
            self._server = None
            self._thread = None
        return True

    def _run(self) -> None:
        server = self._server
        if server is None:
            return
        try:
            server.run()
        except Exception:
            LOGGER.exception("Embedded agent service exited unexpectedly")
