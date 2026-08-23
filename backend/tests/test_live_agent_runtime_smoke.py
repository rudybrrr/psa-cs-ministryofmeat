import os
from uuid import UUID

import pytest


@pytest.mark.skipif(os.getenv("RUN_LIVE_LLM_TESTS") != "1", reason="opt-in live agent test")
def test_live_agent_selects_only_exposed_tool() -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolDefinition, AgentTurnContext
    from backend.app.services.agent_model import OpenAIAgentModel

    tools = (AgentToolDefinition(name="get_incident_context", description="Read incident status.", parameters={"type": "object", "properties": {}, "additionalProperties": False}),)
    turn = OpenAIAgentModel().decide(AgentTurnContext(run_id=UUID(int=1), incident_id=UUID(int=2), step_count=0, remaining_steps=1), tools)
    assert isinstance(turn, AgentModelTurn)
    assert turn.tool_call is not None
    assert turn.tool_call.name == "get_incident_context"
