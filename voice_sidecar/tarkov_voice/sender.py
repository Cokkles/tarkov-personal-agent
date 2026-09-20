from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tarkov_voice.config import ApiConfig
from tarkov_voice.types import Hit

log = logging.getLogger("tarkov_voice.sender")


@dataclass(frozen=True, slots=True)
class SendResult:
    status: str  # "sent", "no_raid", "unauthorized", "unreachable", "rejected"
    detail: str = ""


class MarkerSender:
    """Posts markers to the Tarkov Personal Agent API (POST /api/markers)."""

    def __init__(self, config: ApiConfig) -> None:
        self._config = config
        self._url = f"http://{config.host}:{config.port}/api/markers"

    def send(self, hit: Hit) -> SendResult:
        payload: dict[str, object] = {
            "source": "voice",
            "request_id": str(uuid.uuid4()),
            "details": hit.details,
            # Ignored by an unpatched agent; used once the occurred_at/confidence patch is applied.
            "occurred_at": datetime.fromtimestamp(hit.occurred_at, tz=UTC).isoformat(),
            "confidence": hit.confidence,
        }
        if hit.marker_type is not None:
            payload["marker_type"] = hit.marker_type
        else:
            payload["label"] = hit.label or "Voice note"
            payload["category"] = "note"

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._config.token:
            headers["X-TPA-Token"] = self._config.token

        request = Request(
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._config.timeout_s) as response:  # noqa: S310
                response.read()
            return SendResult("sent")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:200]
            if exc.code == 409:
                return SendResult("no_raid", body)
            if exc.code == 401:
                return SendResult("unauthorized", body)
            return SendResult("rejected", f"HTTP {exc.code}: {body}")
        except (URLError, TimeoutError, OSError) as exc:
            return SendResult("unreachable", str(exc))
