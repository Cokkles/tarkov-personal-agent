from pathlib import Path

from tarkov_agent.config import (
    AppSettings,
    MediaSettings,
    ObsSettings,
    PathSettings,
    RuntimeSettings,
)
from tarkov_agent.domain.models import EvidenceKind, RaidState
from tarkov_agent.domain.state_machine import RaidSignal
from tarkov_agent.integrations.obs import RecordingStatus
from tarkov_agent.services.coordinator import RaidCoordinator
from tarkov_agent.services.markers import MarkerService
from tarkov_agent.services.media import MediaService
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.storage.database import RaidRepository


class FileRecordingController:
    def __init__(self, output_path: Path) -> None:
        self.active = False
        self.output_path = output_path

    def status(self) -> RecordingStatus:
        return RecordingStatus(connected=True, active=self.active)

    def start(self) -> RecordingStatus:
        self.active = True
        return self.status()

    def stop(self) -> RecordingStatus:
        self.active = False
        return RecordingStatus(
            connected=True,
            active=False,
            output_path=str(self.output_path),
        )


def test_raid_end_indexes_stable_obs_recording_before_review(
    tmp_path: Path,
) -> None:
    recording_path = tmp_path / "obs" / "raid.mkv"
    recording_path.parent.mkdir(parents=True)
    recording_path.write_bytes(b"completed-obs-recording")
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        obs=ObsSettings(enabled=True),
        media=MediaSettings(
            file_stability_timeout_seconds=0.1,
            file_stability_poll_seconds=0.001,
            file_stability_checks=1,
            ffprobe_path="definitely-missing-ffprobe",
        ),
        runtime=RuntimeSettings(auto_complete_raid_on_end=False),
    )
    settings.prepare()
    repository = RaidRepository(settings.paths.database_path)
    repository.initialize()
    packages = RaidPackageBuilder(settings.paths.raids_root)
    markers = MarkerService(repository, packages)
    media = MediaService(
        repository,
        packages,
        settings.paths.media_root,
        settings.media,
        [tmp_path],
    )
    recording = FileRecordingController(recording_path)
    coordinator = RaidCoordinator(
        settings,
        repository,
        packages,
        markers,
        recording,
        media,
    )

    coordinator.handle_signal(RaidSignal.GAME_FOUND)
    coordinator.handle_signal(
        RaidSignal.RAID_STARTED,
        payload={"map_name": "Customs", "character_type": "Scav"},
    )
    assert coordinator.active_raid is not None
    raid_id = coordinator.active_raid.id

    coordinator.handle_signal(
        RaidSignal.RAID_ENDED,
        payload={"result": "Survived"},
    )

    stored = repository.get_raid(raid_id)
    assert stored is not None
    assert stored.state is RaidState.REVIEW_PENDING
    recordings = [
        item for item in stored.evidence if item.kind is EvidenceKind.RECORDING
    ]
    assert len(recordings) == 1
    assert recordings[0].path == recording_path.resolve()
    assert recordings[0].size_bytes == recording_path.stat().st_size
    assert recordings[0].sha256 is not None

    event_types = {
        event.event_type for event in repository.list_timeline_events(raid_id)
    }
    assert "recording_stopped" in event_types
    assert "recording_indexed" in event_types
    assert coordinator.active_raid is None
