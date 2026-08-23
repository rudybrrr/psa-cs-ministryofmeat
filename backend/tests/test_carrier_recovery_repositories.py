from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from backend.app.domain.carrier_recovery import (
    ApprovalBinding, AuthorizationSubjectKind, CarrierRecoveryCase,
    CarrierRecoveryCaseState, CarrierRecoveryDisposition,
    ContainerReconsiderationResult, EffectiveConnectionTiming,
    ReconsiderationEvidenceKind,
    RTARequestContext, RequestCloseReason,
)
from backend.app.domain.enums import ApprovalStatus, AuditActor, RTARequestStatus
from backend.app.domain.enums import DecisionAction, DecisionStatus
from backend.app.domain.models import Approval, AuditEvent, Decision, RTARequest
from backend.app.storage.repositories import DecisionRepository
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository


def at(hour: int) -> datetime:
    return datetime(2026, 8, 22, hour, tzinfo=UTC)


def make_case() -> CarrierRecoveryCase:
    return CarrierRecoveryCase(
        id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        incident_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        connection_id="SYN-CONN-SF1",
        source_evaluation_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        affected_container_ids=("SYN-CNT-001",),
        state=CarrierRecoveryCaseState.AWAITING_REQUEST_APPROVAL,
        created_at=at(6),
        updated_at=at(6),
    )


def test_case_is_unique_per_incident_and_connection(session: Session) -> None:
    repository = CarrierRecoveryRepository(session)
    case = make_case()
    repository.create_case(case)
    with pytest.raises(IntegrityError):
        with repository.transaction():
            repository.create_case(case.model_copy(update={"id": uuid4()}))


def test_database_allows_only_one_approval_for_one_bound_proposal(session: Session) -> None:
    repository = CarrierRecoveryRepository(session)
    proposal_id = uuid4()
    repository.add_approval(Approval(
        decision_id=proposal_id,
        operator_id="operator-one",
        status=ApprovalStatus.APPROVED,
        created_at=at(6),
    ))

    with pytest.raises(IntegrityError):
        repository.add_approval(Approval(
            decision_id=proposal_id,
            operator_id="operator-two",
            status=ApprovalStatus.REJECTED,
            created_at=at(7),
        ))




def test_transaction_rolls_back_case_and_case_audit_link(session: Session) -> None:
    repository = CarrierRecoveryRepository(session)
    case = make_case()
    event = AuditEvent(
        actor=AuditActor.SYSTEM,
        incident_id=case.incident_id,
        event_type="carrier_recovery.case_prepared",
        payload={"recovery_case_id": str(case.id)},
        timestamp=at(6),
    )
    with pytest.raises(RuntimeError, match="force rollback"):
        with repository.transaction():
            repository.create_case(case)
            repository.link_audit(case.id, event)
            raise RuntimeError("force rollback")
    assert repository.list_cases(case.incident_id) == []


def test_transaction_restores_depth_when_outer_commit_fails(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = CarrierRecoveryRepository(session)

    def fail_commit() -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="commit failed"):
        with repository.transaction():
            pass

    assert repository._transaction_depth == 0


def test_history_uses_structured_case_audit_links(session: Session) -> None:
    repository = CarrierRecoveryRepository(session)
    case = make_case()
    repository.create_case(case)
    event = AuditEvent(
        actor=AuditActor.SYSTEM,
        incident_id=case.incident_id,
        event_type="carrier_recovery.case_prepared",
        payload={"recovery_case_id": str(case.id)},
        timestamp=at(6),
    )
    with repository.transaction():
        repository.link_audit(case.id, event)
    assert repository.history(case.id).audit_events == (event,)


def test_shared_transaction_rolls_back_uncommitted_decision_with_case_artifacts(
    session: Session,
) -> None:
    repository = CarrierRecoveryRepository(session)
    case = make_case()
    decision = Decision(
        incident_id=case.incident_id,
        container_id="SYN-CNT-001",
        action=DecisionAction.ROLL,
        status=DecisionStatus.APPROVED,
        rationale="rollback probe",
        created_at=at(6),
    )

    with pytest.raises(RuntimeError, match="force rollback"):
        with repository.transaction():
            DecisionRepository(session).add_many_uncommitted((decision,))
            repository.create_case(case)
            raise RuntimeError("force rollback")

    assert DecisionRepository(session).list_for_incident(case.incident_id) == []
    assert repository.list_cases(case.incident_id) == []


def test_result_rejects_cross_case_timing_provenance(session: Session) -> None:
    repository = CarrierRecoveryRepository(session)
    case_a = make_case()
    case_b = case_a.model_copy(update={"id": uuid4(), "connection_id": "SYN-CONN-JV2"})
    repository.create_case(case_a)
    repository.create_case(case_b)
    timing = EffectiveConnectionTiming(case_id=case_b.id, request_id=uuid4(), carrier_response_id=uuid4(), effective_eta_pta=at(7), created_at=at(7))
    repository.add_effective_timing(timing)

    with pytest.raises(ValueError, match="timing provenance"):
        repository.add_result(ContainerReconsiderationResult(
            case_id=case_a.id, container_id="SYN-CNT-001", disposition=CarrierRecoveryDisposition.STILL_ROLL,
            prior_decision_id=uuid4(), preserved_world_count=0, world_count=50, hard_constraints_satisfied=True,
            reconsideration_evidence_kind=ReconsiderationEvidenceKind.EFFECTIVE_CONNECTION_TIMING,
            effective_connection_timing_id=timing.id, created_at=at(8),
        ))


@pytest.mark.parametrize(
    ("binding_kind", "evidence_kind"),
    [
        (AuthorizationSubjectKind.COUNTER_PROPOSAL, ReconsiderationEvidenceKind.REQUEST_REJECTED),
        (AuthorizationSubjectKind.OUTBOUND_REQUEST, ReconsiderationEvidenceKind.COUNTER_REJECTED),
    ],
)
def test_result_rejects_wrong_kind_rejected_approval_provenance(session: Session, binding_kind, evidence_kind) -> None:
    repository = CarrierRecoveryRepository(session)
    case = make_case()
    repository.create_case(case)
    proposal_id = uuid4()
    repository.add_approval_binding(ApprovalBinding(case_id=case.id, proposal_decision_id=proposal_id, subject_kind=binding_kind, subject_id=uuid4(), payload_fingerprint="f" * 64, created_at=at(6)))
    approval = Approval(decision_id=proposal_id, operator_id="operator", status=ApprovalStatus.REJECTED, created_at=at(7))
    repository.add_approval(approval)

    with pytest.raises(ValueError, match="rejected approval provenance"):
        repository.add_result(ContainerReconsiderationResult(
            case_id=case.id, container_id="SYN-CNT-001", disposition=CarrierRecoveryDisposition.STILL_ROLL,
            prior_decision_id=uuid4(), preserved_world_count=0, world_count=50, hard_constraints_satisfied=True,
            reconsideration_evidence_kind=evidence_kind, rejected_approval_id=approval.id, created_at=at(8),
        ))


def test_result_rejects_cross_case_rejected_approval_provenance(session: Session) -> None:
    repository = CarrierRecoveryRepository(session)
    case_a = make_case()
    case_b = case_a.model_copy(update={"id": uuid4(), "connection_id": "SYN-CONN-JV2"})
    repository.create_case(case_a); repository.create_case(case_b)
    proposal_id = uuid4()
    repository.add_approval_binding(ApprovalBinding(case_id=case_b.id, proposal_decision_id=proposal_id, subject_kind=AuthorizationSubjectKind.OUTBOUND_REQUEST, subject_id=uuid4(), payload_fingerprint="f" * 64, created_at=at(6)))
    approval = Approval(decision_id=proposal_id, operator_id="operator", status=ApprovalStatus.REJECTED, created_at=at(7))
    repository.add_approval(approval)
    with pytest.raises(ValueError, match="rejected approval provenance"):
        repository.add_result(ContainerReconsiderationResult(case_id=case_a.id, container_id="SYN-CNT-001", disposition=CarrierRecoveryDisposition.STILL_ROLL, prior_decision_id=uuid4(), preserved_world_count=0, world_count=50, hard_constraints_satisfied=True, reconsideration_evidence_kind=ReconsiderationEvidenceKind.REQUEST_REJECTED, rejected_approval_id=approval.id, created_at=at(8)))


def test_result_rejects_cross_case_timeout_context_provenance(session: Session) -> None:
    repository = CarrierRecoveryRepository(session)
    case_a = make_case()
    case_b = case_a.model_copy(update={"id": uuid4(), "connection_id": "SYN-CONN-JV2"})
    repository.create_case(case_a); repository.create_case(case_b)
    request = RTARequest(incident_id=case_b.incident_id, connection_id=case_b.connection_id, requested_eta_pta=at(7), status=RTARequestStatus.CLOSED, created_at=at(6))
    context = RTARequestContext(case_id=case_b.id, request_id=request.id, payload_fingerprint="f" * 64, response_deadline=at(8), sent_at=at(7), closed_at=at(8), close_reason=RequestCloseReason.RESPONSE_TIMEOUT, timeout_observed_at=at(8))
    repository.add_request(request, context)
    with pytest.raises(ValueError, match="timeout provenance"):
        repository.add_result(ContainerReconsiderationResult(case_id=case_a.id, container_id="SYN-CNT-001", disposition=CarrierRecoveryDisposition.STILL_ROLL, prior_decision_id=uuid4(), preserved_world_count=0, world_count=50, hard_constraints_satisfied=True, reconsideration_evidence_kind=ReconsiderationEvidenceKind.RESPONSE_TIMEOUT, timeout_request_context_id=context.case_id, created_at=at(8)))
