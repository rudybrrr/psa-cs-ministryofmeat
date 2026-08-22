from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
from time import perf_counter_ns

from backend.app.domain.scarcity import (
    AllocationPlan,
    CanonicalIncidentFixture,
    EvaluationSeedManifest,
    HoldoutAllocationComparison,
    ScenarioSet,
    ScarcityBenchmarkReport,
    ScarcityEvaluationReport,
    ServiceOutcome,
    StrategyEvaluation,
)
from backend.app.evaluation.scarcity import ScarcityEvaluator
from backend.app.services.scenarios import SeededScenarioGenerator


DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3]
    / "shared"
    / "fixtures"
    / "scarcity-evaluation-seeds.json"
)


def load_evaluation_seed_manifest(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> EvaluationSeedManifest:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = EvaluationSeedManifest.model_validate(data)
    if not manifest.seeds:
        raise ValueError("evaluation seed manifest must contain seeds")
    if len(set(manifest.seeds)) != len(manifest.seeds):
        raise ValueError("evaluation seed manifest seeds must be unique")
    return manifest


@dataclass
class _Aggregate:
    allocation: AllocationPlan
    preserved_connection_total: int = 0
    rollover_total: int = 0
    world_preserved_counts: list[int] = field(default_factory=list)
    service_totals: Counter[str] = field(default_factory=Counter)
    runtime_ms: float = 0.0


def _world_preserved_counts(
    evaluator: ScarcityEvaluator,
    fixture: CanonicalIncidentFixture,
    scenarios: ScenarioSet,
    allocation: AllocationPlan,
) -> list[int]:
    allocated_ids = set(allocation.allocated_container_ids)
    return [
        sum(
            evaluator.preserves_connection(
                fixture,
                profile,
                world,
                expedited=profile.container.id in allocated_ids,
            )
            for profile in fixture.profiles
        )
        for world in scenarios.worlds
    ]


def _aggregate_evaluation(
    evaluator: ScarcityEvaluator,
    fixture: CanonicalIncidentFixture,
    aggregate: _Aggregate,
) -> StrategyEvaluation:
    world_count = len(aggregate.world_preserved_counts)
    p10_index = ceil(0.10 * world_count) - 1
    capacity_violations, unsafe_allocations = evaluator.constraint_diagnostics(
        fixture,
        aggregate.allocation,
    )
    return StrategyEvaluation(
        allocation=aggregate.allocation,
        world_count=world_count,
        preserved_connection_total=aggregate.preserved_connection_total,
        expected_preserved_connections=(
            aggregate.preserved_connection_total / world_count
        ),
        rollover_total=aggregate.rollover_total,
        expected_rollovers=aggregate.rollover_total / world_count,
        p10_preserved_connections=sorted(aggregate.world_preserved_counts)[
            p10_index
        ],
        allocation_slot_count=len(aggregate.allocation.allocated_container_ids),
        capacity_violations=capacity_violations,
        unsafe_allocations=unsafe_allocations,
        runtime_ms=aggregate.runtime_ms,
        service_outcomes=tuple(
            ServiceOutcome(
                service_id=service.service_id,
                preserved_connection_total=aggregate.service_totals[
                    service.service_id
                ],
            )
            for service in fixture.services
        ),
    )


def _benchmark_reproducibility_key(
    fixture: CanonicalIncidentFixture,
    development_report: ScarcityEvaluationReport,
    manifest: EvaluationSeedManifest,
    baseline: StrategyEvaluation,
    scenario_aware: tuple[HoldoutAllocationComparison, ...],
) -> str:
    payload = {
        "fixture_id": fixture.fixture_id,
        "development_seed": development_report.seed,
        "manifest": manifest.model_dump(mode="json"),
        "baseline": baseline.model_dump(mode="json", exclude={"runtime_ms"}),
        "scenario_aware": [
            comparison.model_dump(
                mode="json",
                exclude={"evaluation": {"runtime_ms"}},
            )
            for comparison in scenario_aware
        ],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class HoldoutBenchmarkService:
    def __init__(
        self,
        *,
        scenario_generator: SeededScenarioGenerator | None = None,
        evaluator: ScarcityEvaluator | None = None,
    ) -> None:
        self._scenario_generator = scenario_generator or SeededScenarioGenerator()
        self._evaluator = evaluator or ScarcityEvaluator()

    def evaluate(
        self,
        fixture: CanonicalIncidentFixture,
        development_report: ScarcityEvaluationReport,
        manifest: EvaluationSeedManifest,
    ) -> ScarcityBenchmarkReport:
        if (
            fixture.fixture_id != development_report.fixture_id
            or fixture.fixture_id != manifest.fixture_id
        ):
            raise ValueError("fixture identifiers must match")
        if not manifest.seeds:
            raise ValueError("benchmark requires at least one evaluation seed")
        if len(set(manifest.seeds)) != len(manifest.seeds):
            raise ValueError("benchmark evaluation seeds must be unique")

        fixed_plans = (
            development_report.baseline.allocation,
            *(
                evaluation.allocation
                for evaluation in development_report.pareto_evaluations
            ),
        )
        known_ids = {profile.container.id for profile in fixture.profiles}
        if any(
            container_id not in known_ids
            for plan in fixed_plans
            for container_id in plan.allocated_container_ids
        ):
            raise ValueError("fixed allocation contains an unknown container")

        aggregates = [_Aggregate(allocation=plan) for plan in fixed_plans]
        for seed in manifest.seeds:
            scenarios = self._scenario_generator.generate(
                fixture,
                seed=seed,
                world_count=manifest.worlds_per_seed,
            )
            for aggregate in aggregates:
                started = perf_counter_ns()
                evaluation = self._evaluator.evaluate(
                    fixture,
                    scenarios,
                    aggregate.allocation,
                    runtime_ms=0,
                )
                aggregate.runtime_ms += (
                    perf_counter_ns() - started
                ) / 1_000_000
                aggregate.preserved_connection_total += (
                    evaluation.preserved_connection_total
                )
                aggregate.rollover_total += evaluation.rollover_total
                aggregate.world_preserved_counts.extend(
                    _world_preserved_counts(
                        self._evaluator,
                        fixture,
                        scenarios,
                        aggregate.allocation,
                    )
                )
                aggregate.service_totals.update(
                    {
                        outcome.service_id: outcome.preserved_connection_total
                        for outcome in evaluation.service_outcomes
                    }
                )

        baseline = _aggregate_evaluation(
            self._evaluator,
            fixture,
            aggregates[0],
        )
        scenario_aware = tuple(
            HoldoutAllocationComparison(
                evaluation=evaluation,
                observed_expected_preserved_delta_vs_baseline=(
                    evaluation.expected_preserved_connections
                    - baseline.expected_preserved_connections
                ),
            )
            for evaluation in (
                _aggregate_evaluation(self._evaluator, fixture, aggregate)
                for aggregate in aggregates[1:]
            )
        )
        return ScarcityBenchmarkReport(
            fixture_id=fixture.fixture_id,
            development_seed=development_report.seed,
            evaluation_seed_manifest_id=manifest.manifest_id,
            evaluation_seeds=manifest.seeds,
            worlds_per_seed=manifest.worlds_per_seed,
            baseline=baseline,
            scenario_aware=scenario_aware,
            reproducibility_key=_benchmark_reproducibility_key(
                fixture,
                development_report,
                manifest,
                baseline,
                scenario_aware,
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the frozen synthetic scarcity holdout benchmark",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from uuid import UUID

    from backend.app.evaluation.scarcity import ScarcityComparisonService
    from backend.app.services.canonical_incident import (
        SyntheticCanonicalIncidentService,
    )

    fixture = SyntheticCanonicalIncidentService().load()
    development_scenarios = SeededScenarioGenerator().generate(
        fixture,
        seed=20260822,
        world_count=50,
    )
    development_report = ScarcityComparisonService().compare(
        incident_id=UUID("00000000-0000-4000-8000-000000000000"),
        fixture=fixture,
        scenarios=development_scenarios,
    )
    report = HoldoutBenchmarkService().evaluate(
        fixture,
        development_report,
        load_evaluation_seed_manifest(),
    )
    args.output.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "baseline": report.baseline.model_dump(mode="json"),
                "scenario_aware": [
                    comparison.model_dump(mode="json")
                    for comparison in report.scenario_aware
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
