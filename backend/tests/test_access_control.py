from __future__ import annotations

from .conftest import auth_headers, seed_access


def test_chat_endpoint_requires_authentication(client) -> None:
    response = client.post("/chatkit", content=b"{}")
    assert response.status_code == 401


def test_chat_endpoint_rejects_invalid_token(client) -> None:
    response = client.post(
        "/chatkit",
        headers={"Authorization": "Bearer wrong-token"},
        content=b"{}",
    )
    assert response.status_code == 401


def test_chat_endpoint_rejects_unpaid_user(client) -> None:
    response = client.post("/chatkit", headers=auth_headers(), content=b"{}")
    assert response.status_code == 403


def test_chat_endpoint_allows_paid_user(app, client) -> None:
    seed_access(
        app,
        has_access=True,
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        stripe_subscription_status="active",
    )

    response = client.post("/chatkit", headers=auth_headers(), content=b"{}")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_access_snapshot_returns_customer_state(app, client) -> None:
    seed_access(
        app,
        has_access=True,
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        stripe_subscription_status="active",
    )

    response = client.get("/api/me/access", headers=auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["auth0_user_id"] == "auth0|user_123"
    assert payload["has_access"] is True
    assert payload["can_manage_billing"] is True
