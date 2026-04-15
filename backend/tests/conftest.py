from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.auth import AuthenticatedUser
from app.config import Settings
from app.main import create_app, get_chatkit_server


class StubTokenVerifier:
    def verify(self, token: str) -> AuthenticatedUser:
        if token != "test-token":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token.",
            )
        return AuthenticatedUser(
            sub="auth0|user_123",
            email="user@example.com",
            claims={"sub": "auth0|user_123", "email": "user@example.com"},
        )


class FakeChatServer:
    async def process(self, payload: bytes, context: dict[str, object]) -> dict[str, bool]:
        return {"ok": True}

    async def suggest_prompts(self, thread_id: str | None, context: dict[str, object]) -> dict[str, object]:
        return {"hasHistory": False, "suggestions": []}


def run_migrations(database_url: str) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url


@pytest.fixture
def app(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    run_migrations(database_url)

    settings = Settings(
        database_url=database_url,
        vite_auth0_domain="dev-example.us.auth0.com",
        vite_auth0_client_id="client_test_123",
        vite_auth0_audience="https://api.example.test",
        vite_chatkit_api_domain_key="domain_pk_localhost_dev",
    )

    app = create_app(settings)
    app.dependency_overrides[get_token_verifier] = lambda: StubTokenVerifier()
    app.dependency_overrides[get_chatkit_server] = lambda: FakeChatServer()
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}
