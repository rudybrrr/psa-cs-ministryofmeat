from backend.app.orchestration.agent_context import _tool


def test_enum_tool_schema_is_exact_and_zero_argument_tools_remain_empty() -> None:
    assert _tool("prepare_rta_request", "prepare", ("connection_id",), {"connection_id": ("SYN-CONN-JV2",)}).parameters == {
        "type": "object", "properties": {"connection_id": {"type": "string", "enum": ["SYN-CONN-JV2"]}},
        "required": ["connection_id"], "additionalProperties": False,
    }
    assert _tool("request_expedite_feasibility", "apply").parameters == {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
