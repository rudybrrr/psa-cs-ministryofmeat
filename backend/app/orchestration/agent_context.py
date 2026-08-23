from __future__ import annotations

from sqlmodel import Session

from backend.app.domain.agent_runtime import AgentRun, AgentRunState, AgentToolDefinition, AgentTurnContext
from backend.app.domain.carrier_recovery import CarrierRecoveryCaseState
from backend.app.orchestration.agent_runtime import AgentRuntimeClock
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository
from backend.app.storage.repositories import DecisionRepository, ScarcityEvaluationRepository


def _tool(name: str, description: str, required: tuple[str, ...] = ()) -> AgentToolDefinition:
    return AgentToolDefinition(name=name, description=description, parameters={"type": "object", "properties": {key: {"type": "string"} for key in required}, "required": list(required), "additionalProperties": False})


class AgentToolRegistry:
    def __init__(self, *, clock: AgentRuntimeClock) -> None:
        self._clock = clock

    def available_tools(self, session: Session, run: AgentRun) -> tuple[AgentToolDefinition, ...]:
        if run.state in {AgentRunState.COMPLETED, AgentRunState.ESCALATED, AgentRunState.FAILED}:
            return ()
        tools = [
            _tool("get_incident_context", "Read compact incident status."),
            _tool("get_scarcity_evaluation", "Read persisted scarcity result."),
            _tool("get_carrier_recovery_cases", "Read carrier recovery cases."),
            _tool("get_cargo_safety_reviews", "Read cargo safety reviews."),
            _tool("pause_agent_run", "Pause only at a durable wait boundary."),
            _tool("complete_agent_run", "Complete only when deterministic validation permits."),
            _tool("escalate_agent_run", "Safely escalate with typed evidence."),
        ]
        cases = CarrierRecoveryRepository(session).list_cases(run.incident_id)
        for case in cases:
            tools.append(_tool("get_carrier_recovery_history", "Read one carrier case history.", ("case_id",)))
            if case.state is CarrierRecoveryCaseState.AWAITING_REQUEST_APPROVAL:
                tools.append(_tool("send_authorised_rta_request", "Send an exact already-authorised request.", ("case_id",)))
            if case.state is CarrierRecoveryCaseState.AWAITING_CARRIER:
                history = CarrierRecoveryRepository(session).history(case.id)
                if history.request_context and not history.carrier_responses and self._clock.now() >= history.request_context.response_deadline:
                    tools.append(_tool("evaluate_carrier_timeout", "Evaluate a due carrier timeout using the trusted clock.", ("case_id",)))
        if not cases:
            tools.append(_tool("prepare_rta_request", "Prepare configured RTA recovery for a connection.", ("connection_id",)))
        return tuple({tool.name: tool for tool in tools}.values())


def build_agent_turn_context(session: Session, run: AgentRun, registry: AgentToolRegistry) -> AgentTurnContext:
    decisions = DecisionRepository(session).list_for_incident(run.incident_id)
    try:
        scarcity = ScarcityEvaluationRepository(session).get_for_incident(run.incident_id)
        scarcity_summary: dict[str, object] = {"evaluation_id": str(scarcity.id), "fixture_id": scarcity.fixture_id}
    except LookupError:
        scarcity_summary = {"status": "missing"}
    cases = CarrierRecoveryRepository(session).list_cases(run.incident_id)
    return AgentTurnContext(
        run_id=run.id,
        incident_id=run.incident_id,
        step_count=run.step_count,
        remaining_steps=max(run.max_steps - run.step_count, 0),
        summary={
            "authority": "LLM selects only exposed tools; typed state is authoritative.",
            "scarcity": scarcity_summary,
            "decision_ids": [str(decision.id) for decision in decisions],
            "carrier_cases": [{"id": str(case.id), "state": case.state.value} for case in cases],
            "available_tools": [tool.name for tool in registry.available_tools(session, run)],
        },
        evidence_refs=tuple(str(decision.id) for decision in decisions[-10:]),
    )
