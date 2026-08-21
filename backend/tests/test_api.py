from datetime import datetime
from uuid import UUID

from fastapi.testclient import TestClient


def test_trigger_synthetic_schedule_delay_returns_persisted_ids(
    client: TestClient,
) -> None:
    response = client.post("/synthetic/scenarios/schedule-delay")

    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {"incident_id", "decision_id"}
    assert UUID(payload["incident_id"])
    assert UUID(payload["decision_id"])


def test_get_incident_returns_persisted_resolved_incident(
    client: TestClient,
) -> None:
    triggered = client.post("/synthetic/scenarios/schedule-delay").json()

    response = client.get(f"/incidents/{triggered['incident_id']}")

    assert response.status_code == 200
    incident = response.json()
    assert incident["id"] == triggered["incident_id"]
    assert incident["source_event_id"] == "SYN-EVT-20260821-001"
    assert incident["state"] == "RESOLVED"
    assert datetime.fromisoformat(incident["created_at"]).tzinfo is not None


def test_unknown_incident_returns_404(client: TestClient) -> None:
    response = client.get(
        "/incidents/ffffffff-ffff-4fff-8fff-ffffffffffff"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}


def test_get_decisions_returns_persisted_policy_decision_in_order(
    client: TestClient,
) -> None:
    triggered = client.post("/synthetic/scenarios/schedule-delay").json()

    response = client.get(
        f"/incidents/{triggered['incident_id']}/decisions"
    )

    assert response.status_code == 200
    decisions = response.json()
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["id"] == triggered["decision_id"]
    assert decision["incident_id"] == triggered["incident_id"]
    assert decision["container_id"] == "PSAU1234567"
    assert decision["action"] == "EXPEDITE"
    assert decision["status"] == "APPROVED"
    assert decision["supersedes"] is None
    assert decision["supersession_reason"] is None
    assert "Normal transfer misses the synthetic cutoff" in decision["rationale"]
    assert datetime.fromisoformat(decision["created_at"]).tzinfo is not None


def test_get_audit_events_preserves_append_sequence_and_evidence(
    client: TestClient,
) -> None:
    triggered = client.post("/synthetic/scenarios/schedule-delay").json()

    response = client.get(
        f"/incidents/{triggered['incident_id']}/audit-events"
    )

    assert response.status_code == 200
    events = response.json()
    assert [event["event_type"] for event in events] == [
        "schedule.delay_ingested",
        "incident.created",
        "incident.state_transitioned",
        "manifest.container_loaded",
        "yard.forecast_retrieved",
        "incident.state_transitioned",
        "connection.feasibility_evaluated",
        "incident.state_transitioned",
        "decision.created",
        "incident.state_transitioned",
    ]
    assert [event["actor"] for event in events] == [
        "SYSTEM",
        "SYSTEM",
        "SYSTEM",
        "SYSTEM",
        "SYSTEM",
        "SYSTEM",
        "POLICY",
        "SYSTEM",
        "POLICY",
        "SYSTEM",
    ]
    assert [event["actor_id"] for event in events] == [
        "synthetic-schedule-service",
        "transshipment-recovery-workflow",
        "transshipment-recovery-workflow",
        "synthetic-manifest-service",
        "synthetic-yard-service",
        "transshipment-recovery-workflow",
        "connection-feasibility-policy",
        "transshipment-recovery-workflow",
        "dominance-policy",
        "transshipment-recovery-workflow",
    ]
    assert events[0]["incident_id"] == triggered["incident_id"]
    assert events[0]["payload"] == {
        "event_id": "SYN-EVT-20260821-001",
        "vessel_call_id": "SYN-VC-SOUTHERN-STAR-01",
        "terminal_id": "SYN-TUAS-TERMINAL",
        "delay_minutes": 90,
    }
    assert events[-1]["payload"] == {
        "from": "RECOVERY_ANALYSIS",
        "to": "RESOLVED",
    }
    assert all(event["actor"] != "AGENT" for event in events)
    assert all(
        datetime.fromisoformat(event["timestamp"]).tzinfo is not None
        for event in events
    )
