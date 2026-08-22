from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlmodel import SQLModel, Session, create_engine

from backend.app.domain.carrier_recovery import (
    CounterApprovalCommand,
    PrepareCarrierRecoveryCaseCommand,
    RequestApprovalCommand,
    SimulateCarrierResponseCommand,
)
from backend.app.domain.enums import ApprovalStatus
from backend.app.orchestration.carrier_recovery import (
    CarrierRecoveryConflict,
    build_carrier_recovery_workflow,
)
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow


@pytest.fixture
def concurrent_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'carrier-recovery-race.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _prepare(session: Session):
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(PrepareCarrierRecoveryCaseCommand(
        incident_id=phase_two.incident.id,
        connection_id="SYN-CONN-JV2",
        requested_eta_pta="2026-08-22T08:00:00Z",
        response_deadline="2026-08-22T09:00:00Z",
    ))
    return case, workflow.history(case.id).bindings[0]


def test_independent_sqlite_sessions_characterize_identical_request_approval_race(
    concurrent_engine,
) -> None:
    with Session(concurrent_engine) as setup:
        case, binding = _prepare(setup)
    gate = Barrier(2)

    def approve():
        with Session(concurrent_engine) as database_session:
            workflow = build_carrier_recovery_workflow(database_session)
            original = workflow._cases.add_approval

            def synchronized_add(approval):
                gate.wait()
                return original(approval)

            workflow._cases.add_approval = synchronized_add
            return workflow.record_request_approval(RequestApprovalCommand(
                case_id=case.id,
                proposal_decision_id=binding.proposal_decision_id,
                request_id=binding.subject_id,
                expected_payload_fingerprint=binding.payload_fingerprint,
                operator_id="operator-race",
                status=ApprovalStatus.APPROVED,
            ))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result() for future in (pool.submit(approve), pool.submit(approve))]

    assert outcomes[0] == outcomes[1]


def test_independent_sqlite_sessions_reconcile_conflicting_request_approval_race(
    concurrent_engine,
) -> None:
    with Session(concurrent_engine) as setup:
        case, binding = _prepare(setup)
    gate = Barrier(2)

    def attempt(status: ApprovalStatus):
        try:
            with Session(concurrent_engine) as database_session:
                workflow = build_carrier_recovery_workflow(database_session)
                original = workflow._cases.add_approval

                def synchronized_add(approval):
                    gate.wait()
                    return original(approval)

                workflow._cases.add_approval = synchronized_add
                return workflow.record_request_approval(RequestApprovalCommand(
                    case_id=case.id,
                    proposal_decision_id=binding.proposal_decision_id,
                    request_id=binding.subject_id,
                    expected_payload_fingerprint=binding.payload_fingerprint,
                    operator_id="operator-race",
                    status=status,
                ))
        except Exception as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            future.result()
            for future in (
                pool.submit(attempt, ApprovalStatus.APPROVED),
                pool.submit(attempt, ApprovalStatus.REJECTED),
            )
        ]

    assert sum(isinstance(item, CarrierRecoveryConflict) for item in outcomes) == 1
    assert sum(not isinstance(item, Exception) for item in outcomes) == 1
    assert not any(type(item).__name__ == "IntegrityError" for item in outcomes)
    with Session(concurrent_engine) as verify:
        history = build_carrier_recovery_workflow(verify).history(case.id)
    assert len(history.approvals) == 1
    assert len(history.bindings) == 1
    assert sum(event.actor.value == "OPERATOR" for event in history.audit_events) == 1


@pytest.mark.parametrize(
    ("statuses", "conflicts"),
    [
        ((ApprovalStatus.APPROVED, ApprovalStatus.APPROVED), 0),
        ((ApprovalStatus.APPROVED, ApprovalStatus.REJECTED), 1),
    ],
)
def test_independent_sqlite_sessions_reconcile_counter_approval_race(
    concurrent_engine, statuses, conflicts,
) -> None:
    with Session(concurrent_engine) as setup:
        case, outbound = _prepare(setup)
        workflow = build_carrier_recovery_workflow(setup)
        workflow.record_request_approval(RequestApprovalCommand(
            case_id=case.id, proposal_decision_id=outbound.proposal_decision_id,
            request_id=outbound.subject_id,
            expected_payload_fingerprint=outbound.payload_fingerprint,
            operator_id="operator-race", status=ApprovalStatus.APPROVED,
        ))
        workflow.send_authorised_request(case.id)
        workflow.simulate_response(SimulateCarrierResponseCommand(
            case_id=case.id, effective_at="2026-08-22T08:30:00Z",
        ))
        binding = workflow.history(case.id).bindings[-1]
    gate = Barrier(2)

    def attempt(status: ApprovalStatus):
        try:
            with Session(concurrent_engine) as database_session:
                workflow = build_carrier_recovery_workflow(database_session)
                original = workflow._cases.add_approval

                def synchronized_add(approval):
                    gate.wait()
                    return original(approval)

                workflow._cases.add_approval = synchronized_add
                return workflow.record_counter_approval(CounterApprovalCommand(
                    case_id=case.id, proposal_decision_id=binding.proposal_decision_id,
                    carrier_response_id=binding.subject_id,
                    expected_payload_fingerprint=binding.payload_fingerprint,
                    operator_id="operator-race", status=status,
                ))
        except Exception as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result() for future in (pool.submit(attempt, statuses[0]), pool.submit(attempt, statuses[1]))]

    assert sum(isinstance(item, CarrierRecoveryConflict) for item in outcomes) == conflicts
    assert sum(not isinstance(item, Exception) for item in outcomes) == 2 - conflicts
    with Session(concurrent_engine) as verify:
        history = build_carrier_recovery_workflow(verify).history(case.id)
    counter_approvals = [item for item in history.approvals if item.decision_id == binding.proposal_decision_id]
    assert len(counter_approvals) == 1
    assert len(history.effective_timings) == (1 if counter_approvals[0].status is ApprovalStatus.APPROVED else 0)
    assert sum(event.event_type == "carrier.counter_approval_recorded" for event in history.audit_events) == 1
