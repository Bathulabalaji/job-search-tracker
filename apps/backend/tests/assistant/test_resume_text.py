from app.services.pii import redact, verhoeff_valid
from app.services.resume_chunking import chunk_resume, split_sections
from tests.assistant.pdf import RESUME_TEXT


def test_identifiers_are_redacted_but_contact_details_and_figures_survive() -> None:
    text = (
        "Aadhaar: 2345 6789 0123\nPAN: ABCDE1234F\nPassport No: M1234567\n"
        "Account no: 1234 5678 9012 34\nIFSC: HDFC0001234\nDOB: 12 March 1998\n"
        "password: hunter2\nCard 4111 1111 1111 1111\n"
        "Phone +91 98765 43210, email me@example.com, handled 1200 000 tickets in 2023."
    )
    out = redact(text)
    for leaked in (
        "ABCDE1234F",
        "M1234567",
        "HDFC0001234",
        "hunter2",
        "4111 1111 1111 1111",
        "12 March 1998",
        "1234 5678 9012 34",
    ):
        assert leaked not in out, leaked
    assert "[REDACTED_ID]" in out and "password: [REDACTED]" in out
    assert "+91 98765 43210" in out and "me@example.com" in out and "1200 000" in out
    assert redact(out) == out  # idempotent


def test_aadhaar_needs_a_valid_checksum_so_ordinary_12_digit_numbers_stay() -> None:
    assert verhoeff_valid("234567890125") is False
    assert "2345 6789 0125" in redact("ref 2345 6789 0125")
    valid = next(f"23456789012{d}" for d in range(10) if verhoeff_valid(f"23456789012{d}"))
    assert valid not in redact(f"UID {valid}")


def test_sections_are_detected_and_chunks_keep_them_together() -> None:
    names = [name for name, _ in split_sections(RESUME_TEXT)]
    assert names == ["header", "summary", "experience", "skills", "education", "projects"]
    chunks = chunk_resume(RESUME_TEXT)
    assert chunks[0].section == "overview"
    assert {c.section for c in chunks} >= {"experience", "skills"}
    assert all(c.token_count > 0 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    skills = next(c for c in chunks if c.section == "skills")
    assert "FastAPI" in skills.text and "PostgreSQL" in skills.text


def test_long_sections_are_windowed_with_overlap() -> None:
    bullets = "\n".join(
        f"- Delivered feature number {i} for a large enterprise client." for i in range(80)
    )
    chunks = [c for c in chunk_resume("Experience\n" + bullets) if c.section == "experience"]
    assert len(chunks) >= 3
    assert all(c.token_count <= 420 for c in chunks)
    assert any(line in chunks[1].text for line in chunks[0].text.splitlines()[-2:])  # overlap
