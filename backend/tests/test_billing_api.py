from __future__ import annotations

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
