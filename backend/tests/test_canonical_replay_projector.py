from uuid import UUID

from backend.app.domain.agent_runtime import (
    AgentEscalationReason,
    AgentModelTurn,
    AgentRunState,
    AgentToolCall,
    AgentWaitKind,
)
from backend.app.domain.canonical_replay import (
    CanonicalReplayActionType,
    CanonicalReplayStage,
    CanonicalReplayStatus,
)
from backend.app.domain.carrier_recovery import (
    CounterApprovalCommand,
    RequestApprovalCommand,
    SimulateCarrierResponseCommand,
)
from backend.app.domain.cargo_safety import SemanticCheckResult
from backend.app.domain.enums import ApprovalStatus
from backend.app.orchestration.agent_runtime import (
    AgentRuntimeCoordinator,
    CanonicalAgentRuntimeConfiguration,
)
from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
from backend.app.services.agent_model import FakeAgentModel
from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness
from backend.app.services.semantic_safety import FakeSemanticSafetyChecker
from backend.app.storage.agent_runtime import AgentRuntimeRepository


CANONICAL_EFFECTIVE_AT = "2026-08-23T05:00:00Z"


def _incident_id(session) -> UUID:
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow

    return build_scarce_capacity_workflow(session).run().incident.id


def _yard(session):
    from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow

    return DynamicYardWorkflow.for_session(session)


def _bootstrap(session, incident_id: UUID) -> None:
    _yard(session).initialize(incident_id, CanonicalDynamicYardHarness().bootstrap_snapshot(incident_id))


def _publish(session, incident_id: UUID):
    return _yard(session).ingest(CanonicalDynamicYardHarness().discharge_active_snapshot(incident_id))


def _runtime(session, turns=None, checker=None) -> AgentRuntimeCoordinator:
    configuration = CanonicalAgentRuntimeConfiguration.load()
    return AgentRuntimeCoordinator(
        session=session,
        model=FakeAgentModel(list(turns or [])),
        clock=configuration.clock("before_deadline"),
        configuration=configuration,
        cargo_safety_checker=checker,
    )


def _prepare_jv2(session, incident_id: UUID) -> UUID:
    configuration = CanonicalAgentRuntimeConfiguration.load()
    command = configuration.prepare_command(incident_id, "SYN-CONN-JV2")
    return build_carrier_recovery_workflow(session).prepare(command).id


def _carrier(session):
    return build_carrier_recovery_workflow(session)


def _request_binding(session, case_id: UUID):
    history = _carrier(session).history(case_id)
    return history.request, next(item for item in history.bindings if item.subject_kind.value == "OUTBOUND_REQUEST")


def _approve_request(session, case_id: UUID, operator_id: str = "operator-console") -> None:
    request, binding = _request_binding(session, case_id)
    _carrier(session).record_request_approval(
        RequestApprovalCommand(
            case_id=case_id,
            proposal_decision_id=binding.proposal_decision_id,
            request_id=request.id,
            expected_payload_fingerprint=binding.payload_fingerprint,
            operator_id=operator_id,
            status=ApprovalStatus.APPROVED,
        )
    )


def _reject_request(session, case_id: UUID, operator_id: str = "operator-console") -> None:
    request, binding = _request_binding(session, case_id)
    _carrier(session).record_request_approval(
        RequestApprovalCommand(
            case_id=case_id,
            proposal_decision_id=binding.proposal_decision_id,
            request_id=request.id,
            expected_payload_fingerprint=binding.payload_fingerprint,
            operator_id=operator_id,
            status=ApprovalStatus.REJECTED,
        )
    )


def _simulate_counter(session, case_id: UUID) -> None:
    _carrier(session).simulate_response(SimulateCarrierResponseCommand(case_id=case_id, effective_at=CANONICAL_EFFECTIVE_AT))


def _counter_binding(session, case_id: UUID):
    history = _carrier(session).history(case_id)
    binding = next(item for item in history.bindings if item.subject_kind.value == "COUNTER_PROPOSAL")
    return history.carrier_responses[0], binding


def _approve_counter(session, case_id: UUID, operator_id: str = "operator-console") -> None:
    response, binding = _counter_binding(session, case_id)
    _carrier(session).record_counter_approval(
        CounterApprovalCommand(
            case_id=case_id,
            proposal_decision_id=binding.proposal_decision_id,
            carrier_response_id=response.id,
            expected_payload_fingerprint=binding.payload_fingerprint,
            operator_id=operator_id,
            status=ApprovalStatus.APPROVED,
        )
    )


def _reject_counter(session, case_id: UUID, operator_id: str = "operator-console") -> None:
    response, binding = _counter_binding(session, case_id)
    _carrier(session).record_counter_approval(
        CounterApprovalCommand(
            case_id=case_id,
            proposal_decision_id=binding.proposal_decision_id,
            carrier_response_id=response.id,
            expected_payload_fingerprint=binding.payload_fingerprint,
            operator_id=operator_id,
            status=ApprovalStatus.REJECTED,
        )
    )


def _persist_contradiction(session, incident_id: UUID, container_id: str = "SYN-CNT-010"):
    from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow

    checker = FakeSemanticSafetyChecker(result=SemanticCheckResult.CONTRADICTION_FOUND)
    workflow = CargoSafetyWorkflow.for_session(session, checker=checker)
    review = workflow.create_review(
        incident_id,
        container_id,
        "Manifest declares general cargo; free-text handling note identifies corrosive material and requires safety review.",
        "synthetic-canonical-cargo-note",
    )
    return workflow, review


def _set_run_state(session, run_id: UUID, **updates):
    repository = AgentRuntimeRepository(session)
    run = repository.get_run(run_id)
    return repository.update_run(run.model_copy(update=updates))


def test_incident_with_scarcity_only_projects_ready_for_pre_discharge(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    view = project_canonical_replay_stage(session, _incident_id(session))
    assert view.stage is CanonicalReplayStage.READY_FOR_PRE_DISCHARGE
    assert view.ordinal == 2
    assert view.progress_label == "Stage 2 of 16"
    assert view.status is CanonicalReplayStatus.PENDING_ACTION
    assert view.next_allowed_action is CanonicalReplayActionType.BOOTSTRAP_PRE_DISCHARGE
    assert view.guided_can_execute is True
    assert view.auto_replay_may_execute is True
    assert view.requires_human_authority is False
    assert view.deviation_reason is None


def test_bootstrapped_incident_projects_ready_to_start_agent(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.READY_TO_START_AGENT
    assert view.ordinal == 3
    assert view.next_allowed_action is CanonicalReplayActionType.START_DEMO_AGENT_RUN


def test_evidence_published_before_agent_start_is_off_canonical(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    _publish(session, incident_id)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.OFF_CANONICAL_PATH
    assert view.deviation_reason == "EVIDENCE_PUBLISHED_BEFORE_AGENT_START"
    assert view.ordinal == 3
    assert view.status is CanonicalReplayStatus.TERMINAL_HALTED
    assert view.next_allowed_action is CanonicalReplayActionType.NONE


def test_fresh_run_projects_ready_to_advance_to_evidence_wait(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.READY_TO_ADVANCE_TO_EVIDENCE_WAIT
    assert view.ordinal == 4
    assert view.next_allowed_action is CanonicalReplayActionType.ADVANCE_AGENT
    assert run.step_count == 0


def test_paused_run_without_evidence_waits_for_publish(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    runtime = _runtime(session, turns=[AgentModelTurn(tool_call=AgentToolCall(name="pause_agent_run", arguments={}))])
    run = runtime.create_run(incident_id)
    runtime.advance(run.id)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.WAITING_FOR_ACTIVE_EVIDENCE
    assert view.ordinal == 5
    assert view.status is CanonicalReplayStatus.WAITING_EXTERNAL
    assert view.next_allowed_action is CanonicalReplayActionType.PUBLISH_DISCHARGE_ACTIVE
    _publish(session, incident_id)
    resumed = project_canonical_replay_stage(session, incident_id)
    assert resumed.stage is CanonicalReplayStage.WAITING_FOR_ACTIVE_EVIDENCE
    assert resumed.status is CanonicalReplayStatus.PENDING_ACTION
    assert resumed.next_allowed_action is CanonicalReplayActionType.ADVANCE_AGENT


def test_unhandled_assessment_before_first_step_demands_reconsideration(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    _publish(session, incident_id)
    _runtime(session).create_run(incident_id)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.READY_TO_RECONSIDER
    assert view.ordinal == 6
    assert view.next_allowed_action is CanonicalReplayActionType.ADVANCE_AGENT


def test_reconsidered_run_projects_ready_to_prepare_rta(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    runtime = _runtime(
        session,
        turns=[
            AgentModelTurn(tool_call=AgentToolCall(name="pause_agent_run", arguments={})),
            AgentModelTurn(tool_call=AgentToolCall(name="request_expedite_feasibility", arguments={})),
        ],
    )
    run = runtime.create_run(incident_id)
    runtime.advance(run.id)
    _publish(session, incident_id)
    runtime.advance(run.id)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.READY_TO_PREPARE_RTA
    assert view.ordinal == 7
    assert view.next_allowed_action is CanonicalReplayActionType.ADVANCE_AGENT


def test_prepared_case_awaits_request_approval(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    case_id = _prepare_jv2(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(
        session,
        run.id,
        state=AgentRunState.WAITING,
        wait_kind=AgentWaitKind.REQUEST_APPROVAL,
        wait_subject_id=str(case_id),
    )
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.REQUEST_APPROVAL_REQUIRED
    assert view.ordinal == 8
    assert view.status is CanonicalReplayStatus.WAITING_HUMAN
    assert view.next_allowed_action is CanonicalReplayActionType.APPROVE_REQUEST
    assert view.requires_human_authority is True
    assert view.auto_replay_may_execute is True


def test_approved_request_projects_ready_to_send(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    case_id = _prepare_jv2(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(session, run.id, state=AgentRunState.WAITING, wait_kind=AgentWaitKind.REQUEST_APPROVAL, wait_subject_id=str(case_id))
    _approve_request(session, case_id)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.REQUEST_APPROVED_READY_TO_SEND
    assert view.ordinal == 9
    assert view.next_allowed_action is CanonicalReplayActionType.ADVANCE_AGENT


def test_rejected_request_leaves_canonical_path(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    case_id = _prepare_jv2(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(session, run.id, state=AgentRunState.WAITING, wait_kind=AgentWaitKind.REQUEST_APPROVAL, wait_subject_id=str(case_id))
    _reject_request(session, case_id)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.OFF_CANONICAL_PATH
    assert view.deviation_reason == "REQUEST_REJECTED"
    assert view.ordinal == 8
    assert view.status is CanonicalReplayStatus.TERMINAL_HALTED


def test_sent_request_waits_for_carrier(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    case_id = _prepare_jv2(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(session, run.id, state=AgentRunState.WAITING, wait_kind=AgentWaitKind.REQUEST_APPROVAL, wait_subject_id=str(case_id))
    _approve_request(session, case_id)
    _carrier(session).send_authorised_request(case_id)
    _set_run_state(session, run.id, wait_kind=AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.WAITING_FOR_CARRIER
    assert view.ordinal == 10
    assert view.status is CanonicalReplayStatus.WAITING_EXTERNAL
    assert view.next_allowed_action is CanonicalReplayActionType.SIMULATE_CARRIER_RESPONSE


def test_counter_response_projects_counter_received(session) -> None:
    import pytest

    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    case_id = _prepare_jv2(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(session, run.id, state=AgentRunState.WAITING, wait_kind=AgentWaitKind.REQUEST_APPROVAL, wait_subject_id=str(case_id))
    _approve_request(session, case_id)
    _carrier(session).send_authorised_request(case_id)
    _set_run_state(session, run.id, wait_kind=AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT)
    _simulate_counter(session, case_id)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.CARRIER_COUNTER_RECEIVED
    assert view.ordinal == 11
    assert view.next_allowed_action is CanonicalReplayActionType.ADVANCE_AGENT
    with pytest.raises(Exception):
        runtime = _runtime(session)
        runtime.advance(run.id)


def test_upgraded_wait_requires_counter_approval(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    case_id = _prepare_jv2(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(session, run.id, state=AgentRunState.WAITING, wait_kind=AgentWaitKind.REQUEST_APPROVAL, wait_subject_id=str(case_id))
    _approve_request(session, case_id)
    _carrier(session).send_authorised_request(case_id)
    _simulate_counter(session, case_id)
    _set_run_state(session, run.id, wait_kind=AgentWaitKind.COUNTER_APPROVAL)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.COUNTER_APPROVAL_REQUIRED
    assert view.ordinal == 12
    assert view.status is CanonicalReplayStatus.WAITING_HUMAN
    assert view.next_allowed_action is CanonicalReplayActionType.APPROVE_COUNTER
    assert view.requires_human_authority is True


def test_counter_rejection_is_off_canonical(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    case_id = _prepare_jv2(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(session, run.id, state=AgentRunState.WAITING, wait_kind=AgentWaitKind.REQUEST_APPROVAL, wait_subject_id=str(case_id))
    _approve_request(session, case_id)
    _carrier(session).send_authorised_request(case_id)
    _simulate_counter(session, case_id)
    _set_run_state(session, run.id, wait_kind=AgentWaitKind.COUNTER_APPROVAL)
    _reject_counter(session, case_id)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.OFF_CANONICAL_PATH
    assert view.deviation_reason == "COUNTER_REJECTED"
    assert view.ordinal == 12


def test_approved_counter_demands_safety_evidence_first(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    case_id = _prepare_jv2(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(session, run.id, state=AgentRunState.WAITING, wait_kind=AgentWaitKind.REQUEST_APPROVAL, wait_subject_id=str(case_id))
    _approve_request(session, case_id)
    _carrier(session).send_authorised_request(case_id)
    _simulate_counter(session, case_id)
    _set_run_state(session, run.id, wait_kind=AgentWaitKind.COUNTER_APPROVAL)
    _approve_counter(session, case_id)
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.COUNTER_APPROVED_READY_TO_RESUME
    assert view.ordinal == 13
    assert view.next_allowed_action is CanonicalReplayActionType.PERSIST_SAFETY_REVIEW
    _persist_contradiction(session, incident_id)
    flipped = project_canonical_replay_stage(session, incident_id)
    assert flipped.stage is CanonicalReplayStage.COUNTER_APPROVED_READY_TO_RESUME
    assert flipped.next_allowed_action is CanonicalReplayActionType.ADVANCE_AGENT


def test_terminal_safety_block_requires_all_three_safety_facts(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(session, run.id, state=AgentRunState.ESCALATED, escalation_reason=AgentEscalationReason.SAFETY_REVIEW_REQUIRED)
    partial = project_canonical_replay_stage(session, incident_id)
    assert partial.stage is CanonicalReplayStage.OFF_CANONICAL_PATH
    assert partial.deviation_reason == "AGENT_ESCALATION_SAFETY_REVIEW_REQUIRED"

    workflow, review = _persist_contradiction(session, incident_id)
    result = workflow.evaluate(review.id)
    assert result.policy_result.automation_blocked is True
    blocked = project_canonical_replay_stage(session, incident_id)
    assert blocked.stage is CanonicalReplayStage.SAFETY_BLOCKED
    assert blocked.ordinal == 16
    assert blocked.status is CanonicalReplayStatus.TERMINAL_SUCCESS
    assert blocked.next_allowed_action is CanonicalReplayActionType.NONE


def test_non_safety_escalations_map_off_canonical_with_typed_reason(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(
        session,
        run.id,
        state=AgentRunState.ESCALATED,
        escalation_reason=AgentEscalationReason.MODEL_UNAVAILABLE,
    )
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.OFF_CANONICAL_PATH
    assert view.deviation_reason == "AGENT_ESCALATION_MODEL_UNAVAILABLE"
    assert view.status is CanonicalReplayStatus.TERMINAL_HALTED


def test_failed_and_completed_runs_project_terminals(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    failed = _runtime(session).create_run(incident_id)
    _set_run_state(session, failed.id, state=AgentRunState.FAILED)
    assert project_canonical_replay_stage(session, incident_id).stage is CanonicalReplayStage.FAILED
    assert project_canonical_replay_stage(session, incident_id).status is CanonicalReplayStatus.TERMINAL_HALTED

    other_incident = _incident_id(session)
    _bootstrap(session, other_incident)
    completed = _runtime(session).create_run(other_incident)
    _set_run_state(session, completed.id, state=AgentRunState.COMPLETED, completed_at=None)
    view = project_canonical_replay_stage(session, other_incident)
    assert view.stage is CanonicalReplayStage.COMPLETE
    assert view.status is CanonicalReplayStatus.TERMINAL_SUCCESS


def test_tradeoff_wait_requires_human_selection_and_halts_auto(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(
        session,
        run.id,
        state=AgentRunState.WAITING,
        wait_kind=AgentWaitKind.HUMAN_TRADEOFF_DECISION,
        wait_subject_id=str(incident_id),
    )
    view = project_canonical_replay_stage(session, incident_id)
    assert view.stage is CanonicalReplayStage.TRADEOFF_DECISION_REQUIRED
    assert view.ordinal == 6
    assert view.status is CanonicalReplayStatus.WAITING_HUMAN
    assert view.next_allowed_action is CanonicalReplayActionType.SELECT_TRADEOFF_OPTION
    assert view.guided_can_execute is True
    assert view.auto_replay_may_execute is False
    assert view.requires_human_authority is True


def test_defensive_rule_ten_branches(session) -> None:
    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    case_id = _prepare_jv2(session, incident_id)
    run = _runtime(session).create_run(incident_id)
    _set_run_state(session, run.id, state=AgentRunState.RUNNING, step_count=2)
    unexpected = project_canonical_replay_stage(session, incident_id)
    assert unexpected.stage is CanonicalReplayStage.OFF_CANONICAL_PATH
    assert unexpected.deviation_reason == "UNEXPECTED_PERSISTED_STATE"

    _set_run_state(session, run.id, state=AgentRunState.RUNNING, step_count=2)
    _persist_contradiction(session, incident_id)
    pending_view = project_canonical_replay_stage(session, incident_id)
    assert pending_view.stage is CanonicalReplayStage.SAFETY_REVIEW_PENDING
    assert pending_view.ordinal == 15
    assert pending_view.next_allowed_action is CanonicalReplayActionType.ADVANCE_AGENT
    assert case_id is not None


def test_projection_is_read_only_and_deterministic_across_sessions(session, test_engine) -> None:
    from hashlib import sha256
    import json
    from sqlalchemy import inspect, text as sql_text
    from sqlmodel import Session as NewSession

    from backend.app.orchestration.canonical_replay import project_canonical_replay_stage

    incident_id = _incident_id(session)
    _bootstrap(session, incident_id)
    runtime = _runtime(session, turns=[AgentModelTurn(tool_call=AgentToolCall(name="pause_agent_run", arguments={}))])
    run = runtime.create_run(incident_id)
    runtime.advance(run.id)

    def snapshot() -> str:
        inspector = inspect(test_engine)
        payload = {}
        with test_engine.connect() as connection:
            for table in inspector.get_table_names():
                rows = connection.execute(sql_text(f"SELECT * FROM {table}")).mappings().all()
                payload[table] = sorted(json.dumps(dict(row), sort_keys=True, default=str) for row in rows)
        return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    session.commit()
    before = snapshot()
    first = project_canonical_replay_stage(session, incident_id)
    second = project_canonical_replay_stage(session, incident_id)
    assert first == second
    with NewSession(test_engine) as reopened:
        third = project_canonical_replay_stage(reopened, incident_id)
        assert third == first
    assert snapshot() == before
