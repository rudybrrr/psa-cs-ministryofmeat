from __future__ import annotations

import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
from backend.app.services.carrier_simulator import (
    DeterministicCarrierSimulator,
    SyntheticCarrierResponsePlan,
)
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository


PREPARE_TIME = "2026-08-22T08:00:00Z"
PREPARED_AT = "2026-08-22T07:00:00Z"
DEADLINE = "2026-08-22T09:00:00Z"
RESPONSE_TIME = "2026-08-22T08:30:00Z"


def _case(client: TestClient, connection_id: str = "SYN-CONN-JV2") -> dict:
    incident_id = client.post("/synthetic/scenarios/canonical-scarcity").json()["incident_id"]
    response = client.post(f"/incidents/{incident_id}/carrier-recovery-cases", json={"connection_id": connection_id, "prepared_at": PREPARED_AT, "requested_eta_pta": PREPARE_TIME, "response_deadline": DEADLINE})
    assert response.status_code == 201, response.text
    return response.json()


def _history(client: TestClient, case_id: str) -> dict:
    response = client.get(f"/carrier-recovery-cases/{case_id}/history")
    assert response.status_code == 200, response.text
    return response.json()


def _outbound_approval(history: dict, status: str = "APPROVED") -> dict:
    binding = history["bindings"][0]
    return {"proposal_decision_id": binding["proposal_decision_id"], "request_id": binding["subject_id"], "expected_payload_fingerprint": binding["payload_fingerprint"], "operator_id": "operator-api", "status": status}


def _counter_approval(history: dict, status: str = "APPROVED") -> dict:
    binding = history["bindings"][-1]
    return {"proposal_decision_id": binding["proposal_decision_id"], "carrier_response_id": binding["subject_id"], "expected_payload_fingerprint": binding["payload_fingerprint"], "operator_id": "operator-api", "status": status}


def _approve_and_send(client: TestClient, case_id: str) -> None:
    response = client.post(f"/carrier-recovery-cases/{case_id}/request-approval", json=_outbound_approval(_history(client, case_id)))
    assert response.status_code == 201, response.text
    response = client.post(f"/carrier-recovery-cases/{case_id}/send")
    assert response.status_code == 201, response.text


def _counter_case(client: TestClient) -> dict:
    case = _case(client, "SYN-CONN-JV2")
    _approve_and_send(client, case["id"])
    response = client.post(f"/carrier-recovery-cases/{case['id']}/simulate-carrier-response", json={"effective_at": RESPONSE_TIME})
    assert response.status_code == 201, response.text
    return case


def _use_demo_simulator(monkeypatch: pytest.MonkeyPatch, run_id: str) -> None:
    simulator = DeterministicCarrierSimulator(
        SyntheticCarrierResponsePlan().load_run(run_id)
    )
    monkeypatch.setattr(
        "backend.app.main.build_carrier_recovery_workflow",
        lambda session: build_carrier_recovery_workflow(session, simulator=simulator),
    )


def test_carrier_recovery_routes_are_exposed_and_no_recompute_route_exists(client: TestClient) -> None:
    routes = {route.path for route in client.app.routes}
    assert {"/incidents/{incident_id}/carrier-recovery-cases", "/carrier-recovery-cases/{case_id}/request-approval", "/carrier-recovery-cases/{case_id}/send", "/carrier-recovery-cases/{case_id}/simulate-carrier-response", "/carrier-recovery-cases/{case_id}/counter-approval", "/carrier-recovery-cases/{case_id}/evaluate-timeout", "/carrier-recovery-cases/{case_id}", "/carrier-recovery-cases/{case_id}/history"} <= routes
    assert all("recompute" not in route for route in routes)


@pytest.mark.parametrize(("requested_eta_pta", "response_deadline"), [("2026-08-22T08:00:00", DEADLINE), ("2026-08-22T08:00:00+08:00", DEADLINE), (PREPARE_TIME, "2026-08-22T09:00:00+08:00")])
def test_prepare_rejects_invalid_command_timestamps_as_422(client: TestClient, requested_eta_pta: str, response_deadline: str) -> None:
    incident_id = client.post("/synthetic/scenarios/canonical-scarcity").json()["incident_id"]
    response = client.post(f"/incidents/{incident_id}/carrier-recovery-cases", json={"connection_id": "SYN-CONN-JV2", "prepared_at": PREPARED_AT, "requested_eta_pta": requested_eta_pta, "response_deadline": response_deadline})
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("prepared_at", "response_deadline"),
    [
        ("2026-08-22T07:00:00", DEADLINE),
        ("2026-08-22T15:00:00+08:00", DEADLINE),
        (DEADLINE, DEADLINE),
    ],
)
def test_prepare_requires_explicit_utc_preparation_time_before_deadline(
    client: TestClient, prepared_at: str, response_deadline: str
) -> None:
    incident_id = client.post("/synthetic/scenarios/canonical-scarcity").json()["incident_id"]
    response = client.post(
        f"/incidents/{incident_id}/carrier-recovery-cases",
        json={
            "connection_id": "SYN-CONN-JV2",
            "prepared_at": prepared_at,
            "requested_eta_pta": PREPARE_TIME,
            "response_deadline": response_deadline,
        },
    )
    assert response.status_code == 422


def test_prepare_accepts_canonical_connection_and_unknown_incident_is_404(client: TestClient) -> None:
    case = _case(client)
    assert _history(client, case["id"])["request_context"]["prepared_at"] == PREPARED_AT
    response = client.post("/incidents/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/carrier-recovery-cases", json={"connection_id": "SYN-CONN-JV2", "prepared_at": PREPARED_AT, "requested_eta_pta": PREPARE_TIME, "response_deadline": DEADLINE})
    assert response.status_code == 404
    response = client.post(f"/incidents/{case['incident_id']}/carrier-recovery-cases", json={"connection_id": "JV2", "prepared_at": PREPARED_AT, "requested_eta_pta": PREPARE_TIME, "response_deadline": DEADLINE})
    assert response.status_code == 409


def test_prepare_reconciles_exact_retry_and_rejects_conflicting_intent(client: TestClient) -> None:
    incident_id = client.post("/synthetic/scenarios/canonical-scarcity").json()["incident_id"]
    url = f"/incidents/{incident_id}/carrier-recovery-cases"
    body = {"connection_id": "SYN-CONN-JV2", "prepared_at": PREPARED_AT, "requested_eta_pta": PREPARE_TIME, "response_deadline": DEADLINE}
    assert client.post(url, json=body).status_code == 201
    assert client.post(url, json=body).status_code == 200
    assert client.post(url, json={**body, "prepared_at": "2026-08-22T07:01:00Z"}).status_code == 409
    assert client.post(url, json={**body, "response_deadline": "2026-08-22T09:01:00Z"}).status_code == 409


def test_request_approval_enforces_subjects_conflicts_and_exact_retries(client: TestClient) -> None:
    case = _case(client)
    url = f"/carrier-recovery-cases/{case['id']}/request-approval"
    body = _outbound_approval(_history(client, case["id"]))
    assert client.post(url, json={**body, "request_id": str(uuid4())}).status_code == 409
    assert client.post(url, json={**body, "expected_payload_fingerprint": "0" * 64}).status_code == 409
    assert client.post(url, json=body).status_code == 201
    assert client.post(url, json=body).status_code == 200
    assert client.post(url, json={**body, "status": "REJECTED"}).status_code == 409
    assert client.post("/carrier-recovery-cases/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/request-approval", json=body).status_code == 404


def test_rejected_request_is_idempotent_and_cannot_be_sent(client: TestClient) -> None:
    case = _case(client)
    url = f"/carrier-recovery-cases/{case['id']}/request-approval"
    body = _outbound_approval(_history(client, case["id"]), "REJECTED")
    assert client.post(url, json=body).status_code == 201
    assert client.post(url, json=body).status_code == 200
    assert client.post(f"/carrier-recovery-cases/{case['id']}/send").status_code == 409


def test_send_requires_approval_and_is_idempotent(client: TestClient) -> None:
    case = _case(client)
    url = f"/carrier-recovery-cases/{case['id']}/send"
    assert client.post(url).status_code == 409
    approval = _outbound_approval(_history(client, case["id"]))
    assert client.post(f"/carrier-recovery-cases/{case['id']}/request-approval", json=approval).status_code == 201
    assert client.post(url).status_code == 201
    assert client.post(url).status_code == 200
    assert client.post("/carrier-recovery-cases/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/send").status_code == 404


def test_accept_simulation_is_durable_and_fail_closed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_demo_simulator(monkeypatch, "ACCEPT-RUN")
    case = _case(client)
    _approve_and_send(client, case["id"])
    url = f"/carrier-recovery-cases/{case['id']}/simulate-carrier-response"
    body = {"effective_at": RESPONSE_TIME}
    assert client.post(url, json=body).status_code == 201
    assert client.post(url, json=body).status_code == 200
    history = _history(client, case["id"])
    assert len(history["carrier_responses"]) == 1
    assert client.post(url, json={"effective_at": "2026-08-22T08:31:00Z"}).status_code == 409


def test_silent_simulation_is_durable_and_persists_no_carrier_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_demo_simulator(monkeypatch, "SILENT-RUN")
    case = _case(client, "SYN-CONN-EC3")
    _approve_and_send(client, case["id"])
    url = f"/carrier-recovery-cases/{case['id']}/simulate-carrier-response"
    body = {"effective_at": RESPONSE_TIME}
    assert client.post(url, json=body).status_code == 201
    assert client.post(url, json=body).status_code == 200
    history = _history(client, case["id"])
    assert history["carrier_responses"] == []
    assert all(event["actor"] != "CARRIER" for event in history["audit_events"])
    assert client.post(url, json={"effective_at": "2026-08-22T08:31:00Z"}).status_code == 409


def test_counter_simulation_creates_single_response_binding_and_audit(client: TestClient) -> None:
    case = _counter_case(client)
    url = f"/carrier-recovery-cases/{case['id']}/simulate-carrier-response"
    assert client.post(url, json={"effective_at": RESPONSE_TIME}).status_code == 200
    history = _history(client, case["id"])
    assert len(history["carrier_responses"]) == 1
    assert len(history["bindings"]) == 2
    assert sum(event["actor"] == "CARRIER" for event in history["audit_events"]) == 1
    assert client.post(url, json={"effective_at": "2026-08-22T08:31:00Z"}).status_code == 409
    assert client.post(url, json={"effective_at": DEADLINE}).status_code == 409


def test_counter_approval_enforces_fresh_binding_and_exact_retry(client: TestClient) -> None:
    case = _counter_case(client)
    history = _history(client, case["id"])
    outbound = _outbound_approval(history)
    body = _counter_approval(history)
    url = f"/carrier-recovery-cases/{case['id']}/counter-approval"
    assert client.post(url, json={
        **body,
        "proposal_decision_id": outbound["proposal_decision_id"],
        "expected_payload_fingerprint": outbound["expected_payload_fingerprint"],
    }).status_code == 409
    assert client.post(url, json={**body, "carrier_response_id": str(uuid4())}).status_code == 409
    assert client.post(url, json={**body, "expected_payload_fingerprint": "0" * 64}).status_code == 409
    assert client.post(url, json=body).status_code == 201
    assert client.post(url, json=body).status_code == 200
    assert client.post(url, json={**body, "status": "REJECTED"}).status_code == 409
    assert client.post("/carrier-recovery-cases/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/counter-approval", json=body).status_code == 404


def test_timeout_requires_deadline_is_idempotent_and_never_creates_response(client: TestClient) -> None:
    case = _case(client, "SYN-CONN-EC3")
    _approve_and_send(client, case["id"])
    url = f"/carrier-recovery-cases/{case['id']}/evaluate-timeout"
    assert client.post(url, json={"effective_at": RESPONSE_TIME}).status_code == 409
    assert client.post(url, json={"effective_at": DEADLINE}).status_code == 201
    assert client.post(url, json={"effective_at": DEADLINE}).status_code == 200
    history = _history(client, case["id"])
    assert history["carrier_responses"] == []
    assert all(event["actor"] != "CARRIER" for event in history["audit_events"])
    assert history["request_context"]["timeout_observed_at"] == DEADLINE
    after_deadline = _case(client, "SYN-CONN-EC3")
    _approve_and_send(client, after_deadline["id"])
    assert client.post(f"/carrier-recovery-cases/{after_deadline['id']}/evaluate-timeout", json={"effective_at": "2026-08-22T09:01:00Z"}).status_code == 201


def test_timeout_after_counter_response_is_conflict(client: TestClient) -> None:
    case = _case(client, "SYN-CONN-JV2")
    _approve_and_send(client, case["id"])
    assert client.post(f"/carrier-recovery-cases/{case['id']}/simulate-carrier-response", json={"effective_at": RESPONSE_TIME}).status_code == 201
    assert client.post(f"/carrier-recovery-cases/{case['id']}/evaluate-timeout", json={"effective_at": DEADLINE}).status_code == 409


def test_timeout_after_accept_response_is_conflict(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_demo_simulator(monkeypatch, "ACCEPT-RUN")
    case = _case(client, "SYN-CONN-JV2")
    _approve_and_send(client, case["id"])
    assert client.post(f"/carrier-recovery-cases/{case['id']}/simulate-carrier-response", json={"effective_at": RESPONSE_TIME}).status_code == 201
    assert client.post(f"/carrier-recovery-cases/{case['id']}/evaluate-timeout", json={"effective_at": DEADLINE}).status_code == 409


@pytest.mark.parametrize("path", ["simulate-carrier-response", "evaluate-timeout"])
@pytest.mark.parametrize("effective_at", ["2026-08-22T08:30:00", "2026-08-22T16:30:00+08:00"])
def test_effective_at_commands_reject_non_explicit_utc(client: TestClient, path: str, effective_at: str) -> None:
    case = _case(client, "SYN-CONN-EC3")
    _approve_and_send(client, case["id"])
    assert client.post(f"/carrier-recovery-cases/{case['id']}/{path}", json={"effective_at": effective_at}).status_code == 422


def test_case_list_detail_and_history_are_scoped_and_404_unknown_resources(client: TestClient) -> None:
    first = _case(client, "SYN-CONN-JV2")
    second_response = client.post(f"/incidents/{first['incident_id']}/carrier-recovery-cases", json={"connection_id": "SYN-CONN-EC3", "prepared_at": PREPARED_AT, "requested_eta_pta": PREPARE_TIME, "response_deadline": DEADLINE})
    assert second_response.status_code == 201
    second = second_response.json()
    listed = client.get(f"/incidents/{first['incident_id']}/carrier-recovery-cases")
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == {first["id"], second["id"]}
    assert client.get("/incidents/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/carrier-recovery-cases").status_code == 404
    assert client.get(f"/carrier-recovery-cases/{first['id']}").status_code == 200
    assert client.get("/carrier-recovery-cases/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa").status_code == 404
    rejected = _outbound_approval(_history(client, first["id"]), "REJECTED")
    assert client.post(f"/carrier-recovery-cases/{first['id']}/request-approval", json=rejected).status_code == 201
    first_history = _history(client, first["id"])
    second_history = _history(client, second["id"])
    assert {event["payload"]["recovery_case_id"] for event in first_history["audit_events"]} == {first["id"]}
    assert not {event["id"] for event in first_history["audit_events"]} & {event["id"] for event in second_history["audit_events"]}
    assert first_history["results"][0]["rejected_approval_id"] == first_history["approvals"][0]["id"]
    assert client.get("/carrier-recovery-cases/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/history").status_code == 404


@pytest.mark.parametrize("status", ["APPROVED", "REJECTED"])
def test_approval_retries_are_http_successes_not_server_errors(client: TestClient, status: str) -> None:
    case = _case(client)
    url = f"/carrier-recovery-cases/{case['id']}/request-approval"
    body = _outbound_approval(_history(client, case["id"]), status)
    first = client.post(url, json=body)
    retry = client.post(url, json=body)
    conflict = client.post(url, json={**body, "status": "REJECTED" if status == "APPROVED" else "APPROVED"})
    assert first.status_code == 201
    assert retry.status_code == 200
    assert conflict.status_code == 409


def test_approval_uniqueness_race_is_http_success_or_conflict_not_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(client)
    url = f"/carrier-recovery-cases/{case['id']}/request-approval"
    body = _outbound_approval(_history(client, case["id"]))
    original = CarrierRecoveryRepository.add_approval
    winner_persisted = False

    def persist_winner_then_raise_unique_error(repository, approval):
        nonlocal winner_persisted
        if winner_persisted:
            return original(repository, approval)
        winner_persisted = True
        with Session(repository.session_bind()) as winner_session:
            original(CarrierRecoveryRepository(winner_session), approval)
        raise IntegrityError(
            "INSERT INTO approvals", {},
            sqlite3.IntegrityError("UNIQUE constraint failed: approvals.decision_id"),
        )

    monkeypatch.setattr(
        CarrierRecoveryRepository, "add_approval", persist_winner_then_raise_unique_error
    )
    assert client.post(url, json=body).status_code == 201
    assert client.post(url, json=body).status_code == 200
    assert client.post(url, json={**body, "status": "REJECTED"}).status_code == 409


def test_phase_three_demo_exercises_accept_counter_and_silent_timeout(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as accept_patch:
        _use_demo_simulator(accept_patch, "ACCEPT-RUN")
        accept_case = _case(client, "SYN-CONN-JV2")
        _approve_and_send(client, accept_case["id"])
        assert client.post(
            f"/carrier-recovery-cases/{accept_case['id']}/simulate-carrier-response",
            json={"effective_at": RESPONSE_TIME},
        ).status_code == 201
        accept_history = _history(client, accept_case["id"])

    with monkeypatch.context() as counter_patch:
        _use_demo_simulator(counter_patch, "COUNTER-RUN")
        counter_case = _counter_case(client)
        counter_history = _history(client, counter_case["id"])
        counter_body = _counter_approval(counter_history)
        assert client.post(
            f"/carrier-recovery-cases/{counter_case['id']}/counter-approval",
            json=counter_body,
        ).status_code == 201
        counter_history = _history(client, counter_case["id"])

    with monkeypatch.context() as silent_patch:
        _use_demo_simulator(silent_patch, "SILENT-RUN")
        silent_case = _case(client, "SYN-CONN-EC3")
        _approve_and_send(client, silent_case["id"])
        assert client.post(
            f"/carrier-recovery-cases/{silent_case['id']}/simulate-carrier-response",
            json={"effective_at": RESPONSE_TIME},
        ).status_code == 201
        assert client.post(
            f"/carrier-recovery-cases/{silent_case['id']}/evaluate-timeout",
            json={"effective_at": DEADLINE},
        ).status_code == 201
        silent_history = _history(client, silent_case["id"])

    assert len(accept_history["carrier_responses"]) == 1
    assert accept_history["effective_timings"][0]["source_kind"] == "ACCEPT"
    assert accept_history["results"]
    assert len(counter_history["carrier_responses"]) == 1
    assert counter_history["effective_timings"][0]["source_kind"] == "APPROVED_COUNTER"
    assert counter_history["results"]
    assert silent_history["carrier_responses"] == []
    assert all(event["actor"] != "CARRIER" for event in silent_history["audit_events"])
    assert silent_history["request_context"]["timeout_observed_at"] == DEADLINE
    assert silent_history["results"]
    assert len(
        {
            accept_case["incident_id"],
            counter_case["incident_id"],
            silent_case["incident_id"],
        }
    ) == 3
