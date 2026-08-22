from datetime import datetime
from uuid import UUID

from fastapi.testclient import TestClient


EXPECTED_ALLOCATION = (
    "SYN-CNT-002",
    "SYN-CNT-004",
    "SYN-CNT-005",
    "SYN-CNT-010",
    "SYN-CNT-011",
    "SYN-CNT-012",
    "SYN-CNT-014",
    "SYN-CNT-015",
)


def test_trigger_canonical_scarcity_scenario(client: TestClient) -> None:
    response = client.post("/synthetic/scenarios/canonical-scarcity")

    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {
        "incident_id",
        "evaluation_id",
        "decision_ids",
        "reproducibility_key",
    }
    assert UUID(payload["incident_id"])
    assert UUID(payload["evaluation_id"])
    assert all(UUID(decision_id) for decision_id in payload["decision_ids"])
    assert len(payload["decision_ids"]) == 8
    assert len(payload["reproducibility_key"]) == 64


def test_get_scarcity_evaluation_reads_persisted_report(
    client: TestClient,
) -> None:
    triggered = client.post(
        "/synthetic/scenarios/canonical-scarcity"
    ).json()

    response = client.get(
        f"/incidents/{triggered['incident_id']}/scarcity-evaluation"
    )

    assert response.status_code == 200
    report = response.json()
    assert report["id"] == triggered["evaluation_id"]
    assert report["incident_id"] == triggered["incident_id"]
    assert report["fixture_id"] == "SYN-CANONICAL-24-V1"
    assert report["seed"] == 20260822
    assert report["scenario_count"] == 50
    assert report["baseline"]["capacity_violations"] == 0
    assert report["baseline"]["unsafe_allocations"] == 0
    assert report["selected_allocation"]["allocated_container_ids"] == list(
        EXPECTED_ALLOCATION
    )
    expected_decision_count = len(
        report["selected_allocation"]["allocated_container_ids"]
    )
    assert len(triggered["decision_ids"]) == expected_decision_count
    assert report["reproducibility_key"] == triggered["reproducibility_key"]
    assert datetime.fromisoformat(report["created_at"]).tzinfo is not None


def test_unknown_scarcity_evaluation_returns_404(client: TestClient) -> None:
    response = client.get(
        "/incidents/ffffffff-ffff-4fff-8fff-ffffffffffff/scarcity-evaluation"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Scarcity evaluation not found"}


def test_repeated_triggers_are_semantically_reproducible(
    client: TestClient,
) -> None:
    first = client.post("/synthetic/scenarios/canonical-scarcity").json()
    second = client.post("/synthetic/scenarios/canonical-scarcity").json()

    assert first["incident_id"] != second["incident_id"]
    assert first["evaluation_id"] != second["evaluation_id"]
    assert first["decision_ids"] != second["decision_ids"]
    assert first["reproducibility_key"] == second["reproducibility_key"]


def test_scarcity_audit_exposes_system_solver_policy_and_no_agent(
    client: TestClient,
) -> None:
    triggered = client.post(
        "/synthetic/scenarios/canonical-scarcity"
    ).json()

    response = client.get(
        f"/incidents/{triggered['incident_id']}/audit-events"
    )

    assert response.status_code == 200
    events = response.json()
    actors = {event["actor"] for event in events}
    assert actors == {"SYSTEM", "SOLVER", "POLICY"}
    assert "AGENT" not in actors
    assert all(event["actor_id"] for event in events)
    assert {
        "baseline.evaluated",
        "scenario_aware.optimized",
        "scarcity.pareto_evaluated",
        "scarcity.evaluation_persisted",
    } <= {event["event_type"] for event in events}


def test_original_one_container_api_still_works(client: TestClient) -> None:
    response = client.post("/synthetic/scenarios/schedule-delay")

    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {"incident_id", "decision_id"}


def test_openapi_contains_both_scarcity_routes_and_original_routes(
    client: TestClient,
) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/synthetic/scenarios/canonical-scarcity" in paths
    assert "post" in paths["/synthetic/scenarios/canonical-scarcity"]
    assert "/incidents/{incident_id}/scarcity-evaluation" in paths
    assert "get" in paths["/incidents/{incident_id}/scarcity-evaluation"]
    assert "/synthetic/scenarios/schedule-delay" in paths


def test_optional_canonical_fixture_endpoint_is_read_only_and_validated(
    client: TestClient,
) -> None:
    response = client.get(
        "/synthetic/scenarios/canonical-scarcity/fixture"
    )

    assert response.status_code == 200
    fixture = response.json()
    assert fixture["fixture_id"] == "SYN-CANONICAL-24-V1"
    assert fixture["event"]["terminal_id"] == "SYN-TUAS-TERMINAL"
    assert len(fixture["profiles"]) == 24
    assert client.post(
        "/synthetic/scenarios/canonical-scarcity/fixture"
    ).status_code == 405
