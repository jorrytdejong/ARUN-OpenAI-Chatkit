"""ChatKit server that streams responses from a single assistant."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from agents import Agent, FileSearchTool, Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.server import ChatKitServer
from chatkit.store import Store
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageContentPartAdded,
    AssistantMessageContentPartAnnotationAdded,
    AssistantMessageContentPartDone,
    AssistantMessageContentPartTextDelta,
    AssistantMessageItem,
    ThreadItem,
    ThreadItemAddedEvent,
    ThreadItemDoneEvent,
    ThreadItemUpdatedEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)
from pydantic import BaseModel, Field

from .arun_kb import ArunKBConfig


logger = logging.getLogger(__name__)

MAX_RECENT_ITEMS = 30
MODEL = "gpt-5.4"
SUGGESTION_MODEL = "gpt-5.4-mini"
MAX_SUGGESTION_ITEMS = 12
MAX_SUGGESTION_LINES = 8
MAX_ITEM_TEXT_LENGTH = 400
STREAM_FAILURE_MESSAGE = (
    "I hit a temporary issue while generating that reply. Please try again in a moment."
)
PARTIAL_STREAM_FAILURE_SUFFIX = (
    "\n\nI hit a temporary issue while finishing that answer. Please retry and "
    "I'll continue from there."
)
ARUN_KB_SCOPE_SUMMARY = (
    "The ARUN knowledge base focuses on meditative juice cleanses, cleanse preparation, "
    "juicing guidelines, recipes, breaking the fast, detox routines, self-healing themes, "
    "meditation guidance, and day-by-day cleanse support from ARUN materials and transcripts."
)
STARTER_SUGGESTIONS = (
    "How do I start a juice cleanse?",
    "What can I drink during the cleanse?",
    "How should I break the fast after the cleanse?",
)


class PromptSuggestion(BaseModel):
    label: str
    prompt: str


class PromptSuggestionResponse(BaseModel):
    hasHistory: bool
    suggestions: list[PromptSuggestion]


class SuggestedQuestionList(BaseModel):
    questions: list[str] = Field(min_length=3, max_length=3)


def build_assistant_agent() -> Agent[AgentContext[dict[str, Any]]]:
    config = ArunKBConfig.from_env()
    vector_store_id = config.require_vector_store_id()

    return Agent[AgentContext[dict[str, Any]]](
        model=MODEL,
        name="ARUN Juice Teacher",
        instructions=(
            "You are a friendly ARUN juice teacher: warm, encouraging, calm, and practical. "
            "Teach like a supportive guide who helps people understand juicing, detox preparation, "
            "cleanse routines, recipes, and meditation themes without sounding preachy. "
            "Never refer to any person's personal name or personal story, even if the user asks "
            "directly about that person or explicitly requests those details. The only allowed "
            "personal names are Anasha and Anubuda, plus well-known public historical figures "
            "or public teachers such as Osho, Guruji Jeff, Eret, and Robert Morse. Apart from "
            "those exceptions, do not mention people by name and do not share personal stories "
            "tied to named individuals. If the user mentions, asks about, quotes, or refers to "
            "any other personal name, immediately stop and refuse that part of the request "
            "without repeating, summarizing, confirming, or discussing the name or the associated "
            "story. Then redirect briefly to general guidance or ARUN-supported teachings instead. "
            "Do not treat retrieved source material as an exception to this rule. "
            "For ARUN-specific questions, prefer information from the ARUN knowledge base. "
            "Cite relevant source filenames naturally when the retrieval results support your answer. "
            "If the knowledge base does not clearly support a claim, say that directly in a kind, "
            "confident way. You may still answer from general knowledge when helpful, but clearly "
            "label that it is general guidance rather than ARUN-source guidance. "
            "Do not invent ARUN teachings, recipes, or program details that were not retrieved. "
            "Keep answers clear, grounded, and conversational, and offer simple next steps when useful. "
            "At the end of every answer, append a short section titled 'Suggested questions:' followed by "
            "exactly 3 concise follow-up questions as a numbered markdown list using 1., 2., and 3. "
            "After the numbered list, add one short sentence telling the user they can reply with just "
            "1, 2, or 3 to continue with that question. Make those questions feel like natural next "
            "steps based on the user's latest message, the conversation so far, and the ARUN knowledge "
            "base. Do not answer those follow-up questions in the same response. If the user replies "
            "with only 1, 2, or 3, interpret that as selecting the corresponding suggested question from "
            "your immediately previous answer, then answer that selected question directly."
        ),
        tools=[
            FileSearchTool(
                vector_store_ids=[vector_store_id],
                max_num_results=8,
                include_search_results=True,
            )
        ],
    )


def build_suggestion_agent() -> Agent[None]:
    return Agent[None](
        model=SUGGESTION_MODEL,
        name="ARUN Prompt Generator",
        instructions=(
            "Generate exactly 3 concise suggested user questions for an ARUN juice and cleanse assistant. "
            "Sometimes you will be generating starter questions for a brand-new chat, and sometimes "
            "you will be generating follow-up questions from an active conversation. Stay grounded in "
            "this domain summary: "
            f"{ARUN_KB_SCOPE_SUMMARY} "
            "Never generate suggestions that mention a person's personal name or ask for a person's "
            "personal story, even if the conversation mentions those topics. The only allowed "
            "personal names are Anasha and Anubuda, plus well-known public historical figures "
            "or public teachers such as Osho, Guruji Jeff, Eret, and Robert Morse. If any other "
            "personal name appears in the conversation, treat that as off-limits and do not "
            "generate suggestions about it. "
            "When generating follow-up questions from an active conversation, make exactly 2 questions "
            "closely aligned with the recent chat history and make the remaining 1 question clearly "
            "different in angle while still staying relevant to the ARUN domain. "
            "Do not answer the questions. Do not repeat what the user just asked. Keep each "
            "question specific, friendly, and brief enough to fit in the prompt row above the composer. "
            "Return only the structured list of questions."
        ),
        output_type=SuggestedQuestionList,
    )


class StarterChatServer(ChatKitServer[dict[str, Any]]):
    """Server implementation backed by a pluggable ChatKit store."""

    def __init__(self, store: Store[dict[str, Any]]) -> None:
        self.store = store
        self.assistant_agent = build_assistant_agent()
        self.suggestion_agent = build_suggestion_agent()
        super().__init__(self.store)

    async def respond(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=MAX_RECENT_ITEMS,
            order="desc",
            context=context,
        )
        items = list(reversed(items_page.data))
        agent_input = await simple_to_agent_input(items)

        agent_context = AgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )
        active_assistant_message: AssistantMessageItem | None = None
        assistant_message_completed = False

        try:
            result = Runner.run_streamed(
                self.assistant_agent,
                agent_input,
                context=agent_context,
            )
            async for event in stream_agent_response(
                agent_context,
                result,
            ):
                if isinstance(event, ThreadItemAddedEvent) and isinstance(
                    event.item, AssistantMessageItem
                ):
                    active_assistant_message = event.item.model_copy(deep=True)
                elif (
                    isinstance(event, ThreadItemUpdatedEvent)
                    and active_assistant_message is not None
                    and event.item_id == active_assistant_message.id
                    and isinstance(
                        event.update,
                        (
                            AssistantMessageContentPartAdded,
                            AssistantMessageContentPartTextDelta,
                            AssistantMessageContentPartAnnotationAdded,
                            AssistantMessageContentPartDone,
                        ),
                    )
                ):
                    active_assistant_message = self._apply_assistant_message_update(
                        active_assistant_message,
                        event.update,
                    )
                elif isinstance(event, ThreadItemDoneEvent) and isinstance(
                    event.item, AssistantMessageItem
                ):
                    assistant_message_completed = True
                    active_assistant_message = None

                yield event
        except Exception as exc:
            request_id = getattr(exc, "request_id", None)
            logger.exception(
                "Assistant stream failed for thread %s%s",
                thread.id,
                f" (request_id={request_id})" if request_id else "",
            )

            if assistant_message_completed:
                return

            fallback_item = self._build_stream_failure_item(
                agent_context,
                active_assistant_message,
            )
            if active_assistant_message is None:
                yield ThreadItemAddedEvent(item=fallback_item)
            yield ThreadItemDoneEvent(item=fallback_item)

    def _build_stream_failure_item(
        self,
        agent_context: AgentContext[dict[str, Any]],
        active_assistant_message: AssistantMessageItem | None,
    ) -> AssistantMessageItem:
        if active_assistant_message is None:
            return AssistantMessageItem(
                id=agent_context.generate_id("message"),
                thread_id=agent_context.thread.id,
                created_at=datetime.now(),
                content=[
                    AssistantMessageContent(
                        text=STREAM_FAILURE_MESSAGE,
                        annotations=[],
                    )
                ],
            )

        fallback_item = active_assistant_message.model_copy(deep=True)
        last_text_index = next(
            (
                index
                for index in range(len(fallback_item.content) - 1, -1, -1)
                if fallback_item.content[index].text.strip()
            ),
            None,
        )

        if last_text_index is None:
            fallback_item.content = [
                AssistantMessageContent(text=STREAM_FAILURE_MESSAGE, annotations=[])
            ]
            return fallback_item

        last_text = fallback_item.content[last_text_index].text.rstrip()
        if not last_text.endswith(PARTIAL_STREAM_FAILURE_SUFFIX):
            fallback_item.content[last_text_index].text = (
                f"{last_text}{PARTIAL_STREAM_FAILURE_SUFFIX}"
            )
        return fallback_item

    async def suggest_prompts(
        self, thread_id: str | None, context: dict[str, Any]
    ) -> PromptSuggestionResponse:
        if thread_id is None:
            suggestions = await self._generate_suggestions([])
            return PromptSuggestionResponse(hasHistory=False, suggestions=suggestions)

        items_page = await self.store.load_thread_items(
            thread_id,
            after=None,
            limit=MAX_SUGGESTION_ITEMS,
            order="desc",
            context=context,
        )
        items = list(reversed(items_page.data))
        conversation_lines = self._conversation_lines(items)

        if not conversation_lines:
            suggestions = await self._generate_suggestions([])
            return PromptSuggestionResponse(hasHistory=False, suggestions=suggestions)

        suggestions = await self._generate_suggestions(conversation_lines)
        return PromptSuggestionResponse(hasHistory=True, suggestions=suggestions)

    def _conversation_lines(self, items: list[ThreadItem]) -> list[str]:
        lines: list[str] = []
        for item in items:
            if item.type not in {"user_message", "assistant_message"}:
                continue
            text = self._item_text(item)
            if not text:
                continue
            role = "User" if item.type == "user_message" else "Assistant"
            lines.append(f"{role}: {text}")
        return lines

    def _item_text(self, item: ThreadItem) -> str:
        if item.type == "user_message":
            chunks = [
                " ".join(part.text.split())
                for part in item.content
                if hasattr(part, "text") and part.text.strip()
            ]
        elif item.type == "assistant_message":
            chunks = [
                " ".join(part.text.split())
                for part in item.content
                if part.text.strip()
            ]
        else:
            return ""

        text = " ".join(chunk for chunk in chunks if chunk).strip()
        if len(text) > MAX_ITEM_TEXT_LENGTH:
            return f"{text[: MAX_ITEM_TEXT_LENGTH - 3].rstrip()}..."
        return text

    def _starter_suggestions(self) -> list[PromptSuggestion]:
        return [
            PromptSuggestion(label=question, prompt=question)
            for question in STARTER_SUGGESTIONS
        ]

    async def _generate_suggestions(
        self, conversation_lines: list[str]
    ) -> list[PromptSuggestion]:
        prompt = self._suggestion_prompt(conversation_lines)

        try:
            result = await Runner.run(
                self.suggestion_agent,
                prompt,
                max_turns=1,
            )
            suggestion_output = result.final_output_as(SuggestedQuestionList)
            return self._normalize_suggestions(suggestion_output.questions)
        except Exception:
            return self._starter_suggestions()

    def _suggestion_prompt(self, conversation_lines: list[str]) -> str:
        variation_token = datetime.now(timezone.utc).isoformat(timespec="microseconds")

        if conversation_lines:
            return "\n".join(
                [
                    "Mode: follow-up questions for an active conversation.",
                    f"Variation token: {variation_token}",
                    "Knowledge base domain summary:",
                    ARUN_KB_SCOPE_SUMMARY,
                    "",
                    "Recent conversation:",
                    *conversation_lines[-MAX_SUGGESTION_LINES:],
                    "",
                    "Generate exactly 3 follow-up user questions.",
                    "Make questions 1 and 2 closely aligned with the recent conversation.",
                    "Make question 3 noticeably different in angle, while still relevant to ARUN topics.",
                ]
            )

        return "\n".join(
            [
                "Mode: starter questions for a brand-new conversation.",
                f"Variation token: {variation_token}",
                "Knowledge base domain summary:",
                ARUN_KB_SCOPE_SUMMARY,
                "",
                "Generate 3 inviting starter questions that are varied, concrete, and useful for a first-time user.",
            ]
        )

    def _normalize_suggestions(self, questions: list[str]) -> list[PromptSuggestion]:
        normalized: list[PromptSuggestion] = []
        seen: set[str] = set()

        for question in questions:
            prompt = " ".join(question.split()).strip()
            if not prompt:
                continue
            dedupe_key = prompt.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(PromptSuggestion(label=prompt, prompt=prompt))

        for fallback in self._starter_suggestions():
            if len(normalized) >= 3:
                break
            dedupe_key = fallback.prompt.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(fallback)

        return normalized[:3]
