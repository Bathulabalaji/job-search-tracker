from fastapi.testclient import TestClient


def test_daily_log_flow_and_streak(client: TestClient) -> None:
    created = client.post("/api/v1/daily-logs", json={"applications_sent": 2, "problems_solved": 3})
    assert created.status_code == 201
    assert created.json()["log_date"] == "2026-11-11"

    duplicate = client.post("/api/v1/daily-logs", json={"log_date": "2026-11-11"})
    assert duplicate.status_code == 409

    patched = client.patch(f"/api/v1/daily-logs/{created.json()['id']}", json={"mocks_done": 1})
    assert patched.json()["mocks_done"] == 1

    streak = client.get("/api/v1/daily-logs/streak").json()
    assert streak == {
        "today": "2026-11-11",
        "current": 1,
        "longest": 1,
        "logged_today": True,
        "last_active_date": "2026-11-11",
    }

    listing = client.get("/api/v1/daily-logs", params={"date_from": "2026-11-01"})
    assert [log["log_date"] for log in listing.json()] == ["2026-11-11"]


def test_weekly_target_validation_and_conflict(client: TestClient) -> None:
    assert (
        client.post("/api/v1/weekly-targets", json={"week_start": "2026-11-11"}).status_code == 422
    )
    ok = client.post(
        "/api/v1/weekly-targets", json={"week_start": "2026-11-09", "applications": 10}
    )
    assert ok.status_code == 201
    assert (
        client.post("/api/v1/weekly-targets", json={"week_start": "2026-11-09"}).status_code == 409
    )


def test_prep_item_flow(client: TestClient) -> None:
    item = client.post("/api/v1/prep-items", json={"topic": "CTEs", "category": "db"}).json()
    assert (item["status"], item["confidence"]) == ("todo", 1)
    done = client.patch(
        f"/api/v1/prep-items/{item['id']}", json={"status": "done", "confidence": 4}
    )
    assert done.json()["status"] == "done"
    assert (
        client.post("/api/v1/prep-items", json={"topic": "x", "category": "nope"}).status_code
        == 422
    )
    assert client.delete(f"/api/v1/prep-items/{item['id']}").status_code == 204


def test_analytics_and_summary_endpoints(client: TestClient) -> None:
    client.post("/api/v1/daily-logs", json={"applications_sent": 4})
    client.post("/api/v1/weekly-targets", json={"week_start": "2026-11-09", "applications": 8})

    weekly = client.get("/api/v1/analytics/weekly")
    assert weekly.status_code == 200
    body = weekly.json()
    assert body["week_start"] == "2026-11-09"
    assert body["is_current_week"] is True
    assert len(body["daily"]) == 7 and len(body["trend"]) == 8
    applications = next(p for p in body["progress"] if p["metric"] == "applications")
    assert (applications["actual"], applications["target"], applications["percent"]) == (4, 8, 50.0)

    assert (
        client.get("/api/v1/analytics/weekly", params={"week_of": "2026-11-01"}).json()[
            "week_start"
        ]
        == "2026-10-26"
    )

    summary = client.get("/api/v1/dashboard/summary").json()
    assert summary["total"] == 0 and summary["response_rate"] is None
    assert summary["counts_per_stage"]["found"] == 0


def test_resume_flow(client: TestClient) -> None:
    created = client.post(
        "/api/v1/resumes",
        json={"label": "Backend", "focus": "Python", "file_name": "cv_backend.pdf", "version": "3"},
    )
    assert created.status_code == 201
    resume_id = created.json()["id"]

    assert (
        client.post("/api/v1/resumes", json={"label": "x", "file_name": "a/b.pdf"}).status_code
        == 422
    )
    assert client.get("/api/v1/resumes", params={"q": "python"}).json()[0]["id"] == resume_id
    patched = client.patch(f"/api/v1/resumes/{resume_id}", json={"version": "4"})
    assert patched.json()["version"] == "4"
    assert client.delete(f"/api/v1/resumes/{resume_id}").status_code == 204
    assert client.get(f"/api/v1/resumes/{resume_id}").status_code == 404


def test_contact_search_endpoint(client: TestClient) -> None:
    client.post("/api/v1/contacts", json={"name": "Asha Rao", "company": "Acme"})
    client.post("/api/v1/contacts", json={"name": "Ben Cole", "company": "Globex"})
    found = client.get("/api/v1/contacts", params={"q": "acme"}).json()
    assert [c["name"] for c in found] == ["Asha Rao"]
