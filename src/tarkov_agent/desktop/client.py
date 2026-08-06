from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tarkov_agent.config import AppSettings
from tarkov_agent.domain.desktop import DesktopStatus
from tarkov_agent.domain.finalization import FinalizationJob
from tarkov_agent.domain.models import MarkerCommand, RaidRecord


class DesktopApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def desktop_base_url(settings: AppSettings) -> str:
    host = settings.api.host
    if host == "0.0.0.0":
        host = "127.0.0.1"
    elif host == "::":
        host = "::1"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{settings.api.port}"


class DesktopApiClient:
    def __init__(
        self,
        settings: AppSettings,
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        self._settings = settings
        self.base_url = desktop_base_url(settings)
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.desktop.request_timeout_seconds
        )

    def is_available(self) -> bool:
        try:
            payload = self._request("GET", "/api/health")
        except DesktopApiError:
            return False
        return isinstance(payload, Mapping) and payload.get("ok") is True

    def status(self) -> DesktopStatus:
        payload = self._request("GET", "/api/desktop/status")
        return DesktopStatus.model_validate(payload)

    def list_raids(self, *, limit: int = 30) -> list[RaidRecord]:
        payload = self._request("GET", f"/api/raids?limit={limit}")
        if not isinstance(payload, list):
            raise DesktopApiError("Raid list API returned an unexpected response")
        return [RaidRecord.model_validate(item) for item in payload]

    def review_queue(self, *, limit: int = 30) -> list[RaidRecord]:
        payload = self._request("GET", f"/api/review-queue?limit={limit}")
        if not isinstance(payload, list):
            raise DesktopApiError("Review queue API returned an unexpected response")
        return [RaidRecord.model_validate(item) for item in payload]

    def timeline(self, raid_id: str) -> list[dict[str, Any]]:
        payload = self._request("GET", f"/api/raids/{raid_id}/timeline")
        if not isinstance(payload, list):
            raise DesktopApiError("Timeline API returned an unexpected response")
        rows: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            rows.append({str(key): value for key, value in item.items()})
        return rows

    def raid_bundle(self, raid_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/api/raids/{raid_id}")
        if not isinstance(payload, Mapping):
            raise DesktopApiError("Raid detail API returned an unexpected response")
        return {str(key): value for key, value in payload.items()}

    def start_raid(
        self,
        *,
        map_name: str | None,
        character_type: str | None,
        primary_objective: str | None,
        secondary_objective: str | None = None,
    ) -> RaidRecord:
        payload = self._request(
            "POST",
            "/api/control/raid/start",
            {
                "game": "tarkov",
                "map_name": map_name,
                "character_type": character_type,
                "primary_objective": primary_objective,
                "secondary_objective": secondary_objective,
            },
        )
        return RaidRecord.model_validate(payload)

    def end_raid(self, *, result: str | None) -> FinalizationJob:
        payload = self._request(
            "POST",
            "/api/control/raid/end",
            {"result": result},
        )
        return FinalizationJob.model_validate(payload)

    def finalization_job(self, job_id: str) -> FinalizationJob:
        payload = self._request("GET", f"/api/finalization/jobs/{job_id}")
        return FinalizationJob.model_validate(payload)

    def retry_finalization(self, job_id: str) -> FinalizationJob:
        payload = self._request(
            "POST",
            f"/api/finalization/jobs/{job_id}/retry",
            {},
        )
        return FinalizationJob.model_validate(payload)

    def abort_raid(self, *, reason: str | None) -> RaidRecord:
        payload = self._request(
            "POST",
            "/api/control/raid/abort",
            {"reason": reason},
        )
        return RaidRecord.model_validate(payload)

    def add_marker(self, command: MarkerCommand) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "/api/markers",
            command.model_dump(mode="json"),
        )
        if not isinstance(payload, dict):
            raise DesktopApiError("Marker API returned an unexpected response")
        return {str(key): value for key, value in payload.items()}

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, object] | None = None,
    ) -> object:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self._settings.api.token:
            headers["X-TPA-Token"] = self._settings.api.token
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers=headers,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
        except HTTPError as exc:
            detail = self._http_error_detail(exc)
            raise DesktopApiError(
                detail,
                status_code=exc.code,
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise DesktopApiError(
                f"Local agent service is unavailable: {exc}"
            ) from exc
        if not body:
            return None
        try:
            decoded: object = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DesktopApiError(
                "Local agent service returned invalid JSON"
            ) from exc
        return decoded

    @staticmethod
    def _http_error_detail(exc: HTTPError) -> str:
        try:
            body = exc.read()
            payload: object = json.loads(body.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return f"Agent API request failed with HTTP {exc.code}"
        if isinstance(payload, dict) and payload.get("detail"):
            return str(payload["detail"])
        return f"Agent API request failed with HTTP {exc.code}"
