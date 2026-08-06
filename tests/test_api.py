import time
from pathlib import Path

from fastapi.testclient import TestClient

from tarkov_agent.api.app import create_app
from tarkov_agent.app_context import build_context
from tarkov_agent.config import AppSettings, PathSettings, RuntimeSettings


def test_manual_raid_review_flow(tmp_path: Path) -> None:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        runtime=RuntimeSettings(
            auto_complete_raid_on_end=False,
            recover_interrupted_sessions=False,
        ),
    )
    context = build_context(settings)

    with TestClient(create_app(context, start_runtime=False)) as client:
        started = client.post(
            "/api/control/raid/start",
            json={
                "game": "tarkov",
                "map_name": "Interchange",
                "character_type": "PMC",
                "primary_objective": "Find Electric Drill",
            },
        )
        assert started.status_code == 200
        raid_id = started.json()["id"]

        marker = client.post(
            "/api/markers",
            json={"label": "Possible PMC", "category": "audio"},
        )
        assert marker.status_code == 200

        ended = client.post("/api/control/raid/end", json={"result": "Survived"})
        assert ended.status_code == 202
        job_id = ended.json()["id"]
        assert ended.json()["raid_id"] == raid_id

        deadline = time.monotonic() + 3.0
        finalization = ended.json()
        while finalization["stage"] not in {"ready", "failed"}:
            assert time.monotonic() < deadline
            time.sleep(0.02)
            response = client.get(f"/api/finalization/jobs/{job_id}")
            assert response.status_code == 200
            finalization = response.json()
        assert finalization["stage"] == "ready"
        assert finalization["progress"] == 100

        raid_response = client.get(f"/api/raids/{raid_id}")
        assert raid_response.status_code == 200
        assert raid_response.json()["raid"]["state"] == "review_pending"

        review_response = client.get(f"/api/raids/{raid_id}/review")
        assert review_response.status_code == 200
        review = review_response.json()
        review["statistics"]["pmc_kills"] = 1

        saved = client.put(
            f"/api/raids/{raid_id}/review",
            json={"review": review, "expected_version": 0, "actor": "test"},
        )
        assert saved.status_code == 200
        saved_review = saved.json()
        assert saved_review["version"] == 1

        finalized = client.post(
            f"/api/raids/{raid_id}/review/finalize",
            json={"review": saved_review, "expected_version": 1, "actor": "test"},
        )
        assert finalized.status_code == 200
        assert finalized.json()["status"] == "finalized"

        markdown = client.get(f"/api/raids/{raid_id}/export/markdown")
        assert markdown.status_code == 200
        assert "Interchange" in markdown.text

        queue = client.get("/api/review-queue")
        assert queue.status_code == 200
        assert queue.json() == []
