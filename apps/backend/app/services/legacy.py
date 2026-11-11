import logging
from typing import Any, cast

from sqlalchemy import CursorResult, update
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    Contact,
    DailyLog,
    Followup,
    Interaction,
    Opportunity,
    PrepItem,
    Resume,
    WeeklyTarget,
)

logger = logging.getLogger("app.auth")

OWNED_MODELS: tuple[type[Base], ...] = (
    Opportunity,
    Contact,
    Interaction,
    Followup,
    DailyLog,
    WeeklyTarget,
    PrepItem,
    Resume,
)


def claim_legacy_data(session: Session, user_id: int) -> int:
    """Give rows that predate accounts (user_id IS NULL) to this user. Returns rows claimed."""
    claimed = 0
    for model in OWNED_MODELS:
        result = session.execute(
            update(model)
            .where(model.user_id.is_(None))  # type: ignore[attr-defined]
            .values(user_id=user_id)
        )
        claimed += cast(CursorResult[Any], result).rowcount or 0
    if claimed:
        logger.info("legacy data claimed", extra={"user_id": user_id, "rows": claimed})
    return claimed
