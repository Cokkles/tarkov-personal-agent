from pathlib import Path

from fastapi.testclient import TestClient

from tarkov_agent.api.application import create_app
from tarkov_agent.app_context import build_context
from tarkov_agent.config import AppSettings, PathSettings, RuntimeSettings


def test_source_truth_api_and_dashboard(tmp_path: Path) -> None:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        runtime=RuntimeSettings(recover_interrupted_sessions=False),
    )
    context = build_context(settings)

    with TestClient(create_app(context, start_runtime=False)) as client:
        dashboard = client.get("/truth")
        assert dashboard.status_code == 200
        assert "Source of Truth" in dashboard.text

        status = client.get("/api/truth/status")
        assert status.status_code == 200
        assert status.json()["source_count"] >= 4
        assert status.json()["verified_claim_count"] >= 3

        resolution = client.post(
            "/api/truth/query",
            json={
                "key": "scav.random_loadout",
                "game": "tarkov",
                "patch_version": None,
                "include_stale": False,
            },
        )
        assert resolution.status_code == 200
        assert resolution.json()["resolution"] == "verified"
        assert resolution.json()["can_recommend"] is True

        exported = client.get("/api/truth/export/markdown")
        assert exported.status_code == 200
        assert "## Citations" in exported.text
        assert "scav.random_loadout" in exported.text
