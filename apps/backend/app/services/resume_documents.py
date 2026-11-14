"""Uploaded resume files: validation, storage, text, chunks, embeddings and the profile.

The upload itself is synchronous and cheap (store the bytes, read the text, cut it into
passages). Embedding and the profile need the AI providers, so they run afterwards and can be
retried: a failure leaves the resume with `embed_status=pending` and a retry time rather than
an error the user has to deal with.
"""

import base64
import hashlib
import hmac
import io
import logging
import uuid
from datetime import datetime, timedelta

from pypdf import PasswordType, PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import DocumentError, NotFoundError
from app.llm.errors import EmbeddingUnavailable, LLMError
from app.llm.gateway import LLMGateway
from app.models.resume import Resume, ResumeChunk
from app.repositories.resume import ResumeRepository
from app.repositories.resume_chunk import ResumeChunkRepository
from app.services.pii import redact
from app.services.resume_chunking import chunk_resume
from app.services.resume_profile import extract_profile
from app.storage.object_store import ObjectStore

logger = logging.getLogger("app.resumes")

PDF_MAGIC = b"%PDF-"
MIN_TEXT_CHARS = 50
EMBED_BATCH = 20
MAX_EMBED_ATTEMPTS = 10
DEFAULT_RETRY = timedelta(minutes=5)
NO_PROVIDER_RETRY = timedelta(hours=1)


class ResumeDocumentService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        settings: Settings,
        user_id: int,
        store: ObjectStore,
        gateway: LLMGateway | None,
    ) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings
        self.user_id = user_id
        self.store = store
        self.gateway = gateway
        self.resumes = ResumeRepository(session, user_id)
        self.chunks = ResumeChunkRepository(session, user_id)

    # ---- upload ---------------------------------------------------------------------------

    def upload(self, resume_id: int, *, filename: str, content_type: str, data: bytes) -> Resume:
        resume = self._get(resume_id)
        max_bytes = self.settings.resume_max_file_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise DocumentError(
                "file_too_large", f"The file is over {self.settings.resume_max_file_mb} MB.", 413
            )
        if not data.startswith(PDF_MAGIC):
            raise DocumentError("unsupported_type", "Only PDF files are supported.", 415)
        if resume.storage_key is None:
            uploaded = sum(
                1 for r in self.resumes.list(q=None, limit=500, offset=0) if r.storage_key
            )
            if uploaded >= self.settings.resume_max_documents:
                raise DocumentError(
                    "document_limit_reached",
                    f"You can keep up to {self.settings.resume_max_documents} resume files. "
                    "Remove one first.",
                    409,
                )
        page_count, text = self._extract(data)
        text = redact(text)
        chunks = chunk_resume(text)

        now = self.clock.now()
        key = f"users/{self.user_id}/resumes/{resume.id}/{uuid.uuid4().hex}.pdf"
        self.store.put(key, data, "application/pdf")
        previous_key = resume.storage_key
        try:
            resume.storage_key = key
            resume.content_type = "application/pdf"
            resume.size_bytes = len(data)
            resume.sha256 = hashlib.sha256(data).hexdigest()
            resume.page_count = page_count
            resume.uploaded_at = now
            resume.file_name = _safe_name(filename)
            resume.text_status = "ready"
            resume.extracted_text = text
            resume.profile = None
            resume.profile_model = None
            resume.embed_status = "pending"
            resume.embed_attempts = 0
            resume.embed_retry_after = None
            resume.processing_error = None
            self.chunks.delete_for_resume(resume.id)
            for chunk in chunks:
                self.chunks.add(
                    ResumeChunk(
                        resume_id=resume.id,
                        chunk_index=chunk.index,
                        section=chunk.section,
                        text=chunk.text,
                        token_count=chunk.token_count,
                    )
                )
            self.session.commit()
        except Exception:
            self.session.rollback()
            self._delete_object(key)
            raise
        if previous_key and previous_key != key:
            self._delete_object(previous_key)
        logger.info(
            "resume_uploaded",
            extra={
                "resume_id": resume.id,
                "pages": page_count,
                "chunks": len(chunks),
                "bytes": len(data),
            },
        )
        return resume

    def _extract(self, data: bytes) -> tuple[int, str]:
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                try:
                    opened = reader.decrypt("")
                except Exception:
                    opened = PasswordType.NOT_DECRYPTED
                if opened == PasswordType.NOT_DECRYPTED:
                    raise DocumentError(
                        "pdf_encrypted",
                        "This PDF is password-protected. Remove the password first.",
                        422,
                    )
            pages = reader.pages
            page_count = len(pages)
            if page_count > self.settings.resume_max_pages:
                raise DocumentError(
                    "too_many_pages",
                    f"A resume can have at most {self.settings.resume_max_pages} pages.",
                    422,
                )
            text = "\n".join((page.extract_text() or "") for page in pages)
        except DocumentError:
            raise
        except FileNotDecryptedError:
            raise DocumentError(
                "pdf_encrypted", "This PDF is password-protected. Remove the password first.", 422
            ) from None
        except (PdfReadError, ValueError, KeyError, TypeError) as exc:
            raise DocumentError(
                "unsupported_type", "This file could not be read as a PDF.", 415
            ) from exc
        if len(text.strip()) < MIN_TEXT_CHARS:
            raise DocumentError(
                "pdf_no_text",
                "This PDF has no selectable text (it may be a scan). Export it as a text PDF.",
                422,
            )
        return page_count, text

    # ---- embeddings and profile (retryable) -------------------------------------------------

    def process(self, resume_id: int, *, force: bool = False) -> Resume:
        resume = self._get(resume_id)
        if resume.storage_key is None:
            raise DocumentError("no_document", "This resume has no file yet.", 404)
        now = self.clock.now()
        if not force and resume.embed_status in ("ready", "failed", "none") and resume.profile:
            return resume
        if not force and resume.embed_retry_after is not None and now < resume.embed_retry_after:
            return resume
        if self.gateway is None or not self.gateway.enabled:
            resume.embed_status = "pending"
            resume.embed_retry_after = now + NO_PROVIDER_RETRY
            resume.processing_error = "No AI provider is configured yet."
            self.session.commit()
            return resume
        if force:
            resume.embed_attempts = 0
        try:
            self._embed_missing(resume)
        except EmbeddingUnavailable as exc:
            resume.embed_attempts += 1
            if resume.embed_attempts >= MAX_EMBED_ATTEMPTS:
                resume.embed_status = "failed"
                resume.processing_error = "Indexing kept failing. Try again later."
                resume.embed_retry_after = None
            else:
                resume.embed_status = "pending"
                resume.processing_error = exc.user_message
                resume.embed_retry_after = (
                    now
                    + timedelta(seconds=exc.retry_after or 0)
                    + (DEFAULT_RETRY if not exc.retry_after else timedelta(0))
                )
            self.session.commit()
            logger.warning(
                "resume_embed_deferred",
                extra={"resume_id": resume.id, "attempt": resume.embed_attempts},
            )
            return resume
        resume.embed_status = "ready"
        resume.embed_retry_after = None
        resume.processing_error = None
        self.session.commit()
        if resume.profile is None and resume.extracted_text:
            extracted = extract_profile(self.gateway, resume.extracted_text)
            if extracted is not None:
                profile, model = extracted
                resume.profile = profile.model_dump()
                resume.profile_model = model
                self.session.commit()
        return resume

    def process_now(self, resume_id: int) -> Resume:
        """The user asked for a re-index: counted against a small daily allowance."""
        from datetime import timedelta as _td

        from app.services.rate_limit import RateLimiter

        RateLimiter(self.session, self.clock).consume(
            f"resume-process:{self.user_id}", self.settings.resume_process_daily_limit, _td(days=1)
        )
        return self.process(resume_id, force=True)

    def _embed_missing(self, resume: Resume) -> None:
        assert self.gateway is not None
        pending = self.chunks.unembedded_for_resume(resume.id)
        for start in range(0, len(pending), EMBED_BATCH):
            batch = pending[start : start + EMBED_BATCH]
            vectors = self.gateway.embed([c.text for c in batch], kind="document")
            for chunk, vector in zip(batch, vectors, strict=True):
                self.chunks.set_embedding(chunk.id, vector, self.settings.embedding_model)
            self.session.commit()  # progress survives a failure on the next batch

    def retry_due(self, resume: Resume) -> bool:
        """Should a lazy retry run now? Called on reads; the retry itself runs in the background."""
        return (
            resume.storage_key is not None
            and resume.embed_status == "pending"
            and (resume.embed_retry_after is None or resume.embed_retry_after <= self.clock.now())
        )

    # ---- delete / download ---------------------------------------------------------------

    def delete_document(self, resume_id: int) -> Resume:
        resume = self._get(resume_id)
        key = resume.storage_key
        self.chunks.delete_for_resume(resume.id)
        resume.storage_key = None
        resume.content_type = None
        resume.size_bytes = None
        resume.sha256 = None
        resume.page_count = None
        resume.uploaded_at = None
        resume.text_status = "none"
        resume.embed_status = "none"
        resume.embed_attempts = 0
        resume.embed_retry_after = None
        resume.processing_error = None
        resume.extracted_text = None
        resume.profile = None
        resume.profile_model = None
        self.session.commit()
        if key:
            self._delete_object(key)
        return resume

    def delete_resume_objects(self, resume: Resume) -> None:
        """Called by ResumeService.delete after the row is gone."""
        if resume.storage_key:
            self._delete_object(resume.storage_key)

    def download(self, resume_id: int) -> tuple[bytes, str, str]:
        resume = self._get(resume_id)
        if resume.storage_key is None:
            raise DocumentError("no_document", "This resume has no file yet.", 404)
        return (
            self.store.get(resume.storage_key),
            resume.content_type or "application/pdf",
            resume.file_name or "resume.pdf",
        )

    def download_url(self, resume_id: int, *, app_file_url: str) -> tuple[str, datetime]:
        """A link that works without a session for a few minutes: presigned by the bucket when
        it can, otherwise the API's own file route with a signed token."""
        resume = self._get(resume_id)
        if resume.storage_key is None:
            raise DocumentError("no_document", "This resume has no file yet.", 404)
        seconds = self.settings.object_store_presign_seconds
        expires_at = self.clock.now() + timedelta(seconds=seconds)
        url = self.store.presigned_get_url(
            resume.storage_key, filename=resume.file_name or "resume.pdf", expires_seconds=seconds
        )
        if url is None:
            token = sign_download_token(
                self.settings.secret_key, self.user_id, resume.id, int(expires_at.timestamp())
            )
            url = f"{app_file_url}?token={token}"
        return url, expires_at

    # ---- internals ------------------------------------------------------------------------

    def _get(self, resume_id: int) -> Resume:
        resume = self.resumes.get(resume_id)
        if resume is None:
            raise NotFoundError("Resume", resume_id)
        return resume

    def _delete_object(self, key: str) -> None:
        try:
            self.store.delete(key)
        except Exception:
            logger.warning("resume_object_delete_failed", extra={"key": key})


def _safe_name(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip() or "resume.pdf"
    return name[:255]


def sign_download_token(secret: str, user_id: int, resume_id: int, expires: int) -> str:
    digest = hmac.new(
        secret.encode(), f"download:{user_id}:{resume_id}:{expires}".encode(), hashlib.sha256
    ).digest()
    sig = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return f"{user_id}.{resume_id}.{expires}.{sig}"


def verify_download_token(secret: str, token: str, resume_id: int, *, now: datetime) -> int | None:
    """The user id the token was issued for, or None when invalid or expired."""
    try:
        user_part, resume_part, expires_part, _sig = token.split(".", 3)
        user_id, token_resume, expires = int(user_part), int(resume_part), int(expires_part)
    except ValueError:
        return None
    if token_resume != resume_id or expires < int(now.timestamp()):
        return None
    expected = sign_download_token(secret, user_id, resume_id, expires)
    return user_id if hmac.compare_digest(expected, token) else None


def embed_later(
    session_factory: object,
    settings: Settings,
    clock: Clock,
    user_id: int,
    resume_id: int,
    store: ObjectStore,
    providers: object,
) -> None:
    """Background step after an upload or a lazy retry: embeddings and profile in a session
    of its own (the request's session is gone by the time this runs)."""
    from app.assistant.runner import SessionScope
    from app.llm import build_llm_gateway
    from app.llm.catalog import Provider
    from app.llm.providers.base import ChatProvider

    scope: SessionScope = session_factory  # type: ignore[assignment]
    typed_providers: dict[Provider, ChatProvider] = providers  # type: ignore[assignment]
    with scope() as session:
        gateway = build_llm_gateway(
            settings, session, clock, user_id=user_id, providers=typed_providers
        )
        service = ResumeDocumentService(session, clock, settings, user_id, store, gateway)
        try:
            service.process(resume_id)
        except LLMError as exc:
            logger.warning(
                "resume_process_failed", extra={"resume_id": resume_id, "code": exc.code}
            )
        except Exception:
            logger.exception("resume_process_crashed", extra={"resume_id": resume_id})
