from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class MediaSource(StrEnum):
    OBS = "obs"
    MANUAL = "manual"
    GENERATED = "generated"


class ProbeStatus(StrEnum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class RecordingAsset(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    raid_id: UUID
    evidence_id: UUID
    source: MediaSource
    original_path: Path
    canonical_path: Path
    indexed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    size_bytes: int = Field(ge=0)
    sha256: str
    copied_into_package: bool = False
    available: bool = True
    probe_status: ProbeStatus = ProbeStatus.UNAVAILABLE
    duration_seconds: float | None = Field(default=None, ge=0.0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    fps: float | None = Field(default=None, ge=0.0)
    video_codec: str | None = Field(default=None, max_length=80)
    audio_stream_count: int | None = Field(default=None, ge=0)
    audio_codecs: list[str] = Field(default_factory=list)
    probe_error: str | None = Field(default=None, max_length=2000)


class MediaNavigationPoint(BaseModel):
    recording_id: UUID
    timeline_event_id: UUID
    event_type: str
    label: str
    raid_offset_ms: int = Field(ge=0)
    seek_seconds: float = Field(ge=0.0)
    source: str
    category: str | None = None


class ClipRequest(BaseModel):
    timeline_event_id: UUID | None = None
    raid_offset_ms: int | None = Field(default=None, ge=0)
    seconds_before: float = Field(default=10.0, ge=0.0, le=300.0)
    seconds_after: float = Field(default=15.0, ge=0.1, le=600.0)
    label: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def require_one_anchor(self) -> ClipRequest:
        supplied = int(self.timeline_event_id is not None) + int(
            self.raid_offset_ms is not None
        )
        if supplied != 1:
            raise ValueError(
                "Supply exactly one of timeline_event_id or raid_offset_ms"
            )
        return self


class MediaClip(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    raid_id: UUID
    recording_id: UUID
    evidence_id: UUID
    path: Path
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    anchor_offset_ms: int = Field(ge=0)
    start_seconds: float = Field(ge=0.0)
    duration_seconds: float = Field(gt=0.0)
    label: str
    timeline_event_id: UUID | None = None
    available: bool = True


class RaidMediaIndex(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    raid_id: UUID
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    recordings: list[RecordingAsset] = Field(default_factory=list)
    clips: list[MediaClip] = Field(default_factory=list)
