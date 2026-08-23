from uuid import UUID

from backend.app.storage.agent_runtime import AgentRuntimeRepository
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository


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
