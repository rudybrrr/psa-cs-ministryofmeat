from datetime import timedelta
from uuid import UUID

import pytest

from backend.app.domain.scarcity import (
    AllocationPlan,
    AllocationStrategy,
    CanonicalIncidentFixture,
    CargoKind,
    NamedFactor,
    ScenarioSet,
    ScenarioWorld,
    ServiceOutcome,
)
from backend.app.evaluation.scarcity import (
    ScarcityComparisonService,
    ScarcityEvaluator,
    semantic_reproducibility_key,
)


EXPECTED_P50_BENEFICIARIES = (
    "SYN-CNT-001",
    "SYN-CNT-002",
    "SYN-CNT-003",
    "SYN-CNT-004",
    "SYN-CNT-005",
    "SYN-CNT-006",
    "SYN-CNT-007",
    "SYN-CNT-010",
    "SYN-CNT-011",
    "SYN-CNT-012",
    "SYN-CNT-013",
    "SYN-CNT-014",
    "SYN-CNT-015",
)

EXPECTED_STOCHASTIC_CANDIDATES = (
    "SYN-CNT-001",
    "SYN-CNT-002",
    "SYN-CNT-003",
    "SYN-CNT-004",
    "SYN-CNT-005",
    "SYN-CNT-006",
    "SYN-CNT-007",
    "SYN-CNT-008",
    "SYN-CNT-010",
    "SYN-CNT-011",
    "SYN-CNT-012",
    "SYN-CNT-013",
    "SYN-CNT-014",
    "SYN-CNT-015",
    "SYN-CNT-016",
    "SYN-CNT-017",
    "SYN-CNT-018",
    "SYN-CNT-019",
    "SYN-CNT-020",
    "SYN-CNT-021",
    "SYN-CNT-024",
)


def profile_for(fixture: CanonicalIncidentFixture, container_id: str):
    return next(
        profile
        for profile in fixture.profiles
        if profile.container.id == container_id
    )


def world_for(
    fixture: CanonicalIncidentFixture,
    *,
    shared: int,
    group: int,
    noise: int,
) -> ScenarioWorld:
    return ScenarioWorld(
        index=0,
        shared_discharge_factor_minutes=shared,
        handling_group_factors=tuple(
            NamedFactor(key=group_id, minutes=group)
            for group_id in sorted(
                {profile.handling_group_id for profile in fixture.profiles}
            )
        ),
        container_noise_factors=tuple(
            NamedFactor(key=profile.container.id, minutes=noise)
            for profile in sorted(
                fixture.profiles,
                key=lambda item: item.container.id,
            )
        ),
    )


def plan_for(*container_ids: str) -> AllocationPlan:
    return AllocationPlan(
        strategy=AllocationStrategy.P50_GREEDY,
        allocated_container_ids=container_ids,
    )


def test_ready_time_uses_all_three_factor_levels(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    profile = profile_for(canonical_fixture, "SYN-CNT-001")
    world = world_for(canonical_fixture, shared=12, group=7, noise=2)

    observed = ScarcityEvaluator().ready_at(profile, world, expedited=False)

    assert observed == profile.base_ready_at - timedelta(minutes=21)


def test_expedition_subtracts_the_fixed_saving(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    profile = profile_for(canonical_fixture, "SYN-CNT-001")
    world = world_for(canonical_fixture, shared=-5, group=3, noise=-1)
    evaluator = ScarcityEvaluator()

    normal = evaluator.ready_at(profile, world, expedited=False)
    expedited = evaluator.ready_at(profile, world, expedited=True)

    assert normal - expedited == timedelta(minutes=30)


def test_preservation_uses_the_service_boundary_and_structural_safety(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    evaluator = ScarcityEvaluator()
    zero_world = world_for(canonical_fixture, shared=0, group=0, noise=0)
    beneficiary = profile_for(canonical_fixture, "SYN-CNT-001")
    uncleared_dg = profile_for(canonical_fixture, "SYN-CNT-009")

    assert not evaluator.preserves_connection(
        canonical_fixture,
        beneficiary,
        zero_world,
        expedited=False,
    )
    assert evaluator.preserves_connection(
        canonical_fixture,
        beneficiary,
        zero_world,
        expedited=True,
    )
    assert not evaluator.preserves_connection(
        canonical_fixture,
        uncleared_dg,
        zero_world,
        expedited=True,
    )


def test_p50_beneficiaries_are_the_derived_canonical_thirteen(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    assert ScarcityEvaluator().p50_beneficiary_ids(
        canonical_fixture,
        canonical_scenarios,
    ) == EXPECTED_P50_BENEFICIARIES


@pytest.mark.parametrize(
    ("container_id", "expected_increment"),
    [
        ("SYN-CNT-001", 28),
        ("SYN-CNT-008", 6),
        ("SYN-CNT-024", 1),
        ("SYN-CNT-009", 0),
    ],
)
def test_incremental_preservation_counts_supplied_world_successes(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
    container_id: str,
    expected_increment: int,
) -> None:
    assert ScarcityEvaluator().incremental_preservation_count(
        canonical_fixture,
        canonical_scenarios,
        container_id,
    ) == expected_increment


def test_stochastic_candidates_are_positive_eligible_and_not_median_gated(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    evaluator = ScarcityEvaluator()

    candidates = evaluator.stochastic_candidate_ids(
        canonical_fixture,
        canonical_scenarios,
    )

    assert candidates == EXPECTED_STOCHASTIC_CANDIDATES
    assert "SYN-CNT-008" in candidates
    assert "SYN-CNT-024" in candidates
    assert "SYN-CNT-009" not in candidates
    assert "SYN-CNT-022" not in candidates
    assert "SYN-CNT-023" not in candidates
    assert set(candidates) > set(EXPECTED_P50_BENEFICIARIES)
    assert all(
        evaluator.incremental_preservation_count(
            canonical_fixture,
            canonical_scenarios,
            container_id,
        )
        > 0
        for container_id in candidates
    )


@pytest.mark.parametrize(
    ("container_ids", "expected_capacity_violations"),
    [
        (
            (
                "SYN-CNT-001",
                "SYN-CNT-002",
                "SYN-CNT-003",
                "SYN-CNT-005",
                "SYN-CNT-006",
                "SYN-CNT-007",
                "SYN-CNT-010",
                "SYN-CNT-012",
                "SYN-CNT-017",
            ),
            1,
        ),
        (
            (
                "SYN-CNT-001",
                "SYN-CNT-002",
                "SYN-CNT-005",
                "SYN-CNT-010",
                "SYN-CNT-011",
            ),
            1,
        ),
        (("SYN-CNT-003", "SYN-CNT-004", "SYN-CNT-012", "SYN-CNT-017"), 1),
        (("SYN-CNT-006", "SYN-CNT-007", "SYN-CNT-014", "SYN-CNT-015"), 1),
        (("SYN-CNT-002", "SYN-CNT-006", "SYN-CNT-011", "SYN-CNT-015"), 1),
        (("SYN-CNT-004", "SYN-CNT-013"), 1),
    ],
)
def test_constraint_diagnostics_detect_every_capacity_limit(
    canonical_fixture: CanonicalIncidentFixture,
    container_ids: tuple[str, ...],
    expected_capacity_violations: int,
) -> None:
    assert ScarcityEvaluator().constraint_diagnostics(
        canonical_fixture,
        plan_for(*container_ids),
    ) == (expected_capacity_violations, 0)


@pytest.mark.parametrize("container_id", ["SYN-CNT-009", "SYN-CNT-022", "SYN-CNT-023"])
def test_constraint_diagnostics_count_structurally_unsafe_allocations(
    canonical_fixture: CanonicalIncidentFixture,
    container_id: str,
) -> None:
    assert ScarcityEvaluator().constraint_diagnostics(
        canonical_fixture,
        plan_for(container_id),
    ) == (0, 1)


def test_evaluation_reports_exact_supplied_world_metrics(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    result = ScarcityEvaluator().evaluate(
        canonical_fixture,
        canonical_scenarios,
        plan_for("SYN-CNT-001"),
        runtime_ms=1.25,
    )

    assert result.world_count == 50
    assert result.preserved_connection_total == 383
    assert result.expected_preserved_connections == pytest.approx(7.66)
    assert result.rollover_total == 817
    assert result.expected_rollovers == pytest.approx(16.34)
    assert result.p10_preserved_connections == 3
    assert result.allocation_slot_count == 1
    assert result.capacity_violations == 0
    assert result.unsafe_allocations == 0
    assert result.runtime_ms == 1.25
    assert result.service_outcomes == (
        ServiceOutcome(service_id="SF1", preserved_connection_total=145),
        ServiceOutcome(service_id="JV2", preserved_connection_total=105),
        ServiceOutcome(service_id="EC3", preserved_connection_total=133),
    )


def test_semantic_reproducibility_key_excludes_runtime_and_event_timestamp(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    evaluator = ScarcityEvaluator()
    allocation = plan_for("SYN-CNT-001")
    evaluation = evaluator.evaluate(
        canonical_fixture,
        canonical_scenarios,
        allocation,
        runtime_ms=1.25,
    )
    changed_runtime = evaluation.model_copy(update={"runtime_ms": 999.0})
    changed_event = canonical_fixture.event.model_copy(
        update={
            "occurred_at": canonical_fixture.event.occurred_at
            + timedelta(days=1)
        }
    )
    changed_fixture = canonical_fixture.model_copy(update={"event": changed_event})

    first = semantic_reproducibility_key(
        canonical_fixture,
        canonical_scenarios,
        evaluation,
    )

    assert len(first) == 64
    assert first == semantic_reproducibility_key(
        canonical_fixture,
        canonical_scenarios,
        changed_runtime,
    )
    assert first == semantic_reproducibility_key(
        changed_fixture,
        canonical_scenarios,
        evaluation,
    )


def test_semantic_reproducibility_key_changes_with_semantic_results(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    evaluator = ScarcityEvaluator()
    first = evaluator.evaluate(
        canonical_fixture,
        canonical_scenarios,
        plan_for("SYN-CNT-001"),
        runtime_ms=1.0,
    )
    second = evaluator.evaluate(
        canonical_fixture,
        canonical_scenarios,
        plan_for("SYN-CNT-002"),
        runtime_ms=1.0,
    )

    assert semantic_reproducibility_key(
        canonical_fixture,
        canonical_scenarios,
        first,
    ) != semantic_reproducibility_key(
        canonical_fixture,
        canonical_scenarios,
        second,
    )


def test_comparison_keeps_baseline_visible_and_selects_the_sole_safe_optimum(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    report = ScarcityComparisonService().compare(
        incident_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        fixture=canonical_fixture,
        scenarios=canonical_scenarios,
    )

    assert report.baseline.allocation.strategy is AllocationStrategy.P50_GREEDY
    assert len(report.scenario_aware_evaluations) == 1
    assert report.pareto_evaluations == report.scenario_aware_evaluations
    assert report.selected_allocation == report.scenario_aware_evaluations[0].allocation
    assert report.baseline.capacity_violations == 0
    assert report.baseline.unsafe_allocations == 0
    assert all(
        evaluation.capacity_violations == 0
        and evaluation.unsafe_allocations == 0
        for evaluation in report.scenario_aware_evaluations
    )


def test_comparison_reports_observed_metrics_without_an_expected_winner(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    report = ScarcityComparisonService().compare(
        incident_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        fixture=canonical_fixture,
        scenarios=canonical_scenarios,
    )
    candidate = report.scenario_aware_evaluations[0]
    observed_delta = (
        candidate.expected_preserved_connections
        - report.baseline.expected_preserved_connections
    )

    assert candidate.expected_preserved_connections == pytest.approx(
        candidate.preserved_connection_total / candidate.world_count
    )
    assert observed_delta == pytest.approx(
        (
            candidate.preserved_connection_total
            - report.baseline.preserved_connection_total
        )
        / candidate.world_count
    )


def test_canonical_comparison_is_semantically_reproducible(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    service = ScarcityComparisonService()
    incident_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

    first = service.compare(
        incident_id=incident_id,
        fixture=canonical_fixture,
        scenarios=canonical_scenarios,
    )
    second = service.compare(
        incident_id=incident_id,
        fixture=canonical_fixture,
        scenarios=canonical_scenarios,
    )

    assert first.id != second.id
    assert first.created_at != second.created_at
    assert first.reproducibility_key == second.reproducibility_key
    assert first.baseline.model_copy(update={"runtime_ms": 0}) == (
        second.baseline.model_copy(update={"runtime_ms": 0})
    )
    assert tuple(
        evaluation.model_copy(update={"runtime_ms": 0})
        for evaluation in first.scenario_aware_evaluations
    ) == tuple(
        evaluation.model_copy(update={"runtime_ms": 0})
        for evaluation in second.scenario_aware_evaluations
    )
    assert first.pareto_evaluations == first.scenario_aware_evaluations
    assert first.selected_allocation == second.selected_allocation
    assert first.baseline.runtime_ms > 0
    assert first.scenario_aware_evaluations[0].runtime_ms > 0
    print(
        {
            "baseline_expected_preserved": (
                first.baseline.expected_preserved_connections
            ),
            "scenario_expected_preserved": (
                first.scenario_aware_evaluations[0].expected_preserved_connections
            ),
            "observed_development_delta": (
                first.scenario_aware_evaluations[0].expected_preserved_connections
                - first.baseline.expected_preserved_connections
            ),
            "baseline_runtime_ms": first.baseline.runtime_ms,
            "scenario_runtime_ms": (
                first.scenario_aware_evaluations[0].runtime_ms
            ),
        }
    )
