import pytest
from uuid import UUID

from backend.app.storage.agent_runtime import AgentRuntimeRepository
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository
from backend.app.storage.cargo_safety import CargoSafetyRepository


def _runtime(session, turns, checker=None):
    from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
    from backend.app.services.agent_model import FakeAgentModel
    configuration = CanonicalAgentRuntimeConfiguration.load()
    return AgentRuntimeCoordinator(session=session, model=FakeAgentModel(turns), clock=configuration.clock("before_deadline"), configuration=configuration, cargo_safety_checker=checker)


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
