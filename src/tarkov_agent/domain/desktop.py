from __future__ import annotations

from pydantic import BaseModel

from tarkov_agent.domain.models import RaidRecord


class DesktopObsStatus(BaseModel):
    enabled: bool
    connected: bool = False
    recording_active: bool = False
    recording_paused: bool = False
    output_path: str | None = None
    error: str | None = None


class DesktopStatus(BaseModel):
    version: str
    lifecycle_state: str
    active_raid: RaidRecord | None = None
    review_queue_count: int
    automatic_log_rules: int
    obs: DesktopObsStatus
    ppe_enabled: bool
    ppe_profile_version: int | None = None
    source_truth_enabled: bool
    recommendations_enabled: bool
    media_enabled: bool
