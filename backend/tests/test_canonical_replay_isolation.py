from uuid import UUID

import pytest

from backend.app.services.canonical_replay import (
    CANONICAL_COUNTER_EFFECTIVE_AT,
    CANONICAL_REPLAY_MODEL_NAME,
)


@pytest.fixture
def no_credentials(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def _create_incident(client) -> str:
    response = client.post("/synthetic/scenarios/canonical-scarcity")
    assert response.status_code == 201
    return response.json()["incident_id"]


def _stage(client, incident_id: str) -> dict:
    return client.get(f"/synthetic/scenarios/{incident_id}/canonical-replay/stage").json()


def _advance_ok(client, run_id: str) -> dict:
    response = client.post(f"/agent-runs/{run_id}/advance")
    assert response.status_code == 200
    return response.json()


def _case_history(client, case_id: str) -> dict:
    return client.get(f"/carrier-recovery-cases/{case_id}/history").json()


def _binding(history: dict, subject_kind: str) -> dict:
    return next(item for item in history["bindings"] if item["subject_kind"] == subject_kind)


def _run_full_replay(client, operator_id: str) -> dict:
    incident_id = _create_incident(client)
    client.post(f"/synthetic/scenarios/{incident_id}/dynamic-yard/bootstrap")
    run_id = client.post(f"/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs").json()["id"]
    _advance_ok(client, run_id)
    client.post(f"/synthetic/scenarios/{incident_id}/dynamic-yard/discharge-active")
    _advance_ok(client, run_id)
    prepared = _advance_ok(client, run_id)
    case_id = prepared["wait_subject_id"]
    request_binding = _binding(_case_history(client, case_id), "OUTBOUND_REQUEST")
    approval = client.post(
        f"/carrier-recovery-cases/{case_id}/request-approval",
        json={
            "proposal_decision_id": request_binding["proposal_decision_id"],
            "request_id": request_binding["subject_id"],
            "expected_payload_fingerprint": request_binding["payload_fingerprint"],
            "operator_id": operator_id,
            "status": "APPROVED",
        },
    )
    assert approval.status_code == 201
    _advance_ok(client, run_id)
    simulated = client.post(f"/carrier-recovery-cases/{case_id}/simulate-carrier-response", json={"effective_at": CANONICAL_COUNTER_EFFECTIVE_AT})
    assert simulated.status_code == 201
    conflict = client.post(f"/agent-runs/{run_id}/advance")
    assert conflict.status_code == 409
    counter_binding = _binding(_case_history(client, case_id), "COUNTER_PROPOSAL")
    counter = client.post(
        f"/carrier-recovery-cases/{case_id}/counter-approval",
        json={
            "proposal_decision_id": counter_binding["proposal_decision_id"],
            "carrier_response_id": counter_binding["subject_id"],
            "expected_payload_fingerprint": counter_binding["payload_fingerprint"],
            "operator_id": operator_id,
            "status": "APPROVED",
        },
    )
    assert counter.status_code == 201
    review = client.post(
        f"/incidents/{incident_id}/cargo-safety-reviews",
        json={"container_id": "SYN-CNT-010", "note": {"text": "Manifest declares general cargo; free-text handling note identifies corrosive material and requires safety review.", "source": "synthetic-canonical-cargo-note"}},
    )
    assert review.status_code == 201
    terminal = _advance_ok(client, run_id)
    assert terminal["state"] == "ESCALATED"
    assert _stage(client, incident_id)["stage"] == "SAFETY_BLOCKED"
    return {"incident_id": incident_id, "run_id": run_id, "case_id": case_id, "review_id": review.json()["id"]}


def test_repeat_replays_are_isolated_by_incident(client, no_credentials) -> None:
    first = _run_full_replay(client, "operator-console")
    second = _run_full_replay(client, "synthetic-demo-operator")

    assert first["incident_id"] != second["incident_id"]
    assert first["run_id"] != second["run_id"]
    assert first["case_id"] != second["case_id"]
    assert first["review_id"] != second["review_id"]

    for replay in (first, second):
        revisions = {revision["id"] for revision in client.get(f"/incidents/{replay['incident_id']}/allocation-revisions").json()}
        cases = {case["id"] for case in client.get(f"/incidents/{replay['incident_id']}/carrier-recovery-cases").json()}
        reviews = {review["id"] for review in client.get(f"/incidents/{replay['incident_id']}/cargo-safety-reviews").json()}
        runs = {item["id"] for item in client.get(f"/incidents/{replay['incident_id']}/agent-runs").json()}
        other = second if replay is first else first
        assert revisions & {r["id"] for r in client.get(f"/incidents/{other['incident_id']}/allocation-revisions").json()} == set()
        assert cases == {replay["case_id"]}
        assert reviews == {replay["review_id"]}
        assert runs == {replay["run_id"]}


def test_legacy_direct_counter_and_silent_paths_still_work_alongside_demo_run(client, no_credentials) -> None:
    """Legacy direct Phase 3 narratives stay functional next to an active demo run.

    ACCEPT semantics through this endpoint family are pinned by the frozen
    Phase 3 suite (which injects the ACCEPT-RUN carrier plan); the default
    direct-API simulator serves the COUNTER-RUN plan, proven here end-to-end.
    """
    demo_incident = _create_incident(client)
    client.post(f"/synthetic/scenarios/{demo_incident}/dynamic-yard/bootstrap")
    demo_run = client.post(f"/synthetic/scenarios/{demo_incident}/canonical-replay/agent-runs")
    assert demo_run.status_code == 201
    assert _stage(client, demo_incident)["next_allowed_action"] == "ADVANCE_AGENT"
    counter_incident = _create_incident(client)
    counter_case = client.post(
        f"/incidents/{counter_incident}/carrier-recovery-cases",
        json={
            "connection_id": "SYN-CONN-JV2",
            "prepared_at": "2026-08-22T07:00:00Z",
            "requested_eta_pta": "2026-08-22T08:00:00Z",
            "response_deadline": "2026-08-22T09:00:00Z",
        },
    ).json()
    counter_history = _case_history(client, counter_case["id"])
    request_binding = _binding(counter_history, "OUTBOUND_REQUEST")
    approved = client.post(
        f"/carrier-recovery-cases/{counter_case['id']}/request-approval",
        json={
            "proposal_decision_id": request_binding["proposal_decision_id"],
            "request_id": request_binding["subject_id"],
            "expected_payload_fingerprint": request_binding["payload_fingerprint"],
            "operator_id": "operator-console",
            "status": "APPROVED",
        },
    )
    assert approved.status_code == 201
    sent = client.post(f"/carrier-recovery-cases/{counter_case['id']}/send")
    assert sent.status_code == 201
    simulated = client.post(
        f"/carrier-recovery-cases/{counter_case['id']}/simulate-carrier-response",
        json={"effective_at": "2026-08-22T08:30:00Z"},
    )
    assert simulated.status_code == 201
    after_sim = _case_history(client, counter_case["id"])["case"]["state"]
    assert after_sim == "AWAITING_COUNTER_APPROVAL"
    counter_binding = _binding(_case_history(client, counter_case["id"]), "COUNTER_PROPOSAL")
    countered = client.post(
        f"/carrier-recovery-cases/{counter_case['id']}/counter-approval",
        json={
            "proposal_decision_id": counter_binding["proposal_decision_id"],
            "carrier_response_id": counter_binding["subject_id"],
            "expected_payload_fingerprint": counter_binding["payload_fingerprint"],
            "operator_id": "operator-console",
            "status": "APPROVED",
        },
    )
    assert countered.status_code == 201
    assert _case_history(client, counter_case["id"])["case"]["state"] == "COMPLETED"

    silent_incident = _create_incident(client)
    silent_case = client.post(
        f"/incidents/{silent_incident}/carrier-recovery-cases",
        json={
            "connection_id": "SYN-CONN-EC3",
            "prepared_at": "2026-08-22T07:00:00Z",
            "requested_eta_pta": "2026-08-22T08:00:00Z",
            "response_deadline": "2026-08-22T09:00:00Z",
        },
    ).json()
    silent_history = _case_history(client, silent_case["id"])
    silent_binding = _binding(silent_history, "OUTBOUND_REQUEST")
    client.post(
        f"/carrier-recovery-cases/{silent_case['id']}/request-approval",
        json={
            "proposal_decision_id": silent_binding["proposal_decision_id"],
            "request_id": silent_binding["subject_id"],
            "expected_payload_fingerprint": silent_binding["payload_fingerprint"],
            "operator_id": "operator-console",
            "status": "APPROVED",
        },
    )
    client.post(f"/carrier-recovery-cases/{silent_case['id']}/send")
    timed_out = client.post(
        f"/carrier-recovery-cases/{silent_case['id']}/evaluate-timeout",
        json={"effective_at": "2026-08-22T09:05:00Z"},
    )
    assert timed_out.status_code == 201
    assert _case_history(client, silent_case["id"])["case"]["state"] in {"COMPLETED", "ESCALATED"}

    assert _stage(client, demo_incident)["next_allowed_action"] == "ADVANCE_AGENT"
    demo_run_body = client.get(f"/agent-runs/{demo_run.json()['id']}").json()
    assert demo_run_body["model_name"] == CANONICAL_REPLAY_MODEL_NAME
