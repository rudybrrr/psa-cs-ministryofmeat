from backend.app.orchestration.agent_context import _tool
from backend.app.storage.agent_runtime import AgentRuntimeRepository  # noqa: F401


def test_enum_tool_schema_is_exact_and_zero_argument_tools_remain_empty() -> None:
    assert _tool("prepare_rta_request", "prepare", ("connection_id",), {"connection_id": ("SYN-CONN-JV2",)}).parameters == {
        "type": "object", "properties": {"connection_id": {"type": "string", "enum": ["SYN-CONN-JV2"]}},
        "required": ["connection_id"], "additionalProperties": False,
    }
    assert _tool("request_expedite_feasibility", "apply").parameters == {"type": "object", "properties": {}, "required": [], "additionalProperties": False}


def test_canonical_active_revision_keeps_jv2_phase3_compatible(session) -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall
    from backend.app.orchestration.agent_context import AgentToolRegistry
    from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
    from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
    from backend.app.services.agent_model import FakeAgentModel
    from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness
    from backend.app.storage.carrier_recovery import CarrierRecoveryRepository

    scarcity = build_scarce_capacity_workflow(session).run()
    yard = DynamicYardWorkflow.for_session(session)
    harness = CanonicalDynamicYardHarness()
    yard.initialize(scarcity.incident.id, harness.bootstrap_snapshot(scarcity.incident.id))
    yard.ingest(harness.discharge_active_snapshot(scarcity.incident.id))
    yard.apply_latest_assessment(scarcity.incident.id)
    assert "SYN-CONN-JV2" in yard.compatible_connection_ids(scarcity.incident.id)
    assert "SYN-CONN-SF1" not in yard.compatible_connection_ids(scarcity.incident.id)
    config = CanonicalAgentRuntimeConfiguration.load()
    model = FakeAgentModel([AgentModelTurn(tool_call=AgentToolCall(name="prepare_rta_request", arguments={"connection_id": "SYN-CONN-JV2"}))])
    runtime = AgentRuntimeCoordinator(session=session, model=model, clock=config.clock("before_deadline"), configuration=config)
    run = runtime.create_run(scarcity.incident.id)
    tool = next(tool for tool in AgentToolRegistry(clock=runtime._clock).available_tools(session, run) if tool.name == "prepare_rta_request")
    assert tool.parameters["properties"]["connection_id"]["enum"] == list(yard.compatible_connection_ids(scarcity.incident.id))
    result = runtime.advance(run.id)
    case = CarrierRecoveryRepository(session).get_case(__import__("uuid").UUID(result.wait_subject_id))
    assert case.affected_container_ids == ("SYN-CNT-017",)


def test_membership_mismatch_is_excluded_and_direct_prepare_is_rejected(session) -> None:
    from backend.app.domain.dynamic_yard import AllocationRevision
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall
    from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
    from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
    from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness
    from backend.app.services.agent_model import FakeAgentModel
    from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
    from backend.app.storage.carrier_recovery import CarrierRecoveryRepository

    scarcity = build_scarce_capacity_workflow(session).run()
    yard = DynamicYardWorkflow.for_session(session); harness = CanonicalDynamicYardHarness()
    yard.initialize(scarcity.incident.id, harness.bootstrap_snapshot(scarcity.incident.id))
    active = harness.discharge_active_snapshot(scarcity.incident.id); yard.ingest(active); yard.apply_latest_assessment(scarcity.incident.id)
    prior = yard.history(scarcity.incident.id).revisions[-1]
    yard._repository.add_revision(AllocationRevision(incident_id=prior.incident_id, source_phase2_evaluation_id=prior.source_phase2_evaluation_id, source_forecast_snapshot_id=prior.source_forecast_snapshot_id, parent_revision_id=prior.id, allocated_container_ids=tuple(item for item in prior.allocated_container_ids if item != "SYN-CNT-010"), locked_container_ids=prior.locked_container_ids, preserved_connection_total=prior.preserved_connection_total, expected_preserved_connections=prior.expected_preserved_connections, reason="test membership mismatch"))
    assert not yard.phase3_compatible(scarcity.incident.id, "SYN-CONN-JV2")
    configuration = CanonicalAgentRuntimeConfiguration.load(); runtime = AgentRuntimeCoordinator(session=session, model=FakeAgentModel([]), clock=configuration.clock("before_deadline"), configuration=configuration)
    run = runtime.create_run(scarcity.incident.id)
    runtime._execute_turn(run, "prepare_rta_request", {"connection_id": "SYN-CONN-JV2"})
    assert not CarrierRecoveryRepository(session).list_cases(scarcity.incident.id)
