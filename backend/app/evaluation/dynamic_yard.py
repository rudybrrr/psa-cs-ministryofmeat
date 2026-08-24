from __future__ import annotations

from datetime import datetime, timedelta
from math import sqrt
from time import perf_counter_ns

from backend.app.domain.dynamic_yard import ContainerReadyForecast, YardForecastSnapshot
from backend.app.domain.scarcity import (
    AllocationPlan,
    CanonicalIncidentFixture,
    ContainerRecoveryProfile,
    ScenarioSet,
    ScenarioWorld,
    ScarcityEvaluationReport,
    StrategyEvaluation,
)
from backend.app.evaluation.scarcity import ScarcityEvaluator, _factor_minutes, _is_structurally_eligible
from backend.app.services.scenarios import SeededScenarioGenerator
from backend.app.evaluation.scarcity import comparison_reproducibility_key


LATENT_STD_MINUTES = sqrt(12**2 + 7**2 + 2**2)
Z90 = 1.2815515655


def reconstruct_phase2_worlds(
    report: ScarcityEvaluationReport, fixture: CanonicalIncidentFixture
) -> ScenarioSet:
    if report.fixture_id != fixture.fixture_id:
        raise ValueError("Phase 2 report fixture does not match dynamic-yard fixture")
    scenarios = SeededScenarioGenerator().generate(
        fixture, seed=report.seed, world_count=report.scenario_count
    )
    if scenarios.assumptions.seed != report.seed or len(scenarios.worlds) != report.scenario_count:
        raise ValueError("Phase 2 scenario reconstruction mismatch")
    if comparison_reproducibility_key(fixture, scenarios, report.baseline, report.scenario_aware_evaluations, report.pareto_evaluations, report.selected_allocation) != report.reproducibility_key:
        raise ValueError("Phase 2 scenario reconstruction reproducibility mismatch")
    return scenarios


def combined_factor_minutes(profile: ContainerRecoveryProfile, world: ScenarioWorld) -> int:
    return (
        world.shared_discharge_factor_minutes
        + _factor_minutes(world.handling_group_factors, profile.handling_group_id)
        + _factor_minutes(world.container_noise_factors, profile.container.id)
    )


def projected_ready_at(
    profile: ContainerRecoveryProfile,
    world: ScenarioWorld,
    forecast: ContainerReadyForecast,
) -> datetime:
    if forecast.container_id != profile.container.id:
        raise ValueError("forecast must belong to the projected container")
    z = combined_factor_minutes(profile, world) / LATENT_STD_MINUTES
    if z >= 0:
        return forecast.p50_ready_at - (z / Z90) * (forecast.p50_ready_at - forecast.p10_ready_at)
    return forecast.p50_ready_at + (-z / Z90) * (forecast.p90_ready_at - forecast.p50_ready_at)


class DynamicYardEvaluator:
    combined_factor_minutes = staticmethod(combined_factor_minutes)

    def evaluate_allocation(
        self,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
        snapshot: YardForecastSnapshot,
        allocation: AllocationPlan,
    ) -> StrategyEvaluation:
        forecasts = {row.container_id: row for row in snapshot.container_forecasts}
        profile_ids = {profile.container.id for profile in fixture.profiles}
        if set(forecasts) != profile_ids:
            raise ValueError("snapshot must forecast every fixture container exactly once")
        started = perf_counter_ns()
        allocated = set(allocation.allocated_container_ids)
        world_totals: list[int] = []
        service_totals = {service.service_id: 0 for service in fixture.services}
        boundaries = {service.service_id: service.ready_boundary for service in fixture.services}
        for world in scenarios.worlds:
            preserved = 0
            for profile in fixture.profiles:
                normal_ready = projected_ready_at(profile, world, forecasts[profile.container.id])
                ready = normal_ready - timedelta(minutes=profile.expedite_minutes_saved) if profile.container.id in allocated else normal_ready
                if _is_structurally_eligible(profile) and ready <= boundaries[profile.service_id]:
                    preserved += 1
                    service_totals[profile.service_id] += 1
            world_totals.append(preserved)
        total = sum(world_totals)
        capacity_violations, unsafe_allocations = ScarcityEvaluator().constraint_diagnostics(fixture, allocation)
        from math import ceil
        from backend.app.domain.scarcity import ServiceOutcome
        world_count = len(scenarios.worlds)
        return StrategyEvaluation(
            allocation=allocation, world_count=world_count, preserved_connection_total=total,
            expected_preserved_connections=total / world_count,
            rollover_total=len(fixture.profiles) * world_count - total,
            expected_rollovers=(len(fixture.profiles) * world_count - total) / world_count,
            p10_preserved_connections=sorted(world_totals)[ceil(.10 * world_count) - 1],
            allocation_slot_count=len(allocation.allocated_container_ids),
            capacity_violations=capacity_violations, unsafe_allocations=unsafe_allocations,
            runtime_ms=(perf_counter_ns() - started) / 1_000_000,
            service_outcomes=tuple(ServiceOutcome(service_id=service.service_id, preserved_connection_total=service_totals[service.service_id]) for service in fixture.services),
        )


def connection_is_phase3_compatible(
    fixture: CanonicalIncidentFixture,
    scenarios: ScenarioSet,
    snapshot: YardForecastSnapshot,
    active_allocation: AllocationPlan,
    frozen_allocation: AllocationPlan,
    connection_id: str,
) -> bool:
    forecasts = {row.container_id: row for row in snapshot.container_forecasts}
    frozen = ScarcityEvaluator()
    active_ids, frozen_ids = set(active_allocation.allocated_container_ids), set(frozen_allocation.allocated_container_ids)
    profiles = [profile for profile in fixture.profiles if profile.container.onward_connection.id == connection_id]
    if not profiles:
        return False
    for profile in profiles:
        container_id = profile.container.id
        if (container_id in active_ids) != (container_id in frozen_ids):
            return False
        forecast = forecasts.get(container_id)
        if forecast is None:
            return False
        for world in scenarios.worlds:
            if projected_ready_at(profile, world, forecast) != frozen.ready_at(profile, world, expedited=False):
                return False
    return True
