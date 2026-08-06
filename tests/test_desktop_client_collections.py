from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from tarkov_agent.desktop.client import DesktopApiClient, DesktopApiError


def _client_with_response(monkeypatch: pytest.MonkeyPatch, response: object) -> DesktopApiClient:
    client = object.__new__(DesktopApiClient)

    def request(method: str, path: str, payload: object = None) -> object:
        del method, path, payload
        return response

    monkeypatch.setattr(client, "_request", request)
    return client


def _raid_payload() -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "game": "tarkov",
        "state": "review_pending",
        "map_name": "Woods",
        "character_type": "Scav",
        "result": "Survived",
        "data_root": "data/raids/test",
    }


def test_list_raids_parses_records(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_with_response(monkeypatch, [_raid_payload()])

    raids = client.list_raids(limit=5)

    assert len(raids) == 1
    assert raids[0].map_name == "Woods"
    assert raids[0].result == "Survived"


def test_timeline_normalizes_mapping_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_with_response(
        monkeypatch,
        [{"id": "event-1", "event_type": "marker", "label": "PMC Heard"}],
    )

    events = client.timeline("raid-1")

    assert events == [
        {"id": "event-1", "event_type": "marker", "label": "PMC Heard"}
    ]


def test_collection_methods_reject_unexpected_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_with_response(monkeypatch, {"unexpected": True})

    with pytest.raises(DesktopApiError):
        client.list_raids()
    with pytest.raises(DesktopApiError):
        client.review_queue()
    with pytest.raises(DesktopApiError):
        client.timeline("raid-1")
