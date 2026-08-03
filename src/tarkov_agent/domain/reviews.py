from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    FINALIZED = "finalized"


class EncounterReview(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    sequence: int = Field(default=1, ge=1)
    opponent_type: str = Field(default="unknown", max_length=80)
    location: str | None = Field(default=None, max_length=160)
    range_band: str | None = Field(default=None, max_length=40)
    detection_order: str | None = Field(default=None, max_length=80)
    posture: str | None = Field(default=None, max_length=80)
    cover_state: str | None = Field(default=None, max_length=80)
    fired_first: str | None = Field(default=None, max_length=40)
    outcome: str | None = Field(default=None, max_length=80)
    objective_progress: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=4000)
    worked: str | None = Field(default=None, max_length=2000)
    change_next_time: str | None = Field(default=None, max_length=2000)
    repositioned: bool | None = None
    repeeked_same_angle: bool | None = None
    could_disengage: bool | None = None
    video_offset_ms: int | None = Field(default=None, ge=0)


class ObjectiveReview(BaseModel):
    primary: str | None = Field(default=None, max_length=500)
    secondary: str | None = Field(default=None, max_length=500)
    primary_progress: str | None = Field(default=None, max_length=80)
    secondary_progress: str | None = Field(default=None, max_length=80)
    priority: str | None = Field(default=None, max_length=80)
    details: str | None = Field(default=None, max_length=4000)


class LoadoutReview(BaseModel):
    weapon: str | None = Field(default=None, max_length=200)
    ammunition: str | None = Field(default=None, max_length=200)
    optic_configuration: str | None = Field(default=None, max_length=300)
    armor: str | None = Field(default=None, max_length=200)
    helmet: str | None = Field(default=None, max_length=200)
    headset: str | None = Field(default=None, max_length=200)
    rig: str | None = Field(default=None, max_length=200)
    starting_weight_kg: float | None = Field(default=None, ge=0)
    first_contact_weight_kg: float | None = Field(default=None, ge=0)
    extract_weight_kg: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=4000)


class RouteReview(BaseModel):
    spawn: str | None = Field(default=None, max_length=200)
    extract: str | None = Field(default=None, max_length=200)
    planned_route: str | None = Field(default=None, max_length=4000)
    actual_route: str | None = Field(default=None, max_length=4000)
    information_received: str | None = Field(default=None, max_length=4000)
    important_choices: str | None = Field(default=None, max_length=4000)
    went_well: str | None = Field(default=None, max_length=4000)
    problems: str | None = Field(default=None, max_length=4000)


class RaidStatisticsReview(BaseModel):
    raid_time: str | None = Field(default=None, max_length=40)
    pmc_kills: int | None = Field(default=None, ge=0)
    scav_kills: int | None = Field(default=None, ge=0)
    ammo_used: int | None = Field(default=None, ge=0)
    hit_count: int | None = Field(default=None, ge=0)
    damage_to_body: int | None = Field(default=None, ge=0)
    accuracy: str | None = Field(default=None, max_length=40)
    distance_km: float | None = Field(default=None, ge=0)
    xp: int | None = Field(default=None, ge=0)
    notable_loot: str | None = Field(default=None, max_length=4000)


class AnalysisRequest(BaseModel):
    analysis_types: list[str] = Field(default_factory=list)
    question: str | None = Field(default=None, max_length=4000)
    additional_notes: str | None = Field(default=None, max_length=4000)


class RaidReview(BaseModel):
    raid_id: UUID
    version: int = Field(default=0, ge=0)
    status: ReviewStatus = ReviewStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finalized_at: datetime | None = None
    map_name: str | None = Field(default=None, max_length=160)
    character_type: str | None = Field(default=None, max_length=80)
    result: str | None = Field(default=None, max_length=80)
    time_of_day: str | None = Field(default=None, max_length=40)
    group_size: str | None = Field(default=None, max_length=40)
    patch: str | None = Field(default=None, max_length=80)
    objectives: ObjectiveReview = Field(default_factory=ObjectiveReview)
    loadout: LoadoutReview = Field(default_factory=LoadoutReview)
    route: RouteReview = Field(default_factory=RouteReview)
    encounters: list[EncounterReview] = Field(default_factory=list)
    statistics: RaidStatisticsReview = Field(default_factory=RaidStatisticsReview)
    analysis_request: AnalysisRequest = Field(default_factory=AnalysisRequest)
    media_notes: str | None = Field(default=None, max_length=4000)
    additional_notes: str | None = Field(default=None, max_length=8000)


class ReviewAuditEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    raid_id: UUID
    version: int = Field(ge=0)
    action: str = Field(max_length=80)
    actor: str = Field(default="local-user", max_length=120)
    changed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    changed_fields: list[str] = Field(default_factory=list)
    snapshot: RaidReview
