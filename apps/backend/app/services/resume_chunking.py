"""Splits resume text into passages worth embedding.

Section headings keep related lines together (a skills list, one job's bullets); long
sections are windowed with an overlap so a sentence on a boundary is still found.
"""

import re
from dataclasses import dataclass

from app.llm.tokens import estimate_tokens

TARGET_TOKENS = 350
OVERLAP_TOKENS = 60
MIN_TOKENS = 40
SUMMARY_CHARS = 1_200

_HEADINGS = {
    "summary": ("summary", "profile", "objective", "about me", "about"),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "work history",
        "career history",
        "internships",
        "internship",
    ),
    "education": ("education", "academics", "academic background", "qualifications"),
    "skills": (
        "skills",
        "technical skills",
        "core skills",
        "technologies",
        "tech stack",
        "competencies",
        "tools",
    ),
    "projects": ("projects", "personal projects", "key projects", "academic projects"),
    "certifications": ("certifications", "certificates", "courses", "training", "licenses"),
    "achievements": ("achievements", "awards", "honors", "honours", "publications"),
}
_HEADING_LOOKUP = {name: section for section, names in _HEADINGS.items() for name in names}


@dataclass(frozen=True)
class Chunk:
    index: int
    section: str
    text: str
    token_count: int


def _heading_of(line: str) -> str | None:
    cleaned = re.sub(r"[^a-z &/]", "", line.strip().lower()).strip()
    if not cleaned or len(line.strip()) > 40:
        return None
    return _HEADING_LOOKUP.get(cleaned)


def split_sections(text: str) -> list[tuple[str, str]]:
    """[(section, body)] in document order; text before the first heading is 'header'."""
    sections: list[tuple[str, list[str]]] = [("header", [])]
    for raw in text.splitlines():
        heading = _heading_of(raw)
        if heading is not None:
            sections.append((heading, []))
            continue
        sections[-1][1].append(raw)
    return [(name, "\n".join(lines).strip()) for name, lines in sections if "".join(lines).strip()]


def _windows(body: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[•\-*▪◦]\s)", body) if p.strip()]
    windows: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in paragraphs:
        tokens = estimate_tokens(paragraph)
        if current and size + tokens > TARGET_TOKENS:
            windows.append("\n".join(current))
            # Overlap: carry the tail of the previous window into the next one.
            tail: list[str] = []
            tail_tokens = 0
            for part in reversed(current):
                if tail_tokens + estimate_tokens(part) > OVERLAP_TOKENS:
                    break
                tail.insert(0, part)
                tail_tokens += estimate_tokens(part)
            current, size = tail, tail_tokens
        current.append(paragraph)
        size += tokens
    if current:
        windows.append("\n".join(current))
    return windows


def chunk_resume(text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    compact = " ".join(text.split())
    if compact:
        chunks.append(
            Chunk(0, "overview", compact[:SUMMARY_CHARS], estimate_tokens(compact[:SUMMARY_CHARS]))
        )
    for section, body in split_sections(text):
        for window in _windows(body):
            tokens = estimate_tokens(window)
            if tokens < MIN_TOKENS and chunks and chunks[-1].section == section:
                merged = chunks[-1].text + "\n" + window
                chunks[-1] = Chunk(chunks[-1].index, section, merged, estimate_tokens(merged))
                continue
            chunks.append(Chunk(len(chunks), section, window, tokens))
    return chunks
