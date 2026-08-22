import ast
import random
from pathlib import Path
from statistics import correlation

import pytest

from backend.app.domain.scarcity import (
    CanonicalIncidentFixture,
    NamedFactor,
    ScenarioAssumptions,
    ScenarioSet,
    ScenarioWorld,
)
from backend.app.services import scenarios as scenarios_module
from backend.app.services.scenarios import SeededScenarioGenerator


EXPECTED_GROUP_IDS = ("SYN-A-EQ1", "SYN-B-EQ2", "SYN-C-EQ3")
EXPECTED_CONTAINER_IDS = tuple(f"SYN-CNT-{index:03d}" for index in range(1, 25))


def factor_series(
    scenarios: ScenarioSet,
    fixture: CanonicalIncidentFixture,
    container_id: str,
) -> list[int]:
    profile = next(
        item for item in fixture.profiles if item.container.id == container_id
    )
    return [
        world.shared_discharge_factor_minutes
        + next(
            factor.minutes
            for factor in world.handling_group_factors
            if factor.key == profile.handling_group_id
        )
        + next(
            factor.minutes
            for factor in world.container_noise_factors
            if factor.key == container_id
        )
        for world in scenarios.worlds
    ]


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def test_same_seed_generates_identical_worlds(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    generator = SeededScenarioGenerator()

    first = generator.generate(canonical_fixture, seed=20260822, world_count=50)
    second = generator.generate(canonical_fixture, seed=20260822, world_count=50)
    different = generator.generate(canonical_fixture, seed=20260823, world_count=50)

    assert first == second
    assert first != different
    assert len(first.worlds) == 50


def test_development_assumptions_and_factor_shapes_are_explicit(
    canonical_scenarios: ScenarioSet,
) -> None:
    assert canonical_scenarios.assumptions == ScenarioAssumptions(
        seed=20260822,
        world_count=50,
        shared_std_minutes=12.0,
        handling_group_std_minutes=7.0,
        container_noise_std_minutes=2.0,
        antithetic_pairs=True,
    )
    assert (
        canonical_scenarios.assumptions.shared_std_minutes
        > canonical_scenarios.assumptions.handling_group_std_minutes
        > canonical_scenarios.assumptions.container_noise_std_minutes
    )
    assert tuple(world.index for world in canonical_scenarios.worlds) == tuple(
        range(50)
    )

    for world in canonical_scenarios.worlds:
        assert isinstance(world.shared_discharge_factor_minutes, int)
        assert tuple(factor.key for factor in world.handling_group_factors) == (
            EXPECTED_GROUP_IDS
        )
        assert tuple(factor.key for factor in world.container_noise_factors) == (
            EXPECTED_CONTAINER_IDS
        )
        assert len(world.handling_group_factors) == 3
        assert len(world.container_noise_factors) == 24


def test_antithetic_pairs_are_exact_mirrors(
    canonical_scenarios: ScenarioSet,
) -> None:
    half = len(canonical_scenarios.worlds) // 2

    for base, mirror in zip(
        canonical_scenarios.worlds[:half],
        canonical_scenarios.worlds[half:],
        strict=True,
    ):
        assert base.shared_discharge_factor_minutes + (
            mirror.shared_discharge_factor_minutes
        ) == 0
        assert tuple(factor.key for factor in base.handling_group_factors) == tuple(
            factor.key for factor in mirror.handling_group_factors
        )
        assert tuple(
            left.minutes + right.minutes
            for left, right in zip(
                base.handling_group_factors,
                mirror.handling_group_factors,
                strict=True,
            )
        ) == (0, 0, 0)
        assert tuple(factor.key for factor in base.container_noise_factors) == tuple(
            factor.key for factor in mirror.container_noise_factors
        )
        assert all(
            left.minutes + right.minutes == 0
            for left, right in zip(
                base.container_noise_factors,
                mirror.container_noise_factors,
                strict=True,
            )
        )


def test_shared_and_group_factors_create_correlation(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    scenarios = SeededScenarioGenerator().generate(
        canonical_fixture,
        seed=20260822,
        world_count=500,
    )
    same_a = factor_series(scenarios, canonical_fixture, "SYN-CNT-001")
    same_b = factor_series(scenarios, canonical_fixture, "SYN-CNT-002")
    cross = factor_series(scenarios, canonical_fixture, "SYN-CNT-006")

    same_group_correlation = correlation(same_a, same_b)
    cross_group_correlation = correlation(same_a, cross)
    print(
        f"same_group_correlation={same_group_correlation:.6f}, "
        f"cross_group_correlation={cross_group_correlation:.6f}"
    )

    assert same_group_correlation > cross_group_correlation
    assert cross_group_correlation > 0.5


@pytest.mark.parametrize("world_count", [0, -2, 3, 49])
def test_world_count_must_be_positive_and_even(
    canonical_fixture: CanonicalIncidentFixture,
    world_count: int,
) -> None:
    with pytest.raises(ValueError, match="positive even"):
        SeededScenarioGenerator().generate(
            canonical_fixture,
            seed=20260822,
            world_count=world_count,
        )


def test_generation_does_not_touch_global_random_state(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    initial_state = random.getstate()
    try:
        random.seed(8675309)
        before = random.getstate()

        SeededScenarioGenerator().generate(
            canonical_fixture,
            seed=20260822,
            world_count=50,
        )

        assert random.getstate() == before
    finally:
        random.setstate(initial_state)


def test_scenario_generation_does_not_import_ortools() -> None:
    module_path = Path(scenarios_module.__file__)

    assert not any(
        module_name == "ortools" or module_name.startswith("ortools.")
        for module_name in imported_modules(module_path)
    )


def test_task_3_preserves_fixture_and_scarcity_contract_boundaries(
    canonical_fixture: CanonicalIncidentFixture,
) -> None:
    assert set(CanonicalIncidentFixture.model_fields) == {
        "fixture_id",
        "event",
        "services",
        "profiles",
        "capacity",
    }
    assert set(ScenarioAssumptions.model_fields) == {
        "seed",
        "world_count",
        "shared_std_minutes",
        "handling_group_std_minutes",
        "container_noise_std_minutes",
        "antithetic_pairs",
    }
    assert set(NamedFactor.model_fields) == {"key", "minutes"}
    assert set(ScenarioWorld.model_fields) == {
        "index",
        "shared_discharge_factor_minutes",
        "handling_group_factors",
        "container_noise_factors",
    }
    assert set(ScenarioSet.model_fields) == {"assumptions", "worlds"}
    assert canonical_fixture.fixture_id == "SYN-CANONICAL-24-V1"
    assert tuple(
        profile.container.id for profile in canonical_fixture.profiles
    ) == EXPECTED_CONTAINER_IDS
    assert {
        profile.handling_group_id for profile in canonical_fixture.profiles
    } == set(EXPECTED_GROUP_IDS)
