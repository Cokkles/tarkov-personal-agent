from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse

from tarkov_agent.app_context import AgentContext
from tarkov_agent.domain.recommendations import RecommendationPlan, RecommendationRequest, StrategyCandidate
from tarkov_agent.services.recommendations import RecommendationDisabledError, recommendation_to_markdown


def attach_recommendation_routes(app: FastAPI, context: AgentContext) -> None:
    @app.get("/recommendations", response_class=HTMLResponse, include_in_schema=False)
    async def recommendations_index() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "recommendations.html")

    @app.post("/api/recommendations/generate", response_model=RecommendationPlan)
    async def generate_recommendation(request: RecommendationRequest) -> RecommendationPlan:
        try:
            return context.recommendations.generate(request)
        except RecommendationDisabledError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/recommendations/templates", response_model=list[StrategyCandidate])
    async def recommendation_templates(request: RecommendationRequest) -> list[StrategyCandidate]:
        try:
            return context.recommendations.templates(request)
        except RecommendationDisabledError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/recommendations/latest", response_model=RecommendationPlan)
    async def latest_recommendation() -> RecommendationPlan:
        latest = context.recommendations.latest()
        if latest is None:
            raise HTTPException(status_code=404, detail="No recommendation plan has been generated")
        return latest

    @app.get("/api/recommendations/export/{format_name}")
    async def export_recommendation(format_name: str) -> Response:
        latest = context.recommendations.latest()
        if latest is None:
            raise HTTPException(status_code=404, detail="No recommendation plan has been generated")
        if format_name == "json":
            return Response(
                content=latest.model_dump_json(indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": 'attachment; filename="recommendation-plan.json"'
                },
            )
        if format_name == "markdown":
            return Response(
                content=recommendation_to_markdown(latest),
                media_type="text/markdown",
                headers={
                    "Content-Disposition": 'attachment; filename="recommendation-plan.md"'
                },
            )
        raise HTTPException(status_code=404, detail="Export format must be markdown or json")
