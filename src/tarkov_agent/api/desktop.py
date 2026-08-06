from __future__ import annotations

from fastapi import FastAPI

from tarkov_agent import __version__
from tarkov_agent.app_context import AgentContext
from tarkov_agent.domain.desktop import DesktopObsStatus, DesktopStatus
from tarkov_agent.integrations.obs import ObsIntegrationError


def attach_desktop_routes(app: FastAPI, context: AgentContext) -> None:
    @app.get("/api/desktop/status", response_model=DesktopStatus)
    async def desktop_status() -> DesktopStatus:
        active = context.coordinator.active_raid
        profile = context.ppe.current()
        obs = DesktopObsStatus(enabled=context.settings.obs.enabled)
        if context.settings.obs.enabled:
            try:
                recording = context.recording.status()
                obs = DesktopObsStatus(
                    enabled=True,
                    connected=recording.connected,
                    recording_active=recording.active,
                    recording_paused=recording.paused,
                    output_path=recording.output_path,
                )
            except ObsIntegrationError as exc:
                obs = DesktopObsStatus(
                    enabled=True,
                    connected=False,
                    error=str(exc),
                )
        return DesktopStatus(
            version=__version__,
            lifecycle_state=context.coordinator.lifecycle.state.value,
            active_raid=active,
            review_queue_count=len(context.recovery.pending(limit=1000)),
            automatic_log_rules=len(context.settings.logs.rules),
            obs=obs,
            ppe_enabled=context.settings.ppe.enabled,
            ppe_profile_version=(profile.version if profile is not None else None),
            source_truth_enabled=context.settings.truth.enabled,
            recommendations_enabled=context.settings.recommendations.enabled,
            media_enabled=context.settings.media.enabled,
            finalization=context.finalization.latest(),
        )
