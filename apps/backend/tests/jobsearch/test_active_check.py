import httpx
import pytest

from app.jobsearch.active_check import ActiveChecker, is_public_host
from tests.jobsearch.helpers import mock_client


def checker(handler: httpx.MockTransport | object) -> ActiveChecker:
    return ActiveChecker(mock_client(handler), timeout=2, host_allowed=lambda _: True)  # type: ignore[arg-type]


def respond(status: int, body: str = "", headers: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body, headers=headers)

    return handler


@pytest.mark.parametrize(
    ("status", "body", "verdict"),
    [
        (200, "<h1>Backend Engineer</h1><button>Apply</button>", "active"),
        (206, "Apply now", "active"),
        (200, "Sorry, this job is no longer accepting applications.", "inactive"),
        (200, "This position has been filled", "inactive"),
        (404, "", "inactive"),
        (410, "", "inactive"),
        (403, "", "unknown"),
        (429, "", "unknown"),
        (503, "", "unknown"),
    ],
)
def test_company_pages_are_read_for_closed_phrases(status: int, body: str, verdict: str) -> None:
    assert checker(respond(status, body)).check("https://careers.acme.example/jobs/1") == verdict


def test_a_redirect_to_the_careers_front_page_means_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/jobs/123":
            return httpx.Response(302, headers={"location": "/careers"})
        return httpx.Response(200, text="All openings")

    assert checker(handler).check("https://acme.example/jobs/123") == "inactive"


def test_a_redirect_to_another_job_page_is_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/j/1":
            return httpx.Response(301, headers={"location": "https://acme.example/jobs/1-backend"})
        return httpx.Response(200, text="Apply")

    assert checker(handler).check("https://acme.example/j/1") == "active"


def test_linkedin_and_naukri_get_a_head_request_only() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(999 if "linkedin" in request.url.host else 200)

    c = checker(handler)
    assert c.check("https://www.linkedin.com/jobs/view/1") == "unknown"  # blocked, not expired
    assert c.check("https://www.naukri.com/job-listings-x-1") == "active"
    assert methods == ["HEAD", "HEAD"]


def test_errors_and_private_addresses_are_unknown() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert checker(boom).check("https://acme.example/jobs/1") == "unknown"
    guarded = ActiveChecker(mock_client(respond(200, "ok")), host_allowed=lambda _: False)
    assert guarded.check("https://acme.example/jobs/1") == "unknown"
    assert checker(respond(200)).check("ftp://acme.example/jobs/1") == "unknown"
    assert not is_public_host("localhost")
    assert not is_public_host("127.0.0.1")
    assert not is_public_host("10.0.0.8")
    assert not is_public_host("169.254.169.254")  # cloud metadata endpoint


def test_check_many_returns_a_verdict_for_every_link() -> None:
    c = checker(respond(200, "Apply"))
    urls = [f"https://acme.example/jobs/{i}" for i in range(7)]
    assert c.check_many(urls) == {u: "active" for u in urls}
