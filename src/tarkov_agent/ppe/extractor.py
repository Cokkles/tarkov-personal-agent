from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from tarkov_agent.domain.models import RaidRecord
from tarkov_agent.domain.ppe import (
    DimensionImpact,
    EvidenceRole,
    EvidenceSource,
    PPEContext,
    PPEEvidence,
)
from tarkov_agent.domain.reviews import EncounterReview, RaidReview, ReviewStatus
from tarkov_agent.ppe.registry import DimensionRegistry

_POSITIVE_OUTCOME = (
    "clean win",
    "costly win",
    "won",
    "win",
    "opponent killed",
    "killed",
    "kill",
    "survived fight",
)
_NEGATIVE_OUTCOME = (
    "execution loss",
    "information loss",
    "positional loss",
    "strategic loss",
    "killed by",
    "lost",
    "loss",
    "died",
    "death",
)
_DISENGAGE_OUTCOME = ("disengaged", "disengage", "withdrew", "escaped", "reset")
_PLAYER_FIRST = ("player first", "i detected", "saw first", "heard first", "me first")
_ENEMY_FIRST = ("enemy first", "opponent first", "they detected", "ambushed", "surprised")
_MUTUAL = ("mutual", "both", "simultaneous")
_CLOSE_RANGE = ("close", "cqb", "point blank", "short")
_TRUE_VALUES = {"yes", "true", "player", "me", "i did", "player first"}
_PROGRESS_POSITIVE = (
    "complete",
    "completed",
    "success",
    "found",
    "obtained",
    "extracted",
    "advanced",
    "progress",
    "done",
)
_PROGRESS_NEGATIVE = ("failed", "none", "no progress", "abandoned", "lost")


def _normalize(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").casefold()).strip()


def _contains(value: str | None, terms: tuple[str, ...]) -> bool:
    normalized = _normalize(value)
    return any(term in normalized for term in terms)


def _is_true(value: str | None) -> bool:
    return _normalize(value) in _TRUE_VALUES


def _progress_direction(value: str | None) -> int:
    normalized = _normalize(value)
    if any(term in normalized for term in _PROGRESS_NEGATIVE):
        return -1
    if any(term in normalized for term in _PROGRESS_POSITIVE):
        return 1
    return 0


def _evidence_id(raid_id: UUID, source_reference: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"tarkov-personal-agent:{raid_id}:{source_reference}")


def _impact(
    dimension_key: str,
    value: float,
    rationale: str,
    *,
    strength: float,
    confidence: float,
    role: EvidenceRole = EvidenceRole.PERFORMANCE,
) -> DimensionImpact:
    return DimensionImpact(
        dimension_key=dimension_key,
        value=value,
        strength=strength,
        confidence=confidence,
        role=role,
        rationale=rationale,
    )


class ReviewEvidenceExtractor:
    """Derive conservative evidence from structured finalized review fields.

    Narrative fields remain available to a human reviewer but are not interpreted as skill
    evidence. Ambiguous prose therefore cannot silently create confident profile changes.
    """

    def __init__(self, registry: DimensionRegistry) -> None:
        self._registry = registry

    def extract(self, raid: RaidRecord, review: RaidReview) -> list[PPEEvidence]:
        if review.status is not ReviewStatus.FINALIZED:
            raise ValueError("PPE evidence can only be extracted from a finalized review")
        observed_at = raid.ended_at or review.finalized_at or review.updated_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        evidence: list[PPEEvidence] = []
        raid_evidence = self._raid_evidence(raid, review, observed_at)
        if raid_evidence is not None:
            evidence.append(raid_evidence)
        for encounter in review.encounters:
            encounter_evidence = self._encounter_evidence(
                raid,
                review,
                encounter,
                observed_at,
            )
            if encounter_evidence is not None:
                evidence.append(encounter_evidence)
        return evidence

    def _raid_evidence(
        self,
        raid: RaidRecord,
        review: RaidReview,
        observed_at: datetime,
    ) -> PPEEvidence | None:
        impacts: list[DimensionImpact] = []
        for label, progress in (
            ("primary", review.objectives.primary_progress),
            ("secondary", review.objectives.secondary_progress),
        ):
            direction = _progress_direction(progress)
            if direction > 0:
                impacts.append(
                    _impact(
                        "objective_discipline",
                        0.75 if label == "primary" else 0.45,
                        (
                            f"The structured {label} objective progress field indicates "
                            "progress or completion."
                        ),
                        strength=0.70 if label == "primary" else 0.45,
                        confidence=0.80,
                        role=EvidenceRole.DECISION,
                    )
                )
            elif direction < 0:
                impacts.append(
                    _impact(
                        "objective_discipline",
                        -0.55 if label == "primary" else -0.25,
                        (
                            f"The structured {label} objective progress field indicates "
                            "failure or abandonment."
                        ),
                        strength=0.60 if label == "primary" else 0.35,
                        confidence=0.70,
                        role=EvidenceRole.DECISION,
                    )
                )

        result = _normalize(review.result or raid.result)
        if any(term in result for term in ("survived", "extracted")):
            impacts.append(
                _impact(
                    "risk_management",
                    0.20,
                    (
                        "The raid ended in survival or extraction; outcome-only evidence "
                        "is deliberately low weight."
                    ),
                    strength=0.30,
                    confidence=0.55,
                    role=EvidenceRole.OUTCOME,
                )
            )
        elif any(term in result for term in ("killed", "dead", "death", "mia")):
            impacts.append(
                _impact(
                    "risk_management",
                    -0.18,
                    (
                        "The raid ended without survival; outcome-only evidence is "
                        "deliberately low weight."
                    ),
                    strength=0.25,
                    confidence=0.45,
                    role=EvidenceRole.OUTCOME,
                )
            )

        if not impacts:
            return None
        self._validate_impacts(impacts)
        source_reference = f"raid-review:{review.version}"
        return PPEEvidence(
            id=_evidence_id(raid.id, source_reference),
            raid_id=raid.id,
            source=EvidenceSource.RAID_REVIEW,
            source_reference=source_reference,
            observed_at=observed_at,
            reliability=0.70,
            context=self._raid_context(raid, review),
            impacts=impacts,
            notes="Automatically derived only from explicit structured raid fields.",
        )

    def _encounter_evidence(
        self,
        raid: RaidRecord,
        review: RaidReview,
        encounter: EncounterReview,
        observed_at: datetime,
    ) -> PPEEvidence | None:
        impacts: list[DimensionImpact] = []
        outcome = _normalize(encounter.outcome)
        negative = any(term in outcome for term in _NEGATIVE_OUTCOME)
        positive = not negative and any(term in outcome for term in _POSITIVE_OUTCOME)
        disengaged = any(term in outcome for term in _DISENGAGE_OUTCOME)
        close_range = _contains(encounter.range_band, _CLOSE_RANGE)
        player_first = _contains(encounter.detection_order, _PLAYER_FIRST)
        enemy_first = _contains(encounter.detection_order, _ENEMY_FIRST)
        mutual = _contains(encounter.detection_order, _MUTUAL)

        if positive:
            impacts.append(
                _impact(
                    "execution_decisiveness",
                    0.55,
                    "The structured encounter outcome records a win.",
                    strength=0.55,
                    confidence=0.75,
                )
            )
        elif negative:
            impacts.append(
                _impact(
                    "execution_decisiveness",
                    -0.45,
                    "The structured encounter outcome records a loss.",
                    strength=0.50,
                    confidence=0.70,
                )
            )

        unprepared_close = mutual or (not player_first and not enemy_first)
        if close_range and unprepared_close and (positive or negative):
            impacts.append(
                _impact(
                    "reactive_close_range_effectiveness",
                    0.75 if positive else -0.75,
                    (
                        "The outcome occurred in a mutually detected or non-prepared "
                        "close-range fight."
                    ),
                    strength=0.80,
                    confidence=0.85,
                )
            )

        if player_first and (positive or negative):
            impacts.append(
                _impact(
                    "prepared_engagement_effectiveness",
                    0.65 if positive else -0.60,
                    (
                        "The player detected first, creating a prepared-engagement "
                        "opportunity."
                    ),
                    strength=0.65,
                    confidence=0.80,
                )
            )
        elif enemy_first and (positive or negative):
            impacts.append(
                _impact(
                    "pressure_stability",
                    0.55 if positive else -0.55,
                    (
                        "The opponent detected first, providing limited evidence about "
                        "response under pressure."
                    ),
                    strength=0.55,
                    confidence=0.70,
                )
            )

        if _is_true(encounter.fired_first) and (positive or negative):
            impacts.append(
                _impact(
                    "first_shot_execution",
                    0.65 if positive else -0.55,
                    (
                        "The player fired first; the outcome indicates whether the opening "
                        "was converted."
                    ),
                    strength=0.60,
                    confidence=0.75,
                )
            )

        if encounter.repositioned is True:
            impacts.append(
                _impact(
                    "repositioning",
                    0.65,
                    "The encounter explicitly records a reposition.",
                    strength=0.65,
                    confidence=0.90,
                    role=EvidenceRole.DECISION,
                )
            )
        elif encounter.repositioned is False and negative:
            impacts.append(
                _impact(
                    "repositioning",
                    -0.35,
                    "The player remained static during a negative encounter.",
                    strength=0.40,
                    confidence=0.60,
                    role=EvidenceRole.DECISION,
                )
            )

        if encounter.repeeked_same_angle is True:
            impacts.append(
                _impact(
                    "angle_discipline",
                    -0.85,
                    "The encounter explicitly records a same-angle re-peek.",
                    strength=0.85,
                    confidence=0.95,
                    role=EvidenceRole.DECISION,
                )
            )
        elif encounter.repeeked_same_angle is False and positive:
            impacts.append(
                _impact(
                    "angle_discipline",
                    0.25,
                    (
                        "The encounter records that the player did not repeat the same "
                        "angle during a win."
                    ),
                    strength=0.30,
                    confidence=0.60,
                    role=EvidenceRole.DECISION,
                )
            )

        if encounter.could_disengage is True and negative:
            impacts.append(
                _impact(
                    "overcommitment_control",
                    -0.75,
                    (
                        "Disengagement was available, but the encounter still ended "
                        "negatively."
                    ),
                    strength=0.75,
                    confidence=0.85,
                    role=EvidenceRole.DECISION,
                )
            )
            impacts.append(
                _impact(
                    "fight_selection",
                    -0.40,
                    "An available disengagement was not used before a negative outcome.",
                    strength=0.45,
                    confidence=0.65,
                    role=EvidenceRole.DECISION,
                )
            )
        elif disengaged:
            impacts.append(
                _impact(
                    "disengagement",
                    0.80,
                    "The structured outcome records a successful disengagement or reset.",
                    strength=0.80,
                    confidence=0.90,
                    role=EvidenceRole.DECISION,
                )
            )

        cover = _normalize(encounter.cover_state)
        if positive and any(term in cover for term in ("hard cover", "cover", "concealment")):
            impacts.append(
                _impact(
                    "cover_utilization",
                    0.35,
                    "The encounter records cover use during a positive outcome.",
                    strength=0.35,
                    confidence=0.60,
                    role=EvidenceRole.DECISION,
                )
            )
        elif negative and any(term in cover for term in ("none", "open", "no cover")):
            impacts.append(
                _impact(
                    "cover_utilization",
                    -0.45,
                    "The encounter records insufficient cover during a negative outcome.",
                    strength=0.45,
                    confidence=0.70,
                    role=EvidenceRole.DECISION,
                )
            )

        objective_direction = _progress_direction(encounter.objective_progress)
        if objective_direction > 0:
            impacts.append(
                _impact(
                    "objective_discipline",
                    0.30,
                    "The encounter explicitly advanced the raid objective.",
                    strength=0.35,
                    confidence=0.65,
                    role=EvidenceRole.DECISION,
                )
            )
        elif objective_direction < 0:
            impacts.append(
                _impact(
                    "objective_discipline",
                    -0.30,
                    "The encounter explicitly harmed objective progress.",
                    strength=0.35,
                    confidence=0.65,
                    role=EvidenceRole.DECISION,
                )
            )

        if not impacts:
            return None
        self._validate_impacts(impacts)
        source_reference = f"encounter:{encounter.id}"
        return PPEEvidence(
            id=_evidence_id(raid.id, source_reference),
            raid_id=raid.id,
            encounter_id=encounter.id,
            source=EvidenceSource.ENCOUNTER_REVIEW,
            source_reference=source_reference,
            observed_at=observed_at,
            reliability=0.88,
            context=PPEContext(
                game=raid.game.value,
                map_name=review.map_name or raid.map_name,
                character_type=review.character_type or raid.character_type,
                group_size=review.group_size,
                objective_priority=review.objectives.priority,
                range_band=encounter.range_band,
                detection_order=encounter.detection_order,
                position_state=encounter.cover_state,
                opponent_type=encounter.opponent_type,
            ),
            impacts=impacts,
            notes="Automatically derived only from explicit structured encounter fields.",
        )

    @staticmethod
    def _raid_context(raid: RaidRecord, review: RaidReview) -> PPEContext:
        return PPEContext(
            game=raid.game.value,
            map_name=review.map_name or raid.map_name,
            character_type=review.character_type or raid.character_type,
            group_size=review.group_size,
            objective_priority=review.objectives.priority,
            loadout_family=review.loadout.weapon,
        )

    def _validate_impacts(self, impacts: list[DimensionImpact]) -> None:
        unknown = [
            impact.dimension_key
            for impact in impacts
            if not self._registry.contains(impact.dimension_key)
        ]
        if unknown:
            raise ValueError(f"Extractor produced unknown dimensions: {sorted(set(unknown))}")
