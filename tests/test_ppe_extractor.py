from datetime import UTC, datetime
from pathlib import Path

import pytest

from tarkov_agent.domain.models import RaidRecord
from tarkov_agent.domain.reviews import EncounterReview, RaidReview, ReviewStatus
from tarkov_agent.ppe.extractor import ReviewEvidenceExtractor
from tarkov_agent.ppe.registry import DEFAULT_DIMENSION_REGISTRY


def _raid(tmp_path: Path) -> RaidRecord:
    now = datetime.now(UTC)
    return RaidRecord(
        data_root=tmp_path,
        map_name="Factory",
        character_type="PMC",
        started_at=now,
        ended_at=now,
        result="Killed",
    )


def _extract(raid: RaidRecord, review: RaidReview) -> list[object]:
    return list(ReviewEvidenceExtractor(DEFAULT_DIMENSION_REGISTRY).extract(raid, review))


def test_close_mutual_loss_produces_specific_negative_evidence(tmp_path: Path) -> None:
    raid = _raid(tmp_path)
    review = RaidReview(
        raid_id=raid.id,
        status=ReviewStatus.FINALIZED,
        finalized_at=datetime.now(UTC),
        result="Killed",
        map_name="Factory",
        encounters=[
            EncounterReview(
                sequence=1,
                range_band="close",
                detection_order="mutual",
                fired_first="yes",
                outcome="execution loss",
                repositioned=False,
                repeeked_same_angle=True,
                could_disengage=True,
            )
        ],
    )

    evidence = ReviewEvidenceExtractor(DEFAULT_DIMENSION_REGISTRY).extract(raid, review)
    encounter = next(item for item in evidence if item.encounter_id is not None)
    impacts = {impact.dimension_key: impact.value for impact in encounter.impacts}

    assert impacts["reactive_close_range_effectiveness"] < 0
    assert impacts["first_shot_execution"] < 0
    assert impacts["angle_discipline"] < 0
    assert impacts["overcommitment_control"] < 0


def test_no_encounter_does_not_invent_pvp_weakness(tmp_path: Path) -> None:
    raid = _raid(tmp_path).model_copy(update={"result": "Survived"})
    review = RaidReview(
        raid_id=raid.id,
        status=ReviewStatus.FINALIZED,
        finalized_at=datetime.now(UTC),
        result="Survived",
    )
    review.objectives.primary_progress = "completed"

    evidence = ReviewEvidenceExtractor(DEFAULT_DIMENSION_REGISTRY).extract(raid, review)
    dimensions = {
        impact.dimension_key
        for item in evidence
        for impact in item.impacts
    }

    assert "objective_discipline" in dimensions
    assert "risk_management" in dimensions
    assert "reactive_close_range_effectiveness" not in dimensions
    assert "first_shot_execution" not in dimensions


def test_no_progress_is_negative_not_positive(tmp_path: Path) -> None:
    raid = _raid(tmp_path)
    review = RaidReview(
        raid_id=raid.id,
        status=ReviewStatus.FINALIZED,
        finalized_at=datetime.now(UTC),
    )
    review.objectives.primary_progress = "no progress"

    evidence = ReviewEvidenceExtractor(DEFAULT_DIMENSION_REGISTRY).extract(raid, review)
    objective_impacts = [
        impact
        for item in evidence
        for impact in item.impacts
        if impact.dimension_key == "objective_discipline"
    ]

    assert len(objective_impacts) == 1
    assert objective_impacts[0].value < 0


def test_enemy_fired_first_does_not_count_as_player_first(tmp_path: Path) -> None:
    raid = _raid(tmp_path)
    review = RaidReview(
        raid_id=raid.id,
        status=ReviewStatus.FINALIZED,
        finalized_at=datetime.now(UTC),
        encounters=[
            EncounterReview(
                sequence=1,
                range_band="close",
                detection_order="enemy first",
                fired_first="enemy",
                outcome="clean win",
            )
        ],
    )

    evidence = ReviewEvidenceExtractor(DEFAULT_DIMENSION_REGISTRY).extract(raid, review)
    encounter = next(item for item in evidence if item.encounter_id is not None)
    dimensions = {impact.dimension_key for impact in encounter.impacts}

    assert "pressure_stability" in dimensions
    assert "first_shot_execution" not in dimensions


def test_killed_by_is_negative_while_kill_is_positive(tmp_path: Path) -> None:
    raid = _raid(tmp_path)
    loss = EncounterReview(sequence=1, outcome="killed by PMC")
    victory = EncounterReview(sequence=2, outcome="kill")
    review = RaidReview(
        raid_id=raid.id,
        status=ReviewStatus.FINALIZED,
        finalized_at=datetime.now(UTC),
        encounters=[loss, victory],
    )

    evidence = ReviewEvidenceExtractor(DEFAULT_DIMENSION_REGISTRY).extract(raid, review)
    by_encounter = {item.encounter_id: item for item in evidence if item.encounter_id is not None}
    loss_impact = next(
        impact
        for impact in by_encounter[loss.id].impacts
        if impact.dimension_key == "execution_decisiveness"
    )
    victory_impact = next(
        impact
        for impact in by_encounter[victory.id].impacts
        if impact.dimension_key == "execution_decisiveness"
    )

    assert loss_impact.value < 0
    assert victory_impact.value > 0


def test_draft_review_is_rejected(tmp_path: Path) -> None:
    raid = _raid(tmp_path)
    review = RaidReview(raid_id=raid.id)

    with pytest.raises(ValueError, match="finalized"):
        ReviewEvidenceExtractor(DEFAULT_DIMENSION_REGISTRY).extract(raid, review)
