"""SQLAlchemy-backed ChatKit store scoped to the authenticated user."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from chatkit.store import NotFoundError, Store
from chatkit.types import Attachment, Page, ThreadItem, ThreadMetadata

from .auth import AuthenticatedUser
from .models import ChatItemRecord, ChatThreadRecord


THREAD_ITEM_ADAPTER = TypeAdapter(ThreadItem)


def _coerce_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PostgresChatStore(Store[dict[str, Any]]):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    def _require_user_id(self, context: dict[str, Any]) -> str:
        auth_user = context.get("auth_user")
        if not isinstance(auth_user, AuthenticatedUser):
            raise NotFoundError("Authenticated user not found in request context.")
        return auth_user.sub

    async def _load_thread_row(
        self,
        thread_id: str,
        auth0_user_id: str,
    ) -> ChatThreadRecord:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ChatThreadRecord).where(
                    ChatThreadRecord.id == thread_id,
                    ChatThreadRecord.auth0_user_id == auth0_user_id,
                )
            )
            row = result.scalars().first()
            if row is None:
                raise NotFoundError(f"Thread {thread_id} not found.")
            return row

    async def load_thread(self, thread_id: str, context: dict[str, Any]) -> ThreadMetadata:
        auth0_user_id = self._require_user_id(context)
        row = await self._load_thread_row(thread_id, auth0_user_id)
        return ThreadMetadata.model_validate_json(row.thread_json)

    async def save_thread(self, thread: ThreadMetadata, context: dict[str, Any]) -> None:
        auth0_user_id = self._require_user_id(context)
        async with self._session_factory.begin() as session:
            result = await session.execute(
                select(ChatThreadRecord).where(
                    ChatThreadRecord.id == thread.id,
                    ChatThreadRecord.auth0_user_id == auth0_user_id,
                )
            )
            row = result.scalars().first()
            payload = thread.model_dump_json()
            if row is None:
                session.add(
                    ChatThreadRecord(
                        id=thread.id,
                        auth0_user_id=auth0_user_id,
                        created_at=_coerce_datetime(thread.created_at),
                        thread_json=payload,
                    )
                )
            else:
                row.thread_json = payload
                row.created_at = _coerce_datetime(thread.created_at)

    async def load_threads(
        self, limit: int, after: str | None, order: str, context: dict[str, Any]
    ) -> Page[ThreadMetadata]:
        auth0_user_id = self._require_user_id(context)
        async with self._session_factory() as session:
            result = await session.execute(
                select(ChatThreadRecord).where(
                    ChatThreadRecord.auth0_user_id == auth0_user_id
                )
            )
            rows = result.scalars().all()

        threads = [
            ThreadMetadata.model_validate_json(row.thread_json)
            for row in rows
        ]
        return self._paginate(
            threads,
            after,
            limit,
            order,
            sort_key=lambda thread: thread.created_at,
            cursor_key=lambda thread: thread.id,
        )

    async def load_thread_items(
        self, thread_id: str, after: str | None, limit: int, order: str, context: dict[str, Any]
    ) -> Page[ThreadItem]:
        auth0_user_id = self._require_user_id(context)
        await self._load_thread_row(thread_id, auth0_user_id)
        async with self._session_factory() as session:
            result = await session.execute(
                select(ChatItemRecord).where(ChatItemRecord.thread_id == thread_id)
            )
            rows = result.scalars().all()

        items = [THREAD_ITEM_ADAPTER.validate_json(row.item_json) for row in rows]
        return self._paginate(
            items,
            after,
            limit,
            order,
            sort_key=lambda item: item.created_at,
            cursor_key=lambda item: item.id,
        )

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, Any]
    ) -> None:
        auth0_user_id = self._require_user_id(context)
        await self._load_thread_row(thread_id, auth0_user_id)
        async with self._session_factory.begin() as session:
            session.add(
                ChatItemRecord(
                    id=item.id,
                    thread_id=thread_id,
                    created_at=_coerce_datetime(item.created_at),
                    item_json=item.model_dump_json(),
                )
            )

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, Any]
    ) -> None:
        auth0_user_id = self._require_user_id(context)
        await self._load_thread_row(thread_id, auth0_user_id)
        async with self._session_factory.begin() as session:
            result = await session.execute(
                select(ChatItemRecord).where(
                    ChatItemRecord.id == item.id,
                    ChatItemRecord.thread_id == thread_id,
                )
            )
            row = result.scalars().first()
            payload = item.model_dump_json()
            if row is None:
                session.add(
                    ChatItemRecord(
                        id=item.id,
                        thread_id=thread_id,
                        created_at=_coerce_datetime(item.created_at),
                        item_json=payload,
                    )
                )
            else:
                row.created_at = _coerce_datetime(item.created_at)
                row.item_json = payload

    async def load_item(
        self, thread_id: str, item_id: str, context: dict[str, Any]
    ) -> ThreadItem:
        auth0_user_id = self._require_user_id(context)
        await self._load_thread_row(thread_id, auth0_user_id)
        async with self._session_factory() as session:
            result = await session.execute(
                select(ChatItemRecord).where(
                    ChatItemRecord.id == item_id,
                    ChatItemRecord.thread_id == thread_id,
                )
            )
            row = result.scalars().first()
            if row is None:
                raise NotFoundError(f"Item {item_id} not found in thread {thread_id}")
            return THREAD_ITEM_ADAPTER.validate_json(row.item_json)

    async def delete_thread(self, thread_id: str, context: dict[str, Any]) -> None:
        auth0_user_id = self._require_user_id(context)
        async with self._session_factory.begin() as session:
            await session.execute(
                delete(ChatItemRecord).where(ChatItemRecord.thread_id == thread_id)
            )
            await session.execute(
                delete(ChatThreadRecord).where(
                    ChatThreadRecord.id == thread_id,
                    ChatThreadRecord.auth0_user_id == auth0_user_id,
                )
            )

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: dict[str, Any]
    ) -> None:
        auth0_user_id = self._require_user_id(context)
        await self._load_thread_row(thread_id, auth0_user_id)
        async with self._session_factory.begin() as session:
            await session.execute(
                delete(ChatItemRecord).where(
                    ChatItemRecord.id == item_id,
                    ChatItemRecord.thread_id == thread_id,
                )
            )

    async def save_attachment(self, attachment: Attachment, context: dict[str, Any]) -> None:
        raise NotImplementedError()

    async def load_attachment(
        self, attachment_id: str, context: dict[str, Any]
    ) -> Attachment:
        raise NotImplementedError()

    async def delete_attachment(self, attachment_id: str, context: dict[str, Any]) -> None:
        raise NotImplementedError()

    def _paginate(
        self,
        rows: list[Any],
        after: str | None,
        limit: int,
        order: str,
        sort_key,
        cursor_key,
    ) -> Page[Any]:
        sorted_rows = sorted(rows, key=sort_key, reverse=order == "desc")
        start = 0
        if after:
            for index, row in enumerate(sorted_rows):
                if cursor_key(row) == after:
                    start = index + 1
                    break
        data = sorted_rows[start : start + limit]
        has_more = start + limit < len(sorted_rows)
        next_after = cursor_key(data[-1]) if has_more and data else None
        return Page(data=data, has_more=has_more, after=next_after)
