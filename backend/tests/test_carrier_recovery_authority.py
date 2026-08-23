from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.services.carrier_simulator import (
    CarrierDemoSuite,
    SyntheticCarrierResponsePlan,
)


def test_canonical_response_plan_is_versioned_and_covers_accept_counter_and_silence() -> None:
    suite = SyntheticCarrierResponsePlan().load()

    assert suite.suite_id == "SYN-CANONICAL-CARRIER-DEMO-V1"
    assert [
        (run.run_id, run.connection_id, run.outcome)
        for run in suite.runs
    ] == [
        ("ACCEPT-RUN", "SYN-CONN-JV2", "ACCEPT"),
        ("COUNTER-RUN", "SYN-CONN-JV2", "COUNTER"),
        ("SILENT-RUN", "SYN-CONN-EC3", "SILENT"),
    ]


def test_carrier_demo_suite_rejects_a_run_for_a_different_phase_two_fixture() -> None:
    with pytest.raises(ValidationError, match="fixture_id"):
        CarrierDemoSuite.model_validate(
            {
                "suite_id": "SYN-CANONICAL-CARRIER-DEMO-V1",
                "fixture_id": "SYN-CANONICAL-24-V1",
                "runs": [
                    {
                        "run_id": "ACCEPT-RUN",
                        "fixture_id": "SYN-OTHER-FIXTURE-V1",
                        "connection_id": "SYN-CONN-JV2",
                        "outcome": "ACCEPT",
                    }
                ],
            }
        )


def test_phase_three_public_modules_expose_no_forbidden_carrier_authority() -> None:
    root = Path(__file__).resolve().parents[1] / "app"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "domain", root / "evaluation", root / "orchestration", root / "services")
        for path in path.glob("*.py")
    ) + (root / "main.py").read_text(encoding="utf-8")

    for forbidden in (
        "hold_feeder(",
        "change_carrier_schedule(",
        "override_dg_rule(",
        "set_yard_capacity(",
        "CarrierResponse.SILENT",
    ):
        assert forbidden not in source

    assert '"/recompute' not in source
    assert "AuditActor.AGENT" not in source
    assert "ScenarioAwareAllocator" not in (root / "evaluation" / "carrier_recovery.py").read_text(encoding="utf-8")
    assert "ScarcityComparisonService" not in (root / "evaluation" / "carrier_recovery.py").read_text(encoding="utf-8")
