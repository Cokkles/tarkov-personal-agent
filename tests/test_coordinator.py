from pathlib import Path

from tarkov_agent.config import AppSettings, ObsSettings, PathSettings, RuntimeSettings
from tarkov_agent.domain.models import RaidState
from tarkov_agent.domain.state_machine import RaidSignal
from tarkov_agent.integrations.obs import RecordingStatus
from tarkov_agent.services.coordinator import RaidCoordinator
from tarkov_agent.services.markers import MarkerService
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.services.reviews import RaidReviewService
from tarkov_agent.storage.database import RaidRepository


class FakeRecordingController:
    def __init__(self) -> None:
        self.active = False

    def status(self) -> RecordingStatus:
        return RecordingStatus(connected=True, active=self.active)

    def start(self) -> RecordingStatus:
        self.active = True
        return self.status()

    def stop(self) -> RecordingStatus:
        self.active = False
        return self.status()


def _coordinator(
    tmp_path: Path,
    *,
    auto_complete: bool,
) -> tuple[
    RaidCoordinator,
    RaidRepository,
    RaidPackageBuilder,
    FakeRecordingController,
]:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        obs=ObsSettings(enabled=True),
        runtime=RuntimeSettings(auto_complete_raid_on_end=auto_complete),
    )
    settings.prepare()
    repository = RaidRepository(settings.paths.database_path)
    repository.initialize()
    packages = RaidPackageBuilder(settings.paths.raids_root)
    markers = MarkerService(repository, packages)
    recording = FakeRecordingController()
    coordinator = RaidCoordinator(settings, repository, packages, markers, recording)
    return coordinator, repository, packages, recording


def test_coordinator_queues_explicit_review(tmp_path: Path) -> None:
    coordinator, repository, packages, recording = _coordinator(
        tmp_path,
        auto_complete=False,
    )

    coordinator.handle_signal(RaidSignal.GAME_FOUND)
    coordinator.handle_signal(
        RaidSignal.RAID_STARTED,
        payload={"map_name": "Interchange", "primary_objective": "Find Electric Drill"},
    )
    assert coordinator.active_raid is not None
    raid_id = coordinator.active_raid.id

    assert coordinator.active_raid.state is RaidState.IN_RAID
    assert recording.active is True

    coordinator.handle_signal(RaidSignal.RAID_ENDED, payload={"result": "Survived"})

    pending = repository.get_raid(raid_id)
    assert pending is not None
    assert pending.state is RaidState.REVIEW_PENDING
    assert pending.result == "Survived"
    assert coordinator.active_raid is None
    assert recording.active is False

    review_service = RaidReviewService(repository, packages)
    review = review_service.get_or_create(raid_id)
    review_service.finalize(raid_id, review, expected_version=0)

    restored = repository.get_raid(raid_id)
    assert restored is not None
    assert restored.state is RaidState.COMPLETE
    assert restored.ended_at is not None


def test_headless_mode_auto_completes_and_allows_next_raid(tmp_path: Path) -> None:
    coordinator, repository, _, _ = _coordinator(tmp_path, auto_complete=True)

    coordinator.handle_signal(RaidSignal.GAME_FOUND)
    coordinator.handle_signal(RaidSignal.RAID_STARTED, payload={"map_name": "Customs"})
    assert coordinator.active_raid is not None
    first_raid_id = coordinator.active_raid.id
    coordinator.handle_signal(RaidSignal.RAID_ENDED)

    assert coordinator.active_raid is None
    first_raid = repository.get_raid(first_raid_id)
    assert first_raid is not None
    assert first_raid.state is RaidState.COMPLETE

    coordinator.handle_signal(RaidSignal.RAID_STARTED, payload={"map_name": "Woods"})
    assert coordinator.active_raid is not None
    assert coordinator.active_raid.map_name == "Woods"
