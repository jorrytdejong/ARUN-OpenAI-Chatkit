from __future__ import annotations

from datetime import datetime

import pytest
from chatkit.store import Store
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageContentPartTextDelta,
    AssistantMessageItem,
    Page,
    ThreadItem,
    ThreadItemAddedEvent,
    ThreadItemDoneEvent,
    ThreadItemUpdatedEvent,
    ThreadMetadata,
)

from app import server as server_module


class StubStore(Store[dict[str, object]]):
    async def load_thread(self, thread_id: str, context: dict[str, object]) -> ThreadMetadata:
        raise NotImplementedError

    async def save_thread(self, thread: ThreadMetadata, context: dict[str, object]) -> None:
        raise NotImplementedError

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: dict[str, object],
    ) -> Page[ThreadItem]:
        del thread_id, after, limit, order, context
        return Page(data=[], has_more=False, after=None)

    async def save_attachment(self, attachment, context: dict[str, object]) -> None:
        raise NotImplementedError

    async def load_attachment(self, attachment_id: str, context: dict[str, object]):
        raise NotImplementedError

    async def delete_attachment(self, attachment_id: str, context: dict[str, object]) -> None:
        raise NotImplementedError

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: dict[str, object],
    ) -> Page[ThreadMetadata]:
        raise NotImplementedError

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, object]
    ) -> None:
        raise NotImplementedError

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, object]
    ) -> None:
        raise NotImplementedError

    async def load_item(
        self, thread_id: str, item_id: str, context: dict[str, object]
    ) -> ThreadItem:
        raise NotImplementedError

    async def delete_thread(self, thread_id: str, context: dict[str, object]) -> None:
        raise NotImplementedError

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: dict[str, object]
    ) -> None:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_respond_finishes_partial_message_when_streaming_fails(monkeypatch) -> None:
    monkeypatch.setattr(server_module, "build_assistant_agent", lambda: object())
    monkeypatch.setattr(server_module, "build_suggestion_agent", lambda: object())
    monkeypatch.setattr(server_module.Runner, "run_streamed", lambda *args, **kwargs: object())

    async def fake_stream_agent_response(agent_context, result):
        del result
        item = AssistantMessageItem(
            id="resp_123",
            thread_id=agent_context.thread.id,
            created_at=datetime.now(),
            content=[AssistantMessageContent(text="", annotations=[])],
        )
        yield ThreadItemAddedEvent(item=item)
        yield ThreadItemUpdatedEvent(
            item_id=item.id,
            update=AssistantMessageContentPartTextDelta(
                content_index=0,
                delta="Partial answer.",
            ),
        )
        raise RuntimeError("upstream streaming failed")

    monkeypatch.setattr(
        server_module,
        "stream_agent_response",
        fake_stream_agent_response,
    )

    server = server_module.StarterChatServer(store=StubStore())
    thread = ThreadMetadata(id="thr_123", created_at=datetime.now())

    events = [event async for event in server.respond(thread, None, {})]

    assert [type(event) for event in events] == [
        ThreadItemAddedEvent,
        ThreadItemUpdatedEvent,
        ThreadItemDoneEvent,
    ]
    assert events[-1].item.id == "resp_123"
    assert "Partial answer." in events[-1].item.content[0].text
    assert "temporary issue while finishing" in events[-1].item.content[0].text

