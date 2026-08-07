from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from tarkov_agent.api.application import create_app
from tarkov_agent.app_context import build_context
from tarkov_agent.config import AppSettings, MediaSettings, PathSettings, RuntimeSettings
from tarkov_agent.domain.evidence import EvidenceBundleProfile, EvidenceBundleRequest
from tarkov_agent.domain.models import MarkerCommand, MarkerType, RaidRecord, RaidState


def _context(tmp_path: Path):
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        media=MediaSettings(
            file_stability_checks=1,
            file_stability_poll_seconds=0.01,
            file_stability_timeout_seconds=1.0,
        ),
        runtime=RuntimeSettings(recover_interrupted_sessions=False),
    )
    return build_context(settings)


def _raid_with_markers(tmp_path: Path):
    context = _context(tmp_path)
    started = datetime.now(UTC)
    raid = RaidRecord(
        state=RaidState.IN_RAID,
        started_at=started,
        map_name="Woods",
        character_type="Scav",
        primary_objective="Loot",
        data_root=tmp_path,
    )
    raid = context.packages.create(raid)
    context.repository.save_raid(raid)
    context.markers.activate(raid)
    context.markers.create(
        MarkerCommand(marker_type=MarkerType.IMPORTANT_LOOT, source="stream_deck"),
        occurred_at=started + timedelta(seconds=20),
    )
    fight = context.markers.create(
        MarkerCommand(marker_type=MarkerType.FIGHT_STARTED, source="stream_deck"),
        occurred_at=started + timedelta(seconds=40),
    )
    analysis = raid.data_root / "analysis"
    (analysis / "review.json").write_text('{"status":"finalized"}', encoding="utf-8")
    return context, raid, fight


def test_evidence_preview_prioritizes_combat_marker(tmp_path: Path) -> None:
    context, raid, fight = _raid_with_markers(tmp_path)

    preview = context.evidence.preview(
        raid.id,
        EvidenceBundleRequest(profile=EvidenceBundleProfile.STANDARD, max_clips=1),
    )

    selected = [item for item in preview.candidates if item.selected]
    assert len(selected) == 1
    assert selected[0].timeline_event_id == fight.id
    assert selected[0].marker_type == MarkerType.FIGHT_STARTED.value
    assert preview.raw_recordings_included is False


def test_evidence_bundle_excludes_raw_recording_and_keeps_reference(tmp_path: Path) -> None:
    context, raid, _ = _raid_with_markers(tmp_path)
    recording = tmp_path / "source-recording.mkv"
    recording.write_bytes(b"not-a-real-video-but-valid-evidence-bytes")
    context.media.index_recording(raid.id, recording)

    result = context.evidence.build(
        raid.id,
        EvidenceBundleRequest(profile=EvidenceBundleProfile.STANDARD, max_clips=2),
    )

    assert result.archive_path.is_file()
    assert result.manifest.recording_references
    assert result.manifest.raw_recordings_included is False
    with ZipFile(result.archive_path) as archive:
        names = set(archive.namelist())
    assert "raid.json" in names
    assert "timeline.jsonl" in names
    assert "analysis/review.json" in names
    assert "analysis/media-index.json" in names
    assert "bundle-manifest.json" in names
    assert "README.md" in names
    assert all("source-recording.mkv" not in name for name in names)


def test_evidence_api_builds_and_downloads_bundle(tmp_path: Path) -> None:
    context, raid, _ = _raid_with_markers(tmp_path)

    with TestClient(create_app(context, start_runtime=False)) as client:
        preview = client.post(
            f"/api/raids/{raid.id}/evidence/preview",
            json={"profile": "metadata"},
        )
        assert preview.status_code == 200
        assert preview.json()["profile"] == "metadata"

        build = client.post(
            f"/api/raids/{raid.id}/evidence/build",
            json={"profile": "metadata"},
        )
        assert build.status_code == 200
        assert build.json()["manifest"]["raw_recordings_included"] is False

        download = client.get(f"/api/raids/{raid.id}/evidence/latest")
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/zip"
