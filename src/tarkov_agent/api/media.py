from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from tarkov_agent.app_context import AgentContext
from tarkov_agent.domain.media import (
    ClipRequest,
    MediaClip,
    MediaNavigationPoint,
    MediaSource,
    RaidMediaIndex,
    RecordingAsset,
)
from tarkov_agent.services.media import (
    MediaDisabledError,
    MediaFinalizationError,
    MediaPathError,
    MediaToolError,
)


class RecordingIndexRequest(BaseModel):
    path: Path
    copy_into_package: bool | None = None


class RecordingIndexResponse(BaseModel):
    recording: RecordingAsset


class ClipResponse(BaseModel):
    clip: MediaClip


def attach_media_routes(app: FastAPI, context: AgentContext) -> None:
    @app.get("/media", response_class=HTMLResponse, include_in_schema=False)
    async def media_index() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "media.html")

    @app.get(
        "/api/raids/{raid_id}/media",
        response_model=RaidMediaIndex,
    )
    async def raid_media(raid_id: UUID) -> RaidMediaIndex:
        try:
            return context.media.index_for_raid(raid_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/raids/{raid_id}/media/navigation",
        response_model=list[MediaNavigationPoint],
    )
    async def raid_media_navigation(
        raid_id: UUID,
    ) -> list[MediaNavigationPoint]:
        try:
            return context.media.navigation_for_raid(raid_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/raids/{raid_id}/media/recordings",
        response_model=RecordingIndexResponse,
    )
    async def index_recording(
        raid_id: UUID,
        request: RecordingIndexRequest,
    ) -> RecordingIndexResponse:
        try:
            _, recording = context.media.index_recording(
                raid_id,
                request.path,
                media_source=MediaSource.MANUAL,
                copy_into_package=request.copy_into_package,
            )
            return RecordingIndexResponse(recording=recording)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (MediaDisabledError, MediaFinalizationError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except MediaPathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/raids/{raid_id}/media/clips",
        response_model=ClipResponse,
    )
    async def extract_clip(
        raid_id: UUID,
        request: ClipRequest,
    ) -> ClipResponse:
        try:
            _, clip = context.media.extract_clip(raid_id, request)
            return ClipResponse(clip=clip)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (MediaDisabledError, MediaFinalizationError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except MediaToolError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post(
        "/api/raids/{raid_id}/media/refresh",
        response_model=RaidMediaIndex,
    )
    async def refresh_media(raid_id: UUID) -> RaidMediaIndex:
        try:
            return context.media.refresh_availability(raid_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
