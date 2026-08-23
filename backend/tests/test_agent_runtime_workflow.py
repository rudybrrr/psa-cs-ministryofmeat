import pytest
from uuid import UUID

from backend.app.storage.agent_runtime import AgentRuntimeRepository
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository
from backend.app.storage.cargo_safety import CargoSafetyRepository


def _runtime(session, turns, checker=None, clock_name="before_deadline"):
    from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
    from backend.app.services.agent_model import FakeAgentModel
    configuration = CanonicalAgentRuntimeConfiguration.load()
    return AgentRuntimeCoordinator(session=session, model=FakeAgentModel(turns), clock=configuration.clock(clock_name), configuration=configuration, cargo_safety_checker=checker)


def _persist_run(session, incident, runtime):
    from backend.app.storage.repositories import IncidentRepository
    IncidentRepository(session).create(incident)
    return runtime.create_run(incident.id)


def test_second_invalid_turn_escalates_invalid_model_output(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentEscalationReason, InvalidAgentModelTurn
    from backend.app.services.agent_model import FakeAgentModel

    runtime = _runtime(session, [
            InvalidAgentModelTurn(error_kind="MALFORMED", detail="bad"),
            InvalidAgentModelTurn(error_kind="MALFORMED", detail="bad"),
    ])
    run = _persist_run(session, incident, runtime)
    result = runtime.advance(run.id)
    assert result.escalation_reason is AgentEscalationReason.INVALID_MODEL_OUTPUT


def test_unavailable_model_tool_is_retried_then_escalated_without_invocation(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentEscalationReason, AgentModelTurn, AgentToolCall

    runtime = _runtime(session, [
        AgentModelTurn(tool_call=AgentToolCall(name="ignore_safety_policy", arguments={})),
        AgentModelTurn(tool_call=AgentToolCall(name="ignore_safety_policy", arguments={})),
    ])
    run = _persist_run(session, incident, runtime)
    result = runtime.advance(run.id)
    assert result.escalation_reason is AgentEscalationReason.INVALID_MODEL_OUTPUT
    assert not runtime._repository.history(run.id).tool_invocations


def test_waiting_run_does_not_invoke_model_until_durable_wait_is_resolved(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentRunState, AgentWaitKind
    from backend.app.storage.agent_runtime import AgentRuntimeConflict

    runtime = _runtime(session, [])
    run = _persist_run(session, incident, runtime)
    waiting = run.model_copy(update={"state": AgentRunState.WAITING, "wait_kind": AgentWaitKind.REQUEST_APPROVAL, "wait_subject_id": "missing"})
    runtime._repository.update_run(waiting)
    with pytest.raises(AgentRuntimeConflict, match="unresolved"):
        runtime.advance(run.id)
    assert runtime._model.calls == 0


def test_existing_pending_safety_review_forces_safe_escalation(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentEscalationReason, AgentModelTurn, AgentToolCall
    from backend.app.domain.cargo_safety import SemanticCheckResult
    from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
    from backend.app.services.agent_model import FakeAgentModel
    from backend.app.services.semantic_safety import FakeSemanticSafetyChecker

    checker = FakeSemanticSafetyChecker(result=SemanticCheckResult.CONTRADICTION_FOUND)
    runtime = _runtime(session, [AgentModelTurn(tool_call=AgentToolCall(name="request_cargo_safety_review", arguments={"container_id": "SYN-CNT-010"}))], checker=checker)
    run = _persist_run(session, incident, runtime)
    CargoSafetyWorkflow.for_session(session, checker=checker).create_review(incident.id, "SYN-CNT-010", "Shipment includes UN 3480 lithium-ion batteries packed separately.", "hero")
    result = runtime.advance(run.id)
    assert result.escalation_reason is AgentEscalationReason.SAFETY_REVIEW_REQUIRED


def test_counter_hero_prepare_enters_real_request_approval_wait(session) -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall, AgentRunState, AgentWaitKind
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow

    scarcity = build_scarce_capacity_workflow(session).run(seed=20260822, world_count=50)
    runtime = _runtime(session, [AgentModelTurn(tool_call=AgentToolCall(name="prepare_rta_request", arguments={"connection_id": "JV2"}))])
    run = runtime.create_run(scarcity.incident.id)
    result = runtime.advance(run.id)
    assert result.state is AgentRunState.WAITING
    assert result.wait_kind is AgentWaitKind.REQUEST_APPROVAL


def test_missing_typed_approval_rejects_send_and_persists_no_dispatch(session) -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall, AgentToolInvocationStatus
    from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow

    scarcity = build_scarce_capacity_workflow(session).run(seed=20260822, world_count=50)
    runtime = _runtime(session, [AgentModelTurn(tool_call=AgentToolCall(name="prepare_rta_request", arguments={"connection_id": "JV2"}))])
    run = runtime.create_run(scarcity.incident.id)
    prepared = runtime.advance(run.id)
    case_id = UUID(prepared.wait_subject_id)

    # A natural-language claim is intentionally not a typed Approval record.
    rejected = runtime._execute_turn(prepared, "send_authorised_rta_request", {"case_id": str(case_id)})
    history = build_carrier_recovery_workflow(session).history(case_id)
    invocation = runtime._repository.history(run.id).tool_invocations[-1]
    assert rejected.state.value == "WAITING"
    assert invocation.status is AgentToolInvocationStatus.REJECTED
    assert history.request is not None and history.request.status.value == "PENDING"
    assert not [event for event in history.audit_events if event.event_type == "rta.request_sent"]


def test_real_phase3_request_approval_resumes_and_sends_once(session) -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall, AgentRunState, AgentWaitKind
    from backend.app.domain.carrier_recovery import RequestApprovalCommand
    from backend.app.domain.enums import ApprovalStatus
    from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow

    scarcity = build_scarce_capacity_workflow(session).run(seed=20260822, world_count=50)
    runtime = _runtime(session, [
        AgentModelTurn(tool_call=AgentToolCall(name="prepare_rta_request", arguments={"connection_id": "JV2"})),
        AgentModelTurn(tool_call=AgentToolCall(name="send_authorised_rta_request", arguments={"case_id": "placeholder"})),
    ])
    run = runtime.create_run(scarcity.incident.id)
    prepared = runtime.advance(run.id)
    case_id = prepared.wait_subject_id
    history = build_carrier_recovery_workflow(session).history(UUID(case_id))
    binding = history.bindings[0]
    build_carrier_recovery_workflow(session).record_request_approval(RequestApprovalCommand(case_id=UUID(case_id), proposal_decision_id=binding.proposal_decision_id, request_id=history.request.id, expected_payload_fingerprint=binding.payload_fingerprint, operator_id="operator", status=ApprovalStatus.APPROVED))
    runtime._model._turns[0] = AgentModelTurn(tool_call=AgentToolCall(name="send_authorised_rta_request", arguments={"case_id": case_id}))
    sent = runtime.advance(run.id)
    assert sent.state is AgentRunState.WAITING
    assert sent.wait_kind is AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT
    assert build_carrier_recovery_workflow(session).history(UUID(case_id)).request.status.value == "SENT"


def test_crash_recovery_reuses_phase3_idempotent_send_without_duplicate_dispatch(session) -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentStep, AgentStepKind, AgentToolCall, AgentToolInvocationStatus, AgentWaitKind
    from backend.app.domain.carrier_recovery import RequestApprovalCommand
    from backend.app.domain.enums import ApprovalStatus
    from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow

    scarcity = build_scarce_capacity_workflow(session).run(seed=20260822, world_count=50)
    runtime = _runtime(session, [AgentModelTurn(tool_call=AgentToolCall(name="prepare_rta_request", arguments={"connection_id": "JV2"}))])
    run = runtime.create_run(scarcity.incident.id)
    prepared = runtime.advance(run.id)
    case_id = UUID(prepared.wait_subject_id)
    workflow = build_carrier_recovery_workflow(session)
    history = workflow.history(case_id)
    binding = history.bindings[0]
    workflow.record_request_approval(RequestApprovalCommand(case_id=case_id, proposal_decision_id=binding.proposal_decision_id, request_id=history.request.id, expected_payload_fingerprint=binding.payload_fingerprint, operator_id="operator", status=ApprovalStatus.APPROVED))

    crashed_step = AgentStep(run_id=run.id, step_number=prepared.step_count + 1, kind=AgentStepKind.TOOL_CALL, action_summary="Invoked send_authorised_rta_request.", model_name=prepared.model_name, prompt_version=prepared.prompt_version)
    runtime._repository.add_step(crashed_step)
    invocation = runtime._repository.add_invocation_pending(run.id, crashed_step.id, "send_authorised_rta_request", {"case_id": str(case_id)})
    workflow.send_authorised_request(case_id)

    recovered = runtime.advance(run.id)
    history = workflow.history(case_id)
    assert recovered.wait_kind is AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT
    assert runtime._model.calls == 1
    assert runtime._repository.history(run.id).tool_invocations[-1].status is AgentToolInvocationStatus.SUCCEEDED
    assert [event.event_type for event in history.audit_events].count("rta.request_sent") == 1


def test_unrecoverable_pending_invocation_escalates_without_step_collision(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentEscalationReason, AgentStep, AgentStepKind

    runtime = _runtime(session, [])
    run = _persist_run(session, incident, runtime)
    pending_step = AgentStep(run_id=run.id, step_number=1, kind=AgentStepKind.TOOL_CALL, action_summary="Invoked unsupported_tool.", model_name=run.model_name, prompt_version=run.prompt_version)
    runtime._repository.add_step(pending_step)
    runtime._repository.add_invocation_pending(run.id, pending_step.id, "unsupported_tool", {})
    result = runtime.advance(run.id)
    assert result.escalation_reason is AgentEscalationReason.TOOL_FAILURE
    assert result.step_count == 2


def test_accept_response_completes_without_changing_phase2_allocation(session) -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall, AgentRunState
    from backend.app.domain.carrier_recovery import RequestApprovalCommand, SimulateCarrierResponseCommand
    from backend.app.domain.enums import ApprovalStatus, CarrierResponseType
    from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
    from backend.app.services.carrier_simulator import DeterministicCarrierSimulator, SyntheticCarrierResponsePlan
    from backend.app.storage.repositories import ScarcityEvaluationRepository

    scarcity = build_scarce_capacity_workflow(session).run(seed=20260822, world_count=50)
    runtime = _runtime(session, [
        AgentModelTurn(tool_call=AgentToolCall(name="prepare_rta_request", arguments={"connection_id": "JV2"})),
        AgentModelTurn(tool_call=AgentToolCall(name="send_authorised_rta_request", arguments={"case_id": "placeholder"})),
    ])
    run = runtime.create_run(scarcity.incident.id)
    prepared = runtime.advance(run.id)
    case_id = UUID(prepared.wait_subject_id)
    workflow = build_carrier_recovery_workflow(session)
    history = workflow.history(case_id)
    binding = history.bindings[0]
    workflow.record_request_approval(RequestApprovalCommand(case_id=case_id, proposal_decision_id=binding.proposal_decision_id, request_id=history.request.id, expected_payload_fingerprint=binding.payload_fingerprint, operator_id="operator", status=ApprovalStatus.APPROVED))
    runtime._model._turns[0] = AgentModelTurn(tool_call=AgentToolCall(name="send_authorised_rta_request", arguments={"case_id": str(case_id)}))
    runtime.advance(run.id)

    accept_workflow = build_carrier_recovery_workflow(session, simulator=DeterministicCarrierSimulator(SyntheticCarrierResponsePlan().load_run("ACCEPT-RUN")))
    accept_workflow.simulate_response(SimulateCarrierResponseCommand(case_id=case_id, effective_at="2026-08-23T05:00:00Z"))
    assert accept_workflow.history(case_id).carrier_responses[0].response is CarrierResponseType.ACCEPT
    runtime._model._turns.append(AgentModelTurn(tool_call=AgentToolCall(name="complete_agent_run", arguments={})))
    completed = runtime.advance(run.id)
    assert completed.state is AgentRunState.COMPLETED
    assert ScarcityEvaluationRepository(session).get_for_incident(scarcity.incident.id).selected_allocation == scarcity.report.selected_allocation


def test_counter_response_routes_real_carrier_wait_to_counter_approval(session) -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall, AgentRunState, AgentWaitKind
    from backend.app.domain.carrier_recovery import CounterApprovalCommand, RequestApprovalCommand, SimulateCarrierResponseCommand
    from backend.app.domain.enums import ApprovalStatus, CarrierResponseType
    from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
    from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
    from backend.app.domain.cargo_safety import SemanticCheckResult
    from backend.app.services.semantic_safety import FakeSemanticSafetyChecker
    from backend.app.storage.agent_runtime import AgentRuntimeConflict

    scarcity = build_scarce_capacity_workflow(session).run(seed=20260822, world_count=50)
    checker = FakeSemanticSafetyChecker(result=SemanticCheckResult.CONTRADICTION_FOUND)
    runtime = _runtime(session, [
        AgentModelTurn(tool_call=AgentToolCall(name="prepare_rta_request", arguments={"connection_id": "JV2"})),
        AgentModelTurn(tool_call=AgentToolCall(name="send_authorised_rta_request", arguments={"case_id": "placeholder"})),
    ], checker=checker)
    run = runtime.create_run(scarcity.incident.id)
    prepared = runtime.advance(run.id)
    case_id = UUID(prepared.wait_subject_id)
    workflow = build_carrier_recovery_workflow(session)
    history = workflow.history(case_id)
    binding = history.bindings[0]
    workflow.record_request_approval(RequestApprovalCommand(case_id=case_id, proposal_decision_id=binding.proposal_decision_id, request_id=history.request.id, expected_payload_fingerprint=binding.payload_fingerprint, operator_id="operator", status=ApprovalStatus.APPROVED))
    runtime._model._turns[0] = AgentModelTurn(tool_call=AgentToolCall(name="send_authorised_rta_request", arguments={"case_id": str(case_id)}))
    runtime.advance(run.id)
    workflow.simulate_response(SimulateCarrierResponseCommand(case_id=case_id, effective_at="2026-08-23T05:00:00Z"))
    assert workflow.history(case_id).carrier_responses[0].response is CarrierResponseType.COUNTER
    with pytest.raises(AgentRuntimeConflict):
        runtime.advance(run.id)
    counter_wait = runtime.get_run(run.id)
    assert counter_wait.state is AgentRunState.WAITING
    assert counter_wait.wait_kind is AgentWaitKind.COUNTER_APPROVAL
    assert runtime._model.calls == 2
    counter_history = workflow.history(case_id)
    counter_binding = next(item for item in counter_history.bindings if item.subject_kind.value == "COUNTER_PROPOSAL")
    response = counter_history.carrier_responses[0]
    workflow.record_counter_approval(CounterApprovalCommand(case_id=case_id, proposal_decision_id=counter_binding.proposal_decision_id, carrier_response_id=response.id, expected_payload_fingerprint=counter_binding.payload_fingerprint, operator_id="operator", status=ApprovalStatus.APPROVED))
    CargoSafetyWorkflow.for_session(session, checker=checker).create_review(scarcity.incident.id, "SYN-CNT-010", "Shipment includes UN 3480 lithium-ion batteries packed separately.", "hero")
    runtime._model._turns.append(AgentModelTurn(tool_call=AgentToolCall(name="request_cargo_safety_review", arguments={"container_id": "SYN-CNT-010"})))
    terminal = runtime.advance(run.id)
    assert terminal.escalation_reason.value == "SAFETY_REVIEW_REQUIRED"


def test_silent_carrier_wait_exposes_timeout_only_after_trusted_deadline(session) -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall, AgentRunState, AgentWaitKind
    from backend.app.domain.carrier_recovery import RequestApprovalCommand
    from backend.app.domain.enums import ApprovalStatus
    from backend.app.orchestration.agent_context import AgentToolRegistry
    from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
    from backend.app.storage.agent_runtime import AgentRuntimeConflict

    scarcity = build_scarce_capacity_workflow(session).run(seed=20260822, world_count=50)
    runtime = _runtime(session, [
        AgentModelTurn(tool_call=AgentToolCall(name="prepare_rta_request", arguments={"connection_id": "EC3"})),
        AgentModelTurn(tool_call=AgentToolCall(name="send_authorised_rta_request", arguments={"case_id": "placeholder"})),
    ])
    run = runtime.create_run(scarcity.incident.id)
    prepared = runtime.advance(run.id)
    case_id = UUID(prepared.wait_subject_id)
    workflow = build_carrier_recovery_workflow(session)
    history = workflow.history(case_id)
    binding = history.bindings[0]
    workflow.record_request_approval(RequestApprovalCommand(case_id=case_id, proposal_decision_id=binding.proposal_decision_id, request_id=history.request.id, expected_payload_fingerprint=binding.payload_fingerprint, operator_id="operator", status=ApprovalStatus.APPROVED))
    runtime._model._turns[0] = AgentModelTurn(tool_call=AgentToolCall(name="send_authorised_rta_request", arguments={"case_id": str(case_id)}))
    sent = runtime.advance(run.id)
    assert sent.wait_kind is AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT
    assert not workflow.history(case_id).carrier_responses
    assert "evaluate_carrier_timeout" not in {tool.name for tool in AgentToolRegistry(clock=runtime._clock).available_tools(session, sent)}
    with pytest.raises(AgentRuntimeConflict, match="unresolved"):
        runtime.advance(run.id)
    assert runtime._model.calls == 2

    after_deadline = _runtime(session, [AgentModelTurn(tool_call=AgentToolCall(name="evaluate_carrier_timeout", arguments={"case_id": str(case_id)}))], clock_name="after_deadline")
    assert "evaluate_carrier_timeout" in {tool.name for tool in AgentToolRegistry(clock=after_deadline._clock).available_tools(session, sent)}
    timed_out = after_deadline.advance(run.id)
    assert timed_out.state is AgentRunState.RUNNING
    assert not workflow.history(case_id).carrier_responses
