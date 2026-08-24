from backend.app.domain.dynamic_yard import ExpediteCommitmentStatus
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness


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
