"""LangGraph checkpoints in Postgres, so a failed run can resume after a restart.

The saver needs its own autocommit psycopg connections (not SQLAlchemy's), and its tables are
created by `setup()` with CREATE INDEX CONCURRENTLY, which cannot run inside an Alembic
transaction: it runs once per process, on first use, and is idempotent.
"""

from functools import lru_cache

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy.engine import make_url


def libpq_url(database_url: str) -> str:
    """SQLAlchemy's 'postgresql+psycopg://...' as a plain libpq connection string."""
    url = make_url(database_url).set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


@lru_cache(maxsize=1)
def postgres_checkpointer(database_url: str) -> BaseCheckpointSaver[str]:
    pool: ConnectionPool = ConnectionPool(
        libpq_url(database_url),
        min_size=0,
        max_size=4,
        # prepare_threshold=None: Neon's pooled endpoint (PgBouncer) rejects prepared statements.
        kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": None},
        open=True,
    )
    saver = PostgresSaver(pool)  # type: ignore[arg-type]
    saver.setup()
    return saver
