"""Is a posting still open? A best-effort look at the apply link.

LinkedIn and Naukri get a HEAD request only: their status code is all we read, no page content
is ever fetched from them. Other sites get a small ranged GET and a check for "no longer
accepting applications"-style phrases. Anything ambiguous (blocked, timeout, odd status) is
"unknown", never "inactive": a false "expired" would hide a real job.

Links come from third-party APIs, so the checker refuses to fetch private or local addresses.
"""

import ipaddress
import logging
import re
import socket
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Literal
from urllib.parse import urljoin, urlsplit

import httpx

from app.jobsearch.normalize import host_of

logger = logging.getLogger("app.jobsearch")

Status = Literal["active", "inactive", "unknown"]
MAX_REDIRECTS = 3
MAX_BYTES = 64_000
HEAD_ONLY_HOSTS = ("linkedin.com", "naukri.com")
CLOSED = re.compile(
    r"no longer accepting applications|(job|position|posting|vacancy|role) (is |has )?"
    r"(no longer (available|open|active)|been filled|closed|expired)|this job has expired"
    r"|job not found|position has been filled|applications? (are |is )?(now )?closed",
    re.I,
)
LISTING_PATHS = re.compile(r"^/(jobs|careers|search|job-search|openings)?/?$", re.I)
USER_AGENT = "Mozilla/5.0 (compatible; JobSmartPilot/1.0; job-link-check)"


def is_public_host(host: str) -> bool:
    """True only when every address the name resolves to is a public one."""
    if not host or host in ("localhost",) or host.endswith((".local", ".internal")):
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if not address.is_global:
            return False
    return True


class ActiveChecker:
    def __init__(
        self,
        client: httpx.Client,
        *,
        timeout: float = 5.0,
        host_allowed: Callable[[str], bool] = is_public_host,
    ) -> None:
        self.client = client
        self.timeout = timeout
        self.host_allowed = host_allowed

    def check(self, url: str) -> Status:
        try:
            return self._check(url)
        except Exception:  # never let a link check fail a search
            logger.info("job_active_check_failed", extra={"host": host_of(url)})
            return "unknown"

    def check_many(self, urls: list[str], *, budget_seconds: float = 6.0) -> dict[str, Status]:
        results: dict[str, Status] = {u: "unknown" for u in urls}
        if not urls:
            return results
        pool = ThreadPoolExecutor(max_workers=min(5, len(urls)), thread_name_prefix="job-check")
        futures = {pool.submit(self.check, u): u for u in urls}
        done, _ = wait(futures, timeout=budget_seconds)
        for future in done:
            results[futures[future]] = future.result()
        pool.shutdown(wait=False, cancel_futures=True)
        return results

    def _check(self, url: str) -> Status:
        head_only = any(
            host_of(url) == h or host_of(url).endswith("." + h) for h in HEAD_ONLY_HOSTS
        )
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            parts = urlsplit(current)
            if parts.scheme not in ("http", "https") or not self.host_allowed(parts.hostname or ""):
                return "unknown"
            if head_only:
                response = self.client.head(
                    current, timeout=self.timeout, headers={"User-Agent": USER_AGENT}
                )
                body = ""
            else:
                response, body = self._get(current)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    return "unknown"
                nxt = urljoin(current, location)
                if _is_listing_redirect(current, nxt):
                    return "inactive"
                current = nxt
                continue
            status = response.status_code
            if status in (404, 410):
                return "inactive"
            if 200 <= status < 300:
                if body and CLOSED.search(body):
                    return "inactive"
                return "active"
            return "unknown"  # 403, 429, 999 (LinkedIn), 5xx...
        return "unknown"

    def _get(self, url: str) -> tuple[httpx.Response, str]:
        with self.client.stream(
            "GET",
            url,
            timeout=self.timeout,
            headers={"User-Agent": USER_AGENT, "Range": f"bytes=0-{MAX_BYTES - 1}"},
        ) as response:
            if response.is_redirect or response.status_code >= 300:
                return response, ""
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= MAX_BYTES:
                    break
            return response, b"".join(chunks)[:MAX_BYTES].decode("utf-8", errors="ignore")


def _is_listing_redirect(old: str, new: str) -> bool:
    """A job page that bounces to the careers front page (or a search page) has closed."""
    a, b = urlsplit(old), urlsplit(new)
    if a.path.rstrip("/") == b.path.rstrip("/"):
        return False
    return bool(LISTING_PATHS.match(b.path or "/")) or "error=" in b.query
