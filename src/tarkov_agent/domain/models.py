from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


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
    CLIP = "clip"
    MARKER = "marker"
    USER_NOTE = "user_note"
    EXPORT = "export"


class MarkerType(StrEnum):
    PMC_HEARD = "contact.audio.possible_pmc"
    PLAYER_SEEN = "contact.visual.player"
    FIGHT_STARTED = "combat.engagement.started"
    ROUTE_CHANGED = "decision.route.changed"
    IMPORTANT_LOOT = "loot.important"
    MISTAKE = "review.mistake"
    GOOD_DECISION = "review.good_decision"


MARKER_DEFAULTS: dict[MarkerType, tuple[str, str, str]] = {
    MarkerType.PMC_HEARD: ("PMC Heard", "audio", "Possible PMC audio cue"),
    MarkerType.PLAYER_SEEN: ("Player Seen", "contact", "Visual player contact"),
    MarkerType.FIGHT_STARTED: ("Fight Started", "combat", "Committed engagement"),
    MarkerType.ROUTE_CHANGED: ("Route Changed", "decision", "Meaningful route change"),
    MarkerType.IMPORTANT_LOOT: (
        "Important Loot",
        "loot",
        "Important loot acquired or observed",
    ),
    MarkerType.MISTAKE: ("Mistake", "review", "Immediate mistake recognition"),
    MarkerType.GOOD_DECISION: (
        "Good Decision",
        "review",
        "Immediate positive decision recognition",
    ),
}


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
    """Stable marker contract shared by desktop, CLI, and Stream Deck clients.

    Legacy callers may continue supplying only ``label`` and ``category``. New
    clients should send ``marker_type`` and allow the canonical defaults below
    to populate the display text and category.
    """

    marker_type: MarkerType | None = None
    label: str = Field(default="", max_length=120)
    category: str = Field(default="", max_length=40)
    details: str | None = Field(default=None, max_length=1000)
    source: str = Field(default="user", min_length=1, max_length=80)
    request_id: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def apply_marker_defaults(self) -> MarkerCommand:
        if self.marker_type is not None:
            label, category, details = MARKER_DEFAULTS[self.marker_type]
            if not self.label.strip():
                self.label = label
            if not self.category.strip():
                self.category = category
            if self.details is None:
                self.details = details
        if not self.label.strip():
            raise ValueError("A marker requires marker_type or label")
        if not self.category.strip():
            self.category = "note"
        self.label = self.label.strip()
        self.category = self.category.strip()
        self.source = self.source.strip()
        return self
