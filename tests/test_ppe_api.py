from pathlib import Path

from fastapi.testclient import TestClient

from tarkov_agent.api.app import create_app
from tarkov_agent.app_context import build_context
from tarkov_agent.config import AppSettings, PathSettings, RuntimeSettings


def _client(tmp_path: Path) -> TestClient:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        runtime=RuntimeSettings(recover_interrupted_sessions=False),
    )
    return TestClient(create_app(build_context(settings), start_runtime=False))


def test_ppe_dashboard_and_profile_endpoints(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        dashboard = client.get("/ppe")
        assert dashboard.status_code == 200
        assert "Personal Playstyle Engine" in dashboard.text

        dimensions = client.get("/api/ppe/dimensions")
        assert dimensions.status_code == 200
        keys = {item["key"] for item in dimensions.json()}
        assert "reactive_close_range_effectiveness" in keys
        assert "objective_discipline" in keys

        profile = client.get("/api/ppe/profile")
        assert profile.status_code == 200
        assert profile.json()["version"] == 1
        assert profile.json()["evidence_count"] == 0

        added = client.post(
            "/api/ppe/evidence/manual",
            json={
                "actor": "test",
                "reliability": 0.9,
                "context": {"map_name": "Factory", "range_band": "close"},
                "impacts": [
                    {
                        "dimension_key": "reactive_close_range_effectiveness",
                        "value": -0.8,
                        "strength": 0.9,
                        "confidence": 0.9,
                        "role": "performance",
                        "rationale": "Repeated mutual-contact losses in a controlled sample.",
                    }
                ],
            },
        )
        assert added.status_code == 200
        assert added.json()["profile"]["version"] == 2

        report = client.get("/api/ppe/report")
        assert report.status_code == 200
        assert report.json()["snapshot_version"] == 2

        evidence = client.get("/api/ppe/evidence")
        assert evidence.status_code == 200
        assert len(evidence.json()) == 1

        exported = client.get("/api/ppe/export/markdown")
        assert exported.status_code == 200
        assert "Personal Playstyle Engine Report" in exported.text


def test_invalid_manual_dimension_returns_validation_error(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post(
            "/api/ppe/evidence/manual",
            json={
                "impacts": [
                    {
                        "dimension_key": "not_registered",
                        "value": 0.5,
                        "rationale": "Invalid test dimension.",
                    }
                ]
            },
        )
        assert response.status_code == 422
