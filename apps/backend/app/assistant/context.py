"""What the model gets to see of earlier turns.

Older turns are folded into a rolling summary stored on the conversation; recent turns go in
verbatim (user and assistant text, plus a one-line marker of the tools used). The budget is in
estimated tokens and sized for the Groq tier, so most turns stay on the fast models.
"""

import logging
from dataclasses import dataclass

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.assistant.prompts import SUMMARY_PROMPT
from app.llm.errors import LLMError
from app.llm.gateway import LLMGateway
from app.llm.policy import Task
from app.llm.tokens import estimate_messages
from app.models.chat import ChatConversation, ChatMessage
from app.repositories.chat import MessageRepository

logger = logging.getLogger("app.assistant")

HISTORY_BUDGET_TOKENS = 1_500
KEEP_VERBATIM = 4  # the most recent messages are never summarized away
SUMMARY_MAX_CHARS = 900


@dataclass(frozen=True)
class Context:
    summary: str | None
    history: list[BaseMessage]


def to_message(row: ChatMessage) -> BaseMessage:
    if row.role == "user":
        return HumanMessage(content=row.content)
    text = row.content
    if row.tool_calls:
        names = ", ".join(sorted({str(c.get("name")) for c in row.tool_calls}))
        text = f"{text}\n\n(looked up: {names})"
    return AIMessage(content=text)


def _usable(row: ChatMessage) -> bool:
    return row.role == "user" or (row.role == "assistant" and row.status == "complete")


class ContextBuilder:
    def __init__(self, messages: MessageRepository, gateway: LLMGateway) -> None:
        self.messages = messages
        self.gateway = gateway

    def build(self, conversation: ChatConversation, before_seq: int) -> Context:
        rows = [
            r
            for r in self.messages.after(
                conversation.id, conversation.summary_through_seq, before_seq=before_seq
            )
            if _usable(r)
        ]
        history = [to_message(r) for r in rows]
        if estimate_messages(history) <= HISTORY_BUDGET_TOKENS:
            return Context(conversation.summary, history)

        # Too long: fold the oldest turns into the summary, keeping the newest ones verbatim.
        keep = len(rows)
        while keep > KEEP_VERBATIM and estimate_messages(history[-keep:]) > HISTORY_BUDGET_TOKENS:
            keep -= 1
        # Never start the window on an assistant reply (it would answer nothing visible).
        while keep > 0 and rows[-keep].role != "user":
            keep -= 1
        folded, kept = rows[:-keep] if keep else rows, rows[-keep:] if keep else []
        if not folded:
            return Context(conversation.summary, [to_message(r) for r in kept])
        summary = self._summarize(conversation.summary, folded)
        conversation.summary = summary
        conversation.summary_through_seq = folded[-1].seq
        return Context(summary, [to_message(r) for r in kept])

    def _summarize(self, previous: str | None, rows: list[ChatMessage]) -> str:
        transcript = "\n".join(
            f"{'User' if r.role == 'user' else 'Assistant'}: {' '.join(r.content.split())[:600]}"
            for r in rows
        )
        prompt = [
            SystemMessage(content=SUMMARY_PROMPT),
            HumanMessage(
                content=f"Current summary:\n{previous or '(none)'}\n\nNew messages:\n{transcript}"
            ),
        ]
        try:
            result = self.gateway.chat(Task.summarize, prompt, max_tokens=400)
            text = result.text.strip()
            if text:
                return text[:SUMMARY_MAX_CHARS]
        except LLMError as exc:
            logger.warning("assistant_summary_fallback", extra={"code": exc.code})
        return extractive_summary(previous, rows)


def extractive_summary(previous: str | None, rows: list[ChatMessage]) -> str:
    """No model available: keep the first sentence of each user question, newest last."""
    asked = [" ".join(r.content.split()).split(". ")[0][:120] for r in rows if r.role == "user"]
    text = ((previous + " | ") if previous else "") + "Asked: " + "; ".join(asked)
    return text[-SUMMARY_MAX_CHARS:]
