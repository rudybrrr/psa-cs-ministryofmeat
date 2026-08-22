import ast
from pathlib import Path

import pytest

from backend.app.domain.scarcity import (
    AllocationStrategy,
    CanonicalIncidentFixture,
    ScenarioSet,
)
from backend.app.evaluation.scarcity import ScarcityEvaluator
from backend.app.policies import baseline as baseline_module
from backend.app.policies.baseline import P50GreedyAllocator


EXPECTED_BASELINE_ALLOCATION = (
    "SYN-CNT-001",
    "SYN-CNT-002",
    "SYN-CNT-003",
    "SYN-CNT-004",
    "SYN-CNT-005",
    "SYN-CNT-006",
    "SYN-CNT-007",
    "SYN-CNT-010",
)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def test_baseline_uses_eight_of_thirteen_p50_beneficiaries(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    evaluator = ScarcityEvaluator()

    plan = P50GreedyAllocator().allocate(
        canonical_fixture,
        canonical_scenarios,
    )
    beneficiaries = evaluator.p50_beneficiary_ids(
        canonical_fixture,
        canonical_scenarios,
    )

    assert len(beneficiaries) == 13
    assert plan.strategy is AllocationStrategy.P50_GREEDY
    assert plan.allocated_container_ids == EXPECTED_BASELINE_ALLOCATION
    assert len(plan.allocated_container_ids) == 8
    assert set(plan.allocated_container_ids) <= set(beneficiaries)
    assert "SYN-CNT-008" in evaluator.stochastic_candidate_ids(
        canonical_fixture,
        canonical_scenarios,
    )
    assert "SYN-CNT-008" not in plan.allocated_container_ids
    assert evaluator.constraint_diagnostics(canonical_fixture, plan) == (0, 0)


def test_baseline_is_reproducible(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    allocator = P50GreedyAllocator()

    assert allocator.allocate(
        canonical_fixture,
        canonical_scenarios,
    ) == allocator.allocate(
        canonical_fixture,
        canonical_scenarios,
    )


def test_baseline_skips_a_p50_beneficiary_that_breaks_a_group_limit(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    constrained_capacity = canonical_fixture.capacity.model_copy(
        update={
            "handling_group_limits": tuple(
                limit.model_copy(
                    update={
                        "slots": 1
                        if limit.handling_group_id == "SYN-A-EQ1"
                        else limit.slots
                    }
                )
                for limit in canonical_fixture.capacity.handling_group_limits
            )
        }
    )
    constrained_fixture = canonical_fixture.model_copy(
        update={"capacity": constrained_capacity}
    )

    plan = P50GreedyAllocator().allocate(
        constrained_fixture,
        canonical_scenarios,
    )

    assert plan.allocated_container_ids == (
        "SYN-CNT-001",
        "SYN-CNT-003",
        "SYN-CNT-004",
        "SYN-CNT-006",
        "SYN-CNT-007",
        "SYN-CNT-012",
        "SYN-CNT-014",
    )
    assert ScarcityEvaluator().constraint_diagnostics(
        constrained_fixture,
        plan,
    ) == (0, 0)


def test_baseline_development_metrics_are_observed_not_weighted(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    plan = P50GreedyAllocator().allocate(
        canonical_fixture,
        canonical_scenarios,
    )

    evaluation = ScarcityEvaluator().evaluate(
        canonical_fixture,
        canonical_scenarios,
        plan,
        runtime_ms=0.5,
    )

    assert evaluation.preserved_connection_total == 584
    assert evaluation.expected_preserved_connections == pytest.approx(11.68)
    assert evaluation.rollover_total == 616
    assert evaluation.expected_rollovers == pytest.approx(12.32)
    assert evaluation.p10_preserved_connections == 5
    assert tuple(
        outcome.preserved_connection_total
        for outcome in evaluation.service_outcomes
    ) == (317, 134, 133)
    assert evaluation.capacity_violations == 0
    assert evaluation.unsafe_allocations == 0


def test_baseline_module_does_not_import_ortools() -> None:
    module_path = Path(baseline_module.__file__)

    assert not any(
        module_name == "ortools" or module_name.startswith("ortools.")
        for module_name in imported_modules(module_path)
    )
