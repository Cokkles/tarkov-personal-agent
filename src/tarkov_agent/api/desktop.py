from __future__ import annotations

import threading
import time

from fastapi import FastAPI

from tarkov_agent import __version__
from tarkov_agent.app_context import AgentContext
from tarkov_agent.domain.desktop import DesktopObsStatus, DesktopStatus
from tarkov_agent.integrations.obs import ObsIntegrationError


class _DesktopObsStatusMonitor:
    """Keep external OBS I/O off the desktop status request path.

    OBS uses a synchronous WebSocket client and may wait for its own transport
    timeout when OBS is closed or unavailable. The desktop polls status more
    frequently and with a shorter HTTP timeout, so probing OBS inline can make
    a healthy local agent look offline. This monitor maintains a last-known
    snapshot and refreshes it on one daemon thread without blocking the API.
    """

    def __init__(self, context: AgentContext) -> None:
        self._context = context
        self._lock = threading.Lock()
        self._probe_running = False
        self._last_probe_started = 0.0
        self._minimum_interval = max(
            1.0,
            context.settings.desktop.poll_interval_seconds,
        )
        self._snapshot = DesktopObsStatus(enabled=context.settings.obs.enabled)

    def snapshot(self) -> DesktopObsStatus:
        if not self._context.settings.obs.enabled:
            return DesktopObsStatus(enabled=False)

        should_start = False
        with self._lock:
            now = time.monotonic()
            if (
                not self._probe_running
                and now - self._last_probe_started >= self._minimum_interval
            ):
                self._probe_running = True
                self._last_probe_started = now
                should_start = True
            snapshot = self._snapshot.model_copy(deep=True)

        if should_start:
            threading.Thread(
                target=self._probe,
                name="desktop-obs-status-probe",
                daemon=True,
            ).start()
        return snapshot

    def _probe(self) -> None:
        try:
            recording = self._context.recording.status()
            snapshot = DesktopObsStatus(
                enabled=True,
                connected=recording.connected,
                recording_active=recording.active,
                recording_paused=recording.paused,
                output_path=recording.output_path,
            )
        except ObsIntegrationError as exc:
            snapshot = DesktopObsStatus(
                enabled=True,
                connected=False,
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover - defensive integration boundary
            snapshot = DesktopObsStatus(
                enabled=True,
                connected=False,
                error=f"Unexpected OBS status error: {exc}",
            )
        finally:
            with self._lock:
                if "snapshot" in locals():
                    self._snapshot = snapshot
                self._probe_running = False


def attach_desktop_routes(app: FastAPI, context: AgentContext) -> None:
    obs_monitor = _DesktopObsStatusMonitor(context)

    @app.get("/api/desktop/status", response_model=DesktopStatus)
    async def desktop_status() -> DesktopStatus:
        active = context.coordinator.active_raid
        profile = context.ppe.current()
        return DesktopStatus(
            version=__version__,
            lifecycle_state=context.coordinator.lifecycle.state.value,
            active_raid=active,
            review_queue_count=len(context.recovery.pending(limit=1000)),
            automatic_log_rules=len(context.settings.logs.rules),
            obs=obs_monitor.snapshot(),
            ppe_enabled=context.settings.ppe.enabled,
            ppe_profile_version=(profile.version if profile is not None else None),
            source_truth_enabled=context.settings.truth.enabled,
            recommendations_enabled=context.settings.recommendations.enabled,
            media_enabled=context.settings.media.enabled,
            finalization=context.finalization.latest(),
        )
