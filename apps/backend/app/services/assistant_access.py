"""Has this user switched the assistant off? Checked wherever their data would go to a model."""

from sqlalchemy.orm import Session

from app.core.errors import AuthError
from app.models.user import User

OPTED_OUT_MESSAGE = "You've switched the AI assistant off in your settings."


def is_opted_out(session: Session, user_id: int) -> bool:
    user = session.get(User, user_id)
    return bool(user is not None and user.assistant_opt_out)


def ensure_opted_in(session: Session, user_id: int) -> None:
    if is_opted_out(session, user_id):
        raise AuthError("assistant_opted_out", OPTED_OUT_MESSAGE, 403)
