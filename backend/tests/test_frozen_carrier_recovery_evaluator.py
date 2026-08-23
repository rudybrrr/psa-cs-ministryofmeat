from datetime import UTC, datetime, timedelta

import pytest

from backend.app.domain.carrier_recovery import CarrierRecoveryDisposition
from backend.app.evaluation.carrier_recovery import FrozenCarrierRecoveryEvaluator
from backend.app.services.canonical_incident import SyntheticCanonicalIncidentService
from backend.app.services.scenarios import SeededScenarioGenerator


def test_frozen_evaluator_is_deterministic_and_scoped_to_affected_connection() -> None:
    fixture = SyntheticCanonicalIncidentService().load()
    scenarios = SeededScenarioGenerator().generate(fixture, seed=20260822, world_count=50)
    evaluator = FrozenCarrierRecoveryEvaluator()
    inputs = dict(
        fixture=fixture, scenarios=scenarios, selected_allocation=(),
        affected_container_ids=("SYN-CNT-017",), connection_id="SYN-CONN-JV2",
        effective_eta_pta=None,
    )
    first = evaluator.evaluate(**inputs)
    second = evaluator.evaluate(**inputs)

    assert first == second
    assert tuple(item.container_id for item in first) == ("SYN-CNT-017",)


@pytest.mark.parametrize(
    ("preserved", "expected"),
    [(45, CarrierRecoveryDisposition.PRESERVED_VIA_RTA), (44, CarrierRecoveryDisposition.ESCALATE), (0, CarrierRecoveryDisposition.STILL_ROLL)],
)
def test_frozen_evaluator_applies_inclusive_p90_policy(monkeypatch, preserved, expected) -> None:
    fixture = SyntheticCanonicalIncidentService().load()
    scenarios = SeededScenarioGenerator().generate(fixture, seed=20260822, world_count=50)
    calls = iter(range(50))
    boundary = datetime(2026, 8, 22, 8, tzinfo=UTC) + timedelta(minutes=35)
    monkeypatch.setattr("backend.app.evaluation.carrier_recovery.ScarcityEvaluator.ready_at", lambda *_args, **_kwargs: boundary if next(calls) < preserved else boundary + timedelta(seconds=1))
    result = FrozenCarrierRecoveryEvaluator().evaluate(fixture=fixture, scenarios=scenarios, selected_allocation=(), affected_container_ids=("SYN-CNT-017",), connection_id="SYN-CONN-JV2", effective_eta_pta=datetime(2026, 8, 22, 8, tzinfo=UTC))
    assert result[0].preserved_world_count == preserved
    assert result[0].disposition is expected


def test_frozen_evaluator_has_no_allocator_dependency() -> None:
    source = __import__("backend.app.evaluation.carrier_recovery", fromlist=["x"]).__file__
    assert "optimizer" not in open(source, encoding="utf-8").read().lower()
