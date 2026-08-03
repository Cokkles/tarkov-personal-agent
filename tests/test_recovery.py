from pathlib import Path

from tarkov_agent.domain.models import RaidRecord, RaidState
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.services.recovery import RecoveryService
from tarkov_agent.storage.database import RaidRepository


def test_interrupted_raid_is_queued_for_review(tmp_path: Path) -> None:
    repository = RaidRepository(tmp_path / "agent.sqlite3")
    repository.initialize()
    packages = RaidPackageBuilder(tmp_path / "raids")
    raid = packages.create(
        RaidRecord(
            state=RaidState.IN_RAID,
            map_name="Customs",
            data_root=tmp_path / "raids",
        )
    )
    repository.save_raid(raid)

    recovered = RecoveryService(repository, packages).recover(game_running=False)

    assert recovered is not None
    assert recovered.state is RaidState.REVIEW_PENDING
    assert recovered.ended_at is not None
    events = repository.list_timeline_events(raid.id)
    assert events[-1].event_type == "recovery"
