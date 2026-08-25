from uuid import uuid4

from backend.app.domain.agent_runtime import (
    AgentToolDefinition,
    AgentTurnContext,
    InvalidAgentModelTurn,
)
from backend.app.services.canonical_replay import (
    CANONICAL_JV2_CONNECTION_ID,
    CANONICAL_REPLAY_MODEL_NAME,
    CANONICAL_SAFETY_CONTAINER_ID,
    CanonicalReplayAgentModel,
)


def _tool(name: str, connection_enum: tuple[str, ...] | None = None) -> AgentToolDefinition:
    properties = (
        {"connection_id": {"type": "string", "enum": list(connection_enum)}}
        if connection_enum is not None
        else {}
    )
    required = ["connection_id"] if connection_enum is not None else []
    return AgentToolDefinition(
        name=name,
        description="test",
        parameters={"type": "object", "properties": properties, "required": required, "additionalProperties": False},
    )


def _context(step_count: int = 0, *, forecast_stages=None, carrier_cases=None, pending_reviews=None, **extra_summary) -> AgentTurnContext:
    summary = dict(extra_summary)
    summary.setdefault("carrier_cases", carrier_cases or [])
    summary.setdefault("cargo_safety_pending_reviews", pending_reviews or [])
    if forecast_stages is not None:
        summary["dynamic_yard"] = {"snapshot_count": len(forecast_stages), "forecast_stages": list(forecast_stages)}
    return AgentTurnContext(run_id=uuid4(), incident_id=uuid4(), step_count=step_count, remaining_steps=max(12 - step_count, 0), summary=summary)


def _decide(context, tools):
    return CanonicalReplayAgentModel().decide(context, tools)


def test_model_name_is_the_pinned_canonical_value() -> None:
    assert CanonicalReplayAgentModel.model_name == CANONICAL_REPLAY_MODEL_NAME


def test_feasibility_has_top_priority() -> None:
    tools = (_tool("request_expedite_feasibility"), _tool("prepare_rta_request", (CANONICAL_JV2_CONNECTION_ID,)), _tool("pause_agent_run"))
    turn = _decide(_context(step_count=3, forecast_stages=["PRE_DISCHARGE"]), tools)
    assert turn.tool_call.name == "request_expedite_feasibility"
    assert turn.tool_call.arguments == {}


def test_first_turn_pauses_after_bootstrap_even_when_prepare_is_exposed() -> None:
    tools = (_tool("pause_agent_run"), _tool("prepare_rta_request", (CANONICAL_JV2_CONNECTION_ID,)))
    turn = _decide(_context(step_count=0, forecast_stages=["PRE_DISCHARGE"]), tools)
    assert turn.tool_call.name == "pause_agent_run"


def test_first_turn_before_bootstrap_fails_safely_with_sequence_violation() -> None:
    tools = (_tool("pause_agent_run"), _tool("prepare_rta_request"))
    outcome = _decide(_context(step_count=0, forecast_stages=[]), tools)
    assert isinstance(outcome, InvalidAgentModelTurn)
    assert outcome.error_kind == "CANONICAL_SEQUENCE_VIOLATION"


def test_prepare_selects_the_single_compatible_connection() -> None:
    tools = (_tool("prepare_rta_request", (CANONICAL_JV2_CONNECTION_ID,)),)
    turn = _decide(_context(step_count=2, forecast_stages=["PRE_DISCHARGE", "DISCHARGE_ACTIVE"]), tools)
    assert turn.tool_call.name == "prepare_rta_request"
    assert turn.tool_call.arguments == {"connection_id": CANONICAL_JV2_CONNECTION_ID}


def test_prepare_without_bootstrap_evidence_violates_sequence() -> None:
    tools = (_tool("prepare_rta_request", (CANONICAL_JV2_CONNECTION_ID,)),)
    outcome = _decide(_context(step_count=4, forecast_stages=[]), tools)
    assert isinstance(outcome, InvalidAgentModelTurn)
    assert outcome.error_kind == "CANONICAL_SEQUENCE_VIOLATION"


def test_prepare_with_ambiguous_connection_enum_fails_closed() -> None:
    tools = (_tool("prepare_rta_request", (CANONICAL_JV2_CONNECTION_ID, "SYN-CONN-SF1")),)
    outcome = _decide(_context(step_count=2, forecast_stages=["PRE_DISCHARGE"]), tools)
    assert isinstance(outcome, InvalidAgentModelTurn)
    assert outcome.error_kind == "CANONICAL_AMBIGUOUS_CONNECTION"

    empty = (_tool("prepare_rta_request"),)
    outcome = _decide(_context(step_count=2, forecast_stages=["PRE_DISCHARGE"]), empty)
    assert isinstance(outcome, InvalidAgentModelTurn)
    assert outcome.error_kind == "CANONICAL_AMBIGUOUS_CONNECTION"


def test_send_targets_the_unique_awaiting_case() -> None:
    tools = (_tool("send_authorised_rta_request",),)
    cases = [
        {"id": "case-a", "state": "COMPLETED"},
        {"id": "case-b", "state": "AWAITING_REQUEST_APPROVAL"},
    ]
    turn = _decide(_context(step_count=4, forecast_stages=["PRE_DISCHARGE"], carrier_cases=cases), tools)
    assert turn.tool_call.name == "send_authorised_rta_request"
    assert turn.tool_call.arguments == {"case_id": "case-b"}


def test_send_with_ambiguous_cases_fails_closed() -> None:
    tools = (_tool("send_authorised_rta_request",),)
    cases = [
        {"id": "case-a", "state": "AWAITING_REQUEST_APPROVAL"},
        {"id": "case-b", "state": "AWAITING_REQUEST_APPROVAL"},
    ]
    outcome = _decide(_context(step_count=4, forecast_stages=["PRE_DISCHARGE"], carrier_cases=cases), tools)
    assert isinstance(outcome, InvalidAgentModelTurn)
    assert outcome.error_kind == "CANONICAL_AMBIGUOUS_CASE"

    outcome = _decide(_context(step_count=4, forecast_stages=["PRE_DISCHARGE"], carrier_cases=[]), tools)
    assert isinstance(outcome, InvalidAgentModelTurn)
    assert outcome.error_kind == "CANONICAL_AMBIGUOUS_CASE"


def test_safety_review_targets_the_canonical_container_only() -> None:
    tools = (_tool("request_cargo_safety_review",),)
    pending = [{"review_id": "rev-1", "container_id": CANONICAL_SAFETY_CONTAINER_ID}]
    turn = _decide(_context(step_count=6, forecast_stages=["PRE_DISCHARGE"], pending_reviews=pending), tools)
    assert turn.tool_call.name == "request_cargo_safety_review"
    assert turn.tool_call.arguments == {"container_id": CANONICAL_SAFETY_CONTAINER_ID}


def test_safety_review_with_unexpected_pending_set_fails_closed() -> None:
    tools = (_tool("request_cargo_safety_review",),)
    pending = [
        {"review_id": "rev-1", "container_id": CANONICAL_SAFETY_CONTAINER_ID},
        {"review_id": "rev-2", "container_id": "SYN-CNT-011"},
    ]
    outcome = _decide(_context(step_count=6, forecast_stages=["PRE_DISCHARGE"], pending_reviews=pending), tools)
    assert isinstance(outcome, InvalidAgentModelTurn)
    assert outcome.error_kind == "CANONICAL_AMBIGUOUS_CONTAINER"

    foreign = [{"review_id": "rev-1", "container_id": "SYN-CNT-017"}]
    outcome = _decide(_context(step_count=6, forecast_stages=["PRE_DISCHARGE"], pending_reviews=foreign), tools)
    assert isinstance(outcome, InvalidAgentModelTurn)
    assert outcome.error_kind == "CANONICAL_AMBIGUOUS_CONTAINER"


def test_no_legal_tool_escalates_instead_of_guessing() -> None:
    tools = (_tool("complete_agent_run"), _tool("escalate_agent_run"))
    turn = _decide(_context(step_count=5, forecast_stages=["PRE_DISCHARGE"]), tools)
    assert turn.tool_call.name == "escalate_agent_run"


def test_model_never_selects_an_unavailable_tool() -> None:
    model = CanonicalReplayAgentModel()
    contexts = [
        _context(step_count=0, forecast_stages=[]),
        _context(step_count=0, forecast_stages=["PRE_DISCHARGE"]),
        _context(step_count=2, forecast_stages=["PRE_DISCHARGE"]),
        _context(step_count=4, forecast_stages=["PRE_DISCHARGE"], carrier_cases=[{"id": "c", "state": "AWAITING_REQUEST_APPROVAL"}]),
        _context(step_count=6, forecast_stages=["PRE_DISCHARGE"], pending_reviews=[{"review_id": "r", "container_id": CANONICAL_SAFETY_CONTAINER_ID}]),
    ]
    tool_sets = [
        (),
        (_tool("pause_agent_run"),),
        (_tool("escalate_agent_run"),),
        (_tool("prepare_rta_request", (CANONICAL_JV2_CONNECTION_ID,)),),
    ]
    for context in contexts:
        for tools in tool_sets:
            allowed = {tool.name for tool in tools}
            outcome = model.decide(context, tools)
            selected = getattr(getattr(outcome, "tool_call", None), "name", None)
            if selected is not None:
                assert selected in allowed
