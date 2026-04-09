from __future__ import annotations

from app.billing import BillingService
from app.config import Settings


def test_cancel_at_period_end_retrieves_subscription_when_modify_omits_period_end(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_modify(subscription_id: str, cancel_at_period_end: bool):
        captured["modified"] = (subscription_id, cancel_at_period_end)
        return {
            "id": subscription_id,
            "status": "active",
            "cancel_at_period_end": True,
            "current_period_end": None,
            "canceled_at": None,
        }

    def fake_retrieve(subscription_id: str):
        captured["retrieved"] = subscription_id
        return {
            "id": subscription_id,
            "status": "active",
            "cancel_at_period_end": True,
            "current_period_end": 1893456000,
            "canceled_at": 1890864000,
        }

    monkeypatch.setattr("app.billing.stripe.Subscription.modify", fake_modify)
    monkeypatch.setattr("app.billing.stripe.Subscription.retrieve", fake_retrieve)

    service = BillingService(
        Settings(
            stripe_secret_key="sk_test_123",
            stripe_price_id="price_test_123",
            stripe_webhook_secret="whsec_test_123",
        )
    )
    result = service.cancel_subscription_at_period_end(stripe_subscription_id="sub_123")

    assert captured["modified"] == ("sub_123", True)
    assert captured["retrieved"] == "sub_123"
    assert result.cancel_at_period_end is True
    assert result.current_period_end is not None
    assert result.current_period_end.isoformat() == "2030-01-01T00:00:00+00:00"
    assert result.cancellation_requested_at is not None
    assert result.cancellation_requested_at.isoformat() == "2029-12-02T00:00:00+00:00"
