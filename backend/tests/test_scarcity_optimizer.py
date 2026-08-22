import ast
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pytest

from backend.app.domain.scarcity import (
    CanonicalIncidentFixture,
    CargoKind,
    ContainerRecoveryProfile,
    HandlingGroupLimit,
    NamedFactor,
    ScenarioAssumptions,
    ScenarioSet,
    ScenarioWorld,
)
from backend.app.evaluation.scarcity import ScarcityEvaluator
from backend.app.optimization import scarcity as optimizer_module
from backend.app.optimization.scarcity import ScenarioAwareAllocator


@dataclass(frozen=True, slots=True)
class OptimizationCase:
    fixture: CanonicalIncidentFixture
    scenarios: ScenarioSet


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def structurally_eligible(profile: ContainerRecoveryProfile) -> bool:
    return (
        profile.cargo_kind is not CargoKind.REEFER
        or profile.reefer_continuity_available
    ) and (
        profile.cargo_kind is not CargoKind.DG
        or profile.dg_structurally_cleared
    )


def optimization_case(
    canonical_fixture: CanonicalIncidentFixture,
    *,
    coefficients: tuple[int, ...],
    total_slots: int,
    groups: tuple[str, ...] | None = None,
    cargo_kinds: tuple[CargoKind, ...] | None = None,
    reefer_continuity: tuple[bool, ...] | None = None,
    dg_clearance: tuple[bool, ...] | None = None,
    group_limits: dict[str, int] | None = None,
    max_reefer_slots: int = 8,
    max_dg_slots: int = 8,
) -> OptimizationCase:
    count = len(coefficients)
    groups = groups or tuple("SYN-A-EQ1" for _ in range(count))
    cargo_kinds = cargo_kinds or tuple(CargoKind.DRY for _ in range(count))
    reefer_continuity = reefer_continuity or tuple(True for _ in range(count))
    dg_clearance = dg_clearance or tuple(True for _ in range(count))
    group_limits = group_limits or {
        "SYN-A-EQ1": total_slots,
        "SYN-B-EQ2": total_slots,
        "SYN-C-EQ3": total_slots,
    }
    sf1 = next(
        service for service in canonical_fixture.services if service.service_id == "SF1"
    )
    source_profile = canonical_fixture.profiles[0]
    profiles: list[ContainerRecoveryProfile] = []

    for index, (group, cargo_kind, has_continuity, is_cleared) in enumerate(
        zip(
            groups,
            cargo_kinds,
            reefer_continuity,
            dg_clearance,
            strict=True,
        ),
        start=1,
    ):
        container_id = f"SYN-OPT-{index:03d}"
        cargo = source_profile.container.cargo.model_copy(
            update={
                "commodity": (
                    "Synthetic declared DG cargo"
                    if cargo_kind is CargoKind.DG
                    else "Synthetic chilled cargo"
                    if cargo_kind is CargoKind.REEFER
                    else "Synthetic dry cargo"
                ),
                "dangerous_goods": cargo_kind is CargoKind.DG,
                "un_number": "UN1993" if cargo_kind is CargoKind.DG else None,
            }
        )
        container = source_profile.container.model_copy(
            update={"id": container_id, "cargo": cargo}
        )
        profiles.append(
            source_profile.model_copy(
                update={
                    "container": container,
                    "service_id": "SF1",
                    "handling_group_id": group,
                    "cargo_kind": cargo_kind,
                    "base_ready_at": sf1.ready_boundary + timedelta(minutes=15),
                    "expedite_minutes_saved": 30,
                    "reefer_continuity_available": has_continuity,
                    "dg_structurally_cleared": is_cleared,
                }
            )
        )

    capacity = canonical_fixture.capacity.model_copy(
        update={
            "total_slots": total_slots,
            "handling_group_limits": tuple(
                HandlingGroupLimit(
                    handling_group_id=group_id,
                    slots=group_limits.get(group_id, 0),
                )
                for group_id in ("SYN-A-EQ1", "SYN-B-EQ2", "SYN-C-EQ3")
            ),
            "max_reefer_slots": max_reefer_slots,
            "max_dg_slots": max_dg_slots,
        }
    )
    fixture = canonical_fixture.model_copy(
        update={"profiles": tuple(profiles), "capacity": capacity}
    )
    worlds = tuple(
        ScenarioWorld(
            index=world_index,
            shared_discharge_factor_minutes=0,
            handling_group_factors=tuple(
                NamedFactor(key=group_id, minutes=0)
                for group_id in ("SYN-A-EQ1", "SYN-B-EQ2", "SYN-C-EQ3")
            ),
            container_noise_factors=tuple(
                NamedFactor(
                    key=profile.container.id,
                    minutes=0 if world_index < coefficient else 20,
                )
                for profile, coefficient in zip(
                    profiles,
                    coefficients,
                    strict=True,
                )
            ),
        )
        for world_index in range(50)
    )
    scenarios = ScenarioSet(
        assumptions=ScenarioAssumptions(
            seed=101,
            world_count=50,
            shared_std_minutes=1.0,
            handling_group_std_minutes=1.0,
            container_noise_std_minutes=1.0,
            antithetic_pairs=False,
        ),
        worlds=worlds,
    )
    return OptimizationCase(fixture=fixture, scenarios=scenarios)


@pytest.fixture
def hand_checkable_case(
    canonical_fixture: CanonicalIncidentFixture,
) -> OptimizationCase:
    return optimization_case(
        canonical_fixture,
        coefficients=(40, 30, 10, 5),
        total_slots=2,
        group_limits={"SYN-A-EQ1": 2},
    )


@pytest.fixture
def tied_optima_case(
    canonical_fixture: CanonicalIncidentFixture,
) -> OptimizationCase:
    return optimization_case(
        canonical_fixture,
        coefficients=(10, 10, 5),
        total_slots=1,
        group_limits={"SYN-A-EQ1": 1},
    )


@pytest.fixture
def non_p50_tail_case(
    canonical_fixture: CanonicalIncidentFixture,
) -> OptimizationCase:
    source_profile = next(
        profile
        for profile in canonical_fixture.profiles
        if profile.container.id == "SYN-CNT-008"
    )
    container = source_profile.container.model_copy(update={"id": "SYN-TAIL-001"})
    profile = source_profile.model_copy(update={"container": container})
    capacity = canonical_fixture.capacity.model_copy(
        update={
            "total_slots": 1,
            "handling_group_limits": (
                HandlingGroupLimit(handling_group_id="SYN-A-EQ1", slots=1),
                HandlingGroupLimit(handling_group_id="SYN-B-EQ2", slots=0),
                HandlingGroupLimit(handling_group_id="SYN-C-EQ3", slots=0),
            ),
            "max_reefer_slots": 0,
            "max_dg_slots": 0,
        }
    )
    fixture = canonical_fixture.model_copy(
        update={"profiles": (profile,), "capacity": capacity}
    )
    worlds = tuple(
        ScenarioWorld(
            index=index,
            shared_discharge_factor_minutes=shared,
            handling_group_factors=(
                NamedFactor(key="SYN-A-EQ1", minutes=0),
            ),
            container_noise_factors=(
                NamedFactor(key="SYN-TAIL-001", minutes=0),
            ),
        )
        for index, shared in enumerate((-25, 25))
    )
    scenarios = ScenarioSet(
        assumptions=ScenarioAssumptions(
            seed=202,
            world_count=2,
            shared_std_minutes=25.0,
            handling_group_std_minutes=1.0,
            container_noise_std_minutes=1.0,
            antithetic_pairs=True,
        ),
        worlds=worlds,
    )
    return OptimizationCase(fixture=fixture, scenarios=scenarios)


def objective_value(case: OptimizationCase, container_ids: tuple[str, ...]) -> int:
    evaluator = ScarcityEvaluator()
    return sum(
        evaluator.incremental_preservation_count(
            case.fixture,
            case.scenarios,
            container_id,
        )
        for container_id in container_ids
    )


def test_cp_sat_maximises_the_hand_checkable_integer_objective(
    hand_checkable_case: OptimizationCase,
) -> None:
    plans = ScenarioAwareAllocator().solve(
        hand_checkable_case.fixture,
        hand_checkable_case.scenarios,
    )

    assert tuple(plan.allocated_container_ids for plan in plans) == (
        ("SYN-OPT-001", "SYN-OPT-002"),
    )
    assert objective_value(hand_checkable_case, plans[0].allocated_container_ids) == 70


def test_canonical_optimum_is_safe_positive_and_reproducible(
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    allocator = ScenarioAwareAllocator()
    evaluator = ScarcityEvaluator()
    candidate_ids = set(
        evaluator.stochastic_candidate_ids(canonical_fixture, canonical_scenarios)
    )
    profiles = {
        profile.container.id: profile for profile in canonical_fixture.profiles
    }

    first = allocator.solve(canonical_fixture, canonical_scenarios)
    second = allocator.solve(canonical_fixture, canonical_scenarios)

    assert first == second
    assert len(candidate_ids) == 21
    assert len(first) == 1
    assert first[0].allocated_container_ids == (
        "SYN-CNT-002",
        "SYN-CNT-004",
        "SYN-CNT-005",
        "SYN-CNT-010",
        "SYN-CNT-011",
        "SYN-CNT-012",
        "SYN-CNT-014",
        "SYN-CNT-015",
    )
    assert objective_value(
        OptimizationCase(canonical_fixture, canonical_scenarios),
        first[0].allocated_container_ids,
    ) == 246
    assert set(first[0].allocated_container_ids) <= candidate_ids
    assert all(
        structurally_eligible(profiles[container_id])
        for container_id in first[0].allocated_container_ids
    )
    assert all(
        evaluator.incremental_preservation_count(
            canonical_fixture,
            canonical_scenarios,
            container_id,
        )
        > 0
        for container_id in first[0].allocated_container_ids
    )
    assert evaluator.constraint_diagnostics(canonical_fixture, first[0]) == (0, 0)


def test_all_tied_objective_optima_are_returned(
    tied_optima_case: OptimizationCase,
) -> None:
    plans = ScenarioAwareAllocator().solve(
        tied_optima_case.fixture,
        tied_optima_case.scenarios,
    )

    assert tuple(plan.allocated_container_ids for plan in plans) == (
        ("SYN-OPT-001",),
        ("SYN-OPT-002",),
    )
    assert {
        objective_value(tied_optima_case, plan.allocated_container_ids)
        for plan in plans
    } == {10}
    assert all(
        ScarcityEvaluator().constraint_diagnostics(
            tied_optima_case.fixture,
            plan,
        )
        == (0, 0)
        for plan in plans
    )


def test_non_p50_tail_candidate_is_legally_considered(
    non_p50_tail_case: OptimizationCase,
) -> None:
    evaluator = ScarcityEvaluator()

    assert evaluator.p50_beneficiary_ids(
        non_p50_tail_case.fixture,
        non_p50_tail_case.scenarios,
    ) == ()
    assert evaluator.stochastic_candidate_ids(
        non_p50_tail_case.fixture,
        non_p50_tail_case.scenarios,
    ) == ("SYN-TAIL-001",)
    assert evaluator.incremental_preservation_count(
        non_p50_tail_case.fixture,
        non_p50_tail_case.scenarios,
        "SYN-TAIL-001",
    ) == 1

    plans = ScenarioAwareAllocator().solve(
        non_p50_tail_case.fixture,
        non_p50_tail_case.scenarios,
    )

    assert tuple(plan.allocated_container_ids for plan in plans) == (
        ("SYN-TAIL-001",),
    )


def test_group_limit_is_a_hard_constraint(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    case = optimization_case(
        canonical_fixture,
        coefficients=(30, 20, 10),
        total_slots=2,
        groups=("SYN-A-EQ1", "SYN-A-EQ1", "SYN-B-EQ2"),
        group_limits={"SYN-A-EQ1": 1, "SYN-B-EQ2": 1},
    )

    plans = ScenarioAwareAllocator().solve(case.fixture, case.scenarios)

    assert tuple(plan.allocated_container_ids for plan in plans) == (
        ("SYN-OPT-001", "SYN-OPT-003"),
    )
    assert objective_value(case, plans[0].allocated_container_ids) == 40


def test_reefer_limit_is_a_hard_constraint(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    case = optimization_case(
        canonical_fixture,
        coefficients=(30, 20, 10),
        total_slots=2,
        cargo_kinds=(CargoKind.REEFER, CargoKind.REEFER, CargoKind.DRY),
        group_limits={"SYN-A-EQ1": 2},
        max_reefer_slots=1,
    )

    plans = ScenarioAwareAllocator().solve(case.fixture, case.scenarios)

    assert tuple(plan.allocated_container_ids for plan in plans) == (
        ("SYN-OPT-001", "SYN-OPT-003"),
    )
    assert objective_value(case, plans[0].allocated_container_ids) == 40


def test_dg_limit_is_a_hard_constraint(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    case = optimization_case(
        canonical_fixture,
        coefficients=(30, 20, 10),
        total_slots=2,
        cargo_kinds=(CargoKind.DG, CargoKind.DG, CargoKind.DRY),
        group_limits={"SYN-A-EQ1": 2},
        max_dg_slots=1,
    )

    plans = ScenarioAwareAllocator().solve(case.fixture, case.scenarios)

    assert tuple(plan.allocated_container_ids for plan in plans) == (
        ("SYN-OPT-001", "SYN-OPT-003"),
    )
    assert objective_value(case, plans[0].allocated_container_ids) == 40


def test_structurally_ineligible_profiles_never_become_solver_variables(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    case = optimization_case(
        canonical_fixture,
        coefficients=(5, 50, 50),
        total_slots=2,
        cargo_kinds=(CargoKind.DRY, CargoKind.REEFER, CargoKind.DG),
        reefer_continuity=(True, False, True),
        dg_clearance=(True, True, False),
        group_limits={"SYN-A-EQ1": 2},
        max_reefer_slots=2,
        max_dg_slots=2,
    )

    candidates = ScarcityEvaluator().stochastic_candidate_ids(
        case.fixture,
        case.scenarios,
    )
    plans = ScenarioAwareAllocator().solve(case.fixture, case.scenarios)

    assert candidates == ("SYN-OPT-001",)
    assert tuple(plan.allocated_container_ids for plan in plans) == (
        ("SYN-OPT-001",),
    )


def test_optimizer_does_not_import_random_or_scenario_generation() -> None:
    module_path = Path(optimizer_module.__file__)
    imports = imported_modules(module_path)

    assert "random" not in imports
    assert "backend.app.services.scenarios" not in imports
