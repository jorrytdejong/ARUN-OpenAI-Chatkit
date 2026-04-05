"""Stripe billing helpers and webhook processing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import stripe
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .access import mark_webhook_event_processed, upsert_customer_access
from .auth import AuthenticatedUser
from .config import Settings


LATEST_STRIPE_API_VERSION = "2026-02-25.clover"


class BillingUrlResponse(BaseModel):
    url: str


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _coerce_period_end(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _subscription_price_id(subscription: dict[str, Any]) -> str | None:
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return None
    price = items[0].get("price")
    if isinstance(price, dict):
        identifier = price.get("id")
        if isinstance(identifier, str):
            return identifier
    return None


class BillingService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _configure_stripe(self) -> None:
        stripe.api_key = self._settings.stripe_secret_key
        stripe.api_version = LATEST_STRIPE_API_VERSION

    def create_checkout_session(
        self,
        *,
        user: AuthenticatedUser,
        stripe_customer_id: str | None,
    ) -> str:
        self._configure_stripe()

        params: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": self._settings.stripe_price_id, "quantity": 1}],
            "success_url": f"{self._settings.app_base_url}/subscribe?checkout=success",
            "cancel_url": f"{self._settings.app_base_url}/subscribe?checkout=cancelled",
            "client_reference_id": user.sub,
            "metadata": {"auth0_user_id": user.sub},
            "subscription_data": {"metadata": {"auth0_user_id": user.sub}},
            "allow_promotion_codes": True,
        }
        if stripe_customer_id:
            params["customer"] = stripe_customer_id
        elif user.email:
            params["customer_email"] = user.email

        session = stripe.checkout.Session.create(**params)
        return session.url

    def create_billing_portal_session(self, *, stripe_customer_id: str) -> str:
        self._configure_stripe()
        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=f"{self._settings.app_base_url}/subscribe?portal=return",
        )
        return session.url

    def construct_event(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        if not self._settings.stripe_webhook_secret:
            raise ValueError("Stripe webhook secret is not configured.")
        if signature is None:
            raise ValueError("Missing Stripe signature header.")

        self._configure_stripe()
        return stripe.Webhook.construct_event(
            payload,
            signature,
            self._settings.stripe_webhook_secret,
        )


async def process_stripe_event(
    session: AsyncSession,
    event: dict[str, Any],
) -> bool:
    event_id = event["id"]
    event_type = event["type"]

    processed = await mark_webhook_event_processed(
        session,
        stripe_event_id=event_id,
        event_type=event_type,
    )
    if not processed:
        return False

    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        if data.get("mode") == "subscription":
            auth0_user_id = data.get("metadata", {}).get("auth0_user_id") or data.get(
                "client_reference_id"
            )
            if isinstance(auth0_user_id, str) and auth0_user_id:
                await upsert_customer_access(
                    session,
                    auth0_user_id=auth0_user_id,
                    stripe_customer_id=_optional_str(data.get("customer")),
                    stripe_subscription_id=_optional_str(data.get("subscription")),
                )
        return True

    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        auth0_user_id = data.get("metadata", {}).get("auth0_user_id")
        if not isinstance(auth0_user_id, str):
            auth0_user_id = None

        status = data.get("status")
        await upsert_customer_access(
            session,
            auth0_user_id=auth0_user_id,
            stripe_customer_id=_optional_str(data.get("customer")),
            stripe_subscription_id=_optional_str(data.get("id")),
            stripe_price_id=_subscription_price_id(data),
            stripe_subscription_status=status if isinstance(status, str) else None,
            current_period_end=_coerce_period_end(data.get("current_period_end")),
        )
        return True

    return True
