from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from tarkov_agent.app_context import AgentContext
from tarkov_agent.domain.models import EvidenceKind, Game, MarkerCommand, RaidRecord
from tarkov_agent.domain.reviews import RaidReview
from tarkov_agent.services.control import ControlConflictError, EvidencePathError
from tarkov_agent.services.markers import NoActiveRaidError
from tarkov_agent.services.reviews import ReviewConflictError, ReviewNotFoundError


class TokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, *, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path.startswith("/api/") and self._token:
            supplied = request.headers.get("X-TPA-Token") or request.query_params.get(
                "token", ""
            )
            if not secrets.compare_digest(supplied, self._token):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid API token"},
                )
        return await call_next(request)


class ManualRaidStartRequest(BaseModel):
    game: Game = Game.TARKOV
    map_name: str | None = Field(default=None, max_length=160)
    character_type: str | None = Field(default=None, max_length=80)
    primary_objective: str | None = Field(default=None, max_length=500)
    secondary_objective: str | None = Field(default=None, max_length=500)


class ManualRaidEndRequest(BaseModel):
    result: str | None = Field(default=None, max_length=80)


class ManualRaidAbortRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ReviewUpdateRequest(BaseModel):
    review: RaidReview
    expected_version: int | None = Field(default=None, ge=0)
    actor: str = Field(default="local-user", max_length=120)


class EvidenceReferenceRequest(BaseModel):
    path: str
    kind: EvidenceKind
    copy_into_package: bool = False


def create_app(context: AgentContext, *, start_runtime: bool = True) -> FastAPI:
    runtime_task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        nonlocal runtime_task
        context.recover_interrupted_session()
        if start_runtime:
            runtime_task = asyncio.create_task(
                context.runtime.run(),
                name="companion-runtime",
            )
        try:
            yield
        finally:
            if runtime_task is not None:
                context.runtime.request_stop()
                try:
                    await asyncio.wait_for(
                        runtime_task,
                        timeout=context.settings.runtime.graceful_shutdown_seconds,
                    )
                except TimeoutError:
                    runtime_task.cancel()
                    await asyncio.gather(runtime_task, return_exceptions=True)

    app = FastAPI(
        title="Tarkov Personal Agent",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.add_middleware(TokenAuthMiddleware, token=context.settings.api.token)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return {"ok": True, "version": "0.2.0"}

    @app.get("/api/status")
    async def agent_status() -> dict[str, object]:
        active = context.coordinator.active_raid
        queue = context.recovery.pending(limit=100)
        return {
            "lifecycle_state": context.coordinator.lifecycle.state.value,
            "active_raid": active,
            "review_queue_count": len(queue),
            "automatic_log_rules": len(context.settings.logs.rules),
            "obs_enabled": context.settings.obs.enabled,
        }

    @app.get("/api/raids", response_model=list[RaidRecord])
    async def list_raids(
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> list[RaidRecord]:
        return context.repository.list_raids(limit=limit)

    @app.get("/api/review-queue", response_model=list[RaidRecord])
    async def review_queue(
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> list[RaidRecord]:
        return context.recovery.pending(limit=limit)

    @app.get("/api/raids/{raid_id}")
    async def get_raid(raid_id: str) -> dict[str, object]:
        raid = context.repository.get_raid(raid_id)
        if raid is None:
            raise HTTPException(status_code=404, detail="Raid not found")
        return {
            "raid": raid,
            "timeline": context.repository.list_timeline_events(raid_id),
            "review": context.reviews.get_or_create(raid_id),
        }

    @app.get("/api/raids/{raid_id}/timeline")
    async def timeline(raid_id: str) -> list[object]:
        if context.repository.get_raid(raid_id) is None:
            raise HTTPException(status_code=404, detail="Raid not found")
        return list(context.repository.list_timeline_events(raid_id))

    @app.get("/api/raids/{raid_id}/review", response_model=RaidReview)
    async def get_review(raid_id: str) -> RaidReview:
        try:
            return context.reviews.get_or_create(raid_id, actor="api")
        except ReviewNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/raids/{raid_id}/review", response_model=RaidReview)
    async def save_review(
        raid_id: str,
        request: ReviewUpdateRequest,
    ) -> RaidReview:
        try:
            return context.reviews.save(
                raid_id,
                request.review,
                expected_version=request.expected_version,
                actor=request.actor,
            )
        except ReviewNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ReviewConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/raids/{raid_id}/review/finalize", response_model=RaidReview)
    async def finalize_review(
        raid_id: str,
        request: ReviewUpdateRequest,
    ) -> RaidReview:
        try:
            return context.reviews.finalize(
                raid_id,
                request.review,
                expected_version=request.expected_version,
                actor=request.actor,
            )
        except ReviewNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ReviewConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/raids/{raid_id}/review/audit")
    async def review_audit(raid_id: str) -> list[object]:
        try:
            return list(context.reviews.audit_history(raid_id))
        except ReviewNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/raids/{raid_id}/export/{format_name}")
    async def export_review(raid_id: str, format_name: str) -> Response:
        raid = context.repository.get_raid(raid_id)
        if raid is None:
            raise HTTPException(status_code=404, detail="Raid not found")
        review = context.reviews.get_or_create(raid_id)
        if format_name == "markdown":
            content = context.reviews.markdown(raid_id)
            return Response(
                content=content,
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f'attachment; filename="raid-{raid_id}.md"'
                },
            )
        if format_name == "json":
            return Response(
                content=review.model_dump_json(indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="raid-{raid_id}.json"'
                },
            )
        raise HTTPException(
            status_code=404,
            detail="Export format must be markdown or json",
        )

    @app.post("/api/control/raid/start", response_model=RaidRecord)
    async def start_raid(request: ManualRaidStartRequest) -> RaidRecord:
        try:
            return context.controls.start_raid(request.model_dump(mode="json"))
        except ControlConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/control/raid/end", response_model=RaidRecord)
    async def end_raid(request: ManualRaidEndRequest) -> RaidRecord:
        try:
            return context.controls.end_raid(result=request.result)
        except ControlConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/control/raid/abort", response_model=RaidRecord)
    async def abort_raid(request: ManualRaidAbortRequest) -> RaidRecord:
        try:
            return context.controls.abort_raid(reason=request.reason)
        except ControlConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/markers")
    async def add_marker(command: MarkerCommand) -> object:
        try:
            return context.controls.marker(command)
        except NoActiveRaidError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/raids/{raid_id}/evidence")
    async def attach_evidence(
        raid_id: str,
        request: EvidenceReferenceRequest,
    ) -> dict[str, Any]:
        try:
            attached = context.controls.attach_evidence(
                raid_id,
                request.path,
                request.kind,
                copy_into_package=request.copy_into_package,
            )
            return {"raid": attached.raid, "evidence_id": attached.evidence_id}
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except EvidencePathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
