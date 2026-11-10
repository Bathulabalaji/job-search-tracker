from fastapi.testclient import TestClient


def _create(client: TestClient, **overrides: object) -> int:
    body: dict[str, object] = {"company": "Acme", "role": "Dev", **overrides}
    response = client.post("/api/v1/opportunities", json=body)
    assert response.status_code == 201, response.text
    opp_id = response.json()["id"]
    assert isinstance(opp_id, int)
    return opp_id


def test_opportunity_crud_roundtrip(client: TestClient) -> None:
    opp_id = _create(client, stack_tags=["python"])

    assert client.get(f"/api/v1/opportunities/{opp_id}").json()["company"] == "Acme"

    patched = client.patch(f"/api/v1/opportunities/{opp_id}", json={"priority": 1})
    assert patched.status_code == 200
    assert patched.json()["priority"] == 1

    assert client.delete(f"/api/v1/opportunities/{opp_id}").status_code == 204
    assert client.get(f"/api/v1/opportunities/{opp_id}").status_code == 404


def test_move_endpoint_returns_interaction_and_followup(client: TestClient) -> None:
    opp_id = _create(client)

    response = client.post(f"/api/v1/opportunities/{opp_id}/move", json={"stage": "applied"})
    assert response.status_code == 200
    body = response.json()
    assert body["opportunity"]["stage"] == "applied"
    assert body["interaction"]["type"] == "stage_change"
    assert body["followup_created"]["due_date"] == "2026-11-13"

    timeline = client.get("/api/v1/interactions", params={"opportunity_id": opp_id}).json()
    assert len(timeline) == 1


def test_move_to_same_stage_returns_409(client: TestClient) -> None:
    opp_id = _create(client, stage="applied")
    response = client.post(f"/api/v1/opportunities/{opp_id}/move", json={"stage": "applied"})
    assert response.status_code == 409


def test_validation_errors_return_422(client: TestClient) -> None:
    assert (
        client.post(
            "/api/v1/opportunities", json={"company": "A", "role": "B", "priority": 9}
        ).status_code
        == 422
    )
    assert client.post("/api/v1/opportunities", json={"company": "A"}).status_code == 422
    opp_id = _create(client)
    assert (
        client.patch(f"/api/v1/opportunities/{opp_id}", json={"company": None}).status_code == 422
    )
    assert (
        client.patch(f"/api/v1/opportunities/{opp_id}", json={"stage": "applied"}).json()["stage"]
        == "found"
    )


def test_followup_done_via_patch(client: TestClient) -> None:
    opp_id = _create(client, stage="applied")
    (followup,) = client.get("/api/v1/followups", params={"opportunity_id": opp_id}).json()

    response = client.patch(f"/api/v1/followups/{followup['id']}", json={"status": "done"})
    assert response.status_code == 200
    assert response.json()["done_at"] is not None


def test_contact_and_interaction_endpoints(client: TestClient) -> None:
    opp_id = _create(client)
    contact = client.post(
        "/api/v1/contacts", json={"name": "Asha", "role": "recruiter", "opportunity_id": opp_id}
    )
    assert contact.status_code == 201

    interaction = client.post(
        "/api/v1/interactions",
        json={
            "opportunity_id": opp_id,
            "contact_id": contact.json()["id"],
            "type": "call",
            "direction": "in",
        },
    )
    assert interaction.status_code == 201
    assert interaction.json()["direction"] == "in"

    missing = client.post("/api/v1/interactions", json={"opportunity_id": 999_999, "type": "call"})
    assert missing.status_code == 404
