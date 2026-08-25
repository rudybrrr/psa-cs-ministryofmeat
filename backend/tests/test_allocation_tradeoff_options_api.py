from fastapi.testclient import TestClient


def test_allocation_tradeoff_options_unknown_incident_is_not_found(client: TestClient) -> None:
    response = client.get("/incidents/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/allocation-tradeoff-options")
    assert response.status_code == 404


def test_allocation_tradeoff_options_is_empty_and_read_only_before_phase_5b(client: TestClient) -> None:
    incident_id = client.post("/synthetic/scenarios/canonical-scarcity").json()["incident_id"]
    paths = [
        "yard-forecast-snapshots", "allocation-revisions", "expedite-commitments",
        "expedite-reconsiderations", "allocation-tradeoff-reviews",
        "allocation-tradeoff-options", "allocation-tradeoff-selections", "audit-events",
    ]
    before = {path: client.get(f"/incidents/{incident_id}/{path}").json() for path in paths}
    response = client.get(f"/incidents/{incident_id}/allocation-tradeoff-options")
    after = {path: client.get(f"/incidents/{incident_id}/{path}").json() for path in paths}
    assert response.status_code == 200
    assert response.json() == []
    assert after == before
