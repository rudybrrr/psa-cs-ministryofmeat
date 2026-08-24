from uuid import UUID

import pytest

from backend.app.services.dynamic_yard import ACTIVE_HALF_WIDTH_MINUTES, CanonicalDynamicYardHarness


def test_harness_tightens_forecast_bands(canonical_fixture) -> None:
    harness = CanonicalDynamicYardHarness()
    incident_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    pre = harness.bootstrap_snapshot(incident_id)
    active = harness.discharge_active_snapshot(incident_id)

    assert (pre.container_forecasts[0].p90_ready_at - pre.container_forecasts[0].p50_ready_at).total_seconds() / 60 == 30
    assert (active.container_forecasts[0].p90_ready_at - active.container_forecasts[0].p50_ready_at).total_seconds() / 60 == pytest.approx(ACTIVE_HALF_WIDTH_MINUTES, abs=1e-8)
    assert ACTIVE_HALF_WIDTH_MINUTES < 30
