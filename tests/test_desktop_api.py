from pathlib import Path

from fastapi.testclient import TestClient

from tarkov_agent import __version__
from tarkov_agent.api.application import create_app
from tarkov_agent.app_context import build_context
from tarkov_agent.config import AppSettings, PathSettings, RuntimeSettings


def test_desktop_status_api_reports_local_subsystems(tmp_path: Path) -> None:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        runtime=RuntimeSettings(recover_interrupted_sessions=False),
    )
    context = build_context(settings)

    with TestClient(create_app(context, start_runtime=False)) as client:
        response = client.get("/api/desktop/status")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == __version__
    assert body["lifecycle_state"] == "idle"
    assert body["active_raid"] is None
    assert body["review_queue_count"] == 0
    assert body["obs"]["enabled"] is False
    assert body["ppe_enabled"] is True
    assert body["source_truth_enabled"] is True
    assert body["recommendations_enabled"] is True
    assert body["media_enabled"] is True
