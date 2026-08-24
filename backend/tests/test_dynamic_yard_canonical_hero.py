from backend.app.domain.dynamic_yard import ExpediteCommitmentStatus
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness
from backend.app.storage.agent_runtime import AgentRuntimeRepository  # noqa: F401
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository  # noqa: F401
from backend.app.storage.cargo_safety import CargoSafetyRepository  # noqa: F401


def test_canonical_dynamic_yard_revises_only_one_uncommitted_slot(session) -> None:
    scarcity = build_scarce_capacity_workflow(session).run()
    yard = DynamicYardWorkflow.for_session(session)
    harness = CanonicalDynamicYardHarness()
    yard.initialize(scarcity.incident.id, harness.bootstrap_snapshot(scarcity.incident.id))
    assessment = yard.ingest(harness.discharge_active_snapshot(scarcity.incident.id))

    assert (assessment.preserved_connection_total_before, assessment.preserved_connection_total_after) == (601, 602)
    r1 = yard.apply_latest_assessment(scarcity.incident.id)
    history = yard.history(scarcity.incident.id)
    assert r1.parent_revision_id == history.revisions[0].id
    assert r1.allocated_container_ids == ("SYN-CNT-001", "SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-010", "SYN-CNT-011", "SYN-CNT-012", "SYN-CNT-014", "SYN-CNT-015")
    statuses = {(item.container_id, item.origin_revision_id): item.status for item in history.commitments}
    assert any(container == "SYN-CNT-005" and status is ExpediteCommitmentStatus.CANCELLED for (container, _), status in statuses.items())
    assert any(container == "SYN-CNT-001" and status is ExpediteCommitmentStatus.PLANNED for (container, _), status in statuses.items())


def test_same_run_waits_for_evidence_then_applies_canonical_revision(session) -> None:
    from uuid import UUID
    import pytest
    from backend.app.domain.agent_runtime import AgentEscalationReason, AgentModelTurn, AgentRunState, AgentToolCall, AgentWaitKind
    from backend.app.domain.carrier_recovery import CounterApprovalCommand, RequestApprovalCommand, SimulateCarrierResponseCommand
    from backend.app.domain.cargo_safety import SemanticCheckResult
    from backend.app.domain.enums import ApprovalStatus
    from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
    from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
    from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
    from backend.app.services.agent_model import FakeAgentModel
    from backend.app.services.semantic_safety import FakeSemanticSafetyChecker
    from backend.app.storage.agent_runtime import AgentRuntimeConflict

    scarcity = build_scarce_capacity_workflow(session).run()
    yard = DynamicYardWorkflow.for_session(session); harness = CanonicalDynamicYardHarness()
    yard.initialize(scarcity.incident.id, harness.bootstrap_snapshot(scarcity.incident.id))
    configuration = CanonicalAgentRuntimeConfiguration.load()
    checker = FakeSemanticSafetyChecker(result=SemanticCheckResult.CONTRADICTION_FOUND)
    model = FakeAgentModel([
        AgentModelTurn(tool_call=AgentToolCall(name="pause_agent_run", arguments={})),
        AgentModelTurn(tool_call=AgentToolCall(name="request_expedite_feasibility", arguments={})),
        AgentModelTurn(tool_call=AgentToolCall(name="prepare_rta_request", arguments={"connection_id": "SYN-CONN-JV2"})),
        AgentModelTurn(tool_call=AgentToolCall(name="send_authorised_rta_request", arguments={"case_id": "placeholder"})),
        AgentModelTurn(tool_call=AgentToolCall(name="request_cargo_safety_review", arguments={"container_id": "SYN-CNT-010"})),
    ])
    runtime = AgentRuntimeCoordinator(session=session, model=model, clock=configuration.clock("before_deadline"), configuration=configuration, cargo_safety_checker=checker)
    run = runtime.create_run(scarcity.incident.id)
    waiting = runtime.advance(run.id)
    assert waiting.id == run.id and waiting.wait_kind is AgentWaitKind.NEW_OPERATIONAL_EVIDENCE
    calls = model.calls
    assessment = yard.ingest(harness.discharge_active_snapshot(scarcity.incident.id))
    assert model.calls == calls and runtime.get_run(run.id).id == run.id
    reconsidered = runtime.advance(run.id)
    history = yard.history(scarcity.incident.id)
    assert (assessment.preserved_connection_total_before, assessment.preserved_connection_total_after) == (601, 602)
    assert history.revisions[-1].allocated_container_ids == ("SYN-CNT-001", "SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-010", "SYN-CNT-011", "SYN-CNT-012", "SYN-CNT-014", "SYN-CNT-015")
    assert reconsidered.id == run.id and reconsidered.state is AgentRunState.RUNNING
    statuses = {commitment.container_id: commitment.status for commitment in history.commitments if commitment.status is not ExpediteCommitmentStatus.CANCELLED}
    assert statuses["SYN-CNT-002"] is ExpediteCommitmentStatus.COMMITTED
    assert statuses["SYN-CNT-004"] is ExpediteCommitmentStatus.COMMITTED
    assert any(commitment.container_id == "SYN-CNT-005" and commitment.status is ExpediteCommitmentStatus.CANCELLED for commitment in history.commitments)
    assert statuses["SYN-CNT-001"] is ExpediteCommitmentStatus.PLANNED
    available = runtime._registry.available_tools(session, reconsidered)
    prepare_tool = next(tool for tool in available if tool.name == "prepare_rta_request")
    compatible_connections = prepare_tool.parameters["properties"]["connection_id"]["enum"]
    assert "SYN-CONN-JV2" in compatible_connections
    assert "SYN-CONN-SF1" not in compatible_connections
    prepared = runtime.advance(run.id)
    assert prepared.id == run.id and prepared.wait_kind is AgentWaitKind.REQUEST_APPROVAL
    carrier = build_carrier_recovery_workflow(session); case_id = UUID(prepared.wait_subject_id); case_history = carrier.history(case_id)
    assert case_history.case.affected_container_ids == ("SYN-CNT-017",)
    request_binding = case_history.bindings[0]
    carrier.record_request_approval(RequestApprovalCommand(case_id=case_id, proposal_decision_id=request_binding.proposal_decision_id, request_id=case_history.request.id, expected_payload_fingerprint=request_binding.payload_fingerprint, operator_id="operator", status=ApprovalStatus.APPROVED))
    model._turns[0] = AgentModelTurn(tool_call=AgentToolCall(name="send_authorised_rta_request", arguments={"case_id": str(case_id)}))
    sent = runtime.advance(run.id)
    assert sent.id == run.id and sent.wait_kind is AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT
    carrier.simulate_response(SimulateCarrierResponseCommand(case_id=case_id, effective_at="2026-08-23T05:00:00Z"))
    with pytest.raises(AgentRuntimeConflict): runtime.advance(run.id)
    assert runtime.get_run(run.id).wait_kind is AgentWaitKind.COUNTER_APPROVAL
    counter_history = carrier.history(case_id); counter_binding = next(item for item in counter_history.bindings if item.subject_kind.value == "COUNTER_PROPOSAL")
    carrier.record_counter_approval(CounterApprovalCommand(case_id=case_id, proposal_decision_id=counter_binding.proposal_decision_id, carrier_response_id=counter_history.carrier_responses[0].id, expected_payload_fingerprint=counter_binding.payload_fingerprint, operator_id="operator", status=ApprovalStatus.APPROVED))
    CargoSafetyWorkflow.for_session(session, checker=checker).create_review(scarcity.incident.id, "SYN-CNT-010", "Shipment includes UN 3480 lithium-ion batteries packed separately.", "hero")
    terminal = runtime.advance(run.id)
    assert terminal.id == run.id and terminal.state is AgentRunState.ESCALATED
    assert terminal.escalation_reason is AgentEscalationReason.SAFETY_REVIEW_REQUIRED
    agent_history = runtime._repository.history(run.id)
    assert all(step.run_id == run.id for step in agent_history.steps)
    assert [(invocation.tool_name, invocation.arguments) for invocation in agent_history.tool_invocations] == [
        ("pause_agent_run", {}),
        ("request_expedite_feasibility", {}),
        ("prepare_rta_request", {"connection_id": "SYN-CONN-JV2"}),
        ("send_authorised_rta_request", {"case_id": str(case_id)}),
        ("request_cargo_safety_review", {"container_id": "SYN-CNT-010"}),
    ]
    assert model.calls == 5
    assert checker.calls == 1
