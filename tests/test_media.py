from datetime import UTC, datetime
from pathlib import Path

import pytest

from tarkov_agent.config import MediaSettings
from tarkov_agent.domain.media import ClipRequest, MediaSource, ProbeStatus
from tarkov_agent.domain.models import RaidRecord, RaidState, TimelineEvent
from tarkov_agent.services.media import MediaService, MediaToolError
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.storage.database import RaidRepository


def _service(
    tmp_path: Path,
) -> tuple[MediaService, RaidRepository, RaidRecord, Path]:
    repository = RaidRepository(tmp_path / "agent.sqlite3")
    repository.initialize()
    packages = RaidPackageBuilder(tmp_path / "raids")
    raid = packages.create(
        RaidRecord(
            state=RaidState.COMPLETE,
            started_at=datetime.now(UTC),
            data_root=tmp_path / "raids",
        )
    )
    repository.save_raid(raid)
    recording = tmp_path / "recordings" / "test-raid.mkv"
    recording.parent.mkdir(parents=True)
    recording.write_bytes(b"stable-recording-content")
    settings = MediaSettings(
        file_stability_timeout_seconds=0.1,
        file_stability_poll_seconds=0.001,
        file_stability_checks=1,
        ffprobe_path="definitely-missing-ffprobe",
        ffmpeg_path="definitely-missing-ffmpeg",
    )
    media = MediaService(
        repository,
        packages,
        tmp_path / "media",
        settings,
        [tmp_path],
    )
    return media, repository, raid, recording


def test_recording_index_is_reference_first_and_idempotent(
    tmp_path: Path,
) -> None:
    media, repository, raid, recording = _service(tmp_path)

    updated, asset = media.index_recording(
        raid.id,
        recording,
        media_source=MediaSource.MANUAL,
    )

    assert updated.evidence[-1].path == recording.resolve()
    assert asset.original_path == recording.resolve()
    assert asset.canonical_path == recording.resolve()
    assert asset.copied_into_package is False
    assert asset.probe_status is ProbeStatus.UNAVAILABLE
    assert len(media.index_for_raid(raid.id).recordings) == 1

    repeated, same_asset = media.index_recording(raid.id, recording)
    assert same_asset.id == asset.id
    assert len(repeated.evidence) == 1
    stored = repository.get_raid(raid.id)
    assert stored is not None
    assert len(stored.evidence) == 1


def test_navigation_uses_timeline_offsets(tmp_path: Path) -> None:
    media, repository, raid, recording = _service(tmp_path)
    _, asset = media.index_recording(raid.id, recording)
    event = TimelineEvent(
        raid_id=raid.id,
        occurred_at=datetime.now(UTC),
        raid_offset_ms=12_345,
        event_type="marker",
        label="PMC Heard",
        source="user",
        payload={"category": "audio"},
    )
    repository.add_timeline_event(event)

    points = media.navigation_for_raid(raid.id)

    assert len(points) == 1
    assert points[0].recording_id == asset.id
    assert points[0].timeline_event_id == event.id
    assert points[0].seek_seconds == 12.345
    assert points[0].category == "audio"


def test_clip_extraction_reports_missing_ffmpeg(tmp_path: Path) -> None:
    media, _, raid, recording = _service(tmp_path)
    media.index_recording(raid.id, recording)

    with pytest.raises(MediaToolError, match="ffmpeg was not found"):
        media.extract_clip(
            raid.id,
            ClipRequest(raid_offset_ms=5_000),
        )
