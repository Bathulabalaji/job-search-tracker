"""Phase 5: files left behind by deleted accounts or failed uploads are found and removed."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.storage_gc import collect
from tests.assistant.conftest import ChatHarness
from tests.assistant.pdf import RESUME_TEXT, make_pdf
from tests.assistant.test_resume_documents import create_resume, script_profile, upload


def put(chat: ChatHarness, key: str, *, age: timedelta = timedelta(days=2)) -> None:
    chat.store.put(key, b"%PDF-1.4 x", "application/pdf")
    chat.store.modified[key] = chat.clock.now - age


def test_gc_finds_only_unreferenced_resume_files_past_the_grace_period(
    chat: ChatHarness, db: Session
) -> None:
    resume_id = create_resume(chat)
    script_profile(chat)
    assert upload(chat, resume_id, make_pdf([RESUME_TEXT])).status_code == 201
    [kept] = list(chat.store.objects)
    chat.store.modified[kept] = chat.clock.now - timedelta(days=5)  # referenced: must stay

    put(chat, "users/99/resumes/7/old-orphan.pdf")
    put(chat, "users/99/resumes/8/just-uploaded.pdf", age=timedelta(minutes=5))
    put(chat, "users/99/other/readme.txt")  # not our layout: never touched

    dry = collect(db, chat.store, chat.clock.now, delete=False)
    assert dry.orphans == ["users/99/resumes/7/old-orphan.pdf"]
    assert dry.deleted == 0 and "users/99/resumes/7/old-orphan.pdf" in chat.store.objects

    done = collect(db, chat.store, chat.clock.now, delete=True)
    assert done.deleted == 1
    assert set(chat.store.objects) == {
        kept,
        "users/99/resumes/8/just-uploaded.pdf",
        "users/99/other/readme.txt",
    }
    assert collect(db, chat.store, chat.clock.now, delete=True).orphans == []  # nothing left


def test_deleting_an_account_leaves_files_that_gc_then_removes(
    chat: ChatHarness, db: Session
) -> None:
    other = User(email="gone@example.com", full_name="Gone", status="active")
    db.add(other)
    db.flush()
    key = f"users/{other.id}/resumes/3/file.pdf"
    put(chat, key)
    assert collect(db, chat.store, chat.clock.now, delete=False).orphans == [key]
    collect(db, chat.store, chat.clock.now, delete=True)
    assert key not in chat.store.objects
