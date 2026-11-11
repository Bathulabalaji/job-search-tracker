"""Turns message content into HTML and plain text. No business logic lives here."""

import html
from pathlib import Path
from string import Template

_TEMPLATES = Path(__file__).parent / "templates"
_PARAGRAPH_STYLE = "margin:0 0 14px 0;font-size:15px;line-height:1.65;color:#374151;"


def _load(name: str) -> Template:
    return Template((_TEMPLATES / name).read_text(encoding="utf-8"))


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def render_email(
    *,
    app_name: str,
    subject: str,
    preheader: str,
    heading: str,
    paragraphs: list[str],
    button_label: str | None,
    button_url: str | None,
    footnote: str,
) -> tuple[str, str]:
    """Return (html, text). Every dynamic value is HTML-escaped; the layout is a static file."""
    body_html = "".join(f'<p style="{_PARAGRAPH_STYLE}">{_escape(p)}</p>' for p in paragraphs)
    button_html = ""
    if button_label and button_url:
        button_html = _load("button.html").substitute(
            url=_escape(button_url), label=_escape(button_label)
        )
    page = _load("layout.html").substitute(
        app_name=_escape(app_name),
        subject=_escape(subject),
        preheader=_escape(preheader),
        heading=_escape(heading),
        body_html=body_html,
        button_html=button_html,
        footnote=_escape(footnote),
    )
    text_parts = [heading, "", *paragraphs]
    if button_label and button_url:
        text_parts += ["", f"{button_label}: {button_url}"]
    text_parts += ["", footnote, "", f"-- {app_name}"]
    return page, "\n".join(text_parts)
