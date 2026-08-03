from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from tarkov_agent.app_context import AgentContext
from tarkov_agent.domain.source_truth import (
    ClaimRecord,
    ClaimResolution,
    ClaimStatus,
    ConflictRecord,
    MechanicsQuery,
    ReviewTask,
    SourceRecord,
)
from tarkov_agent.services.source_truth import (
    SourceTruthDisabledError,
    SourceTruthValidationError,
)


class ReviewTimestampRequest(BaseModel):
    reviewed_at: datetime | None = None


def attach_source_truth_routes(app: FastAPI, context: AgentContext) -> None:
    @app.get("/truth", response_class=HTMLResponse, include_in_schema=False)
    async def source_truth_index() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "source_truth.html")

    @app.get("/api/truth/status")
    async def source_truth_status() -> dict[str, object]:
        return context.truth.status()

    @app.get("/api/truth/sources", response_model=list[SourceRecord])
    async def source_truth_sources(
        limit: int = Query(default=1000, ge=1, le=10000),
    ) -> list[SourceRecord]:
        return context.truth.sources(limit=limit)

    @app.post("/api/truth/sources", response_model=SourceRecord)
    async def save_source(source: SourceRecord) -> SourceRecord:
        try:
            return context.truth.upsert_source(source)
        except SourceTruthDisabledError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except SourceTruthValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/truth/sources/{source_id}/review", response_model=SourceRecord)
    async def review_source(
        source_id: str,
        request: ReviewTimestampRequest,
    ) -> SourceRecord:
        try:
            return context.truth.mark_source_reviewed(
                source_id,
                reviewed_at=request.reviewed_at,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SourceTruthDisabledError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/truth/claims", response_model=list[ClaimRecord])
    async def source_truth_claims(
        key: str | None = Query(default=None, max_length=180),
        status: ClaimStatus | None = None,
        limit: int = Query(default=5000, ge=1, le=10000),
    ) -> list[ClaimRecord]:
        return context.truth.claims(key=key, status=status, limit=limit)

    @app.post("/api/truth/claims", response_model=ClaimRecord)
    async def save_claim(claim: ClaimRecord) -> ClaimRecord:
        try:
            return context.truth.upsert_claim(claim)
        except SourceTruthDisabledError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except SourceTruthValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/truth/claims/{claim_id}/review", response_model=ClaimRecord)
    async def review_claim(
        claim_id: str,
        request: ReviewTimestampRequest,
    ) -> ClaimRecord:
        try:
            return context.truth.mark_claim_reviewed(
                claim_id,
                reviewed_at=request.reviewed_at,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SourceTruthDisabledError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except SourceTruthValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/truth/conflicts", response_model=list[ConflictRecord])
    async def source_truth_conflicts(
        limit: int = Query(default=5000, ge=1, le=10000),
    ) -> list[ConflictRecord]:
        return context.truth.conflicts(limit=limit)

    @app.post("/api/truth/conflicts/rebuild", response_model=list[ConflictRecord])
    async def rebuild_source_truth_conflicts() -> list[ConflictRecord]:
        try:
            return context.truth.rebuild_conflicts()
        except SourceTruthDisabledError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/truth/review-queue", response_model=list[ReviewTask])
    async def source_truth_review_queue() -> list[ReviewTask]:
        return context.truth.review_queue()

    @app.post("/api/truth/query", response_model=ClaimResolution)
    async def query_source_truth(request: MechanicsQuery) -> ClaimResolution:
        try:
            return context.truth.query(request)
        except SourceTruthDisabledError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/truth/export/{format_name}")
    async def export_source_truth(format_name: str) -> Response:
        try:
            if format_name == "markdown":
                return Response(
                    content=context.truth.export_markdown(),
                    media_type="text/markdown",
                    headers={
                        "Content-Disposition": (
                            'attachment; filename="tarkov-source-truth.md"'
                        )
                    },
                )
            if format_name == "json":
                return Response(
                    content=context.truth.export_json(),
                    media_type="application/json",
                    headers={
                        "Content-Disposition": (
                            'attachment; filename="tarkov-source-truth.json"'
                        )
                    },
                )
        except SourceTruthDisabledError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(
            status_code=404,
            detail="Export format must be markdown or json",
        )
