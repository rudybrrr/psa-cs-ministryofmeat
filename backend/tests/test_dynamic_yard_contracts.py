from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.domain.dynamic_yard import (
    AllocationTradeoffOption,
    AllocationTradeoffReview,
    AllocationTradeoffSelection,
    ContainerReadyForecast,
    ExpediteCommitmentStatus,
    ForecastStage,
    TradeoffReviewState,
    allowed_commitment_transition,
)


def test_forecast_requires_utc_ordered_quantiles() -> None:
    with pytest.raises(ValidationError):
        ContainerReadyForecast(
            container_id="SYN-CNT-001",
            p10_ready_at="2026-08-22T05:40:00Z",
            p50_ready_at="2026-08-22T05:39:00Z",
            p90_ready_at="2026-08-22T05:41:00Z",
        )

    with pytest.raises(ValidationError):
        ContainerReadyForecast(
            container_id="SYN-CNT-001",
            p10_ready_at="2026-08-22T05:40:00+08:00",
            p50_ready_at="2026-08-22T05:41:00+08:00",
            p90_ready_at="2026-08-22T05:42:00+08:00",
        )


def test_commitment_lifecycle_has_no_reverse_or_skip_transition() -> None:
    assert allowed_commitment_transition(
        ExpediteCommitmentStatus.PLANNED, ExpediteCommitmentStatus.COMMITTED
    )
    assert allowed_commitment_transition(
        ExpediteCommitmentStatus.PLANNED, ExpediteCommitmentStatus.CANCELLED
    )
    assert allowed_commitment_transition(
        ExpediteCommitmentStatus.COMMITTED, ExpediteCommitmentStatus.EXECUTED
    )
    assert not allowed_commitment_transition(
        ExpediteCommitmentStatus.COMMITTED, ExpediteCommitmentStatus.PLANNED
    )
    assert not allowed_commitment_transition(
        ExpediteCommitmentStatus.EXECUTED, ExpediteCommitmentStatus.CANCELLED
    )


def test_tradeoff_options_and_selection_are_frozen_exact_records() -> None:
    review = AllocationTradeoffReview(
        incident_id=uuid4(),
        reconsideration_assessment_id=uuid4(),
        option_ids=(uuid4(),),
        options_fingerprint="a" * 64,
        state=TradeoffReviewState.OPEN,
    )
    option = AllocationTradeoffOption(
        review_id=review.id,
        allocated_container_ids=("SYN-CNT-001",),
        preserved_connection_total=602,
        expected_preserved_connections=12.04,
    )
    selection = AllocationTradeoffSelection(
        review_id=review.id,
        selected_option_id=option.id,
        expected_options_fingerprint=review.options_fingerprint,
        operator_id="operator-1",
    )

    assert review.state is TradeoffReviewState.OPEN
    assert selection.selected_option_id == option.id
    with pytest.raises(ValidationError):
        review.option_ids += (uuid4(),)


def test_snapshot_stage_values_are_canonical() -> None:
    assert ForecastStage.PRE_DISCHARGE.value == "PRE_DISCHARGE"
    assert datetime.now(UTC).utcoffset() == UTC.utcoffset(None)
