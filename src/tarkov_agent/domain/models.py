from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Game(StrEnum):
    TARKOV = "tarkov"
    ARENA = "arena"


class RaidState(StrEnum):
    IDLE = "idle"
    GAME_RUNNING = "game_running"
    MATCHMAKING = "matchmaking"
    RAID_CANDIDATE = "raid_candidate"
    IN_RAID = "in_raid"
    ENDING = "ending"
    REVIEW_PENDING = "review_pending"
    COMPLETE = "complete"
    ABORTED = "aborted"


class EvidenceKind(StrEnum):
    LOG = "log"
    RECORDING = "recording"
    SCREENSHOT = "screenshot"
    MARKER = "marker"
    USER_NOTE = "user_note"
    EXPORT = "export"


class EvidenceReference(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    kind: EvidenceKind
    path: Path
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sha256: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    available: bool = True
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class TimelineEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    raid_id: UUID
    occurred_at: datetime
    raid_offset_ms: int | None = Field(default=None, ge=0)
    event_type: str
    label: str
    source: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_ids: list[UUID] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RaidRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    game: Game = Game.TARKOV
    state: RaidState = RaidState.IDLE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    ended_at: datetime | None = None
    map_name: str | None = None
    character_type: str | None = None
    result: str | None = None
    primary_objective: str | None = None
    secondary_objective: str | None = None
    data_root: Path
    evidence: list[EvidenceReference] = Field(default_factory=list)
    tags: set[str] = Field(default_factory=set)


class MarkerCommand(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    category: str = Field(default="note", min_length=1, max_length=40)
    details: str | None = Field(default=None, max_length=1000)
