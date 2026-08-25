"""Read-only canonical replay projector (Phase 7).

Derives the canonical replay stage exclusively from persisted durable state.
Writes nothing: no tables are mutated and no audit events are recorded.
"""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session

from backend.app.domain.agent_runtime import (
    AgentRun,
    AgentRunState,
    AgentToolInvocationStatus,
    AgentWaitKind,
)
from backend.app.domain.canonical_replay import (
    CanonicalReplayActionType,
    CanonicalReplayStage,
    CanonicalReplayStageView,
    CanonicalReplayStatus,
    canonical_progress_label,
    canonical_stage_ordinal,
)
from backend.app.domain.carrier_recovery import (
    AuthorizationSubjectKind,
    CarrierRecoveryCaseState,
)
from backend.app.domain.cargo_safety import CargoSafetyReviewState, SemanticCheckResult
from backend.app.domain.dynamic_yard import ForecastStage, TradeoffReviewState
from backend.app.domain.enums import ApprovalStatus
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.services.canonical_replay import (
    CANONICAL_JV2_CONNECTION_ID,
    CANONICAL_SAFETY_CONTAINER_ID,
)
from backend.app.storage.agent_runtime import AgentRuntimeRepository
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository
from backend.app.storage.cargo_safety import CargoSafetyRepository
from backend.app.storage.repositories import (
    IncidentRepository,
    ScarcityEvaluationRepository,
)

_DEVIATION_ORDINAL_BY_INVOCATION = {
    "pause_agent_run": 4,
    "request_expedite_feasibility": 6,
    "prepare_rta_request": 7,
    "send_authorised_rta_request": 9,
    "request_cargo_safety_review": 14,
}


class _Evidence:
    def __init__(self, session: Session, incident_id: UUID) -> None:
        IncidentRepository(session).get(incident_id)
        try:
            ScarcityEvaluationRepository(session).get_for_incident(incident_id)
            self.scarcity_present = True
        except LookupError:
            self.scarcity_present = False
        dynamic = DynamicYardWorkflow.for_session(session).history(incident_id)
        self.snapshots = dynamic.snapshots
        self.revisions = dynamic.revisions
        self.assessments = dynamic.assessments
        self.reviews = dynamic.reviews
        runs = AgentRuntimeRepository(session).list_runs(incident_id)
        self.run = runs[-1] if runs else None
        self.last_invocation_tool: str | None = None
        if self.run is not None:
            history = AgentRuntimeRepository(session).history(self.run.id)
            completed = [item for item in history.tool_invocations if item.status is not AgentToolInvocationStatus.PENDING]
            self.last_invocation_tool = completed[-1].tool_name if completed else None
        case = next(
            (item for item in CarrierRecoveryRepository(session).list_cases(incident_id) if item.connection_id == CANONICAL_JV2_CONNECTION_ID),
            None,
        )
        self.case = case
        self.case_history = CarrierRecoveryRepository(session).history(case.id) if case is not None else None
        review = next(
            (item for item in CargoSafetyRepository(session).list_reviews(incident_id) if item.container_id == CANONICAL_SAFETY_CONTAINER_ID),
            None,
        )
        self.safety_history = CargoSafetyRepository(session).history(review.id) if review is not None else None

    @property
    def has_active_snapshot(self) -> bool:
        return any(snapshot.stage is ForecastStage.DISCHARGE_ACTIVE for snapshot in self.snapshots)

    @property
    def has_any_snapshot(self) -> bool:
        return bool(self.snapshots)

    @property
    def unhandled_assessment(self):
        return next((assessment for assessment in self.assessments if assessment.handled_at is None), None)

    @property
    def open_tradeoff_review(self):
        return next((review for review in self.reviews if review.state is TradeoffReviewState.OPEN), None)


def project_canonical_replay_stage(session: Session, incident_id: UUID) -> CanonicalReplayStageView:
    evidence = _Evidence(session, incident_id)
    run = evidence.run

    if run is None:
        return _project_without_run(evidence)
    if run.state is AgentRunState.ESCALATED:
        return _project_escalated(evidence, run)
    if run.state is AgentRunState.FAILED:
        return _view(
            CanonicalReplayStage.FAILED,
            CanonicalReplayStatus.TERMINAL_HALTED,
            f"AgentRun {run.id} failed; inspect run history for the failure evidence.",
            CanonicalReplayActionType.NONE,
        )
    if run.state is AgentRunState.COMPLETED:
        return _view(
            CanonicalReplayStage.COMPLETE,
            CanonicalReplayStatus.TERMINAL_SUCCESS,
            f"AgentRun {run.id} completed with all actionable recovery work resolved.",
            CanonicalReplayActionType.NONE,
        )
    if run.wait_kind is AgentWaitKind.HUMAN_TRADEOFF_DECISION:
        return _view(
            CanonicalReplayStage.TRADEOFF_DECISION_REQUIRED,
            CanonicalReplayStatus.WAITING_HUMAN,
            "A deterministic tradeoff review requires an exact human selection before the agent may continue.",
            CanonicalReplayActionType.SELECT_TRADEOFF_OPTION,
            auto=False,
            human=True,
            ordinal=6,
        )
    if run.wait_kind is AgentWaitKind.NEW_OPERATIONAL_EVIDENCE:
        if evidence.unhandled_assessment is None:
            return _view(
                CanonicalReplayStage.WAITING_FOR_ACTIVE_EVIDENCE,
                CanonicalReplayStatus.WAITING_EXTERNAL,
                "The agent paused for discharge-active operational evidence; publish DISCHARGE_ACTIVE to continue.",
                CanonicalReplayActionType.PUBLISH_DISCHARGE_ACTIVE,
            )
        return _view(
            CanonicalReplayStage.WAITING_FOR_ACTIVE_EVIDENCE,
            CanonicalReplayStatus.PENDING_ACTION,
            "Fresh discharge-active evidence created a deterministic reconsideration; advance the agent to apply it.",
            CanonicalReplayActionType.ADVANCE_AGENT,
        )
    if run.wait_kind is AgentWaitKind.REQUEST_APPROVAL:
        return _project_request_approval(evidence, run)
    if run.wait_kind is AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT:
        return _project_carrier_response(evidence, run)
    if run.wait_kind is AgentWaitKind.COUNTER_APPROVAL:
        return _project_counter_approval(evidence, run)
    return _project_running(evidence, run)


def _project_without_run(evidence: _Evidence) -> CanonicalReplayStageView:
    if evidence.has_active_snapshot:
        return _deviation_view(
            "EVIDENCE_PUBLISHED_BEFORE_AGENT_START",
            3,
            "Discharge-active evidence was published before any agent run started; start a new canonical replay.",
        )
    if evidence.has_any_snapshot:
        return _view(
            CanonicalReplayStage.READY_TO_START_AGENT,
            CanonicalReplayStatus.PENDING_ACTION,
            "PRE_DISCHARGE evidence is bootstrapped; start the canonical demo AgentRun.",
            CanonicalReplayActionType.START_DEMO_AGENT_RUN,
        )
    if evidence.scarcity_present:
        return _view(
            CanonicalReplayStage.READY_FOR_PRE_DISCHARGE,
            CanonicalReplayStatus.PENDING_ACTION,
            "Canonical incident and scarcity evaluation exist; bootstrap PRE_DISCHARGE yard evidence.",
            CanonicalReplayActionType.BOOTSTRAP_PRE_DISCHARGE,
        )
    return _deviation_view(
        "UNEXPECTED_PERSISTED_STATE",
        16,
        "Incident exists without persisted scarcity evaluation; expected canonical synthetic state is missing.",
    )


def _project_escalated(evidence: _Evidence, run: AgentRun) -> CanonicalReplayStageView:
    safety = evidence.safety_history
    complete_safety_block = (
        run.escalation_reason is not None
        and run.escalation_reason.value == "SAFETY_REVIEW_REQUIRED"
        and safety is not None
        and safety.policy_result is not None
        and safety.policy_result.automation_blocked is True
        and safety.assessment is not None
        and safety.assessment.result is SemanticCheckResult.CONTRADICTION_FOUND
    )
    if complete_safety_block:
        return _view(
            CanonicalReplayStage.SAFETY_BLOCKED,
            CanonicalReplayStatus.TERMINAL_SUCCESS,
            "Cargo-safety contradiction blocked automation; the run ended ESCALATED / SAFETY_REVIEW_REQUIRED for human DG review.",
            CanonicalReplayActionType.NONE,
        )
    reason_value = run.escalation_reason.value if run.escalation_reason is not None else "UNKNOWN"
    ordinal = _DEVIATION_ORDINAL_BY_INVOCATION.get(evidence.last_invocation_tool) if evidence.last_invocation_tool else None
    if ordinal is None:
        ordinal = 16 if evidence.last_invocation_tool else 3
    return _deviation_view(
        f"AGENT_ESCALATION_{reason_value}",
        ordinal,
        f"AgentRun escalated with reason {reason_value}; this departure is terminal for the canonical hero path.",
    )


def _project_request_approval(evidence: _Evidence, run: AgentRun) -> CanonicalReplayStageView:
    history = evidence.case_history
    if history is None:
        return _unexpected_state(run, "request approval wait references a missing JV2 carrier case")
    approval = _latest_approval(history, AuthorizationSubjectKind.OUTBOUND_REQUEST)
    if approval is not None and approval.status is ApprovalStatus.REJECTED:
        return _deviation_view("REQUEST_REJECTED", 8, "The outbound request was rejected by operator decision; Phase 3 semantics escalated the case.")
    if approval is not None and approval.status is ApprovalStatus.APPROVED:
        return _view(
            CanonicalReplayStage.REQUEST_APPROVED_READY_TO_SEND,
            CanonicalReplayStatus.PENDING_ACTION,
            "Request authorization approved; advance the agent to send the authorised RTA request.",
            CanonicalReplayActionType.ADVANCE_AGENT,
        )
    return _view(
        CanonicalReplayStage.REQUEST_APPROVAL_REQUIRED,
        CanonicalReplayStatus.WAITING_HUMAN,
        "The prepared JV2 request needs exact fingerprint-bound operator approval before dispatch.",
        CanonicalReplayActionType.APPROVE_REQUEST,
        human=True,
    )


def _project_carrier_response(evidence: _Evidence, run: AgentRun) -> CanonicalReplayStageView:
    history = evidence.case_history
    if history is None:
        return _unexpected_state(run, "carrier response wait references a missing JV2 carrier case")
    if history.case.state is CarrierRecoveryCaseState.AWAITING_COUNTER_APPROVAL and any(response.response.value == "COUNTER" for response in history.carrier_responses):
        return _view(
            CanonicalReplayStage.CARRIER_COUNTER_RECEIVED,
            CanonicalReplayStatus.PENDING_ACTION,
            "Carrier returned a counter proposal; one advance deliberately answers the known 409 wait upgrade before counter approval.",
            CanonicalReplayActionType.ADVANCE_AGENT,
        )
    if history.case.state is CarrierRecoveryCaseState.AWAITING_CARRIER and not history.carrier_responses:
        return _view(
            CanonicalReplayStage.WAITING_FOR_CARRIER,
            CanonicalReplayStatus.WAITING_EXTERNAL,
            "Authorised RTA request sent; awaiting the synthetic carrier response inside the trusted deadline window.",
            CanonicalReplayActionType.SIMULATE_CARRIER_RESPONSE,
        )
    return _deviation_view(
        "NON_HERO_CARRIER_OUTCOME",
        10,
        f"Carrier case reached non-hero outcome {history.case.state.value}; legacy panels still support it but replay halts here.",
    )


def _project_counter_approval(evidence: _Evidence, run: AgentRun) -> CanonicalReplayStageView:
    history = evidence.case_history
    if history is None:
        return _unexpected_state(run, "counter approval wait references a missing JV2 carrier case")
    approval = _latest_approval(history, AuthorizationSubjectKind.COUNTER_PROPOSAL)
    if approval is not None and approval.status is ApprovalStatus.REJECTED:
        return _deviation_view("COUNTER_REJECTED", 12, "The carrier counter proposal was rejected by operator decision; Phase 3 semantics escalated the case.")
    if approval is not None and approval.status is ApprovalStatus.APPROVED and history.case.state in {CarrierRecoveryCaseState.RECOMPUTING, CarrierRecoveryCaseState.COMPLETED, CarrierRecoveryCaseState.ESCALATED}:
        review_pending = evidence.safety_history is not None and evidence.safety_history.review.state is CargoSafetyReviewState.PENDING_CHECK
        if review_pending:
            return _view(
                CanonicalReplayStage.COUNTER_APPROVED_READY_TO_RESUME,
                CanonicalReplayStatus.PENDING_ACTION,
                "Counter approved and recomputation finished; the resuming advance will resolve the wait and evaluate the persisted SYN-CNT-010 evidence together.",
                CanonicalReplayActionType.ADVANCE_AGENT,
            )
        return _view(
            CanonicalReplayStage.COUNTER_APPROVED_READY_TO_RESUME,
            CanonicalReplayStatus.PENDING_ACTION,
            "Counter approved and recomputation finished; persist the canonical SYN-CNT-010 contradiction evidence before resuming the agent.",
            CanonicalReplayActionType.PERSIST_SAFETY_REVIEW,
        )
    return _view(
        CanonicalReplayStage.COUNTER_APPROVAL_REQUIRED,
        CanonicalReplayStatus.WAITING_HUMAN,
        "The carrier counter proposal needs exact fingerprint-bound operator approval before recomputation.",
        CanonicalReplayActionType.APPROVE_COUNTER,
        human=True,
    )


def _project_running(evidence: _Evidence, run: AgentRun) -> CanonicalReplayStageView:
    if evidence.unhandled_assessment is not None:
        return _view(
            CanonicalReplayStage.READY_TO_RECONSIDER,
            CanonicalReplayStatus.PENDING_ACTION,
            "Unhandled reconsideration assessment exists; advance the agent to apply the deterministic expedite decision.",
            CanonicalReplayActionType.ADVANCE_AGENT,
        )
    if evidence.open_tradeoff_review is not None:
        return _view(
            CanonicalReplayStage.TRADEOFF_DECISION_REQUIRED,
            CanonicalReplayStatus.WAITING_HUMAN,
            "An open allocation tradeoff review requires an exact human selection.",
            CanonicalReplayActionType.SELECT_TRADEOFF_OPTION,
            auto=False,
            human=True,
            ordinal=6,
        )
    if run.step_count == 0:
        return _view(
            CanonicalReplayStage.READY_TO_ADVANCE_TO_EVIDENCE_WAIT,
            CanonicalReplayStatus.PENDING_ACTION,
            "Demo AgentRun created; first advance pauses at the durable NEW_OPERATIONAL_EVIDENCE boundary.",
            CanonicalReplayActionType.ADVANCE_AGENT,
        )
    if evidence.case is None:
        return _view(
            CanonicalReplayStage.READY_TO_PREPARE_RTA,
            CanonicalReplayStatus.PENDING_ACTION,
            "Dynamic-yard evidence is settled; advance the agent to prepare the trusted JV2 recovery request.",
            CanonicalReplayActionType.ADVANCE_AGENT,
        )
    if evidence.case.state in {CarrierRecoveryCaseState.COMPLETED, CarrierRecoveryCaseState.ESCALATED} and evidence.safety_history is None:
        return _view(
            CanonicalReplayStage.READY_FOR_SAFETY_EVIDENCE,
            CanonicalReplayStatus.PENDING_ACTION,
            "JV2 recovery finished without safety evidence; persist the canonical SYN-CNT-010 contradiction review.",
            CanonicalReplayActionType.PERSIST_SAFETY_REVIEW,
        )
    if evidence.safety_history is not None and evidence.safety_history.review.state is CargoSafetyReviewState.PENDING_CHECK:
        return _view(
            CanonicalReplayStage.SAFETY_REVIEW_PENDING,
            CanonicalReplayStatus.PENDING_ACTION,
            "Persisted cargo-safety review awaits evaluation; advance the agent so its own tool performs the check.",
            CanonicalReplayActionType.ADVANCE_AGENT,
        )
    return _unexpected_state(run, f"run state {run.state.value} does not match any canonical hero position")


def _latest_approval(history, subject_kind: AuthorizationSubjectKind):
    bindings = [binding for binding in history.bindings if binding.subject_kind is subject_kind]
    for binding in bindings:
        approval = next((item for item in history.approvals if item.decision_id == binding.proposal_decision_id), None)
        if approval is not None:
            return approval
    return None


def _unexpected_state(run: AgentRun, detail: str) -> CanonicalReplayStageView:
    return _deviation_view("UNEXPECTED_PERSISTED_STATE", 16, f"{detail} (state={run.state.value}, step_count={run.step_count}).")


def _deviation_view(reason: str, ordinal: int, explanation: str) -> CanonicalReplayStageView:
    return CanonicalReplayStageView(
        stage=CanonicalReplayStage.OFF_CANONICAL_PATH,
        ordinal=ordinal,
        progress_label=canonical_progress_label(ordinal),
        status=CanonicalReplayStatus.TERMINAL_HALTED,
        explanation=explanation,
        next_allowed_action=CanonicalReplayActionType.NONE,
        guided_can_execute=False,
        auto_replay_may_execute=False,
        requires_human_authority=False,
        deviation_reason=reason,
    )


def _view(
    stage: CanonicalReplayStage,
    status: CanonicalReplayStatus,
    explanation: str,
    action: CanonicalReplayActionType,
    *,
    auto: bool | None = None,
    human: bool = False,
    ordinal: int | None = None,
) -> CanonicalReplayStageView:
    resolved_ordinal = ordinal if ordinal is not None else canonical_stage_ordinal(stage)
    return CanonicalReplayStageView(
        stage=stage,
        ordinal=resolved_ordinal,
        progress_label=canonical_progress_label(resolved_ordinal),
        status=status,
        explanation=explanation,
        next_allowed_action=action,
        guided_can_execute=action is not CanonicalReplayActionType.NONE,
        auto_replay_may_execute=(action is not CanonicalReplayActionType.NONE and action is not CanonicalReplayActionType.SELECT_TRADEOFF_OPTION) if auto is None else auto,
        requires_human_authority=human,
        deviation_reason=None,
    )
