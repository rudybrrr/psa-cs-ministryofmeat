from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.app.domain.carrier_recovery import PrepareCarrierRecoveryCaseCommand, parse_explicit_utc
from backend.app.domain.agent_runtime import AgentEscalationReason, AgentRun, AgentRunState, AgentStep, AgentStepKind, AgentToolInvocationStatus, AgentWaitKind, InvalidAgentModelTurn
from backend.app.domain.carrier_recovery import EvaluateTimeoutCommand, CarrierRecoveryCaseState
from backend.app.domain.models import utc_now
from backend.app.orchestration.agent_context import AgentToolRegistry, build_agent_turn_context
from backend.app.services.agent_model import AgentModel, AgentModelProviderFailure
from backend.app.storage.agent_runtime import AgentRuntimeConflict, AgentRuntimeRepository
from backend.app.storage.repositories import IncidentRepository
from backend.app.orchestration.carrier_recovery import CarrierRecoveryConflict, build_carrier_recovery_workflow
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository
from backend.app.domain.enums import ApprovalStatus
from backend.app.domain.cargo_safety import CargoSafetyReviewState
from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
from backend.app.storage.cargo_safety import CargoSafetyRepository
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow


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
            connection_id=values.get("connection_id", connection_id),
            prepared_at=values["prepared_at"],
            requested_eta_pta=values["requested_eta_pta"],
            response_deadline=values["response_deadline"],
        )

    def clock(self, name: str) -> FixedAgentRuntimeClock:
        return FixedAgentRuntimeClock(parse_explicit_utc(self._payload["synthetic_clock"][name]))


class AgentRuntimeCoordinator:
    def __init__(self, *, session, model: AgentModel, clock: AgentRuntimeClock, configuration: CanonicalAgentRuntimeConfiguration, cargo_safety_checker=None) -> None:
        self._session = session
        self._model = model
        self._clock = clock
        self._configuration = configuration
        self._repository = AgentRuntimeRepository(session)
        self._registry = AgentToolRegistry(clock=clock)
        self._cargo_safety_checker = cargo_safety_checker

    def create_run(self, incident_id: UUID) -> AgentRun:
        IncidentRepository(self._session).get(incident_id)
        return self._repository.create_run(AgentRun(incident_id=incident_id, model_name=self._model.model_name, prompt_version="incident-agent-v1"))

    def get_run(self, run_id: UUID) -> AgentRun:
        return self._repository.get_run(run_id)

    def advance(self, run_id: UUID) -> AgentRun:
        run = self.get_run(run_id)
        if run.state in {AgentRunState.COMPLETED, AgentRunState.ESCALATED, AgentRunState.FAILED}:
            return run
        recovered = self._recover_pending_invocation(run)
        if recovered is not None:
            return recovered
        if run.state is AgentRunState.WAITING:
            resolved = self._resolve_wait(run)
            if resolved is None:
                raise AgentRuntimeConflict("agent wait condition remains unresolved")
            run = resolved
        running = run.model_copy(update={"state": AgentRunState.RUNNING, "updated_at": utc_now()})
        self._repository.update_run(running)
        for _ in range(min(8, running.max_steps - running.step_count)):
            context = build_agent_turn_context(self._session, running, self._registry)
            tools = self._registry.available_tools(self._session, running)
            outcome = self._decide_once(running, context, tools)
            if isinstance(outcome, AgentRun):
                return outcome
            running = outcome
        return self._escalate(running, AgentEscalationReason.STEP_BUDGET_EXCEEDED, "Agent advance tool-call budget exhausted.")

    def _recover_pending_invocation(self, run: AgentRun) -> AgentRun | None:
        pending = self._repository.pending_invocations(run.id)
        if not pending:
            return None
        latest_step_number = max(
            (step.step_number for step in self._repository.history(run.id).steps),
            default=run.step_count,
        )
        if len(pending) != 1 or pending[0].tool_name != "send_authorised_rta_request":
            return self._escalate(run.model_copy(update={"step_count": latest_step_number}), AgentEscalationReason.TOOL_FAILURE, "Unrecoverable pending agent tool invocation.")
        invocation = pending[0]
        try:
            case_id = UUID(str(invocation.arguments["case_id"]))
            context = build_carrier_recovery_workflow(self._session).send_authorised_request(case_id)
        except (CarrierRecoveryConflict, ValueError, KeyError, LookupError):
            return self._escalate(run.model_copy(update={"step_count": latest_step_number}), AgentEscalationReason.TOOL_FAILURE, "Pending RTA dispatch could not be recovered safely.")
        self._repository.complete_invocation(invocation.model_copy(update={
            "status": AgentToolInvocationStatus.SUCCEEDED,
            "result_summary": f"Recovered authorised request sent at {context.sent_at.isoformat()}.",
            "completed_at": utc_now(),
        }))
        step = next(item for item in self._repository.history(run.id).steps if item.id == invocation.step_id)
        recovered = run.model_copy(update={
            "state": AgentRunState.WAITING,
            "wait_kind": AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT,
            "wait_subject_id": str(case_id),
            "step_count": max(run.step_count, step.step_number),
            "updated_at": utc_now(),
        })
        return self._repository.update_run(recovered)

    def _decide_once(self, running: AgentRun, context, tools) -> AgentRun:
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
            if turn.tool_call is None or turn.tool_call.name not in {tool.name for tool in tools}:
                if attempt == 0:
                    continue
                return self._escalate(running, AgentEscalationReason.INVALID_MODEL_OUTPUT, "Agent model selected an unavailable tool.")
            return self._execute_turn(running, turn.tool_call.name, dict(turn.tool_call.arguments))
        raise AssertionError("unreachable")

    def _execute_turn(self, run: AgentRun, tool_name: str, arguments: dict) -> AgentRun:
        step = AgentStep(run_id=run.id, step_number=run.step_count + 1, kind=AgentStepKind.TOOL_CALL, action_summary=f"Invoked {tool_name}.", model_name=run.model_name, prompt_version=run.prompt_version)
        self._repository.add_step(step)
        invocation = self._repository.add_invocation_pending(run.id, step.id, tool_name, arguments)
        try:
            if tool_name in {"prepare_rta_request", "send_authorised_rta_request", "evaluate_carrier_timeout"} and DynamicYardWorkflow.for_session(self._session).latest_unhandled_assessment(run.incident_id) is not None:
                raise ValueError("material dynamic-yard reconsideration must be handled before carrier mutation")
            if tool_name in {"get_incident_context", "get_scarcity_evaluation", "get_carrier_recovery_cases", "get_carrier_recovery_history", "get_cargo_safety_reviews"}:
                updated = run.model_copy(update={"step_count": step.step_number, "updated_at": utc_now()})
                result = "Evidence read."
            elif tool_name == "prepare_rta_request":
                if not DynamicYardWorkflow.for_session(self._session).phase3_compatible(run.incident_id, str(arguments["connection_id"])):
                    raise ValueError("connection is incompatible with current dynamic-yard evidence")
                case = build_carrier_recovery_workflow(self._session).prepare(self._configuration.prepare_command(run.incident_id, str(arguments["connection_id"])))
                updated = run.model_copy(update={"state": AgentRunState.WAITING, "wait_kind": AgentWaitKind.REQUEST_APPROVAL, "wait_subject_id": str(case.id), "step_count": step.step_number, "updated_at": utc_now()})
                result = "Carrier request prepared; operator approval required."
            elif tool_name == "send_authorised_rta_request":
                context = build_carrier_recovery_workflow(self._session).send_authorised_request(UUID(str(arguments["case_id"])))
                updated = run.model_copy(update={"state": AgentRunState.WAITING, "wait_kind": AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT, "wait_subject_id": str(arguments["case_id"]), "step_count": step.step_number, "updated_at": utc_now()})
                result = f"Authorised request sent at {context.sent_at.isoformat()}."
            elif tool_name == "evaluate_carrier_timeout":
                case_id = UUID(str(arguments["case_id"]))
                history = CarrierRecoveryRepository(self._session).history(case_id)
                if history.case.state is not CarrierRecoveryCaseState.AWAITING_CARRIER or history.carrier_responses or history.request_context is None or self._clock.now() < history.request_context.response_deadline:
                    raise CarrierRecoveryConflict("carrier timeout is not currently eligible")
                build_carrier_recovery_workflow(self._session).evaluate_timeout(EvaluateTimeoutCommand(case_id=case_id, effective_at=self._clock.now().isoformat().replace("+00:00", "Z")))
                updated = run.model_copy(update={"step_count": step.step_number, "updated_at": utc_now()})
                result = "Carrier timeout evaluated using trusted clock."
            elif tool_name == "request_cargo_safety_review":
                review = next((item for item in CargoSafetyRepository(self._session).list_reviews(run.incident_id) if item.container_id == str(arguments["container_id"]) and item.state is CargoSafetyReviewState.PENDING_CHECK), None)
                if review is None:
                    raise ValueError("no pending persisted cargo safety review")
                outcome = CargoSafetyWorkflow.for_session(self._session, checker=self._cargo_safety_checker).evaluate(review.id)
                if outcome.policy_result.automation_blocked:
                    complete = invocation.model_copy(update={"status": AgentToolInvocationStatus.SUCCEEDED, "result_summary": "Phase 4 blocked automation.", "completed_at": utc_now()})
                    self._repository.complete_invocation(complete)
                    return self._escalate(run.model_copy(update={"step_count": step.step_number}), AgentEscalationReason.SAFETY_REVIEW_REQUIRED, "Phase 4 cargo safety policy requires human review.")
                updated = run.model_copy(update={"step_count": step.step_number, "updated_at": utc_now()})
                result = "Cargo safety review completed without automation block."
            elif tool_name == "request_expedite_feasibility":
                result = DynamicYardWorkflow.for_session(self._session).apply_latest_assessment(run.incident_id, run.id)
                if hasattr(result, "state") and result.state.value == "OPEN":
                    updated = run.model_copy(update={"state": AgentRunState.WAITING, "wait_kind": AgentWaitKind.HUMAN_TRADEOFF_DECISION, "wait_subject_id": str(result.id), "step_count": step.step_number, "updated_at": utc_now()})
                    result = "Deterministic tradeoff review requires an exact human selection."
                else:
                    updated = run.model_copy(update={"step_count": step.step_number, "updated_at": utc_now()})
                    result = "Deterministic expedite reconsideration applied."
            elif tool_name == "complete_agent_run":
                if self._actionable_work_remains(run):
                    raise ValueError("actionable recovery work remains")
                complete = invocation.model_copy(update={"status": AgentToolInvocationStatus.SUCCEEDED, "result_summary": "Run completed.", "completed_at": utc_now()})
                self._repository.complete_invocation(complete)
                terminal = run.model_copy(update={"state": AgentRunState.COMPLETED, "step_count": step.step_number, "updated_at": utc_now(), "completed_at": utc_now()})
                return self._repository.update_run(terminal)
            elif tool_name == "escalate_agent_run":
                complete = invocation.model_copy(update={"status": AgentToolInvocationStatus.SUCCEEDED, "result_summary": "Run escalated.", "completed_at": utc_now()})
                self._repository.complete_invocation(complete)
                return self._escalate(run.model_copy(update={"step_count": step.step_number}), AgentEscalationReason.UNRESOLVED_TRADEOFF, "Agent requested safe escalation.")
            elif tool_name == "pause_agent_run":
                history = DynamicYardWorkflow.for_session(self._session).history(run.incident_id)
                if not history.revisions or not any(snapshot.stage.value == "PRE_DISCHARGE" for snapshot in history.snapshots) or any(snapshot.stage.value == "DISCHARGE_ACTIVE" for snapshot in history.snapshots):
                    raise ValueError("pause requires pending dynamic-yard discharge evidence")
                updated = run.model_copy(update={"state": AgentRunState.WAITING, "wait_kind": AgentWaitKind.NEW_OPERATIONAL_EVIDENCE, "wait_subject_id": str(run.incident_id), "step_count": step.step_number, "updated_at": utc_now()})
                result = "Waiting for durable discharge-active operational evidence."
            else:
                raise ValueError("tool is unavailable")
            complete = invocation.model_copy(update={"status": AgentToolInvocationStatus.SUCCEEDED, "result_summary": result, "completed_at": utc_now()})
            self._repository.complete_invocation(complete)
            return self._repository.update_run(updated)
        except (CarrierRecoveryConflict, ValueError, KeyError, LookupError) as error:
            complete = invocation.model_copy(update={"status": AgentToolInvocationStatus.REJECTED, "result_summary": "Tool request rejected by durable state.", "error_kind": type(error).__name__, "completed_at": utc_now()})
            self._repository.complete_invocation(complete)
            return self._repository.update_run(run.model_copy(update={"step_count": step.step_number, "updated_at": utc_now()}))

    def _resolve_wait(self, run: AgentRun) -> AgentRun | None:
        if run.wait_kind is AgentWaitKind.NEW_OPERATIONAL_EVIDENCE:
            if DynamicYardWorkflow.for_session(self._session).latest_unhandled_assessment(run.incident_id) is None:
                return None
            return self._repository.update_run(run.model_copy(update={"state": AgentRunState.RUNNING, "wait_kind": None, "wait_subject_id": None, "updated_at": utc_now()}))
        if run.wait_kind is AgentWaitKind.HUMAN_TRADEOFF_DECISION:
            if run.wait_subject_id is None:
                return None
            try:
                workflow = DynamicYardWorkflow.for_session(self._session)
                review = workflow.get_tradeoff_review(UUID(run.wait_subject_id))
                history = workflow.history(review.incident_id)
            except (LookupError, ValueError):
                return None
            selection = next((item for item in history.selections if item.review_id == review.id), None)
            assessment = next((item for item in history.assessments if item.id == review.reconsideration_assessment_id), None)
            selected_revision = next((item for item in history.revisions if item.parent_revision_id == (assessment.prior_allocation_revision_id if assessment else None)), None)
            if review.state.value != "RESOLVED" or selection is None or assessment is None or assessment.handled_at is None or selection.selected_option_id not in review.option_ids or selection.expected_options_fingerprint != review.options_fingerprint or selected_revision is None:
                return None
            return self._repository.update_run(run.model_copy(update={"state": AgentRunState.RUNNING, "wait_kind": None, "wait_subject_id": None, "updated_at": utc_now()}))
        if run.wait_subject_id is None:
            return None
        try:
            history = CarrierRecoveryRepository(self._session).history(UUID(run.wait_subject_id))
        except (LookupError, ValueError):
            return None
        if run.wait_kind is AgentWaitKind.REQUEST_APPROVAL:
            if history.case.state is CarrierRecoveryCaseState.AWAITING_REQUEST_APPROVAL and any(approval.status is ApprovalStatus.APPROVED for approval in history.approvals):
                resumed = run.model_copy(update={"state": AgentRunState.RUNNING, "wait_kind": None, "wait_subject_id": None, "updated_at": utc_now()})
                return self._repository.update_run(resumed)
            return None
        if run.wait_kind is AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT:
            if history.case.state is CarrierRecoveryCaseState.AWAITING_COUNTER_APPROVAL:
                updated = run.model_copy(update={"wait_kind": AgentWaitKind.COUNTER_APPROVAL, "updated_at": utc_now()})
                self._repository.update_run(updated)
                return None
            if (
                history.case.state is CarrierRecoveryCaseState.AWAITING_CARRIER
                and not history.carrier_responses
                and history.request_context is not None
                and self._clock.now() >= history.request_context.response_deadline
            ):
                resumed = run.model_copy(update={"state": AgentRunState.RUNNING, "wait_kind": None, "wait_subject_id": None, "updated_at": utc_now()})
                return self._repository.update_run(resumed)
            if history.case.state in {CarrierRecoveryCaseState.COMPLETED, CarrierRecoveryCaseState.ESCALATED, CarrierRecoveryCaseState.RECOMPUTING}:
                resumed = run.model_copy(update={"state": AgentRunState.RUNNING, "wait_kind": None, "wait_subject_id": None, "updated_at": utc_now()})
                return self._repository.update_run(resumed)
            return None
        if run.wait_kind is AgentWaitKind.COUNTER_APPROVAL:
            if history.case.state in {CarrierRecoveryCaseState.COMPLETED, CarrierRecoveryCaseState.ESCALATED, CarrierRecoveryCaseState.RECOMPUTING}:
                resumed = run.model_copy(update={"state": AgentRunState.RUNNING, "wait_kind": None, "wait_subject_id": None, "updated_at": utc_now()})
                return self._repository.update_run(resumed)
        return None

    def _actionable_work_remains(self, run: AgentRun) -> bool:
        cases = CarrierRecoveryRepository(self._session).list_cases(run.incident_id)
        dynamic = DynamicYardWorkflow.for_session(self._session).history(run.incident_id)
        return any(assessment.handled_at is None for assessment in dynamic.assessments) or any(review.state.value == "OPEN" for review in dynamic.reviews) or any(case.state not in {CarrierRecoveryCaseState.COMPLETED, CarrierRecoveryCaseState.ESCALATED} for case in cases) or any(review.state is CargoSafetyReviewState.PENDING_CHECK for review in CargoSafetyRepository(self._session).list_reviews(run.incident_id))

    def _escalate(self, run: AgentRun, reason: AgentEscalationReason, summary: str) -> AgentRun:
        step = AgentStep(run_id=run.id, step_number=run.step_count + 1, kind=AgentStepKind.ESCALATE, action_summary=summary, model_name=run.model_name, prompt_version=run.prompt_version)
        self._repository.add_step(step)
        terminal = run.model_copy(update={"state": AgentRunState.ESCALATED, "step_count": step.step_number, "escalation_reason": reason, "updated_at": utc_now(), "completed_at": utc_now()})
        return self._repository.update_run(terminal)
