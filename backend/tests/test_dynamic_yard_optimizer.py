from datetime import timedelta
from uuid import uuid4

from backend.app.domain.dynamic_yard import (
    AllocationRevision,
    ContainerReadyForecast,
    ForecastStage,
    ReconsiderationDisposition,
    YardForecastSnapshot,
)
from backend.app.domain.scarcity import AllocationPlan, AllocationStrategy
from backend.app.optimization.dynamic_yard import assess_reconsideration


def test_locked_assessment_never_moves_locked_slots(canonical_fixture, canonical_scenarios) -> None:
    forecasts = tuple(
        ContainerReadyForecast(
            container_id=profile.container.id,
            p10_ready_at=profile.base_ready_at - timedelta(minutes=30),
            p50_ready_at=profile.base_ready_at,
            p90_ready_at=profile.base_ready_at + timedelta(minutes=30),
        )
        for profile in canonical_fixture.profiles
    )
    snapshot = YardForecastSnapshot(
        incident_id=uuid4(), stage=ForecastStage.DISCHARGE_ACTIVE,
        source="test", container_forecasts=forecasts,
    )
    current = AllocationRevision(
        incident_id=snapshot.incident_id, source_phase2_evaluation_id=uuid4(),
        source_forecast_snapshot_id=snapshot.id,
        allocated_container_ids=("SYN-CNT-002", "SYN-CNT-004"),
        locked_container_ids=("SYN-CNT-002", "SYN-CNT-004"),
        preserved_connection_total=0, expected_preserved_connections=0,
        reason="frozen",
    )

    assessment = assess_reconsideration(
        snapshot.incident_id, snapshot, current, canonical_fixture, canonical_scenarios,
        ("SYN-CNT-002", "SYN-CNT-004"),
    )

    assert assessment.disposition in set(ReconsiderationDisposition)
    assert all(set(current.locked_container_ids) <= set(option.allocated_container_ids) for option in assessment.candidate_options)
