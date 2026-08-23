from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.app.domain.carrier_recovery import PrepareCarrierRecoveryCaseCommand, parse_explicit_utc
from backend.app.domain.agent_runtime import AgentEscalationReason, AgentRun, AgentRunState, AgentStep, AgentStepKind, InvalidAgentModelTurn
from backend.app.domain.models import utc_now
from backend.app.orchestration.agent_context import AgentToolRegistry, build_agent_turn_context
from backend.app.services.agent_model import AgentModel, AgentModelProviderFailure
from backend.app.storage.agent_runtime import AgentRuntimeRepository
from backend.app.storage.repositories import IncidentRepository


class AgentRuntimeClock(Protocol):
    def now(self) -> datetime: ...


class FixedAgentRuntimeClock:
    def __init__(self, value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("agent runtime clock must be UTC")
        self._value = value.astimezone(UTC)

    def now(self) -> datetime:
        return self._value


class CanonicalAgentRuntimeConfiguration:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    @classmethod
    def load(cls) -> "CanonicalAgentRuntimeConfiguration":
        root = Path(__file__).resolve().parents[3]
        path = root / "shared" / "fixtures" / "canonical-agent-runtime-config.json"
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def prepare_command(self, incident_id: UUID, connection_id: str) -> PrepareCarrierRecoveryCaseCommand:
        try:
            values = self._payload["rta_preparation"][connection_id]
        except KeyError as error:
            raise ValueError(f"no trusted RTA preparation configuration for {connection_id}") from error
        return PrepareCarrierRecoveryCaseCommand(
            incident_id=incident_id,
            connection_id=connection_id,
            prepared_at=values["prepared_at"],
            requested_eta_pta=values["requested_eta_pta"],
            response_deadline=values["response_deadline"],
        )

    def clock(self, name: str) -> FixedAgentRuntimeClock:
        return FixedAgentRuntimeClock(parse_explicit_utc(self._payload["synthetic_clock"][name]))


class AgentRuntimeCoordinator:
    def __init__(self, *, session, model: AgentModel, clock: AgentRuntimeClock, configuration: CanonicalAgentRuntimeConfiguration) -> None:
        self._session = session
        self._model = model
        self._clock = clock
        self._configuration = configuration
        self._repository = AgentRuntimeRepository(session)
        self._registry = AgentToolRegistry(clock=clock)

    def create_run(self, incident_id: UUID) -> AgentRun:
        IncidentRepository(self._session).get(incident_id)
        return self._repository.create_run(AgentRun(incident_id=incident_id, model_name=self._model.model_name, prompt_version="incident-agent-v1"))

    def get_run(self, run_id: UUID) -> AgentRun:
        return self._repository.get_run(run_id)

    def advance(self, run_id: UUID) -> AgentRun:
        run = self.get_run(run_id)
        if run.state in {AgentRunState.COMPLETED, AgentRunState.ESCALATED, AgentRunState.FAILED}:
            return run
        if run.state is AgentRunState.WAITING:
            raise AgentRuntimeConflict("agent wait condition remains unresolved")
        running = run.model_copy(update={"state": AgentRunState.RUNNING, "updated_at": utc_now()})
        self._repository.update_run(running)
        context = build_agent_turn_context(self._session, running, self._registry)
        tools = self._registry.available_tools(self._session, running)
        for attempt in range(2):
            try:
                turn = self._model.decide(context, tools)
            except AgentModelProviderFailure:
                if attempt == 0:
                    continue
                return self._escalate(running, AgentEscalationReason.MODEL_UNAVAILABLE, "Agent model unavailable.")
            if isinstance(turn, InvalidAgentModelTurn):
                if attempt == 0:
                    continue
                return self._escalate(running, AgentEscalationReason.INVALID_MODEL_OUTPUT, "Agent model returned invalid output.")
            return self._escalate(running, AgentEscalationReason.MISSING_EVIDENCE, "Tool execution is not yet available.")
        raise AssertionError("unreachable")

    def _escalate(self, run: AgentRun, reason: AgentEscalationReason, summary: str) -> AgentRun:
        step = AgentStep(run_id=run.id, step_number=run.step_count + 1, kind=AgentStepKind.ESCALATE, action_summary=summary, model_name=run.model_name, prompt_version=run.prompt_version)
        self._repository.add_step(step)
        terminal = run.model_copy(update={"state": AgentRunState.ESCALATED, "step_count": step.step_number, "escalation_reason": reason, "updated_at": utc_now(), "completed_at": utc_now()})
        return self._repository.update_run(terminal)
