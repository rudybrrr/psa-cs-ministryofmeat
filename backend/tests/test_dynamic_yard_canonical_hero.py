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
    from backend.app.domain.agent_runtime import AgentModelTurn, AgentToolCall, AgentWaitKind
    from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
    from backend.app.services.agent_model import FakeAgentModel

    scarcity = build_scarce_capacity_workflow(session).run()
    yard = DynamicYardWorkflow.for_session(session); harness = CanonicalDynamicYardHarness()
    yard.initialize(scarcity.incident.id, harness.bootstrap_snapshot(scarcity.incident.id))
    configuration = CanonicalAgentRuntimeConfiguration.load()
    model = FakeAgentModel([
        AgentModelTurn(tool_call=AgentToolCall(name="pause_agent_run", arguments={})),
        AgentModelTurn(tool_call=AgentToolCall(name="request_expedite_feasibility", arguments={})),
        AgentModelTurn(tool_call=AgentToolCall(name="escalate_agent_run", arguments={})),
    ])
    runtime = AgentRuntimeCoordinator(session=session, model=model, clock=configuration.clock("before_deadline"), configuration=configuration)
    run = runtime.create_run(scarcity.incident.id)
    waiting = runtime.advance(run.id)
    assert waiting.id == run.id and waiting.wait_kind is AgentWaitKind.NEW_OPERATIONAL_EVIDENCE
    calls = model.calls
    assessment = yard.ingest(harness.discharge_active_snapshot(scarcity.incident.id))
    assert model.calls == calls and runtime.get_run(run.id).id == run.id
    runtime.advance(run.id)
    history = yard.history(scarcity.incident.id)
    assert (assessment.preserved_connection_total_before, assessment.preserved_connection_total_after) == (601, 602)
    assert history.revisions[-1].allocated_container_ids == ("SYN-CNT-001", "SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-010", "SYN-CNT-011", "SYN-CNT-012", "SYN-CNT-014", "SYN-CNT-015")
