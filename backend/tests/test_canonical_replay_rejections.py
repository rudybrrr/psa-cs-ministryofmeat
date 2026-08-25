from uuid import UUID

import pytest

from backend.app.domain.agent_runtime import AgentEscalationReason
from backend.app.services.canonical_replay import (
    CANONICAL_COUNTER_EFFECTIVE_AT,
    CANONICAL_REPLAY_MODEL_NAME,
    SYNTHETIC_DEMO_OPERATOR_ID,
)


@pytest.fixture
def no_credentials(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def _create_incident(client) -> str:
    response = client.post("/synthetic/scenarios/canonical-scarcity")
    assert response.status_code == 201
    return response.json()["incident_id"]


def _stage(client, incident_id: str) -> dict:
    response = client.get(f"/synthetic/scenarios/{incident_id}/canonical-replay/stage")
    assert response.status_code == 200
    return response.json()


def _advance(client, run_id: str):
    return client.post(f"/agent-runs/{run_id}/advance")


def _case_history(client, case_id: str) -> dict:
    response = client.get(f"/carrier-recovery-cases/{case_id}/history")
    assert response.status_code == 200
    return response.json()


def _binding(history: dict, subject_kind: str) -> dict:
    return next(item for item in history["bindings"] if item["subject_kind"] == subject_kind)


def _prepare_to_request_approval(client, incident_id: str) -> tuple[str, str]:
    client.post(f"/synthetic/scenarios/{incident_id}/dynamic-yard/bootstrap")
    run_id = client.post(f"/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs").json()["id"]
    _advance(client, run_id)
    client.post(f"/synthetic/scenarios/{incident_id}/dynamic-yard/discharge-active")
    _advance(client, run_id)
    prepared = _advance(client, run_id).json()
    return run_id, prepared["wait_subject_id"]


def test_request_rejection_leaves_canonical_path_with_typed_reason(client, no_credentials) -> None:
    incident_id = _create_incident(client)
    run_id, case_id = _prepare_to_request_approval(client, incident_id)
    binding = _binding(_case_history(client, case_id), "OUTBOUND_REQUEST")

    rejected = client.post(
        f"/carrier-recovery-cases/{case_id}/request-approval",
        json={
            "proposal_decision_id": binding["proposal_decision_id"],
            "request_id": binding["subject_id"],
            "expected_payload_fingerprint": binding["payload_fingerprint"],
            "operator_id": "operator-console",
            "status": "REJECTED",
        },
    )
    assert rejected.status_code == 201
    assert _case_history(client, case_id)["case"]["state"] in {"COMPLETED", "ESCALATED"}

    stage = _stage(client, incident_id)
    assert stage["stage"] == "OFF_CANONICAL_PATH"
    assert stage["deviation_reason"] == "REQUEST_REJECTED"
    assert stage["status"] == "TERMINAL_HALTED"
    assert stage["next_allowed_action"] == "NONE"

    run = client.get(f"/agent-runs/{run_id}").json()
    assert run["state"] == "WAITING"


def test_counter_rejection_leaves_canonical_path_with_typed_reason(client, no_credentials) -> None:
    incident_id = _create_incident(client)
    run_id, case_id = _prepare_to_request_approval(client, incident_id)
    request_binding = _binding(_case_history(client, case_id), "OUTBOUND_REQUEST")
    client.post(
        f"/carrier-recovery-cases/{case_id}/request-approval",
        json={
            "proposal_decision_id": request_binding["proposal_decision_id"],
            "request_id": request_binding["subject_id"],
            "expected_payload_fingerprint": request_binding["payload_fingerprint"],
            "operator_id": "operator-console",
            "status": "APPROVED",
        },
    )
    _advance(client, run_id)
    client.post(f"/carrier-recovery-cases/{case_id}/simulate-carrier-response", json={"effective_at": CANONICAL_COUNTER_EFFECTIVE_AT})
    _advance(client, run_id)

    counter_binding = _binding(_case_history(client, case_id), "COUNTER_PROPOSAL")
    rejected = client.post(
        f"/carrier-recovery-cases/{case_id}/counter-approval",
        json={
            "proposal_decision_id": counter_binding["proposal_decision_id"],
            "carrier_response_id": counter_binding["subject_id"],
            "expected_payload_fingerprint": counter_binding["payload_fingerprint"],
            "operator_id": SYNTHETIC_DEMO_OPERATOR_ID,
            "status": "REJECTED",
        },
    )
    assert rejected.status_code == 201
    assert _case_history(client, case_id)["case"]["state"] in {"COMPLETED", "ESCALATED"}

    stage = _stage(client, incident_id)
    assert stage["stage"] == "OFF_CANONICAL_PATH"
    assert stage["deviation_reason"] == "COUNTER_REJECTED"
    assert stage["ordinal"] == 12

    run = client.get(f"/agent-runs/{run_id}").json()
    assert run["state"] in {"WAITING", "RUNNING"}


def test_run_advanced_before_bootstrap_fails_safely_into_escalation(client, no_credentials) -> None:
    incident_id = _create_incident(client)
    created = client.post(f"/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs")
    assert created.status_code == 201
    run_id = created.json()["id"]

    advanced = _advance(client, run_id).json()
    assert advanced["state"] == "ESCALATED"
    assert advanced["escalation_reason"] == AgentEscalationReason.INVALID_MODEL_OUTPUT.value

    stage = _stage(client, incident_id)
    assert stage["stage"] == "OFF_CANONICAL_PATH"
    assert stage["deviation_reason"] == "AGENT_ESCALATION_INVALID_MODEL_OUTPUT"

    history = client.get(f"/agent-runs/{run_id}/history").json()
    assert all(invocation["tool_name"] != "prepare_rta_request" for invocation in history["tool_invocations"])
