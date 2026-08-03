from pathlib import Path

from tarkov_agent.domain.models import RaidRecord, RaidState
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.services.reviews import RaidReviewService
from tarkov_agent.storage.database import RaidRepository


def test_review_save_finalize_and_export(tmp_path: Path) -> None:
    repository = RaidRepository(tmp_path / "agent.sqlite3")
    repository.initialize()
    packages = RaidPackageBuilder(tmp_path / "raids")
    raid = packages.create(
        RaidRecord(
            state=RaidState.REVIEW_PENDING,
            map_name="Interchange",
            primary_objective="Find Electric Drill",
            data_root=tmp_path / "raids",
        )
    )
    repository.save_raid(raid)
    service = RaidReviewService(repository, packages)

    review = service.get_or_create(raid.id)
    review.map_name = "Interchange"
    review.objectives.primary_progress = "Completed"
    review.statistics.pmc_kills = 1
    saved = service.save(raid.id, review, expected_version=0)

    assert saved.version == 1
    assert saved.objectives.primary == "Find Electric Drill"
    assert saved.statistics.pmc_kills == 1

    finalized = service.finalize(raid.id, saved, expected_version=1)
    restored = repository.get_raid(raid.id)

    assert finalized.status.value == "finalized"
    assert restored is not None
    assert restored.state is RaidState.COMPLETE
    assert (raid.data_root / "analysis" / "review.json").exists()
    assert (raid.data_root / "analysis" / "review.md").exists()
    assert len(service.audit_history(raid.id)) == 4
