from datetime import UTC, datetime

from backend.app.domain.agent_runtime import AgentRun, AgentRunState
from backend.app.orchestration.agent_context import AgentToolRegistry
from backend.app.orchestration.agent_runtime import FixedAgentRuntimeClock


def test_feasibility_tool_is_zero_argument_when_material_evidence_is_pending(session, incident) -> None:
    registry = AgentToolRegistry(clock=FixedAgentRuntimeClock(datetime(2026, 8, 22, 5, tzinfo=UTC)))
    run = AgentRun(incident_id=incident.id, state=AgentRunState.RUNNING, model_name="test", prompt_version="test")

    assert "request_expedite_feasibility" not in {tool.name for tool in registry.available_tools(session, run)}
