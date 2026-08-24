from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.domain.dynamic_yard import (
    AllocationRevision,
    AllocationTradeoffOption,
    AllocationTradeoffReview,
    ContainerReadyForecast,
    ExpediteCommitment,
    ExpediteCommitmentStatus,
    ExpediteReconsiderationAssessment,
    ForecastStage,
    ReconsiderationDisposition,
    TradeoffReviewState,
    YardForecastSnapshot,
)
from backend.app.storage.dynamic_yard import DynamicYardConflict, DynamicYardRepository


def _snapshot(incident_id, *, source: str = "canonical") -> YardForecastSnapshot:
    return YardForecastSnapshot(
        incident_id=incident_id,
        stage=ForecastStage.PRE_DISCHARGE,
        source=source,
        generated_at=datetime(2026, 8, 22, 5, 0, tzinfo=UTC),
        container_forecasts=(
            ContainerReadyForecast(
                container_id="SYN-CNT-001",
                p10_ready_at=datetime(2026, 8, 22, 5, 0, tzinfo=UTC),
                p50_ready_at=datetime(2026, 8, 22, 5, 15, tzinfo=UTC),
                p90_ready_at=datetime(2026, 8, 22, 5, 30, tzinfo=UTC),
            ),
        ),
    )


def test_snapshot_retry_is_idempotent_and_conflicting_stage_is_rejected(session, incident) -> None:
    repository = DynamicYardRepository(session)
    snapshot = _snapshot(incident.id)

    assert repository.add_snapshot(snapshot) == repository.add_snapshot(snapshot)
    with pytest.raises(DynamicYardConflict, match="contradictory"):
        repository.add_snapshot(snapshot.model_copy(update={"source": "other"}))


def test_commitment_lifecycle_and_histories_are_append_only(session, incident) -> None:
    repository = DynamicYardRepository(session)
    snapshot = repository.add_snapshot(_snapshot(incident.id))
    revision = AllocationRevision(
        incident_id=incident.id,
        source_phase2_evaluation_id=uuid4(),
        source_forecast_snapshot_id=snapshot.id,
        allocated_container_ids=("SYN-CNT-001",),
        preserved_connection_total=1,
        expected_preserved_connections=1.0,
        reason="initial",
    )
    repository.add_revision(revision)
    commitment = repository.add_commitment(
        ExpediteCommitment(
            incident_id=incident.id,
            origin_revision_id=revision.id,
            container_id="SYN-CNT-001",
        )
    )

    committed = repository.transition_commitment(
        commitment.id, ExpediteCommitmentStatus.COMMITTED
    )
    assert committed.status is ExpediteCommitmentStatus.COMMITTED
    with pytest.raises(DynamicYardConflict, match="invalid"):
        repository.transition_commitment(committed.id, ExpediteCommitmentStatus.PLANNED)
    assert repository.active_revision(incident.id) == revision
    assert repository.history(incident.id).revisions == (revision,)


def test_review_selection_rejects_stale_fingerprint(session, incident) -> None:
    repository = DynamicYardRepository(session)
    assessment = ExpediteReconsiderationAssessment(
        incident_id=incident.id,
        source_snapshot_id=uuid4(),
        prior_allocation_revision_id=uuid4(),
        preserved_connection_total_before=1,
        preserved_connection_total_after=2,
        expected_preserved_connections_before=1.0,
        expected_preserved_connections_after=2.0,
        disposition=ReconsiderationDisposition.HUMAN_REVIEW_REQUIRED,
        reason="policy leaves alternatives",
    )
    repository.add_assessment(assessment)
    option = AllocationTradeoffOption(
        review_id=uuid4(),
        allocated_container_ids=("SYN-CNT-001",),
        preserved_connection_total=2,
        expected_preserved_connections=2.0,
    )
    review = AllocationTradeoffReview(
        id=option.review_id,
        incident_id=incident.id,
        reconsideration_assessment_id=assessment.id,
        option_ids=(option.id,),
        options_fingerprint="a" * 64,
        state=TradeoffReviewState.OPEN,
    )
    repository.create_tradeoff_review(review, (option,))

    with pytest.raises(DynamicYardConflict, match="fingerprint"):
        repository.select_tradeoff_option(
            review.id,
            selected_option_id=option.id,
            expected_options_fingerprint="b" * 64,
            operator_id="operator-1",
        )
