"""FastAPI entrypoint for the ChatKit starter backend."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from chatkit.server import StreamingResult
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from .auth import Auth0TokenVerifier, AuthenticatedUser, require_authenticated_user
from .chat_store import PostgresChatStore
from .config import Settings, get_settings
from .database import create_engine_and_session_factory
from .server import StarterChatServer


FRONTEND_DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_INDEX_PATH = FRONTEND_DIST_DIR / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    engine, session_factory = create_engine_and_session_factory(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.token_verifier = Auth0TokenVerifier(settings)
    app.state.chatkit_server = None

    try:
        yield
    finally:
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(title="ChatKit Starter API", lifespan=lifespan)
    app.state.settings = resolved_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/chatkit-config.js")
    async def chatkit_config(request: Request) -> Response:
        current_settings = request.app.state.settings
        config = {
            "apiUrl": current_settings.vite_chatkit_api_url,
            "domainKey": current_settings.vite_chatkit_api_domain_key,
            "auth0Domain": current_settings.vite_auth0_domain,
            "auth0ClientId": current_settings.vite_auth0_client_id,
            "auth0Audience": current_settings.vite_auth0_audience,
        }
        body = f"window.__CHATKIT_CONFIG__ = {json.dumps(config)};"
        return Response(content=body, media_type="application/javascript")

    @app.post("/chatkit")
    async def chatkit_endpoint(
        request: Request,
        user: AuthenticatedUser = Depends(require_authenticated_user),
        chatkit_server: StarterChatServer = Depends(get_chatkit_server),
    ) -> Response:
        payload = await request.body()
        result = await chatkit_server.process(
            payload,
            {"request": request, "auth_user": user},
        )

        if isinstance(result, StreamingResult):
            return StreamingResponse(result, media_type="text/event-stream")
        if hasattr(result, "json"):
            return Response(content=result.json, media_type="application/json")
        return JSONResponse(result)

    @app.get("/chatkit/suggestions")
    async def starter_suggestions(
        request: Request,
        user: AuthenticatedUser = Depends(require_authenticated_user),
        chatkit_server: StarterChatServer = Depends(get_chatkit_server),
    ) -> Response:
        suggestions = await chatkit_server.suggest_prompts(
            None,
            {"request": request, "auth_user": user},
        )
        payload = suggestions.model_dump() if hasattr(suggestions, "model_dump") else suggestions
        return JSONResponse(payload)

    @app.get("/chatkit/threads/{thread_id}/suggestions")
    async def thread_suggestions(
        thread_id: str,
        request: Request,
        user: AuthenticatedUser = Depends(require_authenticated_user),
        chatkit_server: StarterChatServer = Depends(get_chatkit_server),
    ) -> Response:
        suggestions = await chatkit_server.suggest_prompts(
            thread_id,
            {"request": request, "auth_user": user},
        )
        payload = suggestions.model_dump() if hasattr(suggestions, "model_dump") else suggestions
        return JSONResponse(payload)

    @app.get("/{full_path:path}")
    async def frontend_app(full_path: str) -> Response:
        if not FRONTEND_INDEX_PATH.exists():
            return JSONResponse(
                {
                    "error": "Frontend build not found.",
                    "details": "Build chatkit/frontend before starting the production app.",
                },
                status_code=503,
            )

        asset_path = (FRONTEND_DIST_DIR / full_path).resolve()
        if full_path and asset_path.is_file() and FRONTEND_DIST_DIR in asset_path.parents:
            return FileResponse(asset_path)
        return FileResponse(FRONTEND_INDEX_PATH)

    return app


def get_chatkit_server(request: Request) -> StarterChatServer:
    chatkit_server = request.app.state.chatkit_server
    if chatkit_server is None:
        store = PostgresChatStore(request.app.state.session_factory)
        chatkit_server = StarterChatServer(store=store)
        request.app.state.chatkit_server = chatkit_server
    return chatkit_server


app = create_app()
