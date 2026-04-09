from __future__ import annotations

from datetime import datetime, timezone

from .conftest import auth_headers, seed_access


def test_checkout_session_carries_auth0_subject(app, client) -> None:
    response = client.post("/api/billing/checkout-session", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["url"] == "https://checkout.stripe.test/session"
    assert app.state.fake_billing_service.checkout_args == ("auth0|user_123", None)


def test_portal_session_uses_existing_customer(app, client) -> None:
    seed_access(
        app,
        has_access=False,
        stripe_customer_id="cus_123",
        stripe_subscription_status="past_due",
    )

    response = client.post("/api/billing/portal-session", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["url"] == "https://billing.stripe.test/session"
    assert app.state.fake_billing_service.portal_customer_id == "cus_123"


def test_cancel_at_period_end_requires_owned_subscription(app, client) -> None:
    seed_access(
        app,
        has_access=True,
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        stripe_subscription_status="active",
    )

    response = client.post(
        "/api/billing/subscriptions/sub_123/cancel-at-period-end",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stripe_subscription_id"] == "sub_123"
    assert payload["cancel_at_period_end"] is True
    assert payload["current_period_end"] == "2030-01-01T00:00:00Z"
    assert app.state.fake_billing_service.cancel_subscription_id == "sub_123"

    access_response = client.get("/api/me/access", headers=auth_headers())
    assert access_response.status_code == 200
    access_payload = access_response.json()
    assert access_payload["cancel_at_period_end"] is True
    assert access_payload["current_period_end"] == "2030-01-01T00:00:00"


def test_cancel_at_period_end_rejects_other_users_subscription(app, client) -> None:
    seed_access(
        app,
        has_access=True,
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_owned",
        stripe_subscription_status="active",
    )

    response = client.post(
        "/api/billing/subscriptions/sub_other/cancel-at-period-end",
        headers=auth_headers(),
    )

    assert response.status_code == 404


def test_cancel_at_period_end_handles_unexpected_service_failure(app, client) -> None:
    seed_access(
        app,
        has_access=True,
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        stripe_subscription_status="active",
    )
    app.state.fake_billing_service.raise_on_cancel = RuntimeError("boom")

    response = client.post(
        "/api/billing/subscriptions/sub_123/cancel-at-period-end",
        headers=auth_headers(),
    )

    assert response.status_code == 502
    assert "Unable to schedule end of subscription" in response.json()["detail"]


def test_cancel_at_period_end_falls_back_to_local_period_end(app, client) -> None:
    seed_access(
        app,
        has_access=True,
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        stripe_subscription_status="active",
        current_period_end=datetime(2030, 2, 1, tzinfo=timezone.utc),
    )
    app.state.fake_billing_service.cancel_response_current_period_end = None

    response = client.post(
        "/api/billing/subscriptions/sub_123/cancel-at-period-end",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert response.json()["current_period_end"] == "2030-02-01T00:00:00"

    access_response = client.get("/api/me/access", headers=auth_headers())
    assert access_response.status_code == 200
    assert access_response.json()["cancel_at_period_end"] is True
    assert access_response.json()["current_period_end"] == "2030-02-01T00:00:00"
