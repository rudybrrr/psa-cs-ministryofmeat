from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError


def test_agent_step_records_prompt_version_and_wait_requires_kind() -> None:
    from backend.app.domain.agent_runtime import AgentRun, AgentRunState, AgentStep

    assert "prompt_version" in AgentStep.model_fields
    with pytest.raises(ValidationError, match="wait_kind"):
        AgentRun(
            incident_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            state=AgentRunState.WAITING,
            model_name="fake",
            prompt_version="agent-v1",
            started_at=datetime(2026, 8, 23, tzinfo=UTC),
            updated_at=datetime(2026, 8, 23, tzinfo=UTC),
        )


def test_model_turn_requires_exactly_one_meaningful_action() -> None:
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall

    call = AgentToolCall(name="get_incident_context", arguments={})
    with pytest.raises(ValidationError, match="exactly one"):
        AgentModelTurn(tool_call=call, control="COMPLETE")


def test_escalated_run_requires_reason_and_allows_explicit_terminal_timestamp() -> None:
    from backend.app.domain.agent_runtime import AgentEscalationReason, AgentRun, AgentRunState

    with pytest.raises(ValidationError, match="escalation_reason"):
        AgentRun(
            incident_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            state=AgentRunState.ESCALATED,
            model_name="fake",
            prompt_version="agent-v1",
        )
    run = AgentRun(
        incident_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        state=AgentRunState.ESCALATED,
        model_name="fake",
        prompt_version="agent-v1",
        escalation_reason=AgentEscalationReason.INVALID_MODEL_OUTPUT,
        completed_at=datetime(2026, 8, 23, tzinfo=UTC),
    )
    assert run.completed_at == datetime(2026, 8, 23, tzinfo=UTC)
