"""ChatKit server that streams responses from a single assistant."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncIterator

from agents import Agent, FileSearchTool, Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.server import ChatKitServer
from chatkit.store import Store
from chatkit.types import ThreadItem, ThreadMetadata, ThreadStreamEvent, UserMessageItem
from pydantic import BaseModel, Field

from .arun_kb import ArunKBConfig


MAX_RECENT_ITEMS = 30
MODEL = "gpt-5.4"
SUGGESTION_MODEL = "gpt-5.4-mini"
MAX_SUGGESTION_ITEMS = 12
MAX_SUGGESTION_LINES = 8
MAX_ITEM_TEXT_LENGTH = 400
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

        result = Runner.run_streamed(
            self.assistant_agent,
            agent_input,
            context=agent_context,
        )

        async for event in stream_agent_response(agent_context, result):
            yield event

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
                    "Generate the next 3 user questions that would feel most natural here.",
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
