from __future__ import annotations

from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, model_validator

from backend.app.domain.models import FrozenContract, utc_now


class ForecastStage(StrEnum):
    PRE_DISCHARGE = "PRE_DISCHARGE"
    DISCHARGE_ACTIVE = "DISCHARGE_ACTIVE"


class ExpediteCommitmentStatus(StrEnum):
    PLANNED = "PLANNED"
    COMMITTED = "COMMITTED"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"


class ReconsiderationDisposition(StrEnum):
    NO_CHANGE = "NO_CHANGE"
    AUTO_SUPERSEDE = "AUTO_SUPERSEDE"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class TradeoffReviewState(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


def _require_explicit_utc(value: AwareDatetime, field_name: str) -> None:
    if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field_name} must use an explicit UTC offset")


class ContainerReadyForecast(FrozenContract):
    container_id: str = Field(min_length=1)
    p10_ready_at: AwareDatetime
    p50_ready_at: AwareDatetime
    p90_ready_at: AwareDatetime

    @model_validator(mode="after")
    def validate_quantiles(self) -> Self:
        _require_explicit_utc(self.p10_ready_at, "p10_ready_at")
        _require_explicit_utc(self.p50_ready_at, "p50_ready_at")
        _require_explicit_utc(self.p90_ready_at, "p90_ready_at")
        if not self.p10_ready_at <= self.p50_ready_at <= self.p90_ready_at:
            raise ValueError("forecast quantiles must satisfy p10 <= p50 <= p90")
        return self


class YardForecastSnapshot(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    stage: ForecastStage
    generated_at: AwareDatetime = Field(default_factory=utc_now)
    source: str = Field(min_length=1, max_length=200)
    container_forecasts: tuple[ContainerReadyForecast, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        _require_explicit_utc(self.generated_at, "generated_at")
        container_ids = tuple(row.container_id for row in self.container_forecasts)
        if len(container_ids) != len(set(container_ids)):
            raise ValueError("snapshot contains duplicate container forecasts")
        return self


class AllocationRevision(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    source_phase2_evaluation_id: UUID
    source_forecast_snapshot_id: UUID
    parent_revision_id: UUID | None = None
    allocated_container_ids: tuple[str, ...] = Field(min_length=1)
    locked_container_ids: tuple[str, ...] = ()
    preserved_connection_total: int = Field(ge=0)
    expected_preserved_connections: float = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)
    created_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_membership(self) -> Self:
        if len(self.allocated_container_ids) != len(set(self.allocated_container_ids)):
            raise ValueError("revision contains duplicate allocated containers")
        if len(self.locked_container_ids) != len(set(self.locked_container_ids)):
            raise ValueError("revision contains duplicate locked containers")
        if not set(self.locked_container_ids).issubset(self.allocated_container_ids):
            raise ValueError("locked containers must remain allocated")
        _require_explicit_utc(self.created_at, "created_at")
        return self


class ExpediteCommitment(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    origin_revision_id: UUID
    container_id: str = Field(min_length=1)
    status: ExpediteCommitmentStatus = ExpediteCommitmentStatus.PLANNED
    created_at: AwareDatetime = Field(default_factory=utc_now)
    updated_at: AwareDatetime = Field(default_factory=utc_now)


def allowed_commitment_transition(
    current: ExpediteCommitmentStatus, target: ExpediteCommitmentStatus
) -> bool:
    return (current, target) in {
        (ExpediteCommitmentStatus.PLANNED, ExpediteCommitmentStatus.COMMITTED),
        (ExpediteCommitmentStatus.PLANNED, ExpediteCommitmentStatus.CANCELLED),
        (ExpediteCommitmentStatus.COMMITTED, ExpediteCommitmentStatus.EXECUTED),
    }


class ReconsiderationCandidate(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    allocated_container_ids: tuple[str, ...] = Field(min_length=1)
    preserved_connection_total: int = Field(ge=0)
    expected_preserved_connections: float = Field(ge=0)


class ExpediteReconsiderationAssessment(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    source_snapshot_id: UUID
    prior_allocation_revision_id: UUID
    locked_container_ids: tuple[str, ...] = ()
    candidate_options: tuple[ReconsiderationCandidate, ...] = ()
    preserved_connection_total_before: int = Field(ge=0)
    preserved_connection_total_after: int = Field(ge=0)
    expected_preserved_connections_before: float = Field(ge=0)
    expected_preserved_connections_after: float = Field(ge=0)
    disposition: ReconsiderationDisposition
    reason: str = Field(min_length=1, max_length=1000)
    handled_at: AwareDatetime | None = None
    created_at: AwareDatetime = Field(default_factory=utc_now)


class AllocationTradeoffReview(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    reconsideration_assessment_id: UUID
    option_ids: tuple[UUID, ...] = Field(min_length=1)
    options_fingerprint: str = Field(min_length=64, max_length=64)
    state: TradeoffReviewState = TradeoffReviewState.OPEN
    created_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_option_ids(self) -> Self:
        if len(self.option_ids) != len(set(self.option_ids)):
            raise ValueError("tradeoff review option IDs must be unique")
        return self


class AllocationTradeoffOption(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    review_id: UUID
    allocated_container_ids: tuple[str, ...] = Field(min_length=1)
    preserved_connection_total: int = Field(ge=0)
    expected_preserved_connections: float = Field(ge=0)


class AllocationTradeoffSelection(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    review_id: UUID
    selected_option_id: UUID
    expected_options_fingerprint: str = Field(min_length=64, max_length=64)
    operator_id: str = Field(min_length=1, max_length=200)
    created_at: AwareDatetime = Field(default_factory=utc_now)


class AllocationTradeoffHistory(FrozenContract):
    snapshots: tuple[YardForecastSnapshot, ...] = ()
    revisions: tuple[AllocationRevision, ...] = ()
    commitments: tuple[ExpediteCommitment, ...] = ()
    assessments: tuple[ExpediteReconsiderationAssessment, ...] = ()
    reviews: tuple[AllocationTradeoffReview, ...] = ()
    options: tuple[AllocationTradeoffOption, ...] = ()
    selections: tuple[AllocationTradeoffSelection, ...] = ()
