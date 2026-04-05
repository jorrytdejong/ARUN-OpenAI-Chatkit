from __future__ import annotations

import asyncio
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
from app.main import create_app, get_billing_service, get_chatkit_server
from app.models import CustomerAccess


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


class FakeBillingService:
    def __init__(self) -> None:
        self.checkout_args: tuple[str, str | None] | None = None
        self.portal_customer_id: str | None = None
        self.webhook_event: dict[str, object] | None = None
        self.raise_on_construct: Exception | None = None

    def create_checkout_session(self, *, user: AuthenticatedUser, stripe_customer_id: str | None) -> str:
        self.checkout_args = (user.sub, stripe_customer_id)
        return "https://checkout.stripe.test/session"

    def create_billing_portal_session(self, *, stripe_customer_id: str) -> str:
        self.portal_customer_id = stripe_customer_id
        return "https://billing.stripe.test/session"

    def construct_event(self, payload: bytes, signature: str | None) -> dict[str, object]:
        del payload
        del signature
        if self.raise_on_construct is not None:
            raise self.raise_on_construct
        if self.webhook_event is None:
            raise ValueError("No webhook event configured for the test.")
        return self.webhook_event


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
        app_base_url="http://localhost:3000",
        vite_auth0_domain="dev-example.us.auth0.com",
        vite_auth0_client_id="client_test_123",
        vite_auth0_audience="https://api.example.test",
        vite_chatkit_api_domain_key="domain_pk_localhost_dev",
        stripe_secret_key="sk_test_123",
        stripe_webhook_secret="whsec_test_123",
        stripe_price_id="price_test_123",
    )

    app = create_app(settings)
    app.dependency_overrides[get_token_verifier] = lambda: StubTokenVerifier()
    app.dependency_overrides[get_chatkit_server] = lambda: FakeChatServer()
    fake_billing_service = FakeBillingService()
    app.dependency_overrides[get_billing_service] = lambda: fake_billing_service
    app.state.fake_billing_service = fake_billing_service
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def seed_access(
    app,
    *,
    has_access: bool,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    stripe_subscription_status: str | None = None,
) -> None:
    async def _seed() -> None:
        async with app.state.session_factory() as session:
            session.add(
                CustomerAccess(
                    auth0_user_id="auth0|user_123",
                    stripe_customer_id=stripe_customer_id,
                    stripe_subscription_id=stripe_subscription_id,
                    stripe_subscription_status=stripe_subscription_status,
                    stripe_price_id="price_test_123",
                    has_access=has_access,
                )
            )
            await session.commit()

    asyncio.run(_seed())
