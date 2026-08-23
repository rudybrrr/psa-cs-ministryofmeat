from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from backend.app.domain.models import FrozenContract, utc_now


class AgentRunState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class AgentWaitKind(StrEnum):
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    COUNTER_APPROVAL = "COUNTER_APPROVAL"
    CARRIER_RESPONSE_OR_TIMEOUT = "CARRIER_RESPONSE_OR_TIMEOUT"
    NEW_OPERATIONAL_EVIDENCE = "NEW_OPERATIONAL_EVIDENCE"
    HUMAN_TRADEOFF_DECISION = "HUMAN_TRADEOFF_DECISION"


class AgentStepKind(StrEnum):
    TOOL_CALL = "TOOL_CALL"
    WAIT = "WAIT"
    COMPLETE = "COMPLETE"
    ESCALATE = "ESCALATE"


class AgentToolInvocationStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class AgentEscalationReason(StrEnum):
    SAFETY_REVIEW_REQUIRED = "SAFETY_REVIEW_REQUIRED"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    TOOL_FAILURE = "TOOL_FAILURE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"
    AGENT_LOOP_GUARD = "AGENT_LOOP_GUARD"
    STEP_BUDGET_EXCEEDED = "STEP_BUDGET_EXCEEDED"
    UNRESOLVED_TRADEOFF = "UNRESOLVED_TRADEOFF"


class AgentControlAction(StrEnum):
    PAUSE = "PAUSE"
    COMPLETE = "COMPLETE"
    ESCALATE = "ESCALATE"


class AgentToolCall(FrozenContract):
    name: str = Field(min_length=1, max_length=128)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class AgentModelTurn(FrozenContract):
    tool_call: AgentToolCall | None = None
    control: AgentControlAction | None = None
    action_summary: str = Field(default="", max_length=600)

    @model_validator(mode="after")
    def exactly_one_action(self) -> Self:
        if (self.tool_call is None) == (self.control is None):
            raise ValueError("AgentModelTurn requires exactly one meaningful action")
        return self


class InvalidAgentModelTurn(FrozenContract):
    error_kind: str = Field(min_length=1, max_length=128)
    detail: str = Field(min_length=1, max_length=600)


class AgentToolDefinition(FrozenContract):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=1000)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class AgentTurnContext(FrozenContract):
    run_id: UUID
    incident_id: UUID
    step_count: int = Field(ge=0)
    remaining_steps: int = Field(ge=0)
    summary: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()


class AgentRun(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    state: AgentRunState = AgentRunState.CREATED
    model_name: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=100)
    step_count: int = Field(default=0, ge=0)
    max_steps: int = Field(default=12, gt=0, le=100)
    wait_kind: AgentWaitKind | None = None
    wait_subject_id: str | None = Field(default=None, max_length=128)
    escalation_reason: AgentEscalationReason | None = None
    started_at: AwareDatetime = Field(default_factory=utc_now)
    updated_at: AwareDatetime = Field(default_factory=utc_now)
    completed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def state_shape(self) -> Self:
        if self.state is AgentRunState.WAITING and self.wait_kind is None:
            raise ValueError("WAITING run requires wait_kind")
        if self.state is not AgentRunState.WAITING and self.wait_kind is not None:
            raise ValueError("wait_kind is allowed only for WAITING run")
        if self.state is AgentRunState.ESCALATED and self.escalation_reason is None:
            raise ValueError("ESCALATED run requires escalation_reason")
        if self.state is not AgentRunState.ESCALATED and self.escalation_reason is not None:
            raise ValueError("escalation_reason is allowed only for ESCALATED run")
        return self


class AgentStep(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    step_number: int = Field(ge=1)
    kind: AgentStepKind
    action_summary: str = Field(min_length=1, max_length=600)
    evidence_refs: tuple[str, ...] = ()
    model_name: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=100)
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    created_at: AwareDatetime = Field(default_factory=utc_now)


class AgentToolInvocation(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    step_id: UUID
    tool_name: str = Field(min_length=1, max_length=128)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    status: AgentToolInvocationStatus = AgentToolInvocationStatus.PENDING
    result_summary: str | None = Field(default=None, max_length=1000)
    error_kind: str | None = Field(default=None, max_length=128)
    started_at: AwareDatetime = Field(default_factory=utc_now)
    completed_at: AwareDatetime | None = None


class AgentHistory(FrozenContract):
    run: AgentRun
    steps: tuple[AgentStep, ...] = ()
    tool_invocations: tuple[AgentToolInvocation, ...] = ()
