"""Resume passages and their embeddings.

The embedding column differs by environment (see `ResumeChunk`): with pgvector the search is
an indexed `<=>` query; without it the user's vectors (a few dozen rows) are compared in
Python. Both paths return the same rows and scores.
"""

import math

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.resume import ResumeChunk, SimilarChunk
from app.repositories.base import BaseRepository

_VECTOR_SUPPORT: dict[str, bool] = {}


def vector_available(session: Session) -> bool:
    """Does this database have the pgvector extension? Checked once per database."""
    bind = session.get_bind()
    key = str(bind.engine.url)
    if key not in _VECTOR_SUPPORT:
        row = session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
        _VECTOR_SUPPORT[key] = row is not None
    return _VECTOR_SUPPORT[key]


class ResumeChunkRepository(BaseRepository[ResumeChunk]):
    model = ResumeChunk

    def for_resume(self, resume_id: int) -> list[ResumeChunk]:
        stmt = (
            select(ResumeChunk)
            .where(ResumeChunk.user_id == self.user_id)
            .where(ResumeChunk.resume_id == resume_id)
            .order_by(ResumeChunk.chunk_index)
        )
        return list(self.session.scalars(stmt))

    def delete_for_resume(self, resume_id: int) -> None:
        self.session.query(ResumeChunk).filter(
            ResumeChunk.user_id == self.user_id, ResumeChunk.resume_id == resume_id
        ).delete()

    def unembedded_for_resume(self, resume_id: int) -> list[ResumeChunk]:
        """Chunks whose embedding column is still NULL (raw SQL: the column is not mapped)."""
        rows = self.session.execute(
            text(
                "SELECT id FROM resume_chunks WHERE user_id = :uid AND resume_id = :rid "
                "AND embedding IS NULL ORDER BY chunk_index"
            ),
            {"uid": self.user_id, "rid": resume_id},
        ).scalars()
        ids = list(rows)
        if not ids:
            return []
        stmt = (
            select(ResumeChunk)
            .where(ResumeChunk.user_id == self.user_id)
            .where(ResumeChunk.id.in_(ids))
            .order_by(ResumeChunk.chunk_index)
        )
        return list(self.session.scalars(stmt))

    def set_embedding(self, chunk_id: int, vector: list[float], model: str) -> None:
        if vector_available(self.session):
            self.session.execute(
                text(
                    "UPDATE resume_chunks SET embedding = CAST(:vec AS vector), "
                    "embedding_model = :model WHERE id = :id AND user_id = :uid"
                ),
                {"vec": _literal(vector), "model": model, "id": chunk_id, "uid": self.user_id},
            )
        else:
            self.session.execute(
                text(
                    "UPDATE resume_chunks SET embedding = :vec, embedding_model = :model "
                    "WHERE id = :id AND user_id = :uid"
                ),
                {"vec": vector, "model": model, "id": chunk_id, "uid": self.user_id},
            )

    def similar(
        self, query: list[float], *, resume_ids: list[int] | None = None, k: int = 5
    ) -> list[SimilarChunk]:
        """The user's most similar passages, optionally within some resumes only."""
        params: dict[str, object] = {"uid": self.user_id, "k": k}
        scope = "WHERE user_id = :uid AND embedding IS NOT NULL"
        if resume_ids is not None:
            if not resume_ids:
                return []
            scope += " AND resume_id = ANY(:rids)"
            params["rids"] = resume_ids
        if vector_available(self.session):
            params["vec"] = _literal(query)
            rows = self.session.execute(
                text(
                    "SELECT id, resume_id, chunk_index, section, text, "
                    "1 - (embedding <=> CAST(:vec AS vector)) AS score "
                    f"FROM resume_chunks {scope} "
                    "ORDER BY embedding <=> CAST(:vec AS vector) LIMIT :k"
                ),
                params,
            ).all()
            return [SimilarChunk(*row) for row in rows]
        rows = self.session.execute(
            text(
                f"SELECT id, resume_id, chunk_index, section, text, embedding "
                f"FROM resume_chunks {scope}"
            ),
            {key: value for key, value in params.items() if key != "k"},
        ).all()
        scored = sorted(
            (
                SimilarChunk(row[0], row[1], row[2], row[3], row[4], _cosine(query, list(row[5])))
                for row in rows
            ),
            key=lambda c: c.score,
            reverse=True,
        )
        return scored[:k]


def _literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.8g}" for v in vector) + "]"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
