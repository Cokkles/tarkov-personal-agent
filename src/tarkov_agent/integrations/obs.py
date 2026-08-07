from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Protocol

from tarkov_agent.config import ObsSettings


class ObsIntegrationError(RuntimeError):
    """Wraps OBS SDK or connection failures behind a stable application exception."""


@dataclass(frozen=True, slots=True)
class RecordingStatus:
    connected: bool
    active: bool
    paused: bool = False
    output_path: str | None = None


class RecordingController(Protocol):
    def status(self) -> RecordingStatus: ...

    def start(self) -> RecordingStatus: ...

    def stop(self) -> RecordingStatus: ...


class NoopRecordingController:
    def status(self) -> RecordingStatus:
        return RecordingStatus(connected=False, active=False)

    def start(self) -> RecordingStatus:
        return self.status()

    def stop(self) -> RecordingStatus:
        return self.status()


class ObsRecordingController:
    """Thin synchronous adapter for OBS WebSocket v5 through obsws-python."""

    def __init__(self, settings: ObsSettings) -> None:
        self._settings = settings
        self._client: object | None = None
        self._lock = threading.RLock()

    def _get_client(self) -> object:
        with self._lock:
            if self._client is not None:
                return self._client
            try:
                import obsws_python as obs

                self._client = obs.ReqClient(
                    host=self._settings.host,
                    port=self._settings.port,
                    password=self._settings.password,
                    timeout=self._settings.timeout_seconds,
                )
            except Exception as exc:  # SDK exposes transport-specific exception types.
                self._client = None
                raise ObsIntegrationError(
                    f"Unable to connect to OBS WebSocket: {exc}"
                ) from exc
            return self._client

    @staticmethod
    def _response_bool(response: object, name: str, default: bool = False) -> bool:
        return bool(getattr(response, name, default))

    def status(self) -> RecordingStatus:
        with self._lock:
            try:
                response = self._get_client().get_record_status()  # type: ignore[attr-defined]
                return RecordingStatus(
                    connected=True,
                    active=self._response_bool(response, "output_active"),
                    paused=self._response_bool(response, "output_paused"),
                )
            except Exception as exc:
                self._client = None
                if isinstance(exc, ObsIntegrationError):
                    raise
                raise ObsIntegrationError(
                    f"Unable to read OBS recording status: {exc}"
                ) from exc

    def start(self) -> RecordingStatus:
        with self._lock:
            current = self.status()
            if current.active:
                return current
            try:
                self._get_client().start_record()  # type: ignore[attr-defined]
                return self.status()
            except Exception as exc:
                self._client = None
                if isinstance(exc, ObsIntegrationError):
                    raise
                raise ObsIntegrationError(f"Unable to start OBS recording: {exc}") from exc

    def stop(self) -> RecordingStatus:
        with self._lock:
            current = self.status()
            if not current.active:
                return current
            try:
                response = self._get_client().stop_record()  # type: ignore[attr-defined]
                output_path = getattr(response, "output_path", None)
                return RecordingStatus(
                    connected=True,
                    active=False,
                    paused=False,
                    output_path=str(output_path) if output_path else None,
                )
            except Exception as exc:
                self._client = None
                if isinstance(exc, ObsIntegrationError):
                    raise
                raise ObsIntegrationError(f"Unable to stop OBS recording: {exc}") from exc


def build_recording_controller(settings: ObsSettings) -> RecordingController:
    if not settings.enabled:
        return NoopRecordingController()
    return ObsRecordingController(settings)
