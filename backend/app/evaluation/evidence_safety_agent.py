"""Credential-free safety and agent-orchestration evidence collection."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlmodel import Session

from backend.app.domain.agent_runtime import (
    AgentEscalationReason,
    AgentHistory,
    AgentModelTurn,
    AgentRun,
    AgentRunState,
    AgentToolDefinition,
    AgentToolInvocationStatus,
    AgentTurnContext,
    AgentWaitKind,
    InvalidAgentModelTurn,
)
from backend.app.domain.carrier_recovery import (
    ApprovalBinding,
    AuthorizationSubjectKind,
    CarrierRecoveryHistory,
    CounterApprovalCommand,
    RequestApprovalCommand,
    SimulateCarrierResponseCommand,
)
from backend.app.domain.cargo_safety import (
    SemanticCheckResult,
)
from backend.app.domain.dynamic_yard import AllocationTradeoffHistory
from backend.app.domain.enums import ApprovalStatus
from backend.app.domain.evidence import (
    ClaimReproducibility,
    ClaimStatus,
    EvidenceClaim,
    EvidenceInvariantFailure,
    EvidenceReference,
    assert_verified,
)
from backend.app.domain.models import FrozenContract
from backend.app.orchestration.agent_runtime import (
    AgentRuntimeCoordinator,
    CanonicalAgentRuntimeConfiguration,
)
from backend.app.orchestration.canonical_replay import project_canonical_replay_stage
from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
from backend.app.services.agent_model import AgentModel
from backend.app.services.canonical_replay import (
    CANONICAL_COUNTER_EFFECTIVE_AT,
    CANONICAL_REPLAY_MODEL_NAME,
    CANONICAL_SAFETY_CONTAINER_ID,
    CANONICAL_SAFETY_NOTE_SOURCE,
    CANONICAL_SAFETY_NOTE_TEXT,
    CanonicalReplayAgentModel,
    CanonicalReplaySemanticChecker,
    GUIDED_OPERATOR_ID,
)
from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness
from backend.app.storage.agent_runtime import AgentRuntimeConflict, AgentRuntimeRepository
from backend.app.storage.cargo_safety import CargoSafetyHistory


_FIXTURE_ID = "SYN-CANONICAL-24-V1"

CANONICAL_TOOL_ORDER = (
    "pause_agent_run",
    "request_expedite_feasibility",
    "prepare_rta_request",
    "send_authorised_rta_request",
    "request_cargo_safety_review",
)

CANONICAL_WAIT_ORDER = (
    AgentWaitKind.NEW_OPERATIONAL_EVIDENCE.value,
    AgentWaitKind.REQUEST_APPROVAL.value,
    AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT.value,
    AgentWaitKind.COUNTER_APPROVAL.value,
)

_UNAVAILABLE_AUTHORITY_TOOLS = frozenset(
    {
        "hold_feeder",
        "change_carrier_schedule",
        "override_dg_rule",
        "set_yard_capacity",
    }
)


class CanonicalEvidenceRun(FrozenContract):
    incident_id: UUID
    agent_run: AgentRun
    agent_history: AgentHistory
    dynamic_history: AllocationTradeoffHistory
    carrier_history: CarrierRecoveryHistory
    safety_history: CargoSafetyHistory
    stage_names: tuple[str, ...]
    wait_kinds: tuple[str, ...]
    registry_inventories: tuple[tuple[str, ...], ...]
    approval_operator_ids: tuple[str, ...]


class _InventoryCapturingModel:
    """Record exposed tool names only; never retain turn context or model text."""

    model_name = CANONICAL_REPLAY_MODEL_NAME

    def __init__(self, delegate: AgentModel) -> None:
        self._delegate = delegate
        self.inventories: list[tuple[str, ...]] = []

    def decide(
        self,
        context: AgentTurnContext,
        available_tools: Sequence[AgentToolDefinition],
    ) -> AgentModelTurn | InvalidAgentModelTurn:
        self.inventories.append(tuple(tool.name for tool in available_tools))
        return self._delegate.decide(context, available_tools)


def exact_request_approval(
    case_id: UUID,
    binding: ApprovalBinding,
    operator_id: str,
) -> RequestApprovalCommand:
    """Build request approval from the exact persisted binding."""

    if binding.case_id != case_id:
        raise ValueError("request approval binding belongs to another case")
    if binding.subject_kind is not AuthorizationSubjectKind.OUTBOUND_REQUEST:
        raise ValueError("request approval requires an outbound-request binding")
    return RequestApprovalCommand(
        case_id=case_id,
        proposal_decision_id=binding.proposal_decision_id,
        request_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id=operator_id,
        status=ApprovalStatus.APPROVED,
    )


def exact_counter_approval(
    case_id: UUID,
    binding: ApprovalBinding,
    operator_id: str,
) -> CounterApprovalCommand:
    """Build counter approval from the exact persisted binding."""

    if binding.case_id != case_id:
        raise ValueError("counter approval binding belongs to another case")
    if binding.subject_kind is not AuthorizationSubjectKind.COUNTER_PROPOSAL:
        raise ValueError("counter approval requires a counter-proposal binding")
    return CounterApprovalCommand(
        case_id=case_id,
        proposal_decision_id=binding.proposal_decision_id,
        carrier_response_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id=operator_id,
        status=ApprovalStatus.APPROVED,
    )


def run_canonical_evidence_scenario(session: Session) -> CanonicalEvidenceRun:
    """Drive the public canonical workflows and return their durable histories."""

    stages: list[str] = []
    waits: list[str] = []

    phase2 = build_scarce_capacity_workflow(session).run()
    incident_id = phase2.incident.id

    def capture_stage() -> None:
        stages.append(project_canonical_replay_stage(session, incident_id).stage.value)

    capture_stage()

    yard = DynamicYardWorkflow.for_session(session)
    harness = CanonicalDynamicYardHarness()
    yard.initialize(incident_id, harness.bootstrap_snapshot(incident_id))
    capture_stage()

    configuration = CanonicalAgentRuntimeConfiguration.load()
    model = _InventoryCapturingModel(CanonicalReplayAgentModel())
    runtime = AgentRuntimeCoordinator(
        session=session,
        model=model,
        clock=configuration.clock("before_deadline"),
        configuration=configuration,
        cargo_safety_checker=CanonicalReplaySemanticChecker(),
    )
    run = runtime.create_run(incident_id)
    capture_stage()

    paused = runtime.advance(run.id)
    waits.append(_required_wait(paused, AgentWaitKind.NEW_OPERATIONAL_EVIDENCE))
    capture_stage()

    yard.ingest(harness.discharge_active_snapshot(incident_id))
    capture_stage()

    reconsidered = runtime.advance(run.id)
    assert_verified(
        reconsidered.state is AgentRunState.RUNNING,
        "agent_successful_tool_order",
        "dynamic-yard reconsideration did not return the agent to RUNNING",
    )
    capture_stage()

    prepared = runtime.advance(run.id)
    waits.append(_required_wait(prepared, AgentWaitKind.REQUEST_APPROVAL))
    if prepared.wait_subject_id is None:
        raise EvidenceInvariantFailure(
            "agent_wait_kinds", "request approval wait has no case subject"
        )
    case_id = UUID(prepared.wait_subject_id)
    capture_stage()

    carrier = build_carrier_recovery_workflow(session)
    request_history = carrier.history(case_id)
    request_binding = next(
        binding
        for binding in request_history.bindings
        if binding.subject_kind is AuthorizationSubjectKind.OUTBOUND_REQUEST
    )
    carrier.record_request_approval(
        exact_request_approval(case_id, request_binding, GUIDED_OPERATOR_ID)
    )
    capture_stage()

    sent = runtime.advance(run.id)
    waits.append(_required_wait(sent, AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT))
    capture_stage()

    carrier.simulate_response(
        SimulateCarrierResponseCommand(
            case_id=case_id,
            effective_at=CANONICAL_COUNTER_EFFECTIVE_AT,
        )
    )
    capture_stage()

    try:
        runtime.advance(run.id)
    except AgentRuntimeConflict:
        counter_wait = runtime.get_run(run.id)
    else:
        raise EvidenceInvariantFailure(
            "agent_wait_kinds",
            "COUNTER did not produce the expected wait-upgrade conflict",
        )
    waits.append(_required_wait(counter_wait, AgentWaitKind.COUNTER_APPROVAL))
    capture_stage()

    counter_history = carrier.history(case_id)
    counter_binding = next(
        binding
        for binding in counter_history.bindings
        if binding.subject_kind is AuthorizationSubjectKind.COUNTER_PROPOSAL
    )
    carrier.record_counter_approval(
        exact_counter_approval(case_id, counter_binding, GUIDED_OPERATOR_ID)
    )
    capture_stage()

    safety = CargoSafetyWorkflow.for_session(
        session,
        checker=CanonicalReplaySemanticChecker(),
    )
    review = safety.create_review(
        incident_id,
        CANONICAL_SAFETY_CONTAINER_ID,
        CANONICAL_SAFETY_NOTE_TEXT,
        CANONICAL_SAFETY_NOTE_SOURCE,
    )
    capture_stage()

    terminal = runtime.advance(run.id)
    capture_stage()

    agent_history = AgentRuntimeRepository(session).history(run.id)
    dynamic_history = yard.history(incident_id)
    carrier_history = carrier.history(case_id)
    safety_history = safety.history(review.id)

    result = CanonicalEvidenceRun(
        incident_id=incident_id,
        agent_run=terminal,
        agent_history=agent_history,
        dynamic_history=dynamic_history,
        carrier_history=carrier_history,
        safety_history=safety_history,
        stage_names=tuple(stages),
        wait_kinds=tuple(waits),
        registry_inventories=tuple(model.inventories),
        approval_operator_ids=tuple(
            approval.operator_id for approval in carrier_history.approvals
        ),
    )
    _assert_canonical_result(result)
    return result


def _required_wait(run: AgentRun, expected: AgentWaitKind) -> str:
    assert_verified(
        run.state is AgentRunState.WAITING and run.wait_kind is expected,
        "agent_wait_kinds",
        f"expected {expected.value}, observed {run.state.value}/{run.wait_kind}",
    )
    return expected.value


def _assert_canonical_result(result: CanonicalEvidenceRun) -> None:
    invocations = result.agent_history.tool_invocations
    tool_order = tuple(invocation.tool_name for invocation in invocations)
    assert_verified(
        result.agent_run.state is AgentRunState.ESCALATED
        and result.agent_run.escalation_reason
        is AgentEscalationReason.SAFETY_REVIEW_REQUIRED,
        "agent_terminal_state",
        "canonical run did not terminate ESCALATED / SAFETY_REVIEW_REQUIRED",
    )
    assert_verified(
        result.agent_run.step_count == 6,
        "agent_step_count",
        f"observed {result.agent_run.step_count}",
    )
    assert_verified(
        tool_order == CANONICAL_TOOL_ORDER
        and all(
            invocation.status is AgentToolInvocationStatus.SUCCEEDED
            for invocation in invocations
        ),
        "agent_successful_tool_order",
        f"observed {tool_order}",
    )
    assert_verified(
        result.wait_kinds == CANONICAL_WAIT_ORDER,
        "agent_wait_kinds",
        f"observed {result.wait_kinds}",
    )
    assert_verified(
        result.approval_operator_ids == (GUIDED_OPERATOR_ID, GUIDED_OPERATOR_ID),
        "agent_approval_identities",
        f"observed {result.approval_operator_ids}",
    )
    assert_verified(
        len(result.registry_inventories) == len(CANONICAL_TOOL_ORDER)
        and all(
            selected in inventory
            for selected, inventory in zip(
                CANONICAL_TOOL_ORDER,
                result.registry_inventories,
                strict=True,
            )
        ),
        "agent_successful_tool_order",
        "a selected tool was not present in its captured registry inventory",
    )
    assert_verified(
        all(
            _UNAVAILABLE_AUTHORITY_TOOLS.isdisjoint(inventory)
            for inventory in result.registry_inventories
        )
        and _UNAVAILABLE_AUTHORITY_TOOLS.isdisjoint(tool_order),
        "agent_no_unavailable_tool_execution",
        "an unavailable authority tool was exposed or invoked",
    )
    assessment = result.safety_history.assessment
    policy = result.safety_history.policy_result
    assert_verified(
        assessment is not None
        and assessment.result is SemanticCheckResult.CONTRADICTION_FOUND,
        "safety_canonical_contradiction",
        "canonical safety assessment did not persist CONTRADICTION_FOUND",
    )
    assert_verified(
        policy is not None and policy.automation_blocked is True,
        "safety_automation_blocked",
        "canonical safety policy did not block automation",
    )


def claims_from_canonical_run(
    result: CanonicalEvidenceRun,
) -> tuple[EvidenceClaim, ...]:
    """Map stable observations from canonical durable histories into claims."""

    _assert_canonical_result(result)
    assessment = result.safety_history.assessment
    policy = result.safety_history.policy_result
    if assessment is None or policy is None:
        raise EvidenceInvariantFailure(
            "safety_canonical_contradiction", "canonical safety history is incomplete"
        )

    final_inventory = result.registry_inventories[-1]
    final_tool = result.agent_history.tool_invocations[-1].tool_name
    assert_verified(
        "complete_agent_run" in final_inventory
        and "request_cargo_safety_review" in final_inventory
        and final_tool == "request_cargo_safety_review",
        "safety_pending_review_blocks_bypass",
        "pending safety evidence did not outrank completion automation",
    )

    tool_order = tuple(
        invocation.tool_name for invocation in result.agent_history.tool_invocations
    )
    agent_reference = EvidenceReference(
        record_type="AgentHistory",
        stable_key="canonical-run:agent-history",
        source="AgentRuntimeRepository.history",
        record_id=str(result.agent_run.id),
    )
    safety_reference = EvidenceReference(
        record_type="CargoSafetyHistory",
        stable_key="canonical-run:safety-history",
        source="CargoSafetyRepository.history",
        record_id=str(result.safety_history.review.id),
    )
    carrier_reference = EvidenceReference(
        record_type="CarrierRecoveryHistory",
        stable_key="canonical-run:carrier-history",
        source="CarrierRecoveryRepository.history",
        record_id=str(result.carrier_history.case.id),
    )
    registry_reference = EvidenceReference(
        record_type="AgentToolRegistryInventory",
        stable_key="canonical-run:registry-inventories",
        source="AgentToolRegistry.available_tools",
        record_id=str(result.agent_run.id),
    )
    reproducibility = ClaimReproducibility(
        deterministic=True,
        included_in_fingerprint=True,
        fixture_ids=(_FIXTURE_ID,),
    )
    shared = {
        "status": ClaimStatus.VERIFIED,
        "caveat": "Credential-free deterministic canonical replay only.",
        "reproducibility": reproducibility,
    }

    return (
        EvidenceClaim(
            claim_id="safety_canonical_contradiction",
            statement="Canonical SYN-CNT-010 evidence produces a semantic contradiction.",
            observed_value=assessment.result.value,
            evidence_refs=(safety_reference,),
            **shared,
        ),
        EvidenceClaim(
            claim_id="safety_automation_blocked",
            statement="The deterministic safety policy blocks automation.",
            observed_value=policy.automation_blocked,
            evidence_refs=(safety_reference,),
            **shared,
        ),
        EvidenceClaim(
            claim_id="safety_terminal_escalation",
            statement="The canonical safety block terminates in typed escalation.",
            observed_value={
                "state": result.agent_run.state.value,
                "reason": result.agent_run.escalation_reason.value,
            },
            evidence_refs=(agent_reference, safety_reference),
            **shared,
        ),
        EvidenceClaim(
            claim_id="safety_policy_owns_disposition",
            statement="The policy, separate from checker evidence, owns disposition.",
            observed_value={
                "checker_result": assessment.result.value,
                "policy_disposition": policy.disposition.value,
                "automation_blocked": policy.automation_blocked,
            },
            evidence_refs=(safety_reference,),
            **shared,
        ),
        EvidenceClaim(
            claim_id="safety_pending_review_blocks_bypass",
            statement="Pending safety evidence is evaluated before completion automation.",
            observed_value={
                "completion_exposed": True,
                "selected_tool": final_tool,
                "terminal_reason": result.agent_run.escalation_reason.value,
            },
            evidence_refs=(agent_reference, registry_reference, safety_reference),
            **shared,
        ),
        EvidenceClaim(
            claim_id="agent_terminal_state",
            statement="The canonical agent terminates in the required safe state.",
            observed_value={
                "state": result.agent_run.state.value,
                "reason": result.agent_run.escalation_reason.value,
            },
            evidence_refs=(agent_reference,),
            **shared,
        ),
        EvidenceClaim(
            claim_id="agent_step_count",
            statement="The canonical agent terminates after exactly six steps.",
            observed_value=result.agent_run.step_count,
            evidence_refs=(agent_reference,),
            **shared,
        ),
        EvidenceClaim(
            claim_id="agent_successful_tool_order",
            statement="All five canonical tool calls succeed in the pinned order.",
            observed_value=list(tool_order),
            evidence_refs=(agent_reference, registry_reference),
            **shared,
        ),
        EvidenceClaim(
            claim_id="agent_wait_kinds",
            statement="The canonical agent crosses the four exact durable waits.",
            observed_value=list(result.wait_kinds),
            evidence_refs=(agent_reference,),
            **shared,
        ),
        EvidenceClaim(
            claim_id="agent_approval_identities",
            statement="Both canonical approvals belong to the guided operator.",
            observed_value=list(result.approval_operator_ids),
            evidence_refs=(carrier_reference,),
            **shared,
        ),
        EvidenceClaim(
            claim_id="agent_no_unavailable_tool_execution",
            statement="Unavailable operational-authority tools are neither exposed nor invoked.",
            observed_value={
                "unavailable_tools": sorted(_UNAVAILABLE_AUTHORITY_TOOLS),
                "exposed": [],
                "invoked": [],
            },
            evidence_refs=(agent_reference, registry_reference),
            **shared,
        ),
        EvidenceClaim(
            claim_id="deterministic_tool_call_count",
            statement="The canonical run has exactly five successful tool calls.",
            observed_value=len(result.agent_history.tool_invocations),
            evidence_refs=(agent_reference,),
            **shared,
        ),
    )
