"""Two accounts must never see, change or count each other's data."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.opportunity import Opportunity
from tests.auth_helpers import API, make_user, sign_in

Pair = tuple[TestClient, dict[str, str], TestClient, dict[str, str]]


@pytest.fixture
def two_users(
    auth_client: TestClient, db: Session
) -> tuple[TestClient, dict[str, str], TestClient, dict[str, str]]:
    make_user(db, "alice@example.com", name="Alice Walker")
    make_user(db, "bob@example.com", name="Bob Stone")
    bob = TestClient(auth_client.app, base_url="http://localhost:5173")
    return (
        auth_client,
        sign_in(auth_client, "alice@example.com"),
        bob,
        sign_in(bob, "bob@example.com"),
    )


def _create(client: TestClient, headers: dict[str, str], path: str, body: dict[str, object]) -> int:
    response = client.post(f"{API}{path}", json=body, headers=headers)
    assert response.status_code == 201, response.text
    created_id = response.json()["id"]
    assert isinstance(created_id, int)
    return created_id


def test_lists_only_contain_your_own_rows(two_users: Pair) -> None:
    alice, a_h, bob, b_h = two_users
    _create(alice, a_h, "/opportunities", {"company": "AliceCo", "role": "Dev"})
    _create(bob, b_h, "/opportunities", {"company": "BobCo", "role": "Dev"})

    assert [o["company"] for o in alice.get(f"{API}/opportunities").json()] == ["AliceCo"]
    assert [o["company"] for o in bob.get(f"{API}/opportunities").json()] == ["BobCo"]


@pytest.mark.parametrize(
    ("collection", "body"),
    [
        ("/opportunities", {"company": "Secret", "role": "x"}),
        ("/contacts", {"name": "Secret Person"}),
        ("/prep-items", {"topic": "Secret topic", "category": "python"}),
        ("/resumes", {"label": "Secret resume"}),
        ("/weekly-targets", {"week_start": "2026-11-09", "applications": 5}),
        ("/daily-logs", {"log_date": "2026-11-11", "applications_sent": 3}),
    ],
)
def test_you_cannot_read_change_or_delete_someone_elses_row(
    two_users: Pair,
    collection: str,
    body: dict[str, object],
) -> None:
    alice, a_h, bob, b_h = two_users
    row_id = _create(alice, a_h, collection, body)
    url = f"{API}{collection}/{row_id}"

    # To Bob, Alice's row simply does not exist (404, not 403: no hint that it is there).
    assert bob.get(url).status_code == 404
    assert bob.patch(url, json={}, headers=b_h).status_code == 404
    assert bob.delete(url, headers=b_h).status_code == 404
    assert alice.get(url).status_code == 200  # still intact


def test_you_cannot_attach_your_rows_to_someone_elses_opportunity(two_users: Pair) -> None:
    alice, a_h, bob, b_h = two_users
    opp_id = _create(alice, a_h, "/opportunities", {"company": "AliceCo", "role": "Dev"})

    attempts = [
        ("/interactions", {"opportunity_id": opp_id, "type": "call"}),
        ("/followups", {"opportunity_id": opp_id, "due_date": "2026-11-12"}),
        ("/contacts", {"name": "Sneaky", "opportunity_id": opp_id}),
    ]
    for path, body in attempts:
        assert bob.post(f"{API}{path}", json=body, headers=b_h).status_code == 404, path

    assert (
        bob.post(
            f"{API}/opportunities/{opp_id}/move", json={"stage": "applied"}, headers=b_h
        ).status_code
        == 404
    )


def test_ownership_comes_from_the_session_not_the_request(two_users: Pair, db: Session) -> None:
    alice, a_h, bob, _ = two_users
    bob_id = bob.get(f"{API}/auth/me").json()["user"]["id"]
    response = alice.post(
        f"{API}/opportunities",
        json={"company": "AliceCo", "role": "Dev", "user_id": bob_id},
        headers=a_h,
    )
    # user_id is not a field of the request, so it is ignored; the row belongs to Alice.
    assert response.status_code == 201
    row = db.scalars(select(Opportunity).where(Opportunity.company == "AliceCo")).one()
    assert row.user_id != bob_id


def test_the_same_day_can_be_logged_by_both_users(two_users: Pair) -> None:
    alice, a_h, bob, b_h = two_users
    body = {"log_date": "2026-11-11", "applications_sent": 2}
    _create(alice, a_h, "/daily-logs", body)
    _create(bob, b_h, "/daily-logs", body)  # no clash: uniqueness is per user
    duplicate = alice.post(f"{API}/daily-logs", json=body, headers=a_h)
    assert duplicate.status_code == 409


def test_the_same_week_can_have_targets_for_both_users(two_users: Pair) -> None:
    alice, a_h, bob, b_h = two_users
    body = {"week_start": "2026-11-09", "applications": 5}
    _create(alice, a_h, "/weekly-targets", body)
    _create(bob, b_h, "/weekly-targets", body)


def test_analytics_and_dashboards_only_count_your_data(two_users: Pair) -> None:
    alice, a_h, bob, b_h = two_users
    _create(alice, a_h, "/opportunities", {"company": "A1", "role": "x", "stage": "applied"})
    _create(alice, a_h, "/opportunities", {"company": "A2", "role": "x", "stage": "applied"})
    _create(alice, a_h, "/daily-logs", {"log_date": "2026-11-11", "applications_sent": 9})

    assert alice.get(f"{API}/dashboard/summary").json()["total"] == 2
    assert bob.get(f"{API}/dashboard/summary").json()["total"] == 0
    assert alice.get(f"{API}/analytics/weekly").json()["scorecard"]["applications_total"] == 2
    bobs = bob.get(f"{API}/analytics/weekly").json()
    assert bobs["scorecard"]["applications_total"] == 0
    assert bobs["totals"]["applications"] == 0
    assert bobs["scorecard"]["current_streak"] == 0
    assert bob.get(f"{API}/dashboard/today").json()["followups"] == []
    assert len(alice.get(f"{API}/dashboard/today").json()["followups"]) == 0  # due in 2 days
    assert bob.get(f"{API}/daily-logs/streak").json()["current"] == 0


def test_search_and_filters_never_cross_users(two_users: Pair) -> None:
    alice, a_h, bob, b_h = two_users
    _create(alice, a_h, "/contacts", {"name": "Shared Name"})
    _create(bob, b_h, "/contacts", {"name": "Shared Name"})
    assert len(alice.get(f"{API}/contacts", params={"q": "Shared"}).json()) == 1
    assert len(bob.get(f"{API}/contacts", params={"q": "Shared"}).json()) == 1


def test_deleting_an_account_removes_only_its_data(two_users: Pair, db: Session) -> None:
    from app.models.user import User

    alice, a_h, bob, b_h = two_users
    _create(alice, a_h, "/opportunities", {"company": "AliceCo", "role": "Dev"})
    _create(bob, b_h, "/opportunities", {"company": "BobCo", "role": "Dev"})
    alice_user = db.scalars(select(User).where(User.email == "alice@example.com")).one()

    db.delete(alice_user)
    db.flush()

    assert [o.company for o in db.scalars(select(Opportunity))] == ["BobCo"]
