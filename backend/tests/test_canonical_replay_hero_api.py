from uuid import UUID

import pytest

from backend.app.services.canonical_replay import (
    CANONICAL_COUNTER_EFFECTIVE_AT,
    CANONICAL_REPLAY_MODEL_NAME,
    CANONICAL_SAFETY_CONTAINER_ID,
    CANONICAL_SAFETY_NOTE_SOURCE,
    CANONICAL_SAFETY_NOTE_TEXT,
    GUIDED_OPERATOR_ID,
    SYNTHETIC_DEMO_OPERATOR_ID,
)


NOTE_TEXT = CANONICAL_SAFETY_NOTE_TEXT


@pytest.fixture
def no_credentials(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_AGENT_MODEL", raising=False)


def _create_incident(client) -> str:
    response = client.post("/synthetic/scenarios/canonical-scarcity")
    assert response.status_code == 201
    return response.json()["incident_id"]


def _stage(client, incident_id: str) -> dict:
    response = client.get(f"/synthetic/scenarios/{incident_id}/canonical-replay/stage")
    assert response.status_code == 200
    return response.json()


def _advance(client, run_id: str) -> dict:
    response = client.post(f"/agent-runs/{run_id}/advance")
    return response


def _case_history(client, case_id: str) -> dict:
    response = client.get(f"/carrier-recovery-cases/{case_id}/history")
    assert response.status_code == 200
    return response.json()


def _binding(history: dict, subject_kind: str) -> dict:
    return next(item for item in history["bindings"] if item["subject_kind"] == subject_kind)


def _drive_to_request_approval(client, incident_id: str) -> tuple[str, str]:
    """Shared hero prefix through JV2 preparation; returns (run_id, case_id)."""
    assert client.post(f"/synthetic/scenarios/{incident_id}/dynamic-yard/bootstrap").status_code == 201
    created = client.post(f"/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs")
    assert created.status_code == 201
    run_id = created.json()["id"]
    assert _advance(client, run_id).json()["wait_kind"] == "NEW_OPERATIONAL_EVIDENCE"
    published = client.post(f"/synthetic/scenarios/{incident_id}/dynamic-yard/discharge-active")
    assert published.status_code == 201
    applied = _advance(client, run_id).json()
    assert applied["state"] == "RUNNING"
    prepared = _advance(client, run_id).json()
    assert prepared["wait_kind"] == "REQUEST_APPROVAL"
    return run_id, prepared["wait_subject_id"]


def _assert_exact_yard_evidence(client, incident_id: str) -> None:
    revisions = client.get(f"/incidents/{incident_id}/allocation-revisions").json()
    r1 = revisions[-1]
    assert r1["allocated_container_ids"] == ["SYN-CNT-001", "SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-010", "SYN-CNT-011", "SYN-CNT-012", "SYN-CNT-014", "SYN-CNT-015"]
    commitments = client.get(f"/incidents/{incident_id}/expedite-commitments").json()
    by_container: dict[str, list[str]] = {}
    for commitment in commitments:
        if commitment["status"] == "CANCELLED":
            continue
        by_container.setdefault(commitment["container_id"], []).append(commitment["status"])
    statuses = {}
    for commitment in sorted(commitments, key=lambda item: item["created_at"]):
        statuses[commitment["container_id"]] = commitment["status"]
    cancelled = {c["container_id"] for c in commitments if c["status"] == "CANCELLED"}
    assert "SYN-CNT-005" in cancelled
    active = [c for c in commitments if c["status"] != "CANCELLED"]
    planned_001 = [c for c in active if c["container_id"] == "SYN-CNT-001" and c["status"] == "PLANNED"]
    assert len(planned_001) == 1
    committed = {c["container_id"]: c["status"] for c in active}
    assert committed["SYN-CNT-002"] == "COMMITTED"
    assert committed["SYN-CNT-004"] == "COMMITTED"
    del by_container


def test_guided_shaped_hero_end_to_end(client, no_credentials) -> None:
    incident_id = _create_incident(client)

    stage = _stage(client, incident_id)
    assert stage["stage"] == "READY_FOR_PRE_DISCHARGE"

    assert client.post(f"/synthetic/scenarios/{incident_id}/dynamic-yard/bootstrap").status_code == 201
    assert _stage(client, incident_id)["stage"] == "READY_TO_START_AGENT"

    created = client.post(f"/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs")
    assert created.status_code == 201
    assert created.json()["model_name"] == CANONICAL_REPLAY_MODEL_NAME
    run_id = created.json()["id"]
    assert _stage(client, incident_id)["next_allowed_action"] == "ADVANCE_AGENT"

    paused = _advance(client, run_id).json()
    assert paused["wait_kind"] == "NEW_OPERATIONAL_EVIDENCE"
    waiting_stage = _stage(client, incident_id)
    assert waiting_stage["status"] == "WAITING_EXTERNAL"
    assert waiting_stage["next_allowed_action"] == "PUBLISH_DISCHARGE_ACTIVE"

    published = client.post(f"/synthetic/scenarios/{incident_id}/dynamic-yard/discharge-active").json()
    assert (published["preserved_connection_total_before"], published["preserved_connection_total_after"]) == (601, 602)
    assert (published["expected_preserved_connections_before"], published["expected_preserved_connections_after"]) == (12.02, 12.04)

    assert _stage(client, incident_id)["next_allowed_action"] == "ADVANCE_AGENT"
    applied = _advance(client, run_id).json()
    assert applied["state"] == "RUNNING"
    _assert_exact_yard_evidence(client, incident_id)

    assert _stage(client, incident_id)["stage"] == "READY_TO_PREPARE_RTA"
    prepared = _advance(client, run_id).json()
    assert prepared["wait_kind"] == "REQUEST_APPROVAL"
    case_id = prepared["wait_subject_id"]

    history = _case_history(client, case_id)
    assert history["case"]["affected_container_ids"] == ["SYN-CNT-017"]
    request_binding = _binding(history, "OUTBOUND_REQUEST")

    approval_stage = _stage(client, incident_id)
    assert approval_stage["stage"] == "REQUEST_APPROVAL_REQUIRED"
    assert approval_stage["requires_human_authority"] is True

    wrong = client.post(
        f"/carrier-recovery-cases/{case_id}/request-approval",
        json={
            "proposal_decision_id": request_binding["proposal_decision_id"],
            "request_id": request_binding["subject_id"],
            "expected_payload_fingerprint": "not-the-fingerprint",
            "operator_id": GUIDED_OPERATOR_ID,
            "status": "APPROVED",
        },
    )
    assert wrong.status_code == 409
    assert _case_history(client, case_id)["approvals"] == []

    approved = client.post(
        f"/carrier-recovery-cases/{case_id}/request-approval",
        json={
            "proposal_decision_id": request_binding["proposal_decision_id"],
            "request_id": request_binding["subject_id"],
            "expected_payload_fingerprint": request_binding["payload_fingerprint"],
            "operator_id": GUIDED_OPERATOR_ID,
            "status": "APPROVED",
        },
    )
    assert approved.status_code == 201
    assert _stage(client, incident_id)["stage"] == "REQUEST_APPROVED_READY_TO_SEND"

    sent = _advance(client, run_id).json()
    assert sent["wait_kind"] == "CARRIER_RESPONSE_OR_TIMEOUT"
    assert _stage(client, incident_id)["stage"] == "WAITING_FOR_CARRIER"

    simulated = client.post(
        f"/carrier-recovery-cases/{case_id}/simulate-carrier-response",
        json={"effective_at": CANONICAL_COUNTER_EFFECTIVE_AT},
    )
    assert simulated.status_code == 201
    full_history = _case_history(client, case_id)
    counter_response = full_history["carrier_responses"][0]
    assert counter_response["response"] == "COUNTER"
    assert counter_response["counter_eta_pta"] == "2026-08-22T06:45:00Z"

    assert _stage(client, incident_id)["stage"] == "CARRIER_COUNTER_RECEIVED"
    conflict = _advance(client, run_id)
    assert conflict.status_code == 409
    assert client.get(f"/agent-runs/{run_id}").json()["wait_kind"] == "COUNTER_APPROVAL"

    counter_stage = _stage(client, incident_id)
    assert counter_stage["stage"] == "COUNTER_APPROVAL_REQUIRED"
    assert counter_stage["requires_human_authority"] is True

    counter_history = _case_history(client, case_id)
    counter_binding = _binding(counter_history, "COUNTER_PROPOSAL")
    counter_approved = client.post(
        f"/carrier-recovery-cases/{case_id}/counter-approval",
        json={
            "proposal_decision_id": counter_binding["proposal_decision_id"],
            "carrier_response_id": counter_binding["subject_id"],
            "expected_payload_fingerprint": counter_binding["payload_fingerprint"],
            "operator_id": GUIDED_OPERATOR_ID,
            "status": "APPROVED",
        },
    )
    assert counter_approved.status_code == 201
    assert _case_history(client, case_id)["case"]["state"] == "COMPLETED"

    resume_stage = _stage(client, incident_id)
    assert resume_stage["stage"] == "COUNTER_APPROVED_READY_TO_RESUME"
    assert resume_stage["next_allowed_action"] == "PERSIST_SAFETY_REVIEW"

    review = client.post(
        f"/incidents/{incident_id}/cargo-safety-reviews",
        json={"container_id": CANONICAL_SAFETY_CONTAINER_ID, "note": {"text": NOTE_TEXT, "source": CANONICAL_SAFETY_NOTE_SOURCE}},
    )
    assert review.status_code == 201
    assert review.json()["state"] == "PENDING_CHECK"
    assert _stage(client, incident_id)["next_allowed_action"] == "ADVANCE_AGENT"

    terminal = _advance(client, run_id).json()
    assert terminal["state"] == "ESCALATED"
    assert terminal["escalation_reason"] == "SAFETY_REVIEW_REQUIRED"
    assert terminal["model_name"] == CANONICAL_REPLAY_MODEL_NAME

    safety_history = client.get(f"/cargo-safety-reviews/{review.json()['id']}/history").json()
    assert safety_history["assessment"]["result"] == "CONTRADICTION_FOUND"
    assert safety_history["policy_result"]["automation_blocked"] is True
    assert safety_history["assessment"]["checker_kind"] == "canonical-replay-deterministic"
    assert safety_history["assessment"]["model_name"] is None
    assert safety_history["note"]["text"] == NOTE_TEXT

    final_stage = _stage(client, incident_id)
    assert final_stage["stage"] == "SAFETY_BLOCKED"
    assert final_stage["ordinal"] == 16
    assert final_stage["status"] == "TERMINAL_SUCCESS"

    run_history = client.get(f"/agent-runs/{run_id}/history").json()
    assert [(item["tool_name"], item["arguments"]) for item in run_history["tool_invocations"]] == [
        ("pause_agent_run", {}),
        ("request_expedite_feasibility", {}),
        ("prepare_rta_request", {"connection_id": "SYN-CONN-JV2"}),
        ("send_authorised_rta_request", {"case_id": case_id}),
        ("request_cargo_safety_review", {"container_id": "SYN-CNT-010"}),
    ]
    assert all(step["model_name"] == CANONICAL_REPLAY_MODEL_NAME for step in run_history["steps"])

    approvals = _case_history(client, case_id)["approvals"]
    assert len(approvals) == 2
    assert all(approval["operator_id"] == GUIDED_OPERATOR_ID for approval in approvals)


def test_auto_shaped_hero_records_synthetic_operator_only(client, no_credentials) -> None:
    incident_id = _create_incident(client)
    client.post(f"/synthetic/scenarios/{incident_id}/dynamic-yard/bootstrap")
    run_id = client.post(f"/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs").json()["id"]
    _advance(client, run_id)
    client.post(f"/synthetic/scenarios/{incident_id}/dynamic-yard/discharge-active")
    _advance(client, run_id)
    prepared = _advance(client, run_id).json()
    case_id = prepared["wait_subject_id"]

    history = _case_history(client, case_id)
    request_binding = _binding(history, "OUTBOUND_REQUEST")
    client.post(
        f"/carrier-recovery-cases/{case_id}/request-approval",
        json={
            "proposal_decision_id": request_binding["proposal_decision_id"],
            "request_id": request_binding["subject_id"],
            "expected_payload_fingerprint": request_binding["payload_fingerprint"],
            "operator_id": SYNTHETIC_DEMO_OPERATOR_ID,
            "status": "APPROVED",
        },
    )
    _advance(client, run_id)
    client.post(f"/carrier-recovery-cases/{case_id}/simulate-carrier-response", json={"effective_at": CANONICAL_COUNTER_EFFECTIVE_AT})
    _advance(client, run_id)
    counter_history = _case_history(client, case_id)
    counter_binding = _binding(counter_history, "COUNTER_PROPOSAL")
    client.post(
        f"/carrier-recovery-cases/{case_id}/counter-approval",
        json={
            "proposal_decision_id": counter_binding["proposal_decision_id"],
            "carrier_response_id": counter_binding["subject_id"],
            "expected_payload_fingerprint": counter_binding["payload_fingerprint"],
            "operator_id": SYNTHETIC_DEMO_OPERATOR_ID,
            "status": "APPROVED",
        },
    )
    client.post(f"/incidents/{incident_id}/cargo-safety-reviews", json={"container_id": CANONICAL_SAFETY_CONTAINER_ID, "note": {"text": NOTE_TEXT, "source": CANONICAL_SAFETY_NOTE_SOURCE}})
    terminal = _advance(client, run_id).json()
    assert terminal["state"] == "ESCALATED"
    assert terminal["escalation_reason"] == "SAFETY_REVIEW_REQUIRED"

    approvals = _case_history(client, case_id)["approvals"]
    assert len(approvals) == 2
    assert all(approval["operator_id"] == SYNTHETIC_DEMO_OPERATOR_ID for approval in approvals)
    audit_events = client.get(f"/incidents/{incident_id}/audit-events").json()
    agent_actor_events = [event for event in audit_events if event["actor"] == "AGENT" and "approval" in event["event_type"]]
    assert agent_actor_events == []
