"""Find (and optionally delete) stored files that no resume points at any more.

Files are only ever created by the upload flow under users/{id}/resumes/{id}/, so only keys of
exactly that shape are considered. A grace period keeps the sweep away from an upload that has
stored its file but not yet committed its row. Deleting an account removes its rows by cascade,
which leaves the files orphaned: this is what removes them.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.storage.object_store import ObjectStore

OURS = re.compile(r"^users/\d+/resumes/\d+/[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class GcReport:
    scanned: int
    orphans: list[str]
    deleted: int


def collect(
    session: Session,
    store: ObjectStore,
    now: datetime,
    *,
    delete: bool,
    grace: timedelta = timedelta(hours=1),
) -> GcReport:
    referenced = {
        str(key)
        for key in session.execute(
            text("SELECT storage_key FROM resumes WHERE storage_key IS NOT NULL")
        ).scalars()
    }
    objects = store.list_objects("users/")
    orphans = sorted(
        o.key
        for o in objects
        if OURS.match(o.key) and o.key not in referenced and o.modified < now - grace
    )
    deleted = 0
    if delete:
        for key in orphans:
            store.delete(key)
            deleted += 1
    return GcReport(scanned=len(objects), orphans=orphans, deleted=deleted)
