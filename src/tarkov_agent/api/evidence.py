from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from tarkov_agent.app_context import AgentContext
from tarkov_agent.domain.evidence import (
    EvidenceBundleManifest,
    EvidenceBundleRequest,
    EvidenceBundleResult,
)
from tarkov_agent.services.evidence import (
    EvidenceBundleError,
    EvidenceIntelligenceDisabledError,
)


def attach_evidence_routes(app: FastAPI, context: AgentContext) -> None:
    @app.post(
        "/api/raids/{raid_id}/evidence/preview",
        response_model=EvidenceBundleManifest,
    )
    async def preview_evidence(
        raid_id: UUID,
        request: EvidenceBundleRequest,
    ) -> EvidenceBundleManifest:
        try:
            return context.evidence.preview(raid_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (EvidenceIntelligenceDisabledError, EvidenceBundleError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/raids/{raid_id}/evidence/build",
        response_model=EvidenceBundleResult,
    )
    async def build_evidence(
        raid_id: UUID,
        request: EvidenceBundleRequest,
    ) -> EvidenceBundleResult:
        try:
            return context.evidence.build(raid_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (EvidenceIntelligenceDisabledError, EvidenceBundleError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/raids/{raid_id}/evidence/latest")
    async def latest_evidence(raid_id: UUID) -> FileResponse:
        try:
            archive = context.evidence.latest_archive(raid_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if archive is None:
            raise HTTPException(status_code=404, detail="No evidence bundle has been built")
        return FileResponse(
            archive,
            media_type="application/zip",
            filename=archive.name,
        )
