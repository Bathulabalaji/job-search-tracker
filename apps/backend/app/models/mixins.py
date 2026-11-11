from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class OwnedMixin:
    """Marks a table as per-user data. Every query on these tables must filter by user_id.

    Nullable only because rows that predate accounts have no owner yet; they stay invisible
    until `claim_legacy_data` assigns them. All new rows set it (BaseRepository.add does).
    """

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
