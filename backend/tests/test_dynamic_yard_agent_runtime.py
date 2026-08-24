from datetime import UTC, datetime

import pytest
from backend.app.domain.agent_runtime import AgentRun, AgentRunState
from backend.app.orchestration.agent_context import AgentToolRegistry
from backend.app.orchestration.agent_runtime import FixedAgentRuntimeClock
from backend.app.storage.agent_runtime import AgentRuntimeConflict


def test_feasibility_tool_is_zero_argument_when_material_evidence_is_pending(session, incident) -> None:
    registry = AgentToolRegistry(clock=FixedAgentRuntimeClock(datetime(2026, 8, 22, 5, tzinfo=UTC)))
    run = AgentRun(incident_id=incident.id, state=AgentRunState.RUNNING, model_name="test", prompt_version="test")

    assert "request_expedite_feasibility" not in {tool.name for tool in registry.available_tools(session, run)}


def test_human_tradeoff_wait_resumes_only_after_exact_selection_without_early_model_call(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall, AgentRunState, AgentWaitKind
    from backend.app.services.agent_model import FakeAgentModel
    from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
    from backend.app.storage.repositories import IncidentRepository
    from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
    from backend.tests.test_dynamic_yard_tradeoff_selection import _pending_review

    IncidentRepository(session).create(incident)
    review, option = _pending_review(session, incident.id)
    model = FakeAgentModel([AgentModelTurn(tool_call=AgentToolCall(name="escalate_agent_run", arguments={}))])
    configuration = CanonicalAgentRuntimeConfiguration.load()
    runtime = AgentRuntimeCoordinator(session=session, model=model, clock=configuration.clock("before_deadline"), configuration=configuration)
    run = runtime.create_run(incident.id)
    waiting = run.model_copy(update={"state": AgentRunState.WAITING, "wait_kind": AgentWaitKind.HUMAN_TRADEOFF_DECISION, "wait_subject_id": str(review.id)})
    runtime._repository.update_run(waiting)

    with pytest.raises(AgentRuntimeConflict, match="unresolved"):
        runtime.advance(run.id)
    assert runtime.get_run(run.id).wait_subject_id == str(review.id)
    assert model.calls == 0
    DynamicYardWorkflow.for_session(session).select_tradeoff(review.id, selected_option_id=option.id, expected_options_fingerprint=review.options_fingerprint, operator_id="operator-1")
    assert runtime.get_run(run.id).wait_kind is AgentWaitKind.HUMAN_TRADEOFF_DECISION
    assert model.calls == 0
    resumed = runtime.advance(run.id)
    assert resumed.id == run.id
    assert model.calls == 1
    assert resumed.wait_kind is None and resumed.wait_subject_id is None


def test_human_tradeoff_wait_does_not_resume_for_mismatched_child_revision(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall, AgentWaitKind
    from backend.app.services.agent_model import FakeAgentModel
    from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
    from backend.app.storage.dynamic_yard import AllocationRevisionRecord
    from backend.app.storage.repositories import IncidentRepository
    from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
    from backend.tests.test_dynamic_yard_tradeoff_selection import _pending_review

    IncidentRepository(session).create(incident)
    review, option = _pending_review(session, incident.id)
    configuration = CanonicalAgentRuntimeConfiguration.load()
    model = FakeAgentModel([AgentModelTurn(tool_call=AgentToolCall(name="escalate_agent_run", arguments={}))])
    runtime = AgentRuntimeCoordinator(session=session, model=model, clock=configuration.clock("before_deadline"), configuration=configuration)
    run = runtime.create_run(incident.id)
    runtime._repository.update_run(run.model_copy(update={"state": AgentRunState.WAITING, "wait_kind": AgentWaitKind.HUMAN_TRADEOFF_DECISION, "wait_subject_id": str(review.id)}))
    revision = DynamicYardWorkflow.for_session(session).select_tradeoff(review.id, selected_option_id=option.id, expected_options_fingerprint=review.options_fingerprint, operator_id="operator-1")
    record = session.get(AllocationRevisionRecord, str(revision.id))
    assert record is not None
    record.allocated_container_ids_json = ["SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-005"]
    session.add(record)
    session.commit()

    with pytest.raises(AgentRuntimeConflict, match="unresolved"):
        runtime.advance(run.id)
    assert runtime.get_run(run.id).wait_kind is AgentWaitKind.HUMAN_TRADEOFF_DECISION
    assert model.calls == 0


def test_pending_safety_review_outranks_unhandled_yard_evidence(session, incident) -> None:
    from backend.app.domain.cargo_safety import SemanticCheckResult
    from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
    from backend.app.services.semantic_safety import FakeSemanticSafetyChecker
    from backend.app.storage.repositories import IncidentRepository
    from backend.tests.test_dynamic_yard_tradeoff_selection import _pending_review

    IncidentRepository(session).create(incident)
    _pending_review(session, incident.id)
    CargoSafetyWorkflow.for_session(session, checker=FakeSemanticSafetyChecker(result=SemanticCheckResult.NO_CONTRADICTION_FOUND)).create_review(incident.id, "SYN-CNT-010", "trusted test note", "test")
    registry = AgentToolRegistry(clock=FixedAgentRuntimeClock(datetime(2026, 8, 22, 5, tzinfo=UTC)))
    run = AgentRun(incident_id=incident.id, state=AgentRunState.RUNNING, model_name="test", prompt_version="test")

    names = {tool.name for tool in registry.available_tools(session, run)}

    assert {"request_cargo_safety_review", "request_expedite_feasibility"} <= names
    assert not {"prepare_rta_request", "send_authorised_rta_request", "evaluate_carrier_timeout"} & names
