"""Local streaming helpers that enrich file citations with file-search snippets."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import datetime

from agents import (
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    RunResultStreaming,
)
from chatkit.agents import (
    AgentContext,
    ResponseStreamConverter,
    StreamingThoughtTracker,
    _AsyncQueueIterator,
    _EventWrapper,
    _convert_annotation,
    _convert_content,
    _merge_generators,
)
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageContentPartAdded,
    AssistantMessageContentPartAnnotationAdded,
    AssistantMessageContentPartDone,
    AssistantMessageContentPartTextDelta,
    AssistantMessageItem,
    ClientToolCallItem,
    DurationSummary,
    GeneratedImage,
    GeneratedImageItem,
    GeneratedImageUpdated,
    ThoughtTask,
    ThreadItemAddedEvent,
    ThreadItemDoneEvent,
    ThreadItemRemovedEvent,
    ThreadItemUpdatedEvent,
    ThreadStreamEvent,
    Workflow,
    WorkflowItem,
    WorkflowTaskAdded,
    WorkflowTaskUpdated,
)


async def stream_agent_response_with_snippets(
    context: AgentContext,
    result: RunResultStreaming,
    *,
    converter: ResponseStreamConverter,
) -> AsyncIterator[ThreadStreamEvent]:
    """Mirror ChatKit streaming while caching file-search snippets for citations."""
    current_item_id = None
    current_tool_call = None
    ctx = context
    thread = context.thread
    queue_iterator = _AsyncQueueIterator(context._events)
    produced_items = set()
    streaming_thought: None | StreamingThoughtTracker = None
    item_annotation_count: defaultdict[str, defaultdict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    items = await context.store.load_thread_items(
        thread.id, None, 2, "desc", context.request_context
    )
    last_item = items.data[0] if len(items.data) > 0 else None
    second_last_item = items.data[1] if len(items.data) > 1 else None

    if last_item and last_item.type == "workflow":
        ctx.workflow_item = last_item
    elif (
        last_item
        and last_item.type == "client_tool_call"
        and second_last_item
        and second_last_item.type == "workflow"
    ):
        ctx.workflow_item = second_last_item

    def end_workflow(item: WorkflowItem):
        if item == ctx.workflow_item:
            ctx.workflow_item = None
        delta = datetime.now() - item.created_at
        duration = int(delta.total_seconds())
        if item.workflow.summary is None:
            item.workflow.summary = DurationSummary(duration=duration)
        item.workflow.expanded = False
        return ThreadItemDoneEvent(item=item)

    try:
        async for event in _merge_generators(result.stream_events(), queue_iterator):
            if isinstance(event, _EventWrapper):
                event = event.event
                if (
                    event.type == "thread.item.added"
                    or event.type == "thread.item.done"
                ):
                    if (
                        ctx.workflow_item
                        and ctx.workflow_item.id != event.item.id
                        and event.item.type != "client_tool_call"
                        and event.item.type != "hidden_context_item"
                    ):
                        yield end_workflow(ctx.workflow_item)

                    if (
                        event.type == "thread.item.added"
                        and event.item.type == "workflow"
                    ):
                        ctx.workflow_item = event.item

                    produced_items.add(event.item.id)
                yield event
                continue

            if event.type == "run_item_stream_event":
                event = event.item
                if (
                    event.type == "tool_call_item"
                    and event.raw_item.type == "function_call"
                ):
                    current_tool_call = event.raw_item.call_id
                    current_item_id = event.raw_item.id
                    assert current_item_id
                    produced_items.add(current_item_id)
                continue

            if event.type != "raw_response_event":
                continue

            event = event.data
            if event.type == "response.content_part.added":
                if event.part.type == "reasoning_text":
                    continue
                content = await _convert_content(event.part, converter)
                yield ThreadItemUpdatedEvent(
                    item_id=event.item_id,
                    update=AssistantMessageContentPartAdded(
                        content_index=event.content_index,
                        content=content,
                    ),
                )
            elif event.type == "response.output_text.delta":
                yield ThreadItemUpdatedEvent(
                    item_id=event.item_id,
                    update=AssistantMessageContentPartTextDelta(
                        content_index=event.content_index,
                        delta=event.delta,
                    ),
                )
            elif event.type == "response.output_text.done":
                yield ThreadItemUpdatedEvent(
                    item_id=event.item_id,
                    update=AssistantMessageContentPartDone(
                        content_index=event.content_index,
                        content=AssistantMessageContent(
                            text=event.text,
                            annotations=[],
                        ),
                    ),
                )
            elif event.type == "response.output_text.annotation.added":
                annotation = await _convert_annotation(event.annotation, converter)
                if annotation:
                    annotation_index = item_annotation_count[event.item_id][
                        event.content_index
                    ]
                    item_annotation_count[event.item_id][event.content_index] = (
                        annotation_index + 1
                    )
                    yield ThreadItemUpdatedEvent(
                        item_id=event.item_id,
                        update=AssistantMessageContentPartAnnotationAdded(
                            content_index=event.content_index,
                            annotation_index=annotation_index,
                            annotation=annotation,
                        ),
                    )
                continue
            elif event.type == "response.output_item.added":
                item = event.item
                if item.type == "reasoning" and not ctx.workflow_item:
                    ctx.workflow_item = WorkflowItem(
                        id=ctx.generate_id("workflow"),
                        created_at=datetime.now(),
                        workflow=Workflow(type="reasoning", tasks=[]),
                        thread_id=thread.id,
                    )
                    produced_items.add(ctx.workflow_item.id)
                    yield ThreadItemAddedEvent(item=ctx.workflow_item)
                if item.type == "message":
                    if ctx.workflow_item:
                        yield end_workflow(ctx.workflow_item)
                    produced_items.add(item.id)
                    yield ThreadItemAddedEvent(
                        item=AssistantMessageItem(
                            id=item.id,
                            thread_id=thread.id,
                            content=[
                                await _convert_content(c, converter)
                                for c in item.content
                            ],
                            created_at=datetime.now(),
                        ),
                    )
                elif item.type == "image_generation_call":
                    ctx.generated_image_item = GeneratedImageItem(
                        id=ctx.generate_id("message"),
                        thread_id=thread.id,
                        created_at=datetime.now(),
                        image=None,
                    )
                    produced_items.add(ctx.generated_image_item.id)
                    yield ThreadItemAddedEvent(item=ctx.generated_image_item)
            elif event.type == "response.image_generation_call.partial_image":
                if not ctx.generated_image_item:
                    continue

                url = await converter.base64_image_to_url(
                    image_id=event.item_id,
                    base64_image=event.partial_image_b64,
                    partial_image_index=event.partial_image_index,
                )
                progress = converter.partial_image_index_to_progress(
                    event.partial_image_index
                )

                ctx.generated_image_item.image = GeneratedImage(
                    id=event.item_id, url=url
                )

                yield ThreadItemUpdatedEvent(
                    item_id=ctx.generated_image_item.id,
                    update=GeneratedImageUpdated(
                        image=ctx.generated_image_item.image, progress=progress
                    ),
                )
            elif event.type == "response.reasoning_summary_text.delta":
                if not ctx.workflow_item:
                    continue

                if (
                    ctx.workflow_item.workflow.type == "reasoning"
                    and len(ctx.workflow_item.workflow.tasks) == 0
                ):
                    streaming_thought = StreamingThoughtTracker(
                        item_id=event.item_id,
                        index=event.summary_index,
                        task=ThoughtTask(content=event.delta),
                    )
                    ctx.workflow_item.workflow.tasks.append(streaming_thought.task)
                    yield ThreadItemUpdatedEvent(
                        item_id=ctx.workflow_item.id,
                        update=WorkflowTaskAdded(
                            task=streaming_thought.task,
                            task_index=0,
                        ),
                    )
                elif (
                    streaming_thought
                    and streaming_thought.task in ctx.workflow_item.workflow.tasks
                    and event.item_id == streaming_thought.item_id
                    and event.summary_index == streaming_thought.index
                ):
                    streaming_thought.task.content += event.delta
                    yield ThreadItemUpdatedEvent(
                        item_id=ctx.workflow_item.id,
                        update=WorkflowTaskUpdated(
                            task=streaming_thought.task,
                            task_index=ctx.workflow_item.workflow.tasks.index(
                                streaming_thought.task
                            ),
                        ),
                    )
            elif event.type == "response.reasoning_summary_text.done":
                if ctx.workflow_item:
                    if (
                        streaming_thought
                        and streaming_thought.task in ctx.workflow_item.workflow.tasks
                        and event.item_id == streaming_thought.item_id
                        and event.summary_index == streaming_thought.index
                    ):
                        task = streaming_thought.task
                        task.content = event.text
                        streaming_thought = None
                        update = WorkflowTaskUpdated(
                            task=task,
                            task_index=ctx.workflow_item.workflow.tasks.index(task),
                        )
                    else:
                        task = ThoughtTask(content=event.text)
                        ctx.workflow_item.workflow.tasks.append(task)
                        update = WorkflowTaskAdded(
                            task=task,
                            task_index=ctx.workflow_item.workflow.tasks.index(task),
                        )
                    yield ThreadItemUpdatedEvent(
                        item_id=ctx.workflow_item.id,
                        update=update,
                    )
            elif event.type == "response.output_item.done":
                item = event.item
                if item.type == "message":
                    produced_items.add(item.id)
                    yield ThreadItemDoneEvent(
                        item=AssistantMessageItem(
                            id=item.id,
                            thread_id=thread.id,
                            content=[
                                await _convert_content(c, converter)
                                for c in item.content
                            ],
                            created_at=datetime.now(),
                        ),
                    )
                elif item.type == "file_search_call":
                    converter.remember_file_search_results(item.results or [])
                elif item.type == "image_generation_call" and item.result:
                    if not ctx.generated_image_item:
                        continue

                    url = await converter.base64_image_to_url(
                        image_id=item.id,
                        base64_image=item.result,
                    )
                    image = GeneratedImage(id=item.id, url=url)

                    ctx.generated_image_item.image = image
                    yield ThreadItemDoneEvent(item=ctx.generated_image_item)

                    ctx.generated_image_item = None

    except (InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered):
        for item_id in produced_items:
            yield ThreadItemRemovedEvent(item_id=item_id)

        context._complete()
        queue_iterator.drain_and_complete()
        raise

    context._complete()

    async for event in queue_iterator:
        yield event.event

    if ctx.workflow_item:
        await ctx.store.add_thread_item(
            thread.id, ctx.workflow_item, ctx.request_context
        )

    if context.client_tool_call:
        yield ThreadItemDoneEvent(
            item=ClientToolCallItem(
                id=current_item_id
                or context.store.generate_item_id(
                    "tool_call", thread, context.request_context
                ),
                thread_id=thread.id,
                name=context.client_tool_call.name,
                arguments=context.client_tool_call.arguments,
                created_at=datetime.now(),
                call_id=current_tool_call
                or context.store.generate_item_id(
                    "tool_call", thread, context.request_context
                ),
            ),
        )
