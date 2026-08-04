from __future__ import annotations

from fastapi import FastAPI

from tarkov_agent.api.app import create_app as create_core_app
from tarkov_agent.api.media import attach_media_routes
from tarkov_agent.api.recommendations import attach_recommendation_routes
from tarkov_agent.api.source_truth import attach_source_truth_routes
from tarkov_agent.app_context import AgentContext


def create_app(context: AgentContext, *, start_runtime: bool = True) -> FastAPI:
    app = create_core_app(context, start_runtime=start_runtime)
    attach_source_truth_routes(app, context)
    attach_recommendation_routes(app, context)
    attach_media_routes(app, context)
    return app
