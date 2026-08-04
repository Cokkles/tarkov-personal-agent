from pathlib import Path

from fastapi.testclient import TestClient

from tarkov_agent.api.application import create_app
from tarkov_agent.app_context import build_context
from tarkov_agent.config import AppSettings, PathSettings, RuntimeSettings


def test_recommendation_api_and_dashboard(tmp_path: Path) -> None:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        runtime=RuntimeSettings(recover_interrupted_sessions=False),
    )
    context = build_context(settings)

    with TestClient(create_app(context, start_runtime=False)) as client:
        dashboard = client.get("/recommendations")
        assert dashboard.status_code == 200
        assert "Recommendation Engine" in dashboard.text

        response = client.post(
            "/api/recommendations/generate",
            json={
                "game": "tarkov",
                "objective": "Extract useful loot safely",
                "map_name": "Customs",
                "character_type": "Scav",
                "purpose": "progression",
                "risk_posture": "low",
                "mechanic_keys": [],
                "constraints": [],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["can_recommend"] is True
        assert body["primary"] is not None
        assert body["fallback"] is not None

        latest = client.get("/api/recommendations/latest")
        assert latest.status_code == 200
        assert latest.json()["id"] == body["id"]

        exported = client.get("/api/recommendations/export/markdown")
        assert exported.status_code == 200
        assert "Primary plan" in exported.text
        assert "scav.extracted_loot_transfers" in exported.text
