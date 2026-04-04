"""FastAPI entrypoint for the ChatKit starter backend."""

from __future__ import annotations

import json
import os
from pathlib import Path

from chatkit.server import StreamingResult
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from .server import StarterChatServer

app = FastAPI(title="ChatKit Starter API")
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_INDEX_PATH = FRONTEND_DIST_DIR / "index.html"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chatkit_server = StarterChatServer()


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/chatkit-config.js")
async def chatkit_config() -> Response:
    config = {
        "apiUrl": os.environ.get("VITE_CHATKIT_API_URL", "/chatkit"),
        "domainKey": os.environ.get("VITE_CHATKIT_API_DOMAIN_KEY", ""),
    }
    body = f"window.__CHATKIT_CONFIG__ = {json.dumps(config)};"
    return Response(content=body, media_type="application/javascript")


@app.post("/chatkit")
async def chatkit_endpoint(request: Request) -> Response:
    """Proxy the ChatKit web component payload to the server implementation."""
    payload = await request.body()
    result = await chatkit_server.process(payload, {"request": request})

    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    if hasattr(result, "json"):
        return Response(content=result.json, media_type="application/json")
    return JSONResponse(result)


@app.get("/chatkit/suggestions")
async def starter_suggestions(request: Request) -> Response:
    suggestions = await chatkit_server.suggest_prompts(None, {"request": request})
    return JSONResponse(suggestions.model_dump())


@app.get("/chatkit/threads/{thread_id}/suggestions")
async def thread_suggestions(thread_id: str, request: Request) -> Response:
    suggestions = await chatkit_server.suggest_prompts(thread_id, {"request": request})
    return JSONResponse(suggestions.model_dump())


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
