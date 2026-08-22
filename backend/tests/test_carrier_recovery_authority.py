from pathlib import Path

from backend.app.services.carrier_simulator import SyntheticCarrierResponsePlan


def test_canonical_response_plan_is_versioned_and_covers_accept_counter_and_silence() -> None:
    plan = SyntheticCarrierResponsePlan().load()

    assert plan.plan_id == "SYN-CANONICAL-CARRIER-RTA-V1"
    assert {
        entry.connection_id: entry.outcome for entry in plan.responses
    } == {
        "SYN-CONN-SF1": "ACCEPT",
        "SYN-CONN-JV2": "COUNTER",
        "SYN-CONN-EC3": "SILENT",
    }


def test_phase_three_public_modules_expose_no_forbidden_carrier_authority() -> None:
    root = Path(__file__).resolve().parents[1] / "app"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "orchestration", root / "services")
        for path in path.glob("*.py")
    )

    for forbidden in (
        "hold_feeder(",
        "change_carrier_schedule(",
        "override_dg_rule(",
        "set_yard_capacity(",
        "CarrierResponse.SILENT",
    ):
        assert forbidden not in source
