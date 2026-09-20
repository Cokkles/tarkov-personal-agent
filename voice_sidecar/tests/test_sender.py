from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tarkov_voice.config import ApiConfig
from tarkov_voice.sender import MarkerSender
from tarkov_voice.types import Hit


class _Server:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.received: list[tuple[dict[str, str], dict[str, object]]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                outer.received.append(({k.lower(): v for k, v in self.headers.items()}, body))
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"detail": "x"}')

            def log_message(self, *_args: object) -> None:
                return

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()


@pytest.fixture()
def server():
    servers: list[_Server] = []

    def make(status: int = 200) -> _Server:
        srv = _Server(status)
        servers.append(srv)
        return srv

    yield make
    for srv in servers:
        srv.close()


def _hit(marker_type: str | None = "contact.visual.player") -> Hit:
    return Hit(
        marker_type=marker_type,
        label="",
        confidence=0.8,
        occurred_at=1_800_000_000.0,
        details='"Spotted a guy."',
    )


def test_sends_structured_marker_with_token_time_and_confidence(server):
    srv = server(200)
    sender = MarkerSender(ApiConfig(port=srv.port, token="abc"))

    result = sender.send(_hit())

    assert result.status == "sent"
    headers, body = srv.received[0]
    assert headers["x-tpa-token"] == "abc"
    assert body["marker_type"] == "contact.visual.player"
    assert body["source"] == "voice"
    assert body["confidence"] == 0.8
    assert str(body["occurred_at"]).startswith("2027-01-15T")


def test_free_form_note_sends_label_and_category(server):
    srv = server(200)
    sender = MarkerSender(ApiConfig(port=srv.port))

    sender.send(_hit(None))

    _, body = srv.received[0]
    assert "marker_type" not in body
    assert body["label"] == "Voice note"
    assert body["category"] == "note"


@pytest.mark.parametrize(
    ("status", "expected"),
    [(409, "no_raid"), (401, "unauthorized"), (500, "rejected")],
)
def test_http_errors_are_classified(server, status, expected):
    srv = server(status)
    assert MarkerSender(ApiConfig(port=srv.port)).send(_hit()).status == expected


def test_unreachable_agent_is_reported_not_raised():
    result = MarkerSender(ApiConfig(port=1, timeout_s=0.5)).send(_hit())
    assert result.status == "unreachable"
