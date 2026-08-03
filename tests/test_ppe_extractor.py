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


def test_draft_review_is_rejected(tmp_path: Path) -> None:
    raid = _raid(tmp_path)
    review = RaidReview(raid_id=raid.id)

    with pytest.raises(ValueError, match="finalized"):
        ReviewEvidenceExtractor(DEFAULT_DIMENSION_REGISTRY).extract(raid, review)
