import pytest

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
