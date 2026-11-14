"""Turn provider hits into comparable postings: canonical links, source site, work mode,
plain text, and dedupe across providers."""

import hashlib
import html
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.jobsearch.base import JobHit

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "ref",
    "refid",
    "trk",
    "trackingid",
    "src",
    "source",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
}
SITE_HOSTS = (
    ("linkedin", ("linkedin.com",)),
    ("naukri", ("naukri.com",)),
    ("indeed", ("indeed.com", "indeed.co.in")),
)
AGGREGATOR_HOSTS = (
    "adzuna.",
    "google.com",
    "glassdoor.",
    "monster",
    "foundit.",
    "shine.com",
    "instahyre.",
    "iimjobs.",
    "hirist.",
    "cutshort.",
    "wellfound.",
    "ziprecruiter.",
    "simplyhired.",
    "talent.com",
    "jooble.",
    "apna.co",
    "timesjobs.",
    "jobrapido.",
    "jobleads.",
    "careerjet.",
    "jobisjob.",
    "learn4good.",
    "bebee.",
    "jobsora.",
    "whatjobs.",
    "jobgether.",
    "dice.com",
)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"[ \t\r\f\v]+")
_LINES = re.compile(r"\n{3,}")
_WORD = re.compile(r"[a-z0-9]+")
_REMOTE = re.compile(r"\b(remote|work from home|wfh|anywhere)\b", re.I)
_HYBRID = re.compile(r"\bhybrid\b", re.I)
_ONSITE = re.compile(r"\b(on-?site|in-?office|work from office|wfo)\b", re.I)
_AGO = re.compile(r"(\d+)\+?\s*(minute|min|hour|hr|day|week|month)s?\s+ago", re.I)


def canonical_url(url: str) -> str:
    """Lower-case host, no fragment, no tracking parameters. LinkedIn `/jobs/view/{id}` and
    Naukri `...-{id}` paths are kept whole because the id is what identifies the job."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path or "/"
    if host.endswith("linkedin.com"):
        match = re.search(r"/jobs/view/(?:[^/]*-)?(\d+)", path)
        if match:
            return f"https://linkedin.com/jobs/view/{match.group(1)}"
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit((scheme, host, path, urlencode(sorted(query)), ""))


def host_of(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def source_site(url: str, via: str | None = None) -> str:
    """linkedin | naukri | indeed | company | other: where the apply link really goes."""
    host = host_of(url)
    for site, hosts in SITE_HOSTS:
        if any(host == h or host.endswith("." + h) for h in hosts):
            return site
    if via:
        lowered = via.lower()
        for site, _ in SITE_HOSTS:
            if site in lowered:
                return site
    if any(marker in host for marker in AGGREGATOR_HOSTS):
        return "other"
    return "company" if host else "other"


def strip_html(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"(?i)<\s*(br|/p|/li|/div|/h\d)\s*/?>", "\n", text)
    text = html.unescape(_TAG.sub(" ", text))
    lines = [_SPACE.sub(" ", line).strip() for line in text.splitlines()]
    cleaned = _LINES.sub("\n\n", "\n".join(lines)).strip()
    return cleaned or None


def detect_work_mode(*texts: str | None) -> str | None:
    joined = " ".join(t for t in texts if t)
    if _HYBRID.search(joined):
        return "hybrid"
    if _REMOTE.search(joined):
        return "remote"
    if _ONSITE.search(joined):
        return "onsite"
    return None


def parse_relative(text: str | None, now: datetime) -> datetime | None:
    """'3 days ago', '30+ days ago', '5 hours ago' -> an approximate timestamp."""
    if not text:
        return None
    if re.search(r"\b(today|just now|just posted)\b", text, re.I):
        return now
    if re.search(r"\byesterday\b", text, re.I):
        return now - timedelta(days=1)
    match = _AGO.search(text)
    if not match:
        return None
    n, unit = int(match.group(1)), match.group(2).lower()
    if unit.startswith("min"):
        return now - timedelta(minutes=n)
    if unit in ("hour", "hr"):
        return now - timedelta(hours=n)
    if unit == "day":
        return now - timedelta(days=n)
    if unit == "week":
        return now - timedelta(weeks=n)
    return now - timedelta(days=30 * n)


def _norm(text: str | None) -> str:
    return " ".join(_WORD.findall((text or "").lower()))


def fingerprint(company: str, title: str, location: str | None) -> str:
    city = _norm((location or "").split(",")[0])
    key = f"{_norm(company)}|{_norm(title)}|{city}"
    return hashlib.sha1(key.encode()).hexdigest()


def dedupe(hits: list[JobHit]) -> list[JobHit]:
    """Same canonical link, or same company + title + city: keep the freshest (then the one
    with the longer description). Order of first appearance is preserved."""
    chosen: dict[str, JobHit] = {}
    order: list[str] = []
    by_url: dict[str, str] = {}
    for hit in hits:
        url_key = canonical_url(hit.url)
        fp = fingerprint(hit.company, hit.title, hit.location)
        key = by_url.get(url_key) or (fp if fp in chosen else None)
        if key is None:
            chosen[fp] = hit
            order.append(fp)
            by_url[url_key] = fp
            continue
        by_url[url_key] = key
        current = chosen[key]
        if _better(hit, current):
            chosen[key] = hit
    return [chosen[k] for k in order]


def _better(new: JobHit, old: JobHit) -> bool:
    if new.posted_at and old.posted_at and new.posted_at != old.posted_at:
        return new.posted_at > old.posted_at
    if new.posted_at and not old.posted_at:
        return True
    return len(new.description or "") > len(old.description or "")
