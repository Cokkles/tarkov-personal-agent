import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from tarkov_agent import __version__
from tarkov_agent.api.application import create_app
from tarkov_agent.app_context import build_context
from tarkov_agent.config import AppSettings, ObsSettings, PathSettings, RuntimeSettings
from tarkov_agent.integrations.obs import ObsIntegrationError


class BlockingRecordingController:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def status(self) -> object:
        self.started.set()
        self.release.wait(timeout=2.0)
        raise ObsIntegrationError("OBS is unavailable for test")


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


def test_desktop_status_does_not_block_on_obs_transport_timeout(tmp_path: Path) -> None:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        obs=ObsSettings(enabled=True, timeout_seconds=3.0),
        runtime=RuntimeSettings(recover_interrupted_sessions=False),
    )
    context = build_context(settings)
    blocking = BlockingRecordingController()
    context.recording = blocking  # type: ignore[assignment]

    with TestClient(create_app(context, start_runtime=False)) as client:
        started_at = time.perf_counter()
        response = client.get("/api/desktop/status")
        elapsed = time.perf_counter() - started_at

        assert response.status_code == 200
        assert response.json()["obs"]["enabled"] is True
        assert elapsed < 0.5
        assert blocking.started.wait(timeout=0.5)

        health_started = time.perf_counter()
        health = client.get("/api/health")
        health_elapsed = time.perf_counter() - health_started
        assert health.status_code == 200
        assert health_elapsed < 0.5

        blocking.release.set()
        time.sleep(0.05)
        refreshed = client.get("/api/desktop/status")
        assert refreshed.status_code == 200
        assert "OBS is unavailable for test" in refreshed.json()["obs"]["error"]
