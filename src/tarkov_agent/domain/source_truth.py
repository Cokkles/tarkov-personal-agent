from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

_VERSION_COMPONENTS = 8
_VERSION_MAX = (10**9,) * _VERSION_COMPONENTS


def _version_key(value: str) -> tuple[int, ...]:
    components = [int(part) for part in re.findall(r"\d+", value)]
    if not components:
        raise ValueError(f"Patch version must contain a number: {value!r}")
    padded = (components + ([0] * _VERSION_COMPONENTS))[:_VERSION_COMPONENTS]
    return tuple(padded)


class GameScope(StrEnum):
    TARKOV = "tarkov"
    ARENA = "arena"
    BOTH = "both"

    def includes(self, requested: GameScope) -> bool:
        return self is GameScope.BOTH or requested is GameScope.BOTH or self is requested


class SourceAuthority(StrEnum):
    OFFICIAL_PUBLISHER = "official_publisher"
    OFFICIAL_WIKI = "official_wiki"
    VERIFIED_DATA = "verified_data"
    PRIMARY_TEST = "primary_test"
    COMMUNITY_REFERENCE = "community_reference"
    COMMUNITY_DISCUSSION = "community_discussion"


class SourceStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    RETIRED = "retired"


class CitationRole(StrEnum):
    SUPPORTS = "supports"
    OPPOSES = "opposes"
    CONTEXT = "context"


class ClaimKind(StrEnum):
    MECHANIC = "mechanic"
    ITEM = "item"
    QUEST = "quest"
    MAP = "map"
    PATCH = "patch"
    ECONOMY = "economy"
    STRATEGY_CONSTRAINT = "strategy_constraint"


class ClaimStatus(StrEnum):
    DRAFT = "draft"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    STALE = "stale"
    REJECTED = "rejected"


class ConflictStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class QueryResolution(StrEnum):
    VERIFIED = "verified"
    UNRESOLVED = "unresolved"
    CONFLICTED = "conflicted"
    STALE = "stale"
    NO_MATCH = "no_match"


class ReviewEntityType(StrEnum):
    SOURCE = "source"
    CLAIM = "claim"
    CONFLICT = "conflict"


class ReviewSeverity(StrEnum):
    ROUTINE = "routine"
    IMPORTANT = "important"
    BLOCKING = "blocking"


class PatchWindow(BaseModel):
    introduced_in: str | None = Field(default=None, max_length=80)
    removed_in: str | None = Field(default=None, max_length=80)
    exact_versions: set[str] = Field(default_factory=set)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_window(self) -> PatchWindow:
        if self.introduced_in is not None:
            _version_key(self.introduced_in)
        if self.removed_in is not None:
            _version_key(self.removed_in)
        for version in self.exact_versions:
            _version_key(version)
        if (
            self.introduced_in is not None
            and self.removed_in is not None
            and _version_key(self.introduced_in) >= _version_key(self.removed_in)
        ):
            raise ValueError("introduced_in must be earlier than removed_in")
        return self

    def applies_to(self, version: str) -> bool:
        if self.exact_versions:
            target = _version_key(version)
            return any(_version_key(item) == target for item in self.exact_versions)
        target = _version_key(version)
        if self.introduced_in is not None and target < _version_key(self.introduced_in):
            return False
        return not (self.removed_in is not None and target >= _version_key(self.removed_in))

    def overlaps(self, other: PatchWindow) -> bool:
        if self.exact_versions:
            return any(other.applies_to(version) for version in self.exact_versions)
        if other.exact_versions:
            return any(self.applies_to(version) for version in other.exact_versions)
        self_lower = _version_key(self.introduced_in) if self.introduced_in else (0,) * 8
        other_lower = _version_key(other.introduced_in) if other.introduced_in else (0,) * 8
        self_upper = _version_key(self.removed_in) if self.removed_in else _VERSION_MAX
        other_upper = _version_key(other.removed_in) if other.removed_in else _VERSION_MAX
        return max(self_lower, other_lower) < min(self_upper, other_upper)

    @property
    def is_unbounded(self) -> bool:
        return not self.introduced_in and not self.removed_in and not self.exact_versions

    def label(self) -> str:
        if self.exact_versions:
            return ", ".join(sorted(self.exact_versions, key=_version_key))
        if self.introduced_in and self.removed_in:
            return f">={self.introduced_in}, <{self.removed_in}"
        if self.introduced_in:
            return f">={self.introduced_in}"
        if self.removed_in:
            return f"<{self.removed_in}"
        return "all patches"


class SourceRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    schema_version: int = Field(default=1, ge=1)
    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$", max_length=120)
    name: str = Field(min_length=1, max_length=240)
    base_url: str = Field(pattern=r"^https?://", max_length=2000)
    authority: SourceAuthority
    game_scope: GameScope = GameScope.BOTH
    topics: set[str] = Field(default_factory=set)
    reliability: float = Field(default=0.75, ge=0.0, le=1.0)
    status: SourceStatus = SourceStatus.ACTIVE
    review_interval_days: int = Field(default=30, ge=1, le=3650)
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=4000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CitationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    url: str = Field(pattern=r"^https?://", max_length=2000)
    title: str = Field(min_length=1, max_length=500)
    locator: str | None = Field(default=None, max_length=500)
    role: CitationRole = CitationRole.SUPPORTS
    published_at: datetime | None = None
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_revision: str | None = Field(default=None, max_length=240)
    note: str | None = Field(default=None, max_length=2000)


class ClaimRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    schema_version: int = Field(default=1, ge=1)
    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$", max_length=180)
    statement: str = Field(min_length=1, max_length=4000)
    value: str = Field(min_length=1, max_length=2000)
    unit: str | None = Field(default=None, max_length=80)
    kind: ClaimKind = ClaimKind.MECHANIC
    game_scope: GameScope = GameScope.TARKOV
    topics: set[str] = Field(default_factory=set)
    patch_window: PatchWindow = Field(default_factory=PatchWindow)
    citations: list[CitationRecord] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.DRAFT
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    verification_score: float = Field(default=0.0, ge=0.0, le=1.0)
    review_interval_days: int = Field(default=30, ge=1, le=3650)
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=4000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def normalized_value(self) -> str:
        return re.sub(r"\s+", " ", self.value.casefold()).strip()


class ConflictRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    claim_key: str = Field(max_length=180)
    claim_ids: list[UUID] = Field(min_length=2)
    values: dict[str, str]
    patch_description: str = Field(max_length=1000)
    status: ConflictStatus = ConflictStatus.OPEN
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    resolution_note: str | None = Field(default=None, max_length=4000)


class MechanicsQuery(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$", max_length=180)
    game: GameScope = GameScope.TARKOV
    patch_version: str | None = Field(default=None, max_length=80)
    include_stale: bool = False

    @model_validator(mode="after")
    def validate_patch(self) -> MechanicsQuery:
        if self.patch_version is not None:
            _version_key(self.patch_version)
        return self


class ClaimResolution(BaseModel):
    query: MechanicsQuery
    resolution: QueryResolution
    can_recommend: bool
    reason: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    selected_claim: ClaimRecord | None = None
    candidate_claims: list[ClaimRecord] = Field(default_factory=list)
    citations: list[CitationRecord] = Field(default_factory=list)
    conflict_ids: list[UUID] = Field(default_factory=list)


class ReviewTask(BaseModel):
    entity_type: ReviewEntityType
    entity_id: UUID
    label: str = Field(max_length=500)
    due_at: datetime
    severity: ReviewSeverity
    reason: str = Field(max_length=2000)


class SourceTruthBundle(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sources: list[SourceRecord] = Field(default_factory=list)
    claims: list[ClaimRecord] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    review_queue: list[ReviewTask] = Field(default_factory=list)
