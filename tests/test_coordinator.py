from pathlib import Path

from tarkov_agent.config import AppSettings, ObsSettings, PathSettings
from tarkov_agent.domain.models import RaidState
from tarkov_agent.domain.state_machine import RaidSignal
from tarkov_agent.integrations.obs import RecordingStatus
from tarkov_agent.services.coordinator import RaidCoordinator
from tarkov_agent.services.markers import MarkerService
from tarkov_agent.services.packages import RaidPackageBuilder
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


def test_coordinator_creates_and_completes_raid(tmp_path: Path) -> None:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        obs=ObsSettings(enabled=True),
    )
    settings.prepare()
    repository = RaidRepository(settings.paths.database_path)
    repository.initialize()
    packages = RaidPackageBuilder(settings.paths.raids_root)
    markers = MarkerService(repository, packages)
    recording = FakeRecordingController()
    coordinator = RaidCoordinator(settings, repository, packages, markers, recording)

    coordinator.handle_signal(RaidSignal.GAME_FOUND)
    coordinator.handle_signal(
        RaidSignal.RAID_STARTED,
        payload={"map_name": "Interchange", "primary_objective": "Find Electric Drill"},
    )
    raid_id = coordinator.active_raid.id  # type: ignore[union-attr]

    assert coordinator.active_raid is not None
    assert coordinator.active_raid.state is RaidState.IN_RAID
    assert recording.active is True

    coordinator.handle_signal(RaidSignal.RAID_ENDED)
    coordinator.handle_signal(RaidSignal.REVIEW_COMPLETED)

    restored = repository.get_raid(raid_id)
    assert restored is not None
    assert restored.state is RaidState.COMPLETE
    assert restored.ended_at is not None
    assert recording.active is False
