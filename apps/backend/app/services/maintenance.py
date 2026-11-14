"""The sweep a scheduled job runs: expire, archive and delete what has aged out.

It never needs a user's session and never calls a model. Each rule is idempotent, so a
second run (or two overlapping ones) does no harm. Not done here on purpose: retrying pending
resume embeddings. Those need that user's file store and budget; they retry lazily the next
time the resume is opened, and the owner can press "Retry indexing".
"""

import logging
from dataclasses import asdict, dataclass
from datetime import timedelta

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.repositories.job_posting import JobPostingRepository
from app.repositories.maintenance import MaintenanceRepository

logger = logging.getLogger("app.maintenance")
CHECKPOINT_LOOKBACK = timedelta(days=7)  # older runs were swept by an earlier pass


@dataclass(frozen=True)
class MaintenanceReport:
    checkpoints_pruned: int
    actions_expired: int
    conversations_archived: int
    conversations_purged: int
    job_postings_deleted: int
    usage_events_deleted: int
    rate_limit_events_deleted: int

    def as_json(self) -> dict[str, int]:
        return asdict(self)


class MaintenanceService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        settings: Settings,
        checkpointer: BaseCheckpointSaver[str],
    ) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings
        self.checkpointer = checkpointer
        self.repo = MaintenanceRepository(session)

    def run(self) -> MaintenanceReport:
        now = self.clock.now()
        s = self.settings
        actions = self.repo.expire_pending_actions(now)
        archived = self.repo.archive_idle_conversations(
            now - timedelta(days=s.chat_retention_archive_days)
        )
        purged, purged_runs = self.repo.purge_idle_conversations(
            now - timedelta(days=s.chat_retention_purge_days)
        )
        finished = self.repo.finished_run_ids(
            finished_before=now - timedelta(hours=s.chat_run_retention_hours),
            since=now - CHECKPOINT_LOOKBACK,
        )
        postings = JobPostingRepository(self.session).delete_expired(now)
        usage = self.repo.delete_usage_events(now - timedelta(days=s.usage_events_retention_days))
        limits = self.repo.delete_rate_limit_events(
            now - timedelta(days=s.usage_events_retention_days)
        )
        self.session.commit()  # database work is durable before the slower checkpoint deletes

        pruned = 0
        for run_id in {*finished, *purged_runs}:
            try:
                self.checkpointer.delete_thread(str(run_id))
                pruned += 1
            except Exception:  # one stuck thread must not stop the rest
                logger.warning("checkpoint_prune_failed", extra={"run_id": str(run_id)})
        report = MaintenanceReport(
            checkpoints_pruned=pruned,
            actions_expired=actions,
            conversations_archived=archived,
            conversations_purged=purged,
            job_postings_deleted=postings,
            usage_events_deleted=usage,
            rate_limit_events_deleted=limits,
        )
        logger.info("maintenance_done", extra=report.as_json())
        return report
