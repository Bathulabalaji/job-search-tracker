"""The pending-action ledger a run reads and writes while it proposes and executes changes."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.assistant.write_tools import ActionPreview, ActionResult
from app.core.clock import Clock
from app.models.chat_action import ChatPendingAction
from app.repositories.chat_action import PendingActionRepository


def action_payload(action: ChatPendingAction) -> dict[str, Any]:
    """What the client sees of an action: the card, never the raw tool arguments."""
    preview = action.preview
    result = action.result or {}
    return {
        "id": str(action.id),
        "run_id": str(action.run_id),
        "tool": action.tool_name,
        "title": preview.get("title", action.tool_name),
        "summary": preview.get("summary", ""),
        "fields": preview.get("fields", []),
        "status": action.status,
        "expires_at": action.expires_at.isoformat(),
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "result_summary": result.get("summary"),
        "error": action.error,
        "warning": action.warning,
    }


class ActionStore:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        *,
        user_id: int,
        conversation_id: int,
        run_id: uuid.UUID,
        ttl: timedelta,
    ) -> None:
        self.session = session
        self.clock = clock
        self.repo = PendingActionRepository(session, user_id)
        self.conversation_id = conversation_id
        self.run_id = run_id
        self.ttl = ttl

    def get(self, tool_call_id: str) -> ChatPendingAction | None:
        return self.repo.by_call(self.run_id, tool_call_id)

    def create(
        self, tool_call_id: str, tool_name: str, args: dict[str, Any], preview: ActionPreview
    ) -> ChatPendingAction:
        now = self.clock.now()
        action = self.repo.add(
            ChatPendingAction(
                conversation_id=self.conversation_id,
                run_id=self.run_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                args=args,
                preview=preview.as_json(),
                expires_at=now + self.ttl,
                created_at=now,
            )
        )
        self.session.commit()
        return action

    def executed(self, action: ChatPendingAction, result: ActionResult) -> None:
        action.status = "executed"
        action.result = result.as_json()
        action.executed_at = self.clock.now()
        self.session.commit()

    def failed(self, action: ChatPendingAction, error: str) -> None:
        action.status = "failed"
        action.error = error[:500]
        action.executed_at = self.clock.now()
        self.session.commit()

    def now(self) -> datetime:
        return self.clock.now()
