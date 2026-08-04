from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from tarkov_agent.domain.source_truth import ClaimResolution, GameScope


class RecommendationPurpose(StrEnum):
    PROGRESSION = "progression"
    TRAINING = "training"


class RiskPosture(StrEnum):
    LOW = "low"
    BALANCED = "balanced"
    HIGH = "high"


class CandidateStatus(StrEnum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"


class MechanicRequirement(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$", max_length=180)
    rationale: str = Field(min_length=1, max_length=1000)
    required: bool = True


class RecommendationRequest(BaseModel):
    game: GameScope = GameScope.TARKOV
    patch_version: str | None = Field(default=None, max_length=80)
    objective: str = Field(min_length=1, max_length=1000)
    map_name: str | None = Field(default=None, max_length=160)
    character_type: str | None = Field(default=None, max_length=80)
    group_size: str | None = Field(default=None, max_length=40)
    purpose: RecommendationPurpose = RecommendationPurpose.PROGRESSION
    risk_posture: RiskPosture = RiskPosture.BALANCED
    mechanic_keys: list[str] = Field(default_factory=list, max_length=50)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def normalize_lists(self) -> RecommendationRequest:
        self.mechanic_keys = list(
            dict.fromkeys(
                item.strip() for item in self.mechanic_keys if item.strip()
            )
        )
        self.constraints = list(
            dict.fromkeys(
                item.strip() for item in self.constraints if item.strip()
            )
        )
        return self


class StrategyCandidate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$", max_length=160)
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=2000)
    purpose: RecommendationPurpose
    risk_level: float = Field(ge=0.0, le=1.0)
    objective_alignment: float = Field(ge=0.0, le=1.0)
    mechanic_requirements: list[MechanicRequirement] = Field(default_factory=list)
    fit_weights: dict[str, float] = Field(default_factory=dict)
    steps: list[str] = Field(min_length=1, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_fit_weights(self) -> StrategyCandidate:
        invalid = [
            key
            for key, value in self.fit_weights.items()
            if value < -1.0 or value > 1.0
        ]
        if invalid:
            raise ValueError(
                f"Fit weights must be between -1 and 1: {sorted(invalid)}"
            )
        return self


class MechanicCheck(BaseModel):
    requirement: MechanicRequirement
    resolution: ClaimResolution
    blocking: bool


class PlayerFitCheck(BaseModel):
    dimension_key: str
    context_key: str
    estimate_score: float = Field(ge=-1.0, le=1.0)
    estimate_confidence: float = Field(ge=0.0, le=1.0)
    fit_weight: float = Field(ge=-1.0, le=1.0)
    contribution: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    rationale: str


class CandidateEvaluation(BaseModel):
    candidate: StrategyCandidate
    status: CandidateStatus
    objective_score: float = Field(ge=0.0, le=1.0)
    player_fit_score: float = Field(ge=0.0, le=1.0)
    risk_fit_score: float = Field(ge=0.0, le=1.0)
    total_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    mechanic_checks: list[MechanicCheck] = Field(default_factory=list)
    player_fit_checks: list[PlayerFitCheck] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class ExperimentDesign(BaseModel):
    hypothesis: str = Field(min_length=1, max_length=1000)
    independent_variable: str = Field(min_length=1, max_length=500)
    controls: list[str] = Field(min_length=1, max_length=20)
    success_signals: list[str] = Field(min_length=1, max_length=20)
    recommended_sample_size: int = Field(default=5, ge=1, le=100)


class RecommendationPlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    schema_version: int = Field(default=1, ge=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request: RecommendationRequest
    can_recommend: bool
    profile_version: int | None = None
    primary: CandidateEvaluation | None = None
    fallback: CandidateEvaluation | None = None
    evaluated_candidates: list[CandidateEvaluation] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    research_tasks: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    experiment: ExperimentDesign | None = None
    refusal_reason: str | None = None
