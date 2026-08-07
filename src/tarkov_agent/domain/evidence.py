from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field

from tarkov_agent.domain.media import RecordingAsset


class EvidenceBundleProfile(StrEnum):
    METADATA = "metadata"
    STANDARD = "standard"
    DEEP = "deep"


class EvidenceBundleRequest(BaseModel):
    profile: EvidenceBundleProfile = EvidenceBundleProfile.STANDARD
    max_clips: int | None = Field(default=None, ge=0, le=50)
    max_total_bytes: int | None = Field(
        default=None,
        ge=1_000_000,
        le=5_000_000_000,
    )
    generate_missing_clips: bool | None = None


class EvidenceCandidate(BaseModel):
    timeline_event_id: UUID
    event_type: str
    label: str
    source: str
    category: str | None = None
    marker_type: str | None = None
    raid_offset_ms: int | None = Field(default=None, ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    priority: float = Field(ge=0.0, le=1.0)
    selected: bool = False
    rationale: str
    clip_id: UUID | None = None
    clip_path: Path | None = None


class EvidenceBundleFile(BaseModel):
    archive_path: str
    source_path: Path
    role: str
    size_bytes: int = Field(ge=0)
    sha256: str


class EvidenceBundleManifest(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    raid_id: UUID
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    profile: EvidenceBundleProfile
    raw_recordings_included: bool = False
    recording_references: list[RecordingAsset] = Field(default_factory=list)
    candidates: list[EvidenceCandidate] = Field(default_factory=list)
    files: list[EvidenceBundleFile] = Field(default_factory=list)
    payload_bytes: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)


class EvidenceBundleResult(BaseModel):
    manifest: EvidenceBundleManifest
    archive_path: Path
