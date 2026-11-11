import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.schemas.resume import ResumeCreate, ResumeUpdate
from app.services.resume import ResumeService


def test_create_defaults_version_to_1(db: Session) -> None:
    resume = ResumeService(db, db.info["user_id"]).create(ResumeCreate(label="Backend"))
    assert (resume.version, resume.focus, resume.file_name) == ("1", None, None)


def test_update_changes_only_sent_fields(db: Session) -> None:
    svc = ResumeService(db, db.info["user_id"])
    resume = svc.create(ResumeCreate(label="Backend", focus="Python", version="1"))
    updated = svc.update(resume.id, ResumeUpdate(version="2"))
    assert (updated.label, updated.focus, updated.version) == ("Backend", "Python", "2")


def test_update_can_clear_optional_field(db: Session) -> None:
    svc = ResumeService(db, db.info["user_id"])
    resume = svc.create(ResumeCreate(label="Backend", focus="Python"))
    assert svc.update(resume.id, ResumeUpdate(focus=None)).focus is None


def test_search_matches_label_focus_and_file_name(db: Session) -> None:
    svc = ResumeService(db, db.info["user_id"])
    svc.create(ResumeCreate(label="Backend", focus="FastAPI", file_name="resume_backend_v3.pdf"))
    svc.create(ResumeCreate(label="Data", focus="Airflow"))
    assert [r.label for r in svc.list(q="fastapi")] == ["Backend"]
    assert [r.label for r in svc.list(q="backend_v3")] == ["Backend"]
    assert [r.label for r in svc.list(q="data")] == ["Data"]
    assert len(svc.list()) == 2


def test_delete_and_missing(db: Session) -> None:
    svc = ResumeService(db, db.info["user_id"])
    resume = svc.create(ResumeCreate(label="Old"))
    svc.delete(resume.id)
    with pytest.raises(NotFoundError):
        svc.get(resume.id)


@pytest.mark.parametrize("name", ["../secret.pdf", "C:\\docs\\cv.pdf", "a/b.pdf"])
def test_file_name_must_not_be_a_path(name: str) -> None:
    with pytest.raises(ValidationError, match="not a path"):
        ResumeCreate(label="x", file_name=name)
    with pytest.raises(ValidationError, match="not a path"):
        ResumeUpdate(file_name=name)


def test_required_fields_reject_null_on_update() -> None:
    with pytest.raises(ValueError, match="label cannot be null"):
        ResumeUpdate.model_validate({"label": None})
