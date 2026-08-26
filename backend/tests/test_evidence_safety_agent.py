from __future__ import annotations

from inspect import signature

from backend.app.domain.agent_runtime import (
    AgentEscalationReason,
    AgentModelTurn,
    AgentRunState,
    AgentToolCall,
    AgentToolInvocationStatus,
)
from backend.app.domain.cargo_safety import (
    SemanticCheckFailureKind,
    SemanticCheckResult,
    SemanticSafetyCheckInput,
)
from backend.app.domain.enums import AuditActor
from backend.app.domain.evidence import ClaimStatus
from backend.app.evaluation.evidence_safety_agent import (
    CANONICAL_TOOL_ORDER,
    claims_from_canonical_run,
    exact_counter_approval,
    exact_request_approval,
    run_canonical_evidence_scenario,
)
from backend.app.orchestration.agent_runtime import (
    AgentRuntimeCoordinator,
    CanonicalAgentRuntimeConfiguration,
)
from backend.app.orchestration.carrier_recovery import (
    build_carrier_recovery_workflow,
)
from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
from backend.app.services.agent_model import FakeAgentModel
from backend.app.services.canonical_replay import (
    CANONICAL_REPLAY_MODEL_NAME,
    CANONICAL_SAFETY_CONTAINER_ID,
    CANONICAL_SAFETY_NOTE_SOURCE,
    CANONICAL_SAFETY_NOTE_TEXT,
    CanonicalReplaySemanticChecker,
    SYNTHETIC_DEMO_OPERATOR_ID,
)
from backend.app.services.semantic_safety import FakeSemanticSafetyChecker
from backend.app.storage.agent_runtime import AgentRuntimeRepository
from backend.app.storage.repositories import AuditRepository


EXPECTED_WAITS = (
    "NEW_OPERATIONAL_EVIDENCE",
    "REQUEST_APPROVAL",
    "CARRIER_RESPONSE_OR_TIMEOUT",
    "COUNTER_APPROVAL",
)


def test_canonical_evidence_run_is_credential_free_and_exact(
    session, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_AGENT_MODEL", raising=False)

    result = run_canonical_evidence_scenario(session)

    assert result.agent_run.state is AgentRunState.ESCALATED
    assert (
        result.agent_run.escalation_reason
        is AgentEscalationReason.SAFETY_REVIEW_REQUIRED
    )
    assert result.agent_run.model_name == CANONICAL_REPLAY_MODEL_NAME
    assert result.agent_run.step_count == 6
    assert tuple(
        invocation.tool_name for invocation in result.agent_history.tool_invocations
    ) == CANONICAL_TOOL_ORDER
    assert all(
        invocation.status is AgentToolInvocationStatus.SUCCEEDED
        for invocation in result.agent_history.tool_invocations
    )
    assert result.wait_kinds == EXPECTED_WAITS
    assert result.approval_operator_ids == ("operator-console", "operator-console")
    assert len(result.registry_inventories) == len(CANONICAL_TOOL_ORDER)
    assert all(
        tool_name in inventory
        for tool_name, inventory in zip(
            CANONICAL_TOOL_ORDER, result.registry_inventories, strict=True
        )
    )
    assert result.safety_history.assessment is not None
    assert (
        result.safety_history.assessment.result
        is SemanticCheckResult.CONTRADICTION_FOUND
    )
    assert result.safety_history.policy_result is not None
    assert result.safety_history.policy_result.automation_blocked is True
    assert result.stage_names[0] == "READY_FOR_PRE_DISCHARGE"
    assert result.stage_names[-1] == "SAFETY_BLOCKED"

    persisted = AgentRuntimeRepository(session).history(result.agent_run.id)
    assert persisted == result.agent_history
    serialized = persisted.model_dump(mode="json")
    assert set(serialized) == {"run", "steps", "tool_invocations"}
    assert not ({"prompt", "messages", "reasoning", "chain_of_thought"} & set(serialized))


def test_exact_approval_constructors_copy_durable_bindings_only(
    session, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_canonical_evidence_scenario(session)
    request_binding, counter_binding = result.carrier_history.bindings

    request = exact_request_approval(
        result.carrier_history.case.id,
        request_binding,
        "operator-console",
    )
    counter = exact_counter_approval(
        result.carrier_history.case.id,
        counter_binding,
        "operator-console",
    )

    assert "expected_payload_fingerprint" not in signature(
        exact_request_approval
    ).parameters
    assert "expected_payload_fingerprint" not in signature(
        exact_counter_approval
    ).parameters
    assert request.request_id == request_binding.subject_id
    assert request.proposal_decision_id == request_binding.proposal_decision_id
    assert request.expected_payload_fingerprint == request_binding.payload_fingerprint
    assert counter.carrier_response_id == counter_binding.subject_id
    assert counter.proposal_decision_id == counter_binding.proposal_decision_id
    assert counter.expected_payload_fingerprint == counter_binding.payload_fingerprint


def test_checker_output_is_semantic_evidence_only() -> None:
    output = CanonicalReplaySemanticChecker().check(
        SemanticSafetyCheckInput(
            structured_dangerous_goods=False,
            structured_un_number=None,
            structured_commodity="General cargo",
            note_text=CANONICAL_SAFETY_NOTE_TEXT,
        )
    )

    assert tuple(output.model_dump(mode="json")) == (
        "result",
        "explanation",
        "evidence_excerpt",
    )
    assert not hasattr(output, "disposition")
    assert not hasattr(output, "dangerous_goods")
    assert not hasattr(output, "un_number")


def test_checker_failure_persists_check_failed_and_blocks_automation(
    session,
) -> None:
    phase2 = build_scarce_capacity_workflow(session).run()
    checker = FakeSemanticSafetyChecker(
        result=SemanticCheckResult.NO_CONTRADICTION_FOUND,
        failure_kind=SemanticCheckFailureKind.PROVIDER_ERROR,
    )
    workflow = CargoSafetyWorkflow.for_session(session, checker=checker)
    review = workflow.create_review(
        phase2.incident.id,
        CANONICAL_SAFETY_CONTAINER_ID,
        "Cargo note could not be checked.",
        "failure-probe",
    )

    outcome = workflow.evaluate(review.id)
    history = workflow.history(review.id)

    assert outcome.assessment.result is SemanticCheckResult.CHECK_FAILED
    assert history.assessment is not None
    assert history.assessment.result is SemanticCheckResult.CHECK_FAILED
    assert history.policy_result is not None
    assert history.policy_result.automation_blocked is True


def test_pending_safety_review_outranks_completion_automation(
    session,
) -> None:
    result = run_canonical_evidence_scenario(session)
    final_inventory = result.registry_inventories[-1]

    assert "complete_agent_run" in final_inventory
    assert "request_cargo_safety_review" in final_inventory
    assert result.agent_history.tool_invocations[-1].tool_name == (
        "request_cargo_safety_review"
    )
    assert result.agent_run.state is AgentRunState.ESCALATED


def test_unavailable_model_tool_escalates_without_invocation(session) -> None:
    phase2 = build_scarce_capacity_workflow(session).run()
    turn = AgentModelTurn(
        tool_call=AgentToolCall(name="hold_feeder", arguments={}),
        action_summary="Attempt unavailable authority.",
    )
    configuration = CanonicalAgentRuntimeConfiguration.load()
    runtime = AgentRuntimeCoordinator(
        session=session,
        model=FakeAgentModel((turn, turn)),
        clock=configuration.clock("before_deadline"),
        configuration=configuration,
        cargo_safety_checker=CanonicalReplaySemanticChecker(),
    )
    run = runtime.create_run(phase2.incident.id)

    terminal = runtime.advance(run.id)
    history = AgentRuntimeRepository(session).history(run.id)

    assert terminal.state is AgentRunState.ESCALATED
    assert terminal.escalation_reason is AgentEscalationReason.INVALID_MODEL_OUTPUT
    assert all(item.tool_name != "hold_feeder" for item in history.tool_invocations)


def test_synthetic_operator_probe_is_not_attributed_to_agent(session) -> None:
    phase2 = build_scarce_capacity_workflow(session).run()
    configuration = CanonicalAgentRuntimeConfiguration.load()
    carrier = build_carrier_recovery_workflow(session)
    case = carrier.prepare(
        configuration.prepare_command(phase2.incident.id, "SYN-CONN-JV2")
    )
    binding = carrier.history(case.id).bindings[0]

    carrier.record_request_approval(
        exact_request_approval(case.id, binding, SYNTHETIC_DEMO_OPERATOR_ID)
    )
    history = carrier.history(case.id)
    agent_approval_events = [
        event
        for event in AuditRepository(session).list_for_incident(phase2.incident.id)
        if event.actor is AuditActor.AGENT and "approval" in event.event_type
    ]

    assert tuple(item.operator_id for item in history.approvals) == (
        SYNTHETIC_DEMO_OPERATOR_ID,
    )
    assert agent_approval_events == []


def test_claims_are_derived_from_canonical_histories(session, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_canonical_evidence_scenario(session)
    claims = {claim.claim_id: claim for claim in claims_from_canonical_run(result)}

    assert set(claims) == {
        "safety_canonical_contradiction",
        "safety_automation_blocked",
        "safety_terminal_escalation",
        "safety_checker_scope_limited",
        "safety_policy_owns_disposition",
        "safety_pending_review_blocks_bypass",
        "agent_terminal_state",
        "agent_step_count",
        "agent_successful_tool_order",
        "agent_wait_kinds",
        "agent_approval_identities",
        "agent_no_unavailable_tool_execution",
        "agent_zero_model_credentials",
        "deterministic_tool_call_count",
    }
    assert {claim.status for claim in claims.values()} == {ClaimStatus.VERIFIED}
    assert claims["agent_step_count"].observed_value == 6
    assert claims["deterministic_tool_call_count"].observed_value == 5
    assert claims["agent_successful_tool_order"].observed_value == list(
        CANONICAL_TOOL_ORDER
    )
    assert claims["agent_wait_kinds"].observed_value == list(EXPECTED_WAITS)
    assert claims["agent_approval_identities"].observed_value == [
        "operator-console",
        "operator-console",
    ]
    assert claims["safety_automation_blocked"].observed_value is True
    assert claims["agent_zero_model_credentials"].observed_value is True
    assert all(claim.evidence_refs for claim in claims.values())
