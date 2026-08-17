"""Minimal FastAPI app factory for local development."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hub.api.security import ApiTokenMiddleware

from hub.api.routes_api_actions import router as api_actions_router
from hub.api.routes_agents import router as agents_router
from hub.api.routes_apps import router as apps_router
from hub.api.routes_bridge import router as bridge_router
from hub.api.routes_clipboard import router as clipboard_router
from hub.api.routes_commands import router as commands_router
from hub.api.routes_file_actions import router as file_actions_router
from hub.api.routes_file_cache import router as file_cache_router
from hub.api.routes_fis import router as fis_router
from hub.api.routes_folders import router as folders_router
from hub.api.routes_intelligence import router as intelligence_router
from hub.api.routes_jobs import router as jobs_router
from hub.api.routes_memory import router as memory_router
from hub.api.routes_nodes import router as nodes_router
from hub.api.routes_openai_compat import router as openai_compat_router
from hub.api.routes_prediction import router as prediction_router
from hub.api.routes_providers import router as providers_router
from hub.api.routes_semantic import router as semantic_router
from hub.api.routes_top_of_mind import router as top_of_mind_router


def create_app() -> FastAPI:
    app = FastAPI(title="File Intelligence Hub", version="0.1.0")
    app.include_router(jobs_router)
    app.include_router(api_actions_router)
    app.include_router(agents_router)
    app.include_router(apps_router)
    app.include_router(bridge_router)
    app.include_router(clipboard_router)
    app.include_router(commands_router)
    app.include_router(file_actions_router)
    app.include_router(file_cache_router)
    app.include_router(fis_router)
    app.include_router(folders_router)
    app.include_router(intelligence_router)
    app.include_router(memory_router)
    app.include_router(nodes_router)
    app.include_router(openai_compat_router)
    app.include_router(prediction_router)
    app.include_router(providers_router)
    app.include_router(semantic_router)
    app.include_router(top_of_mind_router)
    app.add_middleware(ApiTokenMiddleware)
    # CORS must be added LAST so it is the outermost middleware: browser
    # preflight (OPTIONS) requests and 401 responses then still carry CORS
    # headers. The desk UI (Vite dev server, any localhost/127.0.0.1 port)
    # calls this API cross-origin, so without this middleware every fetch
    # fails in the browser even when the API is up ("Failed to load
    # messages" / offline indicator in Top of Mind Desk).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()
