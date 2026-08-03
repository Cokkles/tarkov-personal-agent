from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EvidenceSource(StrEnum):
    SELF_REPORT = "self_report"
    RAID_REVIEW = "raid_review"
    ENCOUNTER_REVIEW = "encounter_review"
    RAID_STATISTICS = "raid_statistics"
    MANUAL_ASSESSMENT = "manual_assessment"
    EXPERIMENT = "experiment"


class EvidenceRole(StrEnum):
    PERFORMANCE = "performance"
    DECISION = "decision"
    PREFERENCE = "preference"
    CONSTRAINT = "constraint"
    OUTCOME = "outcome"


class ProfileSignalKind(StrEnum):
    STRENGTH = "strength"
    CONSTRAINT = "constraint"
    CONTEXT_DEPENDENT = "context_dependent"
    UNCERTAIN = "uncertain"


class RecommendationMode(StrEnum):
    ADAPTATION = "adaptation"
    TRAINING = "training"


class PPEContext(BaseModel):
    game: str | None = Field(default=None, max_length=40)
    map_name: str | None = Field(default=None, max_length=160)
    character_type: str | None = Field(default=None, max_length=80)
    group_size: str | None = Field(default=None, max_length=40)
    objective_priority: str | None = Field(default=None, max_length=80)
    range_band: str | None = Field(default=None, max_length=40)
    detection_order: str | None = Field(default=None, max_length=80)
    initiative_state: str | None = Field(default=None, max_length=80)
    position_state: str | None = Field(default=None, max_length=80)
    movement_state: str | None = Field(default=None, max_length=80)
    loadout_family: str | None = Field(default=None, max_length=120)
    opponent_type: str | None = Field(default=None, max_length=80)
    tags: set[str] = Field(default_factory=set)

    @staticmethod
    def normalize(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        return normalized or None

    def value_for(self, field_name: str) -> str | None:
        value = getattr(self, field_name, None)
        if not isinstance(value, str):
            return None
        return self.normalize(value)

    def segment_keys(self, fields: tuple[str, ...]) -> list[str]:
        pairs = [
            (field_name, self.value_for(field_name))
            for field_name in fields
            if self.value_for(field_name) is not None
        ]
        keys = ["global"]
        keys.extend(f"{field_name}={value}" for field_name, value in pairs)
        if len(pairs) >= 2:
            keys.append("|".join(f"{field_name}={value}" for field_name, value in pairs))
        return list(dict.fromkeys(keys))


class DimensionDefinition(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    label: str = Field(max_length=120)
    category: str = Field(max_length=80)
    description: str = Field(max_length=1000)
    positive_label: str = Field(max_length=160)
    negative_label: str = Field(max_length=160)
    context_fields: tuple[str, ...] = ()
    half_life_days: float = Field(default=90.0, gt=0.0, le=3650.0)
    minimum_evidence_weight: float = Field(default=1.0, ge=0.0, le=100.0)
    adaptation_guidance: str = Field(max_length=1000)
    training_guidance: str = Field(max_length=1000)


class DimensionImpact(BaseModel):
    dimension_key: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    value: float = Field(ge=-1.0, le=1.0)
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    role: EvidenceRole = EvidenceRole.PERFORMANCE
    rationale: str = Field(min_length=1, max_length=2000)


class PPEEvidence(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    schema_version: int = Field(default=1, ge=1)
    raid_id: UUID | None = None
    encounter_id: UUID | None = None
    source: EvidenceSource
    source_reference: str = Field(max_length=240)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reliability: float = Field(default=0.75, ge=0.0, le=1.0)
    context: PPEContext = Field(default_factory=PPEContext)
    impacts: list[DimensionImpact] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=4000)


class ProfileEstimate(BaseModel):
    dimension_key: str
    context_key: str
    score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    effective_weight: float = Field(ge=0.0)
    evidence_count: int = Field(ge=0)
    independent_raid_count: int = Field(ge=0)
    contradiction_ratio: float = Field(ge=0.0, le=1.0)
    contradictory_weight: float = Field(ge=0.0)
    last_evidence_at: datetime | None = None
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    interpretation: str


class DimensionChange(BaseModel):
    dimension_key: str
    context_key: str
    previous_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    current_score: float = Field(ge=-1.0, le=1.0)
    previous_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    current_confidence: float = Field(ge=0.0, le=1.0)


class ProfileSnapshot(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    version: int = Field(ge=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence_fingerprint: str = Field(min_length=16, max_length=128)
    evidence_count: int = Field(ge=0)
    estimates: list[ProfileEstimate] = Field(default_factory=list)
    established_strengths: list[str] = Field(default_factory=list)
    likely_constraints: list[str] = Field(default_factory=list)
    uncertain_dimensions: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)

    def estimate(self, dimension_key: str, context_key: str = "global") -> ProfileEstimate | None:
        for estimate in self.estimates:
            if estimate.dimension_key == dimension_key and estimate.context_key == context_key:
                return estimate
        return None


class ProfileAuditEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    snapshot_id: UUID
    previous_snapshot_id: UUID | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trigger: str = Field(max_length=240)
    evidence_ids: list[UUID] = Field(default_factory=list)
    changes: list[DimensionChange] = Field(default_factory=list)


class ProfileSignal(BaseModel):
    kind: ProfileSignalKind
    dimension_key: str
    label: str
    context_key: str = "global"
    score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str


class ProfileGuidance(BaseModel):
    mode: RecommendationMode
    dimension_key: str
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    guidance: str
    reason: str


class ProfileReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    snapshot_version: int
    overview: str
    signals: list[ProfileSignal] = Field(default_factory=list)
    adaptation_guidance: list[ProfileGuidance] = Field(default_factory=list)
    training_guidance: list[ProfileGuidance] = Field(default_factory=list)
    context_variations: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class ManualEvidenceRequest(BaseModel):
    observed_at: datetime | None = None
    reliability: float = Field(default=0.75, ge=0.0, le=1.0)
    context: PPEContext = Field(default_factory=PPEContext)
    impacts: list[DimensionImpact] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=4000)
    actor: str = Field(default="local-user", min_length=1, max_length=120)

    @model_validator(mode="after")
    def require_nonzero_impact(self) -> ManualEvidenceRequest:
        if all(impact.strength == 0.0 or impact.confidence == 0.0 for impact in self.impacts):
            raise ValueError("At least one impact must have non-zero strength and confidence")
        return self
