from typing import Any

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.llm.errors import RateLimited
from app.llm.providers.fake import FakeStep, fake_embedding
from app.models.resume import ResumeChunk
from app.repositories.resume_chunk import ResumeChunkRepository, vector_available
from app.services.resume_documents import sign_download_token, verify_download_token
from app.services.resume_profile import ResumeProfile, Skill
from tests.assistant.conftest import ChatHarness
from tests.assistant.pdf import RESUME_TEXT, encrypt, make_pdf
from tests.assistant.test_chat_api import new_conversation, send, text_of, tool_call, verdict

API = "/api/v1/resumes"
PROFILE = ResumeProfile(
    titles=["Senior Software Engineer"],
    years_experience=4,
    skills=[Skill(name="Python"), Skill(name="FastAPI"), Skill(name="React")],
    domains=["fintech"],
    summary="Full-stack engineer.",
)


def create_resume(chat: ChatHarness, label: str = "Fullstack") -> int:
    response = chat.client.post(API, json={"label": label, "version": "1"})
    assert response.status_code == 201
    return int(response.json()["id"])


def upload(chat: ChatHarness, resume_id: int, data: bytes, name: str = "fullstack.pdf") -> Any:
    return chat.client.post(
        f"{API}/{resume_id}/document", files={"file": (name, data, "application/pdf")}
    )


def script_profile(chat: ChatHarness) -> None:
    chat.google.script(FakeStep(message=AIMessage(content="{}"), parsed=PROFILE))


def test_upload_extracts_redacts_chunks_and_indexes(chat: ChatHarness, db: Session) -> None:
    resume_id = create_resume(chat)
    script_profile(chat)
    pdf = make_pdf([RESUME_TEXT + "\nPAN: ABCDE1234F"])

    response = upload(chat, resume_id, pdf)

    assert response.status_code == 201, response.text
    document = response.json()["document"]
    assert document["file_name"] == "fullstack.pdf" and document["page_count"] == 1
    assert document["text_status"] == "ready"
    assert [k for k in chat.store.objects][0].startswith(
        f"users/{db.info['user_id']}/resumes/{resume_id}/"
    )

    # Indexing ran in the background with the same request's fakes.
    detail = chat.client.get(f"{API}/{resume_id}").json()["document"]
    assert detail["embed_status"] == "ready"
    assert detail["profile"]["skills"][0]["name"] == "Python"
    chunks = db.scalars(select(ResumeChunk).order_by(ResumeChunk.chunk_index)).all()
    assert len(chunks) >= 4 and chunks[0].section == "overview"
    assert chunks and all(c.embedding_model == "gemini-embedding-001" for c in chunks)
    stored = db.execute(
        text("SELECT extracted_text FROM resumes WHERE id = :id"), {"id": resume_id}
    ).scalar()
    assert "ABCDE1234F" not in str(stored) and "[REDACTED_ID]" in str(stored)
    assert all("ABCDE1234F" not in c.text for c in chunks)
    embedded = db.execute(
        text("SELECT count(*) FROM resume_chunks WHERE embedding IS NOT NULL")
    ).scalar()
    assert embedded == len(chunks)
    assert chat.google.embed_calls and len(chat.google.embed_calls[0]) == len(chunks)


def test_similarity_search_finds_the_right_passage(chat: ChatHarness, db: Session) -> None:
    resume_id = create_resume(chat)
    script_profile(chat)
    assert upload(chat, resume_id, make_pdf([RESUME_TEXT])).status_code == 201
    repo = ResumeChunkRepository(db, db.info["user_id"])
    hits = repo.similar(fake_embedding("FastAPI payments service PostgreSQL", 768), k=3)
    assert hits and hits[0].score > 0
    assert "FastAPI" in hits[0].text
    assert repo.similar(fake_embedding("x", 768), resume_ids=[]) == []
    # Explicit about which path this database exercised.
    print("pgvector:", vector_available(db))


def test_validation_rejects_non_pdf_large_encrypted_scanned_and_long_files(
    chat: ChatHarness,
) -> None:
    resume_id = create_resume(chat)
    cases = [
        (b"hello world " * 10, "unsupported_type", 415),
        (
            make_pdf(["x" * 60]).replace(b"%PDF-1.4", b"%PDF-1.4") + b"0" * (5 * 1024 * 1024),
            "file_too_large",
            413,
        ),
        (encrypt(make_pdf([RESUME_TEXT])), "pdf_encrypted", 422),
        (make_pdf(["Hi"]), "pdf_no_text", 422),
        (make_pdf([RESUME_TEXT] * 11), "too_many_pages", 422),
    ]
    for data, code, status in cases:
        response = upload(chat, resume_id, data)
        assert (response.status_code, response.json()["code"]) == (status, code), code
    assert chat.store.objects == {}


def test_at_most_three_files_and_replacing_frees_the_old_object(chat: ChatHarness) -> None:
    ids = [create_resume(chat, f"r{i}") for i in range(4)]
    for resume_id in ids[:3]:
        script_profile(chat)
        assert upload(chat, resume_id, make_pdf([RESUME_TEXT])).status_code == 201
    blocked = upload(chat, ids[3], make_pdf([RESUME_TEXT]))
    assert (blocked.status_code, blocked.json()["code"]) == (409, "document_limit_reached")

    before = set(chat.store.objects)
    script_profile(chat)
    assert upload(chat, ids[0], make_pdf([RESUME_TEXT + "\nv2"]), name="v2.pdf").status_code == 201
    after = set(chat.store.objects)
    assert len(after) == 3 and len(after - before) == 1  # one new object, one old one gone
    assert chat.client.get(f"{API}/{ids[0]}").json()["file_name"] == "v2.pdf"


def test_embedding_outage_leaves_the_upload_usable_and_heals_on_a_later_read(
    chat: ChatHarness, db: Session
) -> None:
    resume_id = create_resume(chat)
    chat.google.embed_error = RateLimited("quota", kind="minute", retry_after=120)
    assert upload(chat, resume_id, make_pdf([RESUME_TEXT])).status_code == 201
    document = chat.client.get(f"{API}/{resume_id}").json()["document"]
    assert (
        document["embed_status"] == "pending" and "paused" in document["processing_error"].lower()
    )

    chat.google.embed_error = None
    script_profile(chat)
    chat.client.get(f"{API}/{resume_id}")  # too early: retry time not reached
    assert chat.client.get(f"{API}/{resume_id}").json()["document"]["embed_status"] == "pending"
    chat.clock.advance(minutes=3)
    chat.client.get(f"{API}/{resume_id}")  # a read after the retry time triggers indexing
    assert chat.client.get(f"{API}/{resume_id}").json()["document"]["embed_status"] == "ready"


def test_manual_reindex_is_rate_limited(chat: ChatHarness) -> None:
    chat.settings.resume_process_daily_limit = 1
    resume_id = create_resume(chat)
    script_profile(chat)
    assert upload(chat, resume_id, make_pdf([RESUME_TEXT])).status_code == 201
    script_profile(chat)
    assert chat.client.post(f"{API}/{resume_id}/document/process").status_code == 200
    again = chat.client.post(f"{API}/{resume_id}/document/process")
    assert again.status_code == 429


def test_download_link_is_signed_short_lived_and_scoped(chat: ChatHarness) -> None:
    resume_id = create_resume(chat)
    script_profile(chat)
    pdf = make_pdf([RESUME_TEXT])
    assert upload(chat, resume_id, pdf).status_code == 201

    link = chat.client.get(f"{API}/{resume_id}/document/url").json()
    assert "/document/file?token=" in link["url"]
    download = chat.client.get(link["url"])
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/pdf")
    assert download.content == pdf
    assert 'filename="fullstack.pdf"' in download.headers["content-disposition"]

    bad = chat.client.get(link["url"] + "x")
    assert (bad.status_code, bad.json()["code"]) == (403, "invalid_link")
    other = chat.client.get(
        f"{API}/{resume_id + 1}/document/file", params={"token": link["url"].split("token=")[1]}
    )
    assert other.status_code == 403
    secret = chat.settings.secret_key
    expired = sign_download_token(secret, 1, resume_id, int(chat.clock.now.timestamp()) - 5)
    assert verify_download_token(secret, expired, resume_id, now=chat.clock.now) is None


def test_removing_the_file_or_the_resume_wipes_chunks_and_the_object(
    chat: ChatHarness, db: Session
) -> None:
    resume_id = create_resume(chat)
    script_profile(chat)
    assert upload(chat, resume_id, make_pdf([RESUME_TEXT])).status_code == 201
    assert chat.client.delete(f"{API}/{resume_id}/document").status_code == 204
    assert chat.store.objects == {}
    assert db.scalars(select(ResumeChunk)).all() == []
    assert chat.client.get(f"{API}/{resume_id}").json()["document"] is None

    script_profile(chat)
    assert upload(chat, resume_id, make_pdf([RESUME_TEXT])).status_code == 201
    assert chat.client.delete(f"{API}/{resume_id}").status_code == 204
    assert chat.store.objects == {} and db.scalars(select(ResumeChunk)).all() == []


def test_other_users_cannot_touch_the_file(chat: ChatHarness, db: Session) -> None:
    from app.models.user import User

    resume_id = create_resume(chat)
    script_profile(chat)
    assert upload(chat, resume_id, make_pdf([RESUME_TEXT])).status_code == 201
    other = User(email="other@example.com", full_name="Other", status="active")
    db.add(other)
    db.flush()
    db.info["user"] = other
    assert upload(chat, resume_id, make_pdf([RESUME_TEXT])).status_code == 404
    assert chat.client.get(f"{API}/{resume_id}/document/url").status_code == 404
    assert chat.client.delete(f"{API}/{resume_id}/document").status_code == 404


def test_uploads_are_refused_without_storage(chat: ChatHarness) -> None:
    from app.api.deps import get_object_store
    from app.main import app
    from app.storage.object_store import DisabledObjectStore

    app.dependency_overrides[get_object_store] = lambda: DisabledObjectStore()
    resume_id = create_resume(chat)
    response = upload(chat, resume_id, make_pdf([RESUME_TEXT]))
    assert (response.status_code, response.json()["code"]) == (503, "storage_disabled")


def test_the_assistant_can_read_the_profile_and_search_passages(chat: ChatHarness) -> None:
    resume_id = create_resume(chat)
    script_profile(chat)
    assert upload(chat, resume_id, make_pdf([RESUME_TEXT])).status_code == 201

    chat.groq.script(
        verdict("resumes"),
        tool_call("get_resume_profile", {"resume_id": resume_id}, "c1"),
        tool_call("search_resume", {"query": "payments service"}, "c2"),
        AIMessage(content="Your Fullstack resume lists Python, FastAPI and React."),
    )
    events = send(chat, new_conversation(chat), "What's on my fullstack resume about payments?")
    ends = [d for n, d in events if n == "tool_end"]
    assert [(e["name"], e["ok"]) for e in ends] == [
        ("get_resume_profile", True),
        ("search_resume", True),
    ]
    assert ends[0]["summary"] == "Fullstack" and ends[1]["summary"].endswith(
        "match" if ends[1]["summary"].startswith("1 ") else "matches"
    )
    assert "FastAPI" in text_of(events)


@pytest.mark.parametrize("name", ["../../etc/passwd", "C:\\\\Users\\\\x\\\\cv.pdf"])
def test_file_names_are_reduced_to_a_base_name(chat: ChatHarness, name: str) -> None:
    resume_id = create_resume(chat)
    script_profile(chat)
    response = upload(chat, resume_id, make_pdf([RESUME_TEXT]), name=name)
    assert response.status_code == 201
    assert "/" not in response.json()["file_name"] and ".." not in response.json()["file_name"]
