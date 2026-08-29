from types import SimpleNamespace
from uuid import UUID


def context():
    from backend.app.domain.agent_runtime import AgentTurnContext

    return AgentTurnContext(run_id=UUID(int=1), incident_id=UUID(int=2), step_count=0, remaining_steps=12)


def tools():
    from backend.app.domain.agent_runtime import AgentToolDefinition

    return (AgentToolDefinition(name="get_incident_context", description="Read incident.", parameters={"type": "object"}),)


def test_fake_model_returns_scripted_turn_without_network() -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall
    from backend.app.services.agent_model import FakeAgentModel

    turn = AgentModelTurn(tool_call=AgentToolCall(name="get_incident_context"))
    assert FakeAgentModel([turn]).decide(context(), tools()) == turn


def test_openai_adapter_returns_invalid_turn_for_unknown_tool() -> None:
    from backend.app.domain.agent_runtime import InvalidAgentModelTurn
    from backend.app.services.agent_model import OpenAIAgentModel

    response = SimpleNamespace(output=[SimpleNamespace(type="function_call", name="shell", arguments="{}", status="completed")])
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **_: response))
    assert isinstance(OpenAIAgentModel(api_key="test", client=client).decide(context(), tools()), InvalidAgentModelTurn)


def test_openai_adapter_requires_one_nonparallel_tool_call() -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn
    from backend.app.services.agent_model import OpenAIAgentModel

    request = {}
    response = SimpleNamespace(output=[SimpleNamespace(type="function_call", name="get_incident_context", arguments="{}", status="completed")])

    def create(**kwargs):
        request.update(kwargs)
        return response

    turn = OpenAIAgentModel(api_key="test", client=SimpleNamespace(responses=SimpleNamespace(create=create))).decide(context(), tools())
    assert isinstance(turn, AgentModelTurn)
    assert request["tool_choice"] == "required"
    assert request["parallel_tool_calls"] is False
