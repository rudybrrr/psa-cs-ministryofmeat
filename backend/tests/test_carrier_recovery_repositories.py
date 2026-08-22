from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from backend.app.domain.carrier_recovery import CarrierRecoveryCase, CarrierRecoveryCaseState
from backend.app.domain.enums import ApprovalStatus, AuditActor
from backend.app.domain.enums import DecisionAction, DecisionStatus
from backend.app.domain.models import Approval, AuditEvent, Decision
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


def test_unique_approval_collision_is_reported_without_aborting_the_session(session: Session) -> None:
    repository = CarrierRecoveryRepository(session)
    proposal_id = uuid4()
    first = Approval(decision_id=proposal_id, operator_id="operator-one", status=ApprovalStatus.APPROVED, created_at=at(6))
    loser = Approval(decision_id=proposal_id, operator_id="operator-two", status=ApprovalStatus.REJECTED, created_at=at(7))

    assert repository.try_add_approval(first) is True
    assert repository.try_add_approval(loser) is False
    assert repository.get_approval_for_proposal(proposal_id) == first


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
