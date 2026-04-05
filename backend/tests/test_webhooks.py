from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from .conftest import auth_headers


def test_subscription_webhook_updates_and_revokes_access(app, client) -> None:
    event = {
        "id": "evt_sub_updated",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_123",
                "status": "active",
                "current_period_end": 1893456000,
                "metadata": {"auth0_user_id": "auth0|user_123"},
                "items": {
                    "data": [
                        {
                            "price": {"id": "price_test_123"},
                        }
                    ]
                },
            }
        },
    }
    app.state.fake_billing_service.webhook_event = event

    first_response = client.post(
        "/api/stripe/webhook",
        content=b"{}",
        headers={"stripe-signature": "sig_test"},
    )
    second_response = client.post(
        "/api/stripe/webhook",
        content=b"{}",
        headers={"stripe-signature": "sig_test"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    access_response = client.get("/api/me/access", headers=auth_headers())
    assert access_response.status_code == 200
    assert access_response.json()["has_access"] is True

    delete_event = {
        "id": "evt_sub_deleted",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_123",
                "status": "canceled",
                "current_period_end": 1893456000,
                "metadata": {"auth0_user_id": "auth0|user_123"},
                "items": {
                    "data": [
                        {
                            "price": {"id": "price_test_123"},
                        }
                    ]
                },
            }
        },
    }
    app.state.fake_billing_service.webhook_event = delete_event

    delete_response = client.post(
        "/api/stripe/webhook",
        content=b"{}",
        headers={"stripe-signature": "sig_test"},
    )

    assert delete_response.status_code == 200
    revoked_response = client.get("/api/me/access", headers=auth_headers())
    assert revoked_response.json()["has_access"] is False


def test_invalid_webhook_signature_is_rejected(app, client) -> None:
    app.state.fake_billing_service.raise_on_construct = ValueError("Invalid signature")

    response = client.post(
        "/api/stripe/webhook",
        content=b"{}",
        headers={"stripe-signature": "sig_test"},
    )

    assert response.status_code == 400


def test_alembic_upgrade_creates_expected_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "migration-test.db"
    database_url = f"sqlite:///{database_path}"
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    table_names = {row[0] for row in rows}
    assert {"customer_access", "stripe_webhook_events", "chat_threads", "chat_items"} <= table_names
