from datetime import UTC, datetime
from pathlib import Path

import pytest

from tarkov_agent.config import PpeSettings
from tarkov_agent.domain.models import RaidRecord
from tarkov_agent.domain.ppe import DimensionImpact, ManualEvidenceRequest
from tarkov_agent.domain.reviews import EncounterReview, RaidReview, ReviewStatus
from tarkov_agent.services.ppe import PPEProfileService, PPEValidationError
from tarkov_agent.storage.database import RaidRepository


def _service(tmp_path: Path) -> tuple[PPEProfileService, RaidRepository]:
    repository = RaidRepository(tmp_path / "agent.sqlite3")
    repository.initialize()
    service = PPEProfileService(
        repository,
        tmp_path / "ppe",
        PpeSettings(
            minimum_report_confidence=0.1,
            minimum_established_confidence=0.2,
        ),
    )
    return service, repository


def _raid_and_review(tmp_path: Path) -> tuple[RaidRecord, RaidReview]:
    now = datetime.now(UTC)
    raid = RaidRecord(
        data_root=tmp_path,
        map_name="Interchange",
        character_type="PMC",
        started_at=now,
        ended_at=now,
        result="Survived",
    )
    review = RaidReview(
        raid_id=raid.id,
        version=2,
        status=ReviewStatus.FINALIZED,
        finalized_at=now,
        result="Survived",
        map_name="Interchange",
        encounters=[
            EncounterReview(
                sequence=1,
                range_band="medium",
                detection_order="player first",
                fired_first="yes",
                outcome="clean win",
                repositioned=True,
                repeeked_same_angle=False,
            )
        ],
    )
    review.objectives.primary_progress = "completed"
    return raid, review


def test_finalized_review_updates_profile_and_is_idempotent(tmp_path: Path) -> None:
    service, repository = _service(tmp_path)
    raid, review = _raid_and_review(tmp_path)
    repository.save_raid(raid)

    first = service.ingest_finalized_review(raid, review)
    assert first is not None
    first_evidence = service.evidence_for_raid(str(raid.id))
    assert first_evidence

    second = service.ingest_finalized_review(raid, review)
    assert second is not None
    second_evidence = service.evidence_for_raid(str(raid.id))

    assert second.version == first.version
    assert len(second_evidence) == len(first_evidence)
    assert (tmp_path / "ppe" / "profile-current.json").exists()
    assert (tmp_path / "ppe" / "profile-report.md").exists()


def test_manual_evidence_creates_new_snapshot(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    initial = service.rebuild(trigger="test-initial").snapshot

    evidence, updated = service.add_manual_evidence(
        ManualEvidenceRequest(
            impacts=[
                DimensionImpact(
                    dimension_key="audio_interpretation",
                    value=0.8,
                    strength=0.9,
                    confidence=0.9,
                    rationale="Repeatedly identified floor and direction correctly.",
                )
            ]
        )
    )

    assert evidence.source.value == "manual_assessment"
    assert updated.version == initial.version + 1
    assert updated.estimate("audio_interpretation") is not None
    assert len(service.history()) == 2
    assert len(service.audit_history()) == 2


def test_unknown_manual_dimension_is_rejected(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)

    with pytest.raises(PPEValidationError, match="Unknown PPE dimensions"):
        service.add_manual_evidence(
            ManualEvidenceRequest(
                impacts=[
                    DimensionImpact(
                        dimension_key="imaginary_dimension",
                        value=1.0,
                        rationale="Not a registered dimension.",
                    )
                ]
            )
        )
