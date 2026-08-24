from datetime import timedelta
from types import SimpleNamespace

from backend.app.domain.dynamic_yard import ContainerReadyForecast
from backend.app.evaluation.dynamic_yard import (
    DynamicYardEvaluator,
    Z90,
    projected_ready_at,
    reconstruct_phase2_worlds,
)


def _forecast(profile):
    return ContainerReadyForecast(
        container_id=profile.container.id,
        p10_ready_at=profile.base_ready_at - timedelta(minutes=30),
        p50_ready_at=profile.base_ready_at,
        p90_ready_at=profile.base_ready_at + timedelta(minutes=30),
    )


def test_reconstruction_reuses_exact_phase_two_world_identities(canonical_fixture, canonical_scenarios) -> None:
    reconstructed = reconstruct_phase2_worlds(
        SimpleNamespace(seed=20260822, scenario_count=50), canonical_fixture
    )

    assert reconstructed == canonical_scenarios


def test_projection_uses_positive_and_negative_quantile_branches(canonical_fixture, canonical_scenarios) -> None:
    profile = canonical_fixture.profiles[0]
    forecast = _forecast(profile)
    positive_world = next(
        world for world in canonical_scenarios.worlds
        if DynamicYardEvaluator.combined_factor_minutes(profile, world) > 0
    )
    negative_world = next(
        world for world in canonical_scenarios.worlds
        if DynamicYardEvaluator.combined_factor_minutes(profile, world) < 0
    )

    positive_z = DynamicYardEvaluator.combined_factor_minutes(profile, positive_world) / (12**2 + 7**2 + 2**2) ** 0.5
    negative_z = DynamicYardEvaluator.combined_factor_minutes(profile, negative_world) / (12**2 + 7**2 + 2**2) ** 0.5
    assert projected_ready_at(profile, positive_world, forecast) == forecast.p50_ready_at - (positive_z / Z90) * (forecast.p50_ready_at - forecast.p10_ready_at)
    assert projected_ready_at(profile, negative_world, forecast) == forecast.p50_ready_at + (-negative_z / Z90) * (forecast.p90_ready_at - forecast.p50_ready_at)
