from backend.app.domain.scarcity import (
    AllocationPlan,
    AllocationStrategy,
    ServiceOutcome,
    StrategyEvaluation,
)
from backend.app.policies.allocation_dominance import (
    AllocationDominancePolicy,
    pareto_front,
)


def evaluation(
    name: str,
    *,
    total: int,
    p10: int,
    service_totals: tuple[int, int, int],
    slots: int,
    capacity_violations: int = 0,
    unsafe_allocations: int = 0,
) -> StrategyEvaluation:
    world_count = 10
    return StrategyEvaluation(
        allocation=AllocationPlan(
            strategy=AllocationStrategy.SCENARIO_AWARE,
            allocated_container_ids=(name,),
        ),
        world_count=world_count,
        preserved_connection_total=total,
        expected_preserved_connections=total / world_count,
        rollover_total=240 - total,
        expected_rollovers=(240 - total) / world_count,
        p10_preserved_connections=p10,
        allocation_slot_count=slots,
        capacity_violations=capacity_violations,
        unsafe_allocations=unsafe_allocations,
        runtime_ms=1.0,
        service_outcomes=tuple(
            ServiceOutcome(
                service_id=service_id,
                preserved_connection_total=service_total,
            )
            for service_id, service_total in zip(
                ("SF1", "JV2", "EC3"),
                service_totals,
                strict=True,
            )
        ),
    )


def test_policy_selects_only_a_candidate_dominating_every_other_candidate() -> None:
    dominant = evaluation(
        "SYN-DOMINANT",
        total=110,
        p10=8,
        service_totals=(45, 35, 30),
        slots=7,
    )
    dominated = evaluation(
        "SYN-DOMINATED",
        total=100,
        p10=7,
        service_totals=(45, 30, 25),
        slots=8,
    )

    assert pareto_front((dominated, dominant)) == (dominant,)
    assert AllocationDominancePolicy().select(
        (dominant, dominated)
    ) == dominant.allocation


def test_policy_refuses_a_real_sf1_jv2_tradeoff() -> None:
    sf1_favouring = evaluation(
        "SYN-SF1-FAVOURING",
        total=100,
        p10=7,
        service_totals=(50, 20, 30),
        slots=8,
    )
    jv2_favouring = evaluation(
        "SYN-JV2-FAVOURING",
        total=100,
        p10=7,
        service_totals=(30, 40, 30),
        slots=8,
    )

    frontier = pareto_front((sf1_favouring, jv2_favouring))

    assert frontier == (sf1_favouring, jv2_favouring)
    assert AllocationDominancePolicy().select(frontier) is None


def test_equal_candidates_do_not_create_an_automatic_preference() -> None:
    first = evaluation(
        "SYN-EQUAL-A",
        total=100,
        p10=7,
        service_totals=(40, 30, 30),
        slots=8,
    )
    second = evaluation(
        "SYN-EQUAL-B",
        total=100,
        p10=7,
        service_totals=(40, 30, 30),
        slots=8,
    )

    assert pareto_front((first, second)) == (first, second)
    assert AllocationDominancePolicy().select((first, second)) is None


def test_a_sole_safe_alternative_may_be_selected() -> None:
    sole = evaluation(
        "SYN-SOLE",
        total=100,
        p10=7,
        service_totals=(40, 30, 30),
        slots=8,
    )

    assert pareto_front((sole,)) == (sole,)
    assert AllocationDominancePolicy().select((sole,)) == sole.allocation


def test_unsafe_or_capacity_violating_candidates_are_not_pareto_options() -> None:
    safe = evaluation(
        "SYN-SAFE",
        total=90,
        p10=6,
        service_totals=(30, 30, 30),
        slots=8,
    )
    unsafe = evaluation(
        "SYN-UNSAFE",
        total=120,
        p10=9,
        service_totals=(40, 40, 40),
        slots=8,
        unsafe_allocations=1,
    )
    over_capacity = evaluation(
        "SYN-OVER-CAPACITY",
        total=120,
        p10=9,
        service_totals=(40, 40, 40),
        slots=9,
        capacity_violations=1,
    )

    assert pareto_front((unsafe, safe, over_capacity)) == (safe,)
    assert AllocationDominancePolicy().select((unsafe, over_capacity)) is None


def test_using_fewer_slots_is_a_non_weighted_dominance_dimension() -> None:
    fewer_slots = evaluation(
        "SYN-FEWER-SLOTS",
        total=100,
        p10=7,
        service_totals=(40, 30, 30),
        slots=7,
    )
    more_slots = evaluation(
        "SYN-MORE-SLOTS",
        total=100,
        p10=7,
        service_totals=(40, 30, 30),
        slots=8,
    )

    assert pareto_front((more_slots, fewer_slots)) == (fewer_slots,)
