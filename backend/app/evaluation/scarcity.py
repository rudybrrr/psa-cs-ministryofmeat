import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from math import ceil
from statistics import median
from time import perf_counter_ns
from uuid import UUID

from backend.app.domain.scarcity import (
    AllocationPlan,
    CanonicalIncidentFixture,
    CargoKind,
    ContainerRecoveryProfile,
    NamedFactor,
    ScenarioSet,
    ScenarioWorld,
    ScarcityEvaluationReport,
    ServiceOutcome,
    StrategyEvaluation,
)


def _factor_minutes(factors: tuple[NamedFactor, ...], key: str) -> int:
    try:
        return next(factor.minutes for factor in factors if factor.key == key)
    except StopIteration as error:
        raise ValueError(f"missing scenario factor for {key}") from error


def _is_structurally_eligible(profile: ContainerRecoveryProfile) -> bool:
    reefer_is_safe = (
        profile.cargo_kind is not CargoKind.REEFER
        or profile.reefer_continuity_available
    )
    dg_is_safe = (
        profile.cargo_kind is not CargoKind.DG
        or profile.dg_structurally_cleared
    )
    return reefer_is_safe and dg_is_safe


class ScarcityEvaluator:
    def ready_at(
        self,
        profile: ContainerRecoveryProfile,
        world: ScenarioWorld,
        *,
        expedited: bool,
    ) -> datetime:
        factor_minutes = (
            world.shared_discharge_factor_minutes
            + _factor_minutes(
                world.handling_group_factors,
                profile.handling_group_id,
            )
            + _factor_minutes(
                world.container_noise_factors,
                profile.container.id,
            )
        )
        ready_at = profile.base_ready_at - timedelta(minutes=factor_minutes)
        if expedited:
            ready_at -= timedelta(minutes=profile.expedite_minutes_saved)
        return ready_at

    def preserves_connection(
        self,
        fixture: CanonicalIncidentFixture,
        profile: ContainerRecoveryProfile,
        world: ScenarioWorld,
        *,
        expedited: bool,
    ) -> bool:
        if not _is_structurally_eligible(profile):
            return False
        service = next(
            item for item in fixture.services if item.service_id == profile.service_id
        )
        return self.ready_at(profile, world, expedited=expedited) <= (
            service.ready_boundary
        )

    def p50_beneficiary_ids(
        self,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
    ) -> tuple[str, ...]:
        boundaries = {
            service.service_id: service.ready_boundary.timestamp()
            for service in fixture.services
        }
        beneficiaries: list[str] = []
        for profile in sorted(
            fixture.profiles,
            key=lambda item: item.container.id,
        ):
            if not _is_structurally_eligible(profile):
                continue
            normal_p50 = median(
                self.ready_at(profile, world, expedited=False).timestamp()
                for world in scenarios.worlds
            )
            expedited_p50 = median(
                self.ready_at(profile, world, expedited=True).timestamp()
                for world in scenarios.worlds
            )
            boundary = boundaries[profile.service_id]
            if normal_p50 > boundary and expedited_p50 <= boundary:
                beneficiaries.append(profile.container.id)
        return tuple(beneficiaries)

    def incremental_preservation_count(
        self,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
        container_id: str,
    ) -> int:
        profile = next(
            item
            for item in fixture.profiles
            if item.container.id == container_id
        )
        expedited_successes = sum(
            self.preserves_connection(
                fixture,
                profile,
                world,
                expedited=True,
            )
            for world in scenarios.worlds
        )
        normal_successes = sum(
            self.preserves_connection(
                fixture,
                profile,
                world,
                expedited=False,
            )
            for world in scenarios.worlds
        )
        return expedited_successes - normal_successes

    def stochastic_candidate_ids(
        self,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
    ) -> tuple[str, ...]:
        return tuple(
            profile.container.id
            for profile in sorted(
                fixture.profiles,
                key=lambda item: item.container.id,
            )
            if _is_structurally_eligible(profile)
            and self.incremental_preservation_count(
                fixture,
                scenarios,
                profile.container.id,
            )
            > 0
        )

    def constraint_diagnostics(
        self,
        fixture: CanonicalIncidentFixture,
        allocation: AllocationPlan,
    ) -> tuple[int, int]:
        profiles = {
            profile.container.id: profile for profile in fixture.profiles
        }
        allocated_profiles = [
            profiles[container_id]
            for container_id in allocation.allocated_container_ids
            if container_id in profiles
        ]
        capacity = fixture.capacity
        group_counts = Counter(
            profile.handling_group_id for profile in allocated_profiles
        )
        capacity_violations = int(
            len(allocation.allocated_container_ids) > capacity.total_slots
        )
        capacity_violations += sum(
            group_counts[limit.handling_group_id] > limit.slots
            for limit in capacity.handling_group_limits
        )
        capacity_violations += int(
            sum(
                profile.cargo_kind is CargoKind.REEFER
                for profile in allocated_profiles
            )
            > capacity.max_reefer_slots
        )
        capacity_violations += int(
            sum(
                profile.cargo_kind is CargoKind.DG for profile in allocated_profiles
            )
            > capacity.max_dg_slots
        )
        unsafe_allocations = sum(
            not _is_structurally_eligible(profile)
            for profile in allocated_profiles
        ) + sum(
            container_id not in profiles
            for container_id in allocation.allocated_container_ids
        )
        return capacity_violations, unsafe_allocations

    def evaluate(
        self,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
        allocation: AllocationPlan,
        *,
        runtime_ms: float,
    ) -> StrategyEvaluation:
        allocated_ids = set(allocation.allocated_container_ids)
        world_preserved_counts: list[int] = []
        service_totals = {
            service.service_id: 0 for service in fixture.services
        }

        for world in scenarios.worlds:
            world_preserved = 0
            for profile in fixture.profiles:
                preserved = self.preserves_connection(
                    fixture,
                    profile,
                    world,
                    expedited=profile.container.id in allocated_ids,
                )
                if preserved:
                    world_preserved += 1
                    service_totals[profile.service_id] += 1
            world_preserved_counts.append(world_preserved)

        world_count = len(scenarios.worlds)
        preserved_total = sum(world_preserved_counts)
        rollover_total = len(fixture.profiles) * world_count - preserved_total
        p10_index = ceil(0.10 * world_count) - 1
        capacity_violations, unsafe_allocations = self.constraint_diagnostics(
            fixture,
            allocation,
        )
        return StrategyEvaluation(
            allocation=allocation,
            world_count=world_count,
            preserved_connection_total=preserved_total,
            expected_preserved_connections=preserved_total / world_count,
            rollover_total=rollover_total,
            expected_rollovers=rollover_total / world_count,
            p10_preserved_connections=sorted(world_preserved_counts)[p10_index],
            allocation_slot_count=len(allocation.allocated_container_ids),
            capacity_violations=capacity_violations,
            unsafe_allocations=unsafe_allocations,
            runtime_ms=runtime_ms,
            service_outcomes=tuple(
                ServiceOutcome(
                    service_id=service.service_id,
                    preserved_connection_total=service_totals[service.service_id],
                )
                for service in fixture.services
            ),
        )


def semantic_reproducibility_key(
    fixture: CanonicalIncidentFixture,
    scenarios: ScenarioSet,
    evaluation: StrategyEvaluation,
) -> str:
    boundaries = {
        service.service_id: service.ready_boundary
        for service in fixture.services
    }
    payload = {
        "fixture": {
            "fixture_id": fixture.fixture_id,
            "profiles": [
                {
                    "container_id": profile.container.id,
                    "service_id": profile.service_id,
                    "handling_group_id": profile.handling_group_id,
                    "cargo_kind": profile.cargo_kind.value,
                    "base_ready_offset_minutes": int(
                        (
                            profile.base_ready_at
                            - boundaries[profile.service_id]
                        ).total_seconds()
                        // 60
                    ),
                    "expedite_minutes_saved": profile.expedite_minutes_saved,
                    "reefer_continuity_available": (
                        profile.reefer_continuity_available
                    ),
                    "dg_structurally_cleared": profile.dg_structurally_cleared,
                }
                for profile in fixture.profiles
            ],
            "capacity": {
                "id": fixture.capacity.id,
                "terminal_id": fixture.capacity.terminal_id,
                "overlap_service_ids": fixture.capacity.overlap_service_ids,
                "total_slots": fixture.capacity.total_slots,
                "handling_group_limits": [
                    limit.model_dump(mode="json")
                    for limit in fixture.capacity.handling_group_limits
                ],
                "max_reefer_slots": fixture.capacity.max_reefer_slots,
                "max_dg_slots": fixture.capacity.max_dg_slots,
            },
        },
        "scenarios": scenarios.model_dump(mode="json"),
        "evaluation": evaluation.model_dump(
            mode="json",
            exclude={"runtime_ms"},
        ),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def comparison_reproducibility_key(
    fixture: CanonicalIncidentFixture,
    scenarios: ScenarioSet,
    baseline: StrategyEvaluation,
    scenario_aware_evaluations: tuple[StrategyEvaluation, ...],
    pareto_evaluations: tuple[StrategyEvaluation, ...],
    selected_allocation: AllocationPlan | None,
) -> str:
    payload = {
        "fixture_id": fixture.fixture_id,
        "scenario_assumptions": scenarios.assumptions.model_dump(mode="json"),
        "baseline": semantic_reproducibility_key(
            fixture,
            scenarios,
            baseline,
        ),
        "scenario_aware": [
            semantic_reproducibility_key(fixture, scenarios, evaluation)
            for evaluation in scenario_aware_evaluations
        ],
        "pareto_allocations": [
            evaluation.allocation.model_dump(mode="json")
            for evaluation in pareto_evaluations
        ],
        "selected_allocation": (
            selected_allocation.model_dump(mode="json")
            if selected_allocation is not None
            else None
        ),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ScarcityComparisonService:
    def compare(
        self,
        *,
        incident_id: UUID,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
    ) -> ScarcityEvaluationReport:
        from backend.app.optimization.scarcity import ScenarioAwareAllocator
        from backend.app.policies.allocation_dominance import (
            AllocationDominancePolicy,
            pareto_front,
        )
        from backend.app.policies.baseline import P50GreedyAllocator

        evaluator = ScarcityEvaluator()

        baseline_started = perf_counter_ns()
        baseline_plan = P50GreedyAllocator().allocate(fixture, scenarios)
        baseline_runtime_ms = (perf_counter_ns() - baseline_started) / 1_000_000
        baseline = evaluator.evaluate(
            fixture,
            scenarios,
            baseline_plan,
            runtime_ms=baseline_runtime_ms,
        )

        optimizer_started = perf_counter_ns()
        scenario_plans = ScenarioAwareAllocator().solve(fixture, scenarios)
        optimizer_runtime_ms = (perf_counter_ns() - optimizer_started) / 1_000_000
        scenario_aware_evaluations = tuple(
            evaluator.evaluate(
                fixture,
                scenarios,
                plan,
                runtime_ms=optimizer_runtime_ms,
            )
            for plan in scenario_plans
        )
        pareto_evaluations = pareto_front(scenario_aware_evaluations)
        selected_allocation = AllocationDominancePolicy().select(
            pareto_evaluations
        )
        reproducibility_key = comparison_reproducibility_key(
            fixture,
            scenarios,
            baseline,
            scenario_aware_evaluations,
            pareto_evaluations,
            selected_allocation,
        )
        return ScarcityEvaluationReport(
            incident_id=incident_id,
            fixture_id=fixture.fixture_id,
            seed=scenarios.assumptions.seed,
            scenario_count=len(scenarios.worlds),
            baseline=baseline,
            scenario_aware_evaluations=scenario_aware_evaluations,
            pareto_evaluations=pareto_evaluations,
            selected_allocation=selected_allocation,
            reproducibility_key=reproducibility_key,
        )
