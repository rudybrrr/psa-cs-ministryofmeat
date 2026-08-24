from datetime import timedelta

from backend.app.domain.dynamic_yard import ContainerReadyForecast, ForecastStage, YardForecastSnapshot
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow


def _snapshot(incident_id, fixture, stage):
    return YardForecastSnapshot(
        incident_id=incident_id, stage=stage, source="test",
        container_forecasts=tuple(ContainerReadyForecast(
            container_id=profile.container.id,
            p10_ready_at=profile.base_ready_at - timedelta(minutes=30),
            p50_ready_at=profile.base_ready_at,
            p90_ready_at=profile.base_ready_at + timedelta(minutes=30),
        ) for profile in fixture.profiles),
    )


def test_initialize_creates_immutable_r0_and_commits_only_canonical_locks(session, canonical_fixture) -> None:
    scarcity = build_scarce_capacity_workflow(session).run()
    workflow = DynamicYardWorkflow.for_session(session)

    history = workflow.initialize(
        scarcity.incident.id, _snapshot(scarcity.incident.id, canonical_fixture, ForecastStage.PRE_DISCHARGE)
    )

    assert history.revisions[0].allocated_container_ids == scarcity.report.selected_allocation.allocated_container_ids
    statuses = {item.container_id: item.status.value for item in history.commitments}
    assert statuses["SYN-CNT-002"] == "COMMITTED"
    assert statuses["SYN-CNT-004"] == "COMMITTED"
