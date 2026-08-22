from __future__ import annotations

from collections import defaultdict
from uuid import UUID

import pytest

from backend.app.domain.scarcity import (
    AllocationPlan,
    CanonicalIncidentFixture,
    EvaluationSeedManifest,
    ScenarioSet,
    ScarcityEvaluationReport,
)
from backend.app.evaluation.benchmark import (
    HoldoutBenchmarkService,
    load_evaluation_seed_manifest,
)
from backend.app.evaluation.scarcity import (
    ScarcityComparisonService,
    ScarcityEvaluator,
)
from backend.app.services.scenarios import SeededScenarioGenerator


DEBUG_MANIFEST = EvaluationSeedManifest(
    manifest_id="SYN-DEBUG-HOLDOUT",
    fixture_id="SYN-CANONICAL-24-V1",
    worlds_per_seed=10,
    seeds=(314159, 271828, 161803),
)


@pytest.fixture
def canonical_development_report(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> ScarcityEvaluationReport:
    return ScarcityComparisonService().compare(
        incident_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        fixture=canonical_fixture,
        scenarios=canonical_scenarios,
    )


@pytest.fixture
def holdout_debug_report(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_development_report: ScarcityEvaluationReport,
):
    return HoldoutBenchmarkService().evaluate(
        canonical_fixture,
        canonical_development_report,
        DEBUG_MANIFEST,
    )


def test_frozen_evaluation_seed_manifest_is_separate_and_well_formed() -> None:
    manifest = load_evaluation_seed_manifest()

    assert manifest.manifest_id == "SYN-CANONICAL-24-HOLDOUT-V1"
    assert manifest.fixture_id == "SYN-CANONICAL-24-V1"
    assert manifest.worlds_per_seed == 50
    assert len(manifest.seeds) == 50
    assert len(set(manifest.seeds)) == 50
    assert set(manifest.seeds).isdisjoint({20260822, 20260823, 20260824})


def test_holdout_benchmark_is_reproducible_for_fixed_debug_seeds(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_development_report: ScarcityEvaluationReport,
) -> None:
    service = HoldoutBenchmarkService()

    first = service.evaluate(
        canonical_fixture,
        canonical_development_report,
        DEBUG_MANIFEST,
    )
    second = service.evaluate(
        canonical_fixture,
        canonical_development_report,
        DEBUG_MANIFEST,
    )

    assert first.reproducibility_key == second.reproducibility_key
    assert first.baseline.model_copy(update={"runtime_ms": 0}) == (
        second.baseline.model_copy(update={"runtime_ms": 0})
    )
    assert tuple(
        item.evaluation.model_copy(update={"runtime_ms": 0})
        for item in first.scenario_aware
    ) == tuple(
        item.evaluation.model_copy(update={"runtime_ms": 0})
        for item in second.scenario_aware
    )
    assert tuple(
        item.evaluation.allocation for item in first.scenario_aware
    ) == tuple(
        item.allocation
        for item in canonical_development_report.pareto_evaluations
    )


def test_holdout_benchmark_reports_valid_calculations_without_sign_assertion(
    holdout_debug_report,
) -> None:
    total_worlds = 3 * 10
    baseline = holdout_debug_report.baseline

    assert baseline.world_count == total_worlds
    assert baseline.preserved_connection_total + baseline.rollover_total == (
        24 * total_worlds
    )
    assert baseline.expected_preserved_connections == pytest.approx(
        baseline.preserved_connection_total / total_worlds
    )
    assert baseline.expected_rollovers == pytest.approx(
        baseline.rollover_total / total_worlds
    )
    assert baseline.capacity_violations == 0
    assert baseline.unsafe_allocations == 0
    for comparison in holdout_debug_report.scenario_aware:
        evaluation = comparison.evaluation
        assert evaluation.world_count == total_worlds
        assert evaluation.expected_preserved_connections == pytest.approx(
            evaluation.preserved_connection_total / total_worlds
        )
        assert evaluation.capacity_violations == 0
        assert evaluation.unsafe_allocations == 0
        assert comparison.observed_expected_preserved_delta_vs_baseline == (
            pytest.approx(
                evaluation.expected_preserved_connections
                - baseline.expected_preserved_connections
            )
        )


class RecordingGenerator(SeededScenarioGenerator):
    def __init__(self) -> None:
        self.generated: dict[int, ScenarioSet] = {}

    def generate(
        self,
        fixture: CanonicalIncidentFixture,
        *,
        seed: int = 20260822,
        world_count: int = 50,
    ) -> ScenarioSet:
        assert seed not in self.generated
        scenarios = super().generate(
            fixture,
            seed=seed,
            world_count=world_count,
        )
        self.generated[seed] = scenarios
        return scenarios


class RecordingEvaluator(ScarcityEvaluator):
    def __init__(self) -> None:
        self.scenario_ids_by_seed: dict[int, list[int]] = defaultdict(list)
        self.allocations: list[AllocationPlan] = []

    def evaluate(
        self,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
        allocation: AllocationPlan,
        *,
        runtime_ms: float,
    ):
        self.scenario_ids_by_seed[scenarios.assumptions.seed].append(
            id(scenarios)
        )
        self.allocations.append(allocation)
        return super().evaluate(
            fixture,
            scenarios,
            allocation,
            runtime_ms=runtime_ms,
        )


def test_each_debug_seed_is_generated_once_and_shared_by_every_fixed_plan(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_development_report: ScarcityEvaluationReport,
) -> None:
    generator = RecordingGenerator()
    evaluator = RecordingEvaluator()
    service = HoldoutBenchmarkService(
        scenario_generator=generator,
        evaluator=evaluator,
    )

    service.evaluate(
        canonical_fixture,
        canonical_development_report,
        DEBUG_MANIFEST,
    )

    fixed_plans = (
        canonical_development_report.baseline.allocation,
        *(
            item.allocation
            for item in canonical_development_report.pareto_evaluations
        ),
    )
    assert set(generator.generated) == set(DEBUG_MANIFEST.seeds)
    assert evaluator.allocations == list(fixed_plans) * len(DEBUG_MANIFEST.seeds)
    for seed, scenario_ids in evaluator.scenario_ids_by_seed.items():
        assert scenario_ids == [id(generator.generated[seed])] * len(fixed_plans)


def test_benchmark_never_reruns_allocators_or_changes_fixed_allocations(
    monkeypatch: pytest.MonkeyPatch,
    canonical_fixture: CanonicalIncidentFixture,
    canonical_development_report: ScarcityEvaluationReport,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("holdout benchmark must not solve allocations")

    monkeypatch.setattr(
        "backend.app.policies.baseline.P50GreedyAllocator.allocate",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.app.optimization.scarcity.ScenarioAwareAllocator.solve",
        forbidden,
    )

    report = HoldoutBenchmarkService().evaluate(
        canonical_fixture,
        canonical_development_report,
        DEBUG_MANIFEST,
    )

    assert report.baseline.allocation == (
        canonical_development_report.baseline.allocation
    )
    assert tuple(item.evaluation.allocation for item in report.scenario_aware) == (
        tuple(
            item.allocation
            for item in canonical_development_report.pareto_evaluations
        )
    )


def test_benchmark_rejects_mismatched_or_empty_protocol_inputs(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_development_report: ScarcityEvaluationReport,
) -> None:
    service = HoldoutBenchmarkService()
    mismatched = DEBUG_MANIFEST.model_copy(
        update={"fixture_id": "SYN-DIFFERENT-FIXTURE"}
    )
    empty = DEBUG_MANIFEST.model_copy(update={"seeds": ()})

    with pytest.raises(ValueError, match="fixture"):
        service.evaluate(
            canonical_fixture,
            canonical_development_report,
            mismatched,
        )
    with pytest.raises(ValueError, match="seed"):
        service.evaluate(
            canonical_fixture,
            canonical_development_report,
            empty,
        )
