from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session

from backend.app.domain.carrier_recovery import PrepareCarrierRecoveryCaseCommand
from backend.app.domain.carrier_recovery import RequestApprovalCommand
from backend.app.domain.enums import ApprovalStatus, DecisionAction, DecisionStatus
from backend.app.orchestration.carrier_recovery import CarrierRecoveryConflict, build_carrier_recovery_workflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
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
    case = workflow.prepare(command(phase_two.incident.id, "JV2"))

    assert case.incident_id == phase_two.incident.id
    assert case.source_evaluation_id == phase_two.report.id
    assert case.connection_id == "JV2"
    assert case.affected_container_ids
    history = workflow.history(case.id)
    assert history.request is not None
    assert history.request.connection_id == "JV2"


def test_prepare_creates_fallback_rolls_with_explicit_current_decision_lineage(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "JV2"))
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


def test_request_approval_requires_exact_proposal_request_and_fingerprint(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "JV2"))
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
    case = workflow.prepare(command(phase_two.incident.id, "JV2"))
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


def test_request_rejection_closes_authorization_without_a_dead_end(session: Session) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "JV2"))
    binding = workflow.history(case.id).bindings[0]

    workflow.record_request_approval(RequestApprovalCommand(
        case_id=case.id,
        proposal_decision_id=binding.proposal_decision_id,
        request_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id="operator-18",
        status=ApprovalStatus.REJECTED,
    ))

    assert workflow.history(case.id).case.state.value == "RECOMPUTING"


def test_send_requires_exact_approved_binding(session: Session) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "JV2"))

    with pytest.raises(CarrierRecoveryConflict):
        workflow.send_authorised_request(case.id)


def test_send_is_idempotent_after_exact_approval(session: Session) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "JV2"))
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
