import pytest

from backend.app.domain.carrier_recovery import (
    CarrierRecoveryDisposition,
    CounterApprovalCommand,
    EvaluateTimeoutCommand,
    PrepareCarrierRecoveryCaseCommand,
    RequestApprovalCommand,
    SimulateCarrierResponseCommand,
)
from backend.app.evaluation.carrier_recovery import FrozenRecoveryEvaluation
from backend.app.domain.enums import AuditActor
from backend.app.domain.enums import ApprovalStatus, DecisionAction
from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
from backend.app.storage.repositories import DecisionRepository


def prepare_command(incident_id, connection_id: str):
    return PrepareCarrierRecoveryCaseCommand(
        incident_id=incident_id,
        connection_id=connection_id,
        prepared_at="2026-08-22T07:00:00Z",
        requested_eta_pta="2026-08-22T08:00:00Z",
        response_deadline="2026-08-22T09:00:00Z",
    )


def approve_and_send(workflow, case) -> None:
    binding = workflow.history(case.id).bindings[0]
    workflow.record_request_approval(RequestApprovalCommand(
        case_id=case.id,
        proposal_decision_id=binding.proposal_decision_id,
        request_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id="operator-30",
        status=ApprovalStatus.APPROVED,
    ))
    workflow.send_authorised_request(case.id)


def test_recompute_reuses_frozen_evidence_and_persists_one_result_per_snapshot(
    session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(prepare_command(phase_two.incident.id, "SYN-CONN-JV2"))
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
        operator_id="operator-31",
        status=ApprovalStatus.APPROVED,
    ))

    first = workflow.recompute(case.id)
    second = workflow.recompute(case.id)
    history = workflow.history(case.id)

    assert second == first
    assert tuple(result.container_id for result in history.results) == case.affected_container_ids
    assert {result.world_count for result in history.results} == {phase_two.report.scenario_count}
    assert history.case.state.value in {"COMPLETED", "ESCALATED"}


def test_timeout_recompute_keeps_fallback_roll_without_external_timing(session) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(prepare_command(phase_two.incident.id, "SYN-CONN-EC3"))
    approve_and_send(workflow, case)
    workflow.evaluate_timeout(EvaluateTimeoutCommand(
        case_id=case.id,
        effective_at="2026-08-22T09:00:00Z",
    ))

    workflow.recompute(case.id)
    history = workflow.history(case.id)

    assert all(result.disposition.value == "STILL_ROLL" for result in history.results)
    assert all(result.replacement_decision_id is None for result in history.results)
    assert all(link.role != "PRESERVE_VIA_RTA" for link in history.decision_links)


def test_recompute_rolls_back_replacement_decisions_when_results_fail(
    session,
    monkeypatch,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(prepare_command(phase_two.incident.id, "SYN-CONN-JV2"))
    approve_and_send(workflow, case)
    workflow.simulate_response(SimulateCarrierResponseCommand(
        case_id=case.id,
        effective_at="2026-08-22T08:30:00Z",
    ))
    binding = workflow.history(case.id).bindings[-1]
    before = DecisionRepository(session).list_for_incident(phase_two.incident.id)

    def fail_result(*_args, **_kwargs) -> None:
        raise RuntimeError("force recomputation rollback")

    monkeypatch.setattr(workflow._cases, "add_result", fail_result)

    with pytest.raises(RuntimeError, match="force recomputation rollback"):
        workflow.record_counter_approval(CounterApprovalCommand(
            case_id=case.id,
            proposal_decision_id=binding.proposal_decision_id,
            carrier_response_id=binding.subject_id,
            expected_payload_fingerprint=binding.payload_fingerprint,
            operator_id="operator-31",
            status=ApprovalStatus.APPROVED,
        ))

    assert DecisionRepository(session).list_for_incident(phase_two.incident.id) == before
    history = workflow.history(case.id)
    assert history.results == ()
    assert {approval.decision_id for approval in history.approvals} == {
        workflow.history(case.id).bindings[0].proposal_decision_id
    }
    assert history.effective_timings == ()
    assert history.case.state.value == "AWAITING_COUNTER_APPROVAL"


def test_history_is_case_scoped_ordered_and_includes_linked_decisions(session) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(prepare_command(phase_two.incident.id, "SYN-CONN-EC3"))
    approve_and_send(workflow, case)
    workflow.evaluate_timeout(EvaluateTimeoutCommand(
        case_id=case.id,
        effective_at="2026-08-22T09:00:00Z",
    ))
    workflow.recompute(case.id)

    history = workflow.history(case.id)

    assert {decision.id for decision in history.decisions} == {
        link.decision_id for link in history.decision_links
    }
    assert [event.id for event in history.audit_events] == list(dict.fromkeys(event.id for event in history.audit_events))
    assert all(event.incident_id == phase_two.incident.id for event in history.audit_events)


@pytest.mark.parametrize(
    ("disposition", "preserved_world_count", "expects_replacement_audit"),
    [
        (CarrierRecoveryDisposition.PRESERVED_VIA_RTA, 50, True),
        (CarrierRecoveryDisposition.ESCALATE, 1, True),
        (CarrierRecoveryDisposition.STILL_ROLL, 0, False),
    ],
)
def test_recomputation_records_one_policy_audit_for_each_replacement(
    session, monkeypatch, disposition, preserved_world_count, expects_replacement_audit
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(prepare_command(phase_two.incident.id, "SYN-CONN-JV2"))
    approve_and_send(workflow, case)
    workflow.simulate_response(SimulateCarrierResponseCommand(
        case_id=case.id, effective_at="2026-08-22T08:30:00Z",
    ))
    binding = workflow.history(case.id).bindings[-1]
    monkeypatch.setattr(
        "backend.app.orchestration.carrier_recovery.FrozenCarrierRecoveryEvaluator.evaluate",
        lambda _self, **_kwargs: (
            FrozenRecoveryEvaluation(
                container_id=case.affected_container_ids[0],
                disposition=disposition,
                preserved_world_count=preserved_world_count,
                world_count=50,
                hard_constraints_satisfied=True,
            ),
        ),
    )

    workflow.record_counter_approval(CounterApprovalCommand(
        case_id=case.id,
        proposal_decision_id=binding.proposal_decision_id,
        carrier_response_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id="operator-31",
        status=ApprovalStatus.APPROVED,
    ))
    history = workflow.history(case.id)
    replacement_events = [
        event for event in history.audit_events
        if event.actor is AuditActor.POLICY
        and event.event_type == "carrier_recovery.replacement_recorded"
    ]

    assert len(replacement_events) == int(expects_replacement_audit)
    if expects_replacement_audit:
        result = history.results[0]
        payload = replacement_events[0].payload
        assert payload == {
            "recovery_case_id": str(case.id),
            "container_id": result.container_id,
            "prior_decision_id": str(result.prior_decision_id),
            "replacement_decision_id": str(result.replacement_decision_id),
            "disposition": result.disposition.value,
            "evidence_kind": result.reconsideration_evidence_kind.value,
            "evidence_id": str(result.effective_connection_timing_id),
        }
    workflow.recompute(case.id)
    assert len([
        event for event in workflow.history(case.id).audit_events
        if event.event_type == "carrier_recovery.replacement_recorded"
    ]) == int(expects_replacement_audit)
