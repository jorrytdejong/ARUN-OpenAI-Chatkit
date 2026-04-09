"""Customer access persistence and access-control helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import AuthenticatedUser
from .models import CustomerAccess, StripeWebhookEvent


ACCESS_GRANTING_STATUSES = {"active", "trialing"}


class AccessSnapshot(BaseModel):
    auth0_user_id: str
    has_access: bool
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    stripe_price_id: str | None = None
    stripe_subscription_status: str | None = None
    cancel_at_period_end: bool = False
    current_period_end: datetime | None = None
    cancellation_requested_at: datetime | None = None
    ended_at: datetime | None = None
    can_manage_billing: bool = False


def coerce_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def subscription_has_access(status: str | None) -> bool:
    return status in ACCESS_GRANTING_STATUSES


def build_access_snapshot(
    auth0_user_id: str,
    record: CustomerAccess | None,
) -> AccessSnapshot:
    if record is None:
        return AccessSnapshot(
            auth0_user_id=auth0_user_id,
            has_access=False,
            can_manage_billing=False,
        )

    return AccessSnapshot(
        auth0_user_id=auth0_user_id,
        has_access=record.has_access,
        stripe_customer_id=record.stripe_customer_id,
        stripe_subscription_id=record.stripe_subscription_id,
        stripe_price_id=record.stripe_price_id,
        stripe_subscription_status=record.stripe_subscription_status,
        cancel_at_period_end=record.cancel_at_period_end,
        current_period_end=record.current_period_end,
        cancellation_requested_at=record.cancellation_requested_at,
        ended_at=record.ended_at,
        can_manage_billing=record.stripe_customer_id is not None,
    )


async def get_customer_access(
    session: AsyncSession,
    auth0_user_id: str,
) -> CustomerAccess | None:
    return await session.get(CustomerAccess, auth0_user_id)


async def find_customer_access(
    session: AsyncSession,
    *,
    auth0_user_id: str | None = None,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
) -> CustomerAccess | None:
    if auth0_user_id:
        record = await session.get(CustomerAccess, auth0_user_id)
        if record is not None:
            return record

    filters = [
        field
        for field in (
            CustomerAccess.stripe_customer_id == stripe_customer_id
            if stripe_customer_id
            else None,
            CustomerAccess.stripe_subscription_id == stripe_subscription_id
            if stripe_subscription_id
            else None,
        )
        if field is not None
    ]
    if not filters:
        return None

    result = await session.execute(select(CustomerAccess).where(or_(*filters)))
    return result.scalars().first()


async def upsert_customer_access(
    session: AsyncSession,
    *,
    auth0_user_id: str | None = None,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    stripe_price_id: str | None = None,
    stripe_subscription_status: str | None = None,
    cancel_at_period_end: bool | None = None,
    current_period_end: datetime | None = None,
    cancellation_requested_at: datetime | None = None,
    ended_at: datetime | None = None,
) -> CustomerAccess | None:
    record = await find_customer_access(
        session,
        auth0_user_id=auth0_user_id,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
    )

    if record is None:
        if auth0_user_id is None:
            return None
        record = CustomerAccess(auth0_user_id=auth0_user_id)
        session.add(record)

    if auth0_user_id is not None:
        record.auth0_user_id = auth0_user_id
    if stripe_customer_id is not None:
        record.stripe_customer_id = stripe_customer_id
    if stripe_subscription_id is not None:
        record.stripe_subscription_id = stripe_subscription_id
    if stripe_price_id is not None:
        record.stripe_price_id = stripe_price_id
    if stripe_subscription_status is not None:
        record.stripe_subscription_status = stripe_subscription_status
        record.has_access = subscription_has_access(stripe_subscription_status)
    if cancel_at_period_end is not None:
        record.cancel_at_period_end = cancel_at_period_end
    if current_period_end is not None or stripe_subscription_status == "canceled":
        record.current_period_end = coerce_utc_datetime(current_period_end)
    if cancellation_requested_at is not None:
        record.cancellation_requested_at = coerce_utc_datetime(cancellation_requested_at)
    if ended_at is not None:
        record.ended_at = coerce_utc_datetime(ended_at)
    if stripe_subscription_status == "canceled" and record.ended_at is None:
        record.ended_at = datetime.now(timezone.utc)

    await session.flush()
    return record


async def mark_webhook_event_processed(
    session: AsyncSession,
    *,
    stripe_event_id: str,
    event_type: str,
) -> bool:
    session.add(
        StripeWebhookEvent(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
        )
    )
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def get_access_snapshot_for_user(
    session: AsyncSession,
    user: AuthenticatedUser,
) -> AccessSnapshot:
    record = await get_customer_access(session, user.sub)
    return build_access_snapshot(user.sub, record)


async def require_active_access(
    session: AsyncSession,
    user: AuthenticatedUser,
) -> CustomerAccess:
    record = await get_customer_access(session, user.sub)
    if record is None or not record.has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required.",
        )
    return record
