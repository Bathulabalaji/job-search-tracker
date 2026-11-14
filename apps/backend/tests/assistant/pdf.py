"""A tiny PDF writer for tests: one text object per page, readable by pypdf."""

import io

from pypdf import PdfReader, PdfWriter


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[str]) -> bytes:
    objects: list[bytes] = []

    def add(body: str) -> int:
        objects.append(body.encode("latin-1"))
        return len(objects)

    font = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []
    pages_id = len(objects) + 2 * len(pages) + 1  # reserved after pages and contents
    for text in pages:
        lines = text.splitlines() or [""]
        stream = (
            "BT /F1 11 Tf 40 780 Td 14 TL "
            + " ".join(f"({_escape(line)}) Tj T*" for line in lines)
            + " ET"
        )
        content = add(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        page_ids.append(
            add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {font} 0 R >> >> /Contents {content} 0 R >>"
            )
        )
    kids = " ".join(f"{p} 0 R" for p in page_ids)
    assert add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>") == pages_id
    catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\n".encode())
    out.write(f"startxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def encrypt(pdf: bytes, password: str = "secret") -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    writer.encrypt(user_password=password, algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


RESUME_TEXT = """Balaji Bathula
Bengaluru, India | balaji@example.com | +91 98765 43210

Summary
Full-stack engineer with 4 years building Python and React products for fintech teams.

Experience
Senior Software Engineer, Acme Fintech (2023 - present)
- Built a FastAPI payments service handling 2M requests a day on PostgreSQL.
- Led the migration of the React dashboard to TypeScript and TanStack Query.
Software Engineer, Globex (2021 - 2023)
- Shipped Django REST APIs and a Celery pipeline for statement ingestion.

Skills
Python, FastAPI, Django, PostgreSQL, React, TypeScript, Docker, AWS

Education
B.Tech Computer Science, JNTU Hyderabad, 2021

Projects
Open-source LangGraph agent for job tracking with Groq and Gemini models.
"""
