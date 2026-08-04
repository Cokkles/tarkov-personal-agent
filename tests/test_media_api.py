from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from tarkov_agent.api.application import create_app
from tarkov_agent.app_context import build_context
from tarkov_agent.config import (
    AppSettings,
    MediaSettings,
    PathSettings,
    RuntimeSettings,
)
from tarkov_agent.domain.models import RaidRecord, RaidState, TimelineEvent


def test_media_dashboard_and_recording_api(tmp_path: Path) -> None:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        media=MediaSettings(
            file_stability_timeout_seconds=0.1,
            file_stability_poll_seconds=0.001,
            file_stability_checks=1,
            ffprobe_path="definitely-missing-ffprobe",
        ),
        runtime=RuntimeSettings(recover_interrupted_sessions=False),
    )
    context = build_context(settings)
    raid = context.packages.create(
        RaidRecord(
            state=RaidState.COMPLETE,
            started_at=datetime.now(UTC),
            data_root=settings.paths.raids_root,
        )
    )
    context.repository.save_raid(raid)
    marker = TimelineEvent(
        raid_id=raid.id,
        occurred_at=datetime.now(UTC),
        raid_offset_ms=2_500,
        event_type="marker",
        label="Important Loot",
        source="user",
        payload={"category": "loot"},
    )
    context.repository.add_timeline_event(marker)
    recording = tmp_path / "recordings" / "api-test.mkv"
    recording.parent.mkdir(parents=True)
    recording.write_bytes(b"api-recording")

    with TestClient(create_app(context, start_runtime=False)) as client:
        dashboard = client.get("/media")
        assert dashboard.status_code == 200
        assert "Media Assistance" in dashboard.text

        response = client.post(
            f"/api/raids/{raid.id}/media/recordings",
            json={"path": str(recording), "copy_into_package": False},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["recording"]["available"] is True

        media = client.get(f"/api/raids/{raid.id}/media")
        assert media.status_code == 200
        assert len(media.json()["recordings"]) == 1

        navigation = client.get(
            f"/api/raids/{raid.id}/media/navigation"
        )
        assert navigation.status_code == 200
        assert navigation.json()[0]["timeline_event_id"] == str(marker.id)
