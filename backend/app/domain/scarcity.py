from datetime import timedelta
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, model_validator

from backend.app.domain.models import (
    Connection,
    Container,
    FrozenContract,
    ScheduleEvent,
    utc_now,
)


class CargoKind(StrEnum):
    DRY = "DRY"
    REEFER = "REEFER"
    DG = "DG"


class AllocationStrategy(StrEnum):
    P50_GREEDY = "P50_GREEDY"
    SCENARIO_AWARE = "SCENARIO_AWARE"


class ServiceWindow(FrozenContract):
    service_id: str
    connection: Connection
    planned_time_of_arrival: AwareDatetime
    ready_boundary: AwareDatetime

    @model_validator(mode="after")
    def validate_ready_boundary(self) -> Self:
        if self.ready_boundary != self.planned_time_of_arrival + timedelta(minutes=35):
            raise ValueError("ready_boundary must be PTA plus 35 minutes")
        return self


class ContainerRecoveryProfile(FrozenContract):
    container: Container
    service_id: str
    handling_group_id: str
    cargo_kind: CargoKind
    base_ready_at: AwareDatetime
    expedite_minutes_saved: int = Field(gt=0)
    reefer_continuity_available: bool
    dg_structurally_cleared: bool


class HandlingGroupLimit(FrozenContract):
    handling_group_id: str
    slots: int = Field(ge=0)


class ExpediteCapacityPlan(FrozenContract):
    id: str
    terminal_id: str
    window_start: AwareDatetime
    window_end: AwareDatetime
    overlap_service_ids: tuple[str, ...]
    total_slots: int = Field(ge=0)
    handling_group_limits: tuple[HandlingGroupLimit, ...]
    max_reefer_slots: int = Field(ge=0)
    max_dg_slots: int = Field(ge=0)


class CanonicalIncidentFixture(FrozenContract):
    fixture_id: str
    event: ScheduleEvent
    services: tuple[ServiceWindow, ...]
    profiles: tuple[ContainerRecoveryProfile, ...]
    capacity: ExpediteCapacityPlan


class ScenarioAssumptions(FrozenContract):
    seed: int
    world_count: int = Field(gt=0)
    shared_std_minutes: float = Field(gt=0)
    handling_group_std_minutes: float = Field(gt=0)
    container_noise_std_minutes: float = Field(gt=0)
    antithetic_pairs: bool


class NamedFactor(FrozenContract):
    key: str
    minutes: int


class ScenarioWorld(FrozenContract):
    index: int = Field(ge=0)
    shared_discharge_factor_minutes: int
    handling_group_factors: tuple[NamedFactor, ...]
    container_noise_factors: tuple[NamedFactor, ...]


class ScenarioSet(FrozenContract):
    assumptions: ScenarioAssumptions
    worlds: tuple[ScenarioWorld, ...]


class AllocationPlan(FrozenContract):
    strategy: AllocationStrategy
    allocated_container_ids: tuple[str, ...]


class ServiceOutcome(FrozenContract):
    service_id: str
    preserved_connection_total: int = Field(ge=0)


class StrategyEvaluation(FrozenContract):
    allocation: AllocationPlan
    world_count: int = Field(gt=0)
    preserved_connection_total: int = Field(ge=0)
    expected_preserved_connections: float = Field(ge=0)
    rollover_total: int = Field(ge=0)
    expected_rollovers: float = Field(ge=0)
    p10_preserved_connections: int = Field(ge=0)
    allocation_slot_count: int = Field(ge=0)
    capacity_violations: int = Field(ge=0)
    unsafe_allocations: int = Field(ge=0)
    runtime_ms: float = Field(ge=0)
    service_outcomes: tuple[ServiceOutcome, ...]


class ScarcityEvaluationReport(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    fixture_id: str
    seed: int
    scenario_count: int = Field(gt=0)
    baseline: StrategyEvaluation
    scenario_aware_evaluations: tuple[StrategyEvaluation, ...]
    pareto_evaluations: tuple[StrategyEvaluation, ...]
    selected_allocation: AllocationPlan | None
    reproducibility_key: str = Field(min_length=64, max_length=64)
    created_at: AwareDatetime = Field(default_factory=utc_now)


class EvaluationSeedManifest(FrozenContract):
    manifest_id: str
    fixture_id: str
    worlds_per_seed: int = Field(gt=0)
    seeds: tuple[int, ...]


class HoldoutAllocationComparison(FrozenContract):
    evaluation: StrategyEvaluation
    observed_expected_preserved_delta_vs_baseline: float


class ScarcityBenchmarkReport(FrozenContract):
    fixture_id: str
    development_seed: int
    evaluation_seed_manifest_id: str
    evaluation_seeds: tuple[int, ...]
    worlds_per_seed: int = Field(gt=0)
    baseline: StrategyEvaluation
    scenario_aware: tuple[HoldoutAllocationComparison, ...]
    reproducibility_key: str = Field(min_length=64, max_length=64)
    created_at: AwareDatetime = Field(default_factory=utc_now)
