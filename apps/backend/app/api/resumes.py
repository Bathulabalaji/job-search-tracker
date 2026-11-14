from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response, UploadFile, status
from fastapi.responses import Response as RawResponse

from app.api.auth_deps import ClockDep, DbSession, SettingsDep
from app.api.deps import (
    EmbedLaterDep,
    ObjectStoreDep,
    ResumeDocumentServiceDep,
    ResumeServiceDep,
)
from app.core.errors import DocumentError
from app.models.resume import Resume
from app.schemas.resume import DocumentUrl, ResumeCreate, ResumeRead, ResumeUpdate

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("", response_model=list[ResumeRead])
def list_resumes(
    service: ResumeServiceDep,
    q: Annotated[str | None, Query(description="Search label, focus or file name")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Resume]:
    return service.list(q=q, limit=limit, offset=offset)


@router.post("", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def create_resume(data: ResumeCreate, service: ResumeServiceDep) -> Resume:
    """Metadata first; the file is uploaded separately to `/{id}/document`."""
    return service.create(data)


@router.get("/{resume_id}", response_model=ResumeRead)
def get_resume(
    resume_id: int,
    service: ResumeServiceDep,
    documents: ResumeDocumentServiceDep,
    background: BackgroundTasks,
    embed_later: EmbedLaterDep,
) -> Resume:
    resume = service.get(resume_id)
    if documents.retry_due(resume):  # indexing that was deferred (quota) heals on reads
        background.add_task(embed_later, resume.id)
    return resume


@router.patch("/{resume_id}", response_model=ResumeRead)
def update_resume(resume_id: int, data: ResumeUpdate, service: ResumeServiceDep) -> Resume:
    return service.update(resume_id, data)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: int, service: ResumeServiceDep, documents: ResumeDocumentServiceDep
) -> Response:
    resume = service.get(resume_id)
    service.delete(resume_id)
    documents.delete_resume_objects(resume)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- the document (Phase 2) -------------------------------------------------------------------


@router.post(
    "/{resume_id}/document", response_model=ResumeRead, status_code=status.HTTP_201_CREATED
)
def upload_document(
    resume_id: int,
    file: UploadFile,
    documents: ResumeDocumentServiceDep,
    settings: SettingsDep,
    background: BackgroundTasks,
    embed_later: EmbedLaterDep,
) -> Resume:
    """Attach (or replace) the PDF. Text is extracted and redacted at once; embeddings and the
    profile follow in the background and can be retried."""
    limit = settings.resume_max_file_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise DocumentError(
            "file_too_large", f"The file is over {settings.resume_max_file_mb} MB.", 413
        )
    resume = documents.upload(
        resume_id,
        filename=file.filename or "resume.pdf",
        content_type=file.content_type or "application/pdf",
        data=data,
    )
    background.add_task(embed_later, resume.id)
    return resume


@router.delete("/{resume_id}/document", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(resume_id: int, documents: ResumeDocumentServiceDep) -> Response:
    documents.delete_document(resume_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{resume_id}/document/url", response_model=DocumentUrl)
def document_url(
    resume_id: int, request: Request, documents: ResumeDocumentServiceDep
) -> DocumentUrl:
    """A short-lived link to view or download the file."""
    file_url = str(request.url_for("download_resume_document", resume_id=resume_id))
    url, expires_at = documents.download_url(resume_id, app_file_url=file_url)
    return DocumentUrl(url=url, expires_at=expires_at)


@router.post("/{resume_id}/document/process", response_model=ResumeRead)
def process_document(resume_id: int, documents: ResumeDocumentServiceDep) -> Resume:
    """Re-run indexing (embeddings and profile) now. Rate-limited per user and day."""
    return documents.process_now(resume_id)


# Served without a session: the link carries its own signed, short-lived token. Mounted
# separately (see router.py) so the protected dependency does not apply.
files_router = APIRouter(prefix="/resumes", tags=["resumes"])


@files_router.get("/{resume_id}/document/file", name="download_resume_document")
def download_resume_document(
    resume_id: int,
    token: str,
    db: DbSession,
    settings: SettingsDep,
    clock: ClockDep,
    store: ObjectStoreDep,
) -> RawResponse:
    from app.api.deps import build_document_service_for_token

    service = build_document_service_for_token(db, settings, clock, store, token, resume_id)
    data, content_type, filename = service.download(resume_id)
    safe = filename.replace('"', "")
    return RawResponse(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe}"',
            "Cache-Control": "private, no-store",
        },
    )
