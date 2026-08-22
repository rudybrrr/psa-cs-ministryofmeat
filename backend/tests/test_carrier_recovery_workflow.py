from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session

from backend.app.domain.carrier_recovery import PrepareCarrierRecoveryCaseCommand
from backend.app.domain.carrier_recovery import (
    CounterApprovalCommand,
    EvaluateTimeoutCommand,
    RequestApprovalCommand,
    SimulateCarrierResponseCommand,
)
from backend.app.domain.enums import ApprovalStatus, AuditActor, DecisionAction, DecisionStatus
from backend.app.orchestration.carrier_recovery import CarrierRecoveryConflict, build_carrier_recovery_workflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
from backend.app.services.carrier_simulator import (
    CarrierResponsePlan,
    DeterministicCarrierSimulator,
)
from backend.app.storage.repositories import DecisionRepository


def command(incident_id, connection_id: str) -> PrepareCarrierRecoveryCaseCommand:
    return PrepareCarrierRecoveryCaseCommand(
        incident_id=incident_id,
        connection_id=connection_id,
        requested_eta_pta="2026-08-22T08:00:00Z",
        response_deadline="2026-08-22T09:00:00Z",
    )


def test_prepare_reuses_resolved_phase_two_evidence_and_freezes_connection_snapshot(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))

    assert case.incident_id == phase_two.incident.id
    assert case.source_evaluation_id == phase_two.report.id
    assert case.connection_id == "SYN-CONN-JV2"
    assert case.affected_container_ids == ("SYN-CNT-017",)
    history = workflow.history(case.id)
    assert history.request is not None
    assert history.request.connection_id == "SYN-CONN-JV2"


def test_prepare_creates_fallback_rolls_with_explicit_current_decision_lineage(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))
    decisions = DecisionRepository(session).list_for_incident(phase_two.incident.id)
    fallbacks = [
        item for item in decisions
        if item.action is DecisionAction.ROLL and item.container_id in case.affected_container_ids
    ]
    proposal = [item for item in decisions if item.action is DecisionAction.REQUEST_RTA]

    assert len(fallbacks) == len(case.affected_container_ids)
    assert all(item.status is DecisionStatus.APPROVED for item in fallbacks)
    assert all("zero preserved worlds" in (item.supersession_reason or "") or item.supersedes is None for item in fallbacks)
    assert len(proposal) == 1
    assert proposal[0].container_id is None


def test_prepare_rolls_back_staged_decisions_when_case_artifacts_fail(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    before = DecisionRepository(session).list_for_incident(phase_two.incident.id)

    def fail_after_decisions(*_args, **_kwargs) -> None:
        raise RuntimeError("force preparation rollback")

    monkeypatch.setattr(workflow._cases, "add_approval_binding", fail_after_decisions)

    with pytest.raises(RuntimeError, match="force preparation rollback"):
        workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))

    assert DecisionRepository(session).list_for_incident(phase_two.incident.id) == before
    assert workflow._cases.list_cases(phase_two.incident.id) == []


def test_request_approval_requires_exact_proposal_request_and_fingerprint(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))
    history = workflow.history(case.id)
    binding = history.bindings[0]
    exact = RequestApprovalCommand(
        case_id=case.id,
        proposal_decision_id=binding.proposal_decision_id,
        request_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id="operator-17",
        status=ApprovalStatus.APPROVED,
    )

    approval = workflow.record_request_approval(exact)

    assert approval.decision_id == exact.proposal_decision_id
    assert approval.operator_id == "operator-17"
    assert workflow.record_request_approval(exact) == approval


def test_request_approval_rejects_stale_subject_without_creating_approval(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))
    binding = workflow.history(case.id).bindings[0]
    exact = RequestApprovalCommand(
        case_id=case.id,
        proposal_decision_id=binding.proposal_decision_id,
        request_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id="operator-17",
        status=ApprovalStatus.APPROVED,
    )

    with pytest.raises(CarrierRecoveryConflict):
        workflow.record_request_approval(exact.model_copy(update={"request_id": uuid4()}))


def test_counter_simulation_rolls_back_proposal_when_binding_fails(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))
    binding = workflow.history(case.id).bindings[0]
    workflow.record_request_approval(RequestApprovalCommand(
        case_id=case.id,
        proposal_decision_id=binding.proposal_decision_id,
        request_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id="operator-transaction",
        status=ApprovalStatus.APPROVED,
    ))
    workflow.send_authorised_request(case.id)
    before = DecisionRepository(session).list_for_incident(phase_two.incident.id)

    def fail_counter_binding(*_args, **_kwargs) -> None:
        raise RuntimeError("force counter rollback")

    monkeypatch.setattr(workflow._cases, "add_approval_binding", fail_counter_binding)

    with pytest.raises(RuntimeError, match="force counter rollback"):
        workflow.simulate_response(SimulateCarrierResponseCommand(
            case_id=case.id,
            effective_at="2026-08-22T08:30:00Z",
        ))

    assert DecisionRepository(session).list_for_incident(phase_two.incident.id) == before
    history = workflow.history(case.id)
    assert history.carrier_responses == ()
    assert history.case.state.value == "AWAITING_CARRIER"


def test_request_rejection_closes_authorization_and_recomputes_without_a_dead_end(session: Session) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))
    binding = workflow.history(case.id).bindings[0]

    workflow.record_request_approval(RequestApprovalCommand(
        case_id=case.id,
        proposal_decision_id=binding.proposal_decision_id,
        request_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id="operator-18",
        status=ApprovalStatus.REJECTED,
    ))

    history = workflow.history(case.id)
    assert history.case.state.value in {"COMPLETED", "ESCALATED"}
    assert history.request is not None
    assert history.request.status.value == "CLOSED"
    assert history.request_context is not None
    assert history.request_context.closed_at is not None
    assert history.results


def test_send_requires_exact_approved_binding(session: Session) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))

    with pytest.raises(CarrierRecoveryConflict):
        workflow.send_authorised_request(case.id)


def test_send_is_idempotent_after_exact_approval(session: Session) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))
    binding = workflow.history(case.id).bindings[0]
    workflow.record_request_approval(RequestApprovalCommand(
        case_id=case.id,
        proposal_decision_id=binding.proposal_decision_id,
        request_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id="operator-19",
        status=ApprovalStatus.APPROVED,
    ))

    first = workflow.send_authorised_request(case.id)
    second = workflow.send_authorised_request(case.id)
    history = workflow.history(case.id)

    assert second == first
    assert history.case.state.value == "AWAITING_CARRIER"
    assert history.request is not None
    assert history.request.status.value == "SENT"
    assert history.request_context is not None
    assert history.request_context.sent_at is not None
    assert [event.event_type for event in history.audit_events].count("rta.request_sent") == 1


def test_prepare_rejects_service_label_when_connection_id_is_required(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)

    with pytest.raises(CarrierRecoveryConflict, match="unknown connection"):
        workflow.prepare(command(phase_two.incident.id, "JV2"))


def approve_and_send(workflow, case) -> None:
    binding = workflow.history(case.id).bindings[0]
    workflow.record_request_approval(RequestApprovalCommand(
        case_id=case.id,
        proposal_decision_id=binding.proposal_decision_id,
        request_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id="operator-20",
        status=ApprovalStatus.APPROVED,
    ))
    workflow.send_authorised_request(case.id)


def test_silent_plan_returns_no_response_and_persists_no_carrier_event(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-EC3"))
    approve_and_send(workflow, case)

    result = workflow.simulate_response(SimulateCarrierResponseCommand(
        case_id=case.id,
        effective_at="2026-08-22T08:30:00Z",
    ))
    history = workflow.history(case.id)

    assert result.no_response_emitted is True
    assert history.carrier_responses == ()
    assert AuditActor.CARRIER not in {event.actor for event in history.audit_events}


def test_simulator_rejects_effective_at_at_or_after_deadline(session: Session) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-EC3"))
    approve_and_send(workflow, case)

    with pytest.raises(CarrierRecoveryConflict):
        workflow.simulate_response(SimulateCarrierResponseCommand(
            case_id=case.id,
            effective_at="2026-08-22T09:00:00Z",
        ))


def accept_simulator_for_jv2() -> DeterministicCarrierSimulator:
    return DeterministicCarrierSimulator(CarrierResponsePlan.model_validate({
        "plan_id": "TEST-ACCEPT-V1",
        "fixture_id": "SYN-CANONICAL-24-V1",
        "responses": [{"connection_id": "SYN-CONN-JV2", "outcome": "ACCEPT"}],
    }))


def test_accept_creates_effective_requested_timing_without_second_approval(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(
        session,
        simulator=accept_simulator_for_jv2(),
    )
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))
    approve_and_send(workflow, case)

    result = workflow.simulate_response(SimulateCarrierResponseCommand(
        case_id=case.id,
        effective_at="2026-08-22T08:30:00Z",
    ))
    history = workflow.history(case.id)

    assert result.carrier_response_id is not None
    assert history.carrier_responses[0].response.value == "ACCEPT"
    assert history.effective_timings[0].effective_eta_pta == history.request.requested_eta_pta
    assert history.case.state.value in {"COMPLETED", "ESCALATED"}


def test_counter_requires_fresh_exact_approval_before_effective_timing(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))
    approve_and_send(workflow, case)

    response = workflow.simulate_response(SimulateCarrierResponseCommand(
        case_id=case.id,
        effective_at="2026-08-22T08:30:00Z",
    ))
    history = workflow.history(case.id)

    assert response.carrier_response_id is not None
    assert history.effective_timings == ()
    assert history.case.state.value == "AWAITING_COUNTER_APPROVAL"
    assert history.bindings[-1].subject_kind.value == "COUNTER_PROPOSAL"


def test_approved_counter_creates_exact_effective_timing_idempotently(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))
    approve_and_send(workflow, case)
    workflow.simulate_response(SimulateCarrierResponseCommand(
        case_id=case.id,
        effective_at="2026-08-22T08:30:00Z",
    ))
    binding = workflow.history(case.id).bindings[-1]
    exact = CounterApprovalCommand(
        case_id=case.id,
        proposal_decision_id=binding.proposal_decision_id,
        carrier_response_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id="operator-21",
        status=ApprovalStatus.APPROVED,
    )

    first = workflow.record_counter_approval(exact)
    second = workflow.record_counter_approval(exact)
    history = workflow.history(case.id)

    assert first == second
    assert history.effective_timings[0].effective_eta_pta == history.carrier_responses[0].counter_eta_pta
    assert history.case.state.value in {"COMPLETED", "ESCALATED"}


def test_rejected_counter_uses_no_counter_effective_timing(session: Session) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))
    approve_and_send(workflow, case)
    workflow.simulate_response(SimulateCarrierResponseCommand(
        case_id=case.id,
        effective_at="2026-08-22T08:30:00Z",
    ))
    binding = workflow.history(case.id).bindings[-1]

    workflow.record_counter_approval(CounterApprovalCommand(
        case_id=case.id,
        proposal_decision_id=binding.proposal_decision_id,
        carrier_response_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id="operator-22",
        status=ApprovalStatus.REJECTED,
    ))
    history = workflow.history(case.id)

    assert history.effective_timings == ()
    assert history.case.state.value in {"COMPLETED", "ESCALATED"}


def test_timeout_at_deadline_observes_absence_once_and_retries_idempotently(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-EC3"))
    approve_and_send(workflow, case)
    at_deadline = EvaluateTimeoutCommand(
        case_id=case.id,
        effective_at="2026-08-22T09:00:00Z",
    )

    first = workflow.evaluate_timeout(at_deadline)
    second = workflow.evaluate_timeout(at_deadline)
    history = workflow.history(case.id)

    assert second == first
    assert history.case.state.value in {"COMPLETED", "ESCALATED"}
    assert history.carrier_responses == ()
    assert [event.event_type for event in history.audit_events].count("carrier.response_timed_out") == 1
    assert AuditActor.CARRIER not in {event.actor for event in history.audit_events}


def test_timeout_before_deadline_and_after_response_fail_closed(session: Session) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    silent_case = workflow.prepare(command(phase_two.incident.id, "SYN-CONN-EC3"))
    approve_and_send(workflow, silent_case)

    with pytest.raises(CarrierRecoveryConflict):
        workflow.evaluate_timeout(EvaluateTimeoutCommand(
            case_id=silent_case.id,
            effective_at="2026-08-22T08:59:00Z",
        ))

    accepting = build_carrier_recovery_workflow(
        session,
        simulator=accept_simulator_for_jv2(),
    )
    accept_case = accepting.prepare(command(phase_two.incident.id, "SYN-CONN-JV2"))
    approve_and_send(accepting, accept_case)
    accepting.simulate_response(SimulateCarrierResponseCommand(
        case_id=accept_case.id,
        effective_at="2026-08-22T08:30:00Z",
    ))

    with pytest.raises(CarrierRecoveryConflict):
        accepting.evaluate_timeout(EvaluateTimeoutCommand(
            case_id=accept_case.id,
            effective_at="2026-08-22T09:00:00Z",
        ))
