from uuid import UUID

from backend.app.storage.agent_runtime import AgentRuntimeRepository
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository
from backend.app.storage.cargo_safety import CargoSafetyRepository  # noqa: F401
from backend.app.storage.dynamic_yard import DynamicYardRepository  # noqa: F401


def test_context_uses_durable_ids_and_registry_filters_timeout_before_deadline(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentRun
    from backend.app.orchestration.agent_context import AgentToolRegistry, build_agent_turn_context
    from backend.app.orchestration.agent_runtime import CanonicalAgentRuntimeConfiguration
    run = AgentRuntimeRepository(session).create_run(AgentRun(incident_id=incident.id, model_name="fake", prompt_version="v1"))
    registry = AgentToolRegistry(clock=CanonicalAgentRuntimeConfiguration.load().clock("before_deadline"))
    context = build_agent_turn_context(session, run, registry)
    assert context.incident_id == incident.id
    assert "raw_response" not in context.model_dump_json()
    assert "evaluate_carrier_timeout" not in {tool.name for tool in registry.available_tools(session, run)}


def test_registry_explains_pre_discharge_wait(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentRun
    from backend.app.orchestration.agent_context import AgentToolRegistry
    from backend.app.orchestration.agent_runtime import CanonicalAgentRuntimeConfiguration

    run = AgentRuntimeRepository(session).create_run(AgentRun(incident_id=incident.id, model_name="fake", prompt_version="v1"))
    tools = {tool.name: tool for tool in AgentToolRegistry(clock=CanonicalAgentRuntimeConfiguration.load().clock("before_deadline")).available_tools(session, run)}
    assert "pause_agent_run" in tools
    assert "PRE_DISCHARGE" in tools["pause_agent_run"].description
    assert "DISCHARGE_ACTIVE" in tools["pause_agent_run"].description


def test_registry_prioritizes_authorized_send_over_redundant_reads(session) -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall
    from backend.app.domain.carrier_recovery import RequestApprovalCommand
    from backend.app.domain.enums import ApprovalStatus
    from backend.app.orchestration.agent_context import AgentToolRegistry
    from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
    from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
    from backend.app.services.agent_model import FakeAgentModel

    scarcity = build_scarce_capacity_workflow(session).run(seed=20260822, world_count=50)
    configuration = CanonicalAgentRuntimeConfiguration.load()
    runtime = AgentRuntimeCoordinator(session=session, model=FakeAgentModel([AgentModelTurn(tool_call=AgentToolCall(name="prepare_rta_request", arguments={"connection_id": "JV2"}))]), clock=configuration.clock("before_deadline"), configuration=configuration)
    prepared = runtime.advance(runtime.create_run(scarcity.incident.id).id)
    history = build_carrier_recovery_workflow(session).history(UUID(prepared.wait_subject_id))
    binding = history.bindings[0]
    build_carrier_recovery_workflow(session).record_request_approval(RequestApprovalCommand(case_id=history.case.id, proposal_decision_id=binding.proposal_decision_id, request_id=history.request.id, expected_payload_fingerprint=binding.payload_fingerprint, operator_id="operator", status=ApprovalStatus.APPROVED))

    tools = {tool.name for tool in AgentToolRegistry(clock=configuration.clock("before_deadline")).available_tools(session, prepared)}
    assert "send_authorised_rta_request" in tools
    assert not {name for name in tools if name.startswith("get_")}

    sent = runtime._execute_turn(prepared, "send_authorised_rta_request", {"case_id": str(history.case.id)})
    ordinary_tools = {tool.name: tool for tool in AgentToolRegistry(clock=configuration.clock("before_deadline")).available_tools(session, sent)}
    assert {"get_incident_context", "get_scarcity_evaluation", "get_carrier_recovery_cases", "get_cargo_safety_reviews", "get_carrier_recovery_history"} <= ordinary_tools.keys()
    assert "Use only when required detail is absent from the supplied turn context" in ordinary_tools["get_incident_context"].description


def test_context_exposes_forecast_stages_and_pending_safety_reviews(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentRun
    from backend.app.orchestration.agent_context import AgentToolRegistry, build_agent_turn_context
    from backend.app.orchestration.agent_runtime import CanonicalAgentRuntimeConfiguration
    from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
    from backend.app.services.canonical_replay import CANONICAL_SAFETY_CONTAINER_ID, CANONICAL_SAFETY_NOTE_SOURCE, CANONICAL_SAFETY_NOTE_TEXT
    from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness
    from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow

    scarcity = build_scarce_capacity_workflow(session).run()
    yard = DynamicYardWorkflow.for_session(session)
    yard.initialize(scarcity.incident.id, CanonicalDynamicYardHarness().bootstrap_snapshot(scarcity.incident.id))
    run = AgentRuntimeRepository(session).create_run(AgentRun(incident_id=scarcity.incident.id, model_name="fake", prompt_version="v1"))
    registry = AgentToolRegistry(clock=CanonicalAgentRuntimeConfiguration.load().clock("before_deadline"))

    bootstrapped = build_agent_turn_context(session, run, registry)
    assert bootstrapped.summary["dynamic_yard"]["forecast_stages"] == ["PRE_DISCHARGE"]
    assert bootstrapped.summary["cargo_safety_pending_reviews"] == []
    assert "pause_agent_run" in {tool.name for tool in registry.available_tools(session, run)}

    workflow = CargoSafetyWorkflow.for_session(session)
    review = workflow.create_review(scarcity.incident.id, "SYN-CNT-010", CANONICAL_SAFETY_NOTE_TEXT, CANONICAL_SAFETY_NOTE_SOURCE)
    pending = build_agent_turn_context(session, run, registry).summary["cargo_safety_pending_reviews"]
    assert pending == [{"review_id": str(review.id), "container_id": CANONICAL_SAFETY_CONTAINER_ID}]
    pending_tools = {tool.name for tool in registry.available_tools(session, run)}
    assert "request_cargo_safety_review" in pending_tools
    assert not {name for name in pending_tools if name.startswith("get_")}

    workflow.evaluate(review.id)
    evaluated = build_agent_turn_context(session, run, registry)
    assert evaluated.summary["cargo_safety_pending_reviews"] == []
    assert evaluated.summary["dynamic_yard"]["forecast_stages"] == ["PRE_DISCHARGE"]
