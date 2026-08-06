from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.request import Request

from tarkov_agent.config import ApiSettings, AppSettings, PathSettings
from tarkov_agent.desktop.client import DesktopApiClient, desktop_base_url
from tarkov_agent.domain.models import MarkerCommand


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = BytesIO(payload)

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload.read()


def test_desktop_base_url_normalizes_wildcard_host(tmp_path: Path) -> None:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        api=ApiSettings(host="0.0.0.0", token="required"),
    )

    assert desktop_base_url(settings) == "http://127.0.0.1:8765"


def test_status_request_uses_token_and_parses_model(tmp_path: Path) -> None:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        api=ApiSettings(token="desktop-token"),
    )
    client = DesktopApiClient(settings)
    captured: list[Request] = []

    def fake_urlopen(
        request: Request,
        timeout: float,
    ) -> FakeResponse:
        captured.append(request)
        assert timeout == settings.desktop.request_timeout_seconds
        return FakeResponse(
            b'{"version":"0.10.0","lifecycle_state":"idle",'
            b'"active_raid":null,"review_queue_count":0,'
            b'"automatic_log_rules":0,"obs":{"enabled":false},'
            b'"ppe_enabled":true,"ppe_profile_version":null,'
            b'"source_truth_enabled":true,'
            b'"recommendations_enabled":true,"media_enabled":true,'
            b'"finalization":null}'
        )

    with patch("tarkov_agent.desktop.client.urlopen", fake_urlopen):
        status = client.status()

    assert status.lifecycle_state == "idle"
    assert status.finalization is None
    assert captured[0].get_header("X-tpa-token") == "desktop-token"


def test_end_raid_returns_background_finalization_job(tmp_path: Path) -> None:
    settings = AppSettings(paths=PathSettings(data_root=tmp_path))
    client = DesktopApiClient(settings)

    def fake_urlopen(
        request: Request,
        timeout: float,
    ) -> FakeResponse:
        assert request.full_url.endswith("/api/control/raid/end")
        return FakeResponse(
            b'{"id":"11111111-1111-1111-1111-111111111111",'
            b'"raid_id":"22222222-2222-2222-2222-222222222222",'
            b'"result":"Survived","stage":"accepted","progress":5,'
            b'"message":"Raid end accepted",'
            b'"created_at":"2026-08-06T05:00:00Z",'
            b'"updated_at":"2026-08-06T05:00:00Z",'
            b'"completed_at":null,"error":null,'
            b'"retryable":false,"attempt":1}'
        )

    with patch("tarkov_agent.desktop.client.urlopen", fake_urlopen):
        job = client.end_raid(result="Survived")

    assert job.stage.value == "accepted"
    assert job.progress == 5
    assert str(job.raid_id) == "22222222-2222-2222-2222-222222222222"


def test_marker_request_sends_expected_json(tmp_path: Path) -> None:
    settings = AppSettings(paths=PathSettings(data_root=tmp_path))
    client = DesktopApiClient(settings)
    captured: dict[str, Any] = {}

    def fake_urlopen(
        request: Request,
        timeout: float,
    ) -> FakeResponse:
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["body"] = request.data
        return FakeResponse(b'{"event_type":"marker"}')

    with patch("tarkov_agent.desktop.client.urlopen", fake_urlopen):
        response = client.add_marker(
            MarkerCommand(
                label="PMC Heard",
                category="audio",
                details="Possible audio cue",
            )
        )

    assert response["event_type"] == "marker"
    assert captured["url"] == "http://127.0.0.1:8765/api/markers"
    assert captured["method"] == "POST"
    assert b'"label": "PMC Heard"' in captured["body"]
