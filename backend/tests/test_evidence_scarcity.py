from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.app.domain.evidence import (
    ClaimStatus,
    EvidenceInvariantFailure,
)
from backend.app.domain.scarcity import ScarcityBenchmarkReport
from backend.app.evaluation import evidence_scarcity
from backend.app.evaluation.evidence_scarcity import collect_scarcity_claims


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CLAIM_IDS = {
    "scarcity_holdout_world_count",
    "scarcity_scenario_aware_beats_p50",
    "scarcity_expected_preserved_delta",
    "scarcity_expedite_slot_cap",
    "scarcity_zero_capacity_violations",
    "scarcity_zero_unsafe_allocations",
    "scarcity_reproducibility_key",
}


def _patch_committed_report(
    monkeypatch: pytest.MonkeyPatch,
    transform,
) -> None:
    original = ScarcityBenchmarkReport.model_validate_json

    def patched_model_validate_json(cls, json_data, **kwargs):
        return transform(original(json_data, **kwargs))

    monkeypatch.setattr(
        evidence_scarcity.ScarcityBenchmarkReport,
        "model_validate_json",
        classmethod(patched_model_validate_json),
    )


def test_scarcity_collector_regenerates_exact_frozen_evidence() -> None:
    claims = {claim.claim_id: claim for claim in collect_scarcity_claims(REPO_ROOT)}

    assert set(claims) == EXPECTED_CLAIM_IDS
    assert {claim.status for claim in claims.values()} == {ClaimStatus.VERIFIED}
    assert claims["scarcity_holdout_world_count"].observed_value == {
        "seed_count": 50,
        "worlds_per_seed": 50,
        "world_count": 2500,
    }
    assert claims["scarcity_scenario_aware_beats_p50"].observed_value == {
        "baseline_preserved_total": 30034,
        "scenario_aware_preserved_total": 31272,
        "scenario_aware_beats_p50": True,
    }
    assert claims["scarcity_expected_preserved_delta"].observed_value == {
        "baseline_expected_preserved": 12.0136,
        "scenario_aware_expected_preserved": 12.5088,
        "delta": 0.49520000000000053,
        "relative_improvement_percent": pytest.approx(4.12199507225145),
    }
    assert claims["scarcity_expedite_slot_cap"].observed_value == {
        "slot_cap": 8,
        "baseline_slot_count": 8,
        "scenario_aware_slot_count": 8,
    }
    assert claims["scarcity_zero_capacity_violations"].observed_value == {
        "baseline": 0,
        "scenario_aware": 0,
    }
    assert claims["scarcity_zero_unsafe_allocations"].observed_value == {
        "baseline": 0,
        "scenario_aware": 0,
    }
    assert claims["scarcity_reproducibility_key"].observed_value == (
        "d0dc76fb9239f4f77320f4b0a0fd5572d0b9a86a80da0448892d5336f205fe21"
    )


def test_scarcity_collector_rejects_drifted_frozen_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_committed_report(
        monkeypatch,
        lambda report: report.model_copy(update={"reproducibility_key": "0" * 64}),
    )

    with pytest.raises(
        EvidenceInvariantFailure,
        match="scarcity_reproducibility_key",
    ):
        collect_scarcity_claims(REPO_ROOT)


def test_scarcity_collector_rejects_drifted_deterministic_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def drift_total(report: ScarcityBenchmarkReport) -> ScarcityBenchmarkReport:
        comparison = report.scenario_aware[0]
        drifted_evaluation = comparison.evaluation.model_copy(
            update={"preserved_connection_total": 31271}
        )
        drifted_comparison = comparison.model_copy(
            update={"evaluation": drifted_evaluation}
        )
        return report.model_copy(update={"scenario_aware": (drifted_comparison,)})

    _patch_committed_report(monkeypatch, drift_total)

    with pytest.raises(
        EvidenceInvariantFailure,
        match="scarcity_scenario_aware_beats_p50",
    ):
        collect_scarcity_claims(REPO_ROOT)


def test_scarcity_collector_excludes_created_at_and_every_runtime_ms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = collect_scarcity_claims(REPO_ROOT)

    def change_volatile_fields(
        report: ScarcityBenchmarkReport,
    ) -> ScarcityBenchmarkReport:
        baseline = report.baseline.model_copy(update={"runtime_ms": 999999.0})
        scenario_aware = tuple(
            comparison.model_copy(
                update={
                    "evaluation": comparison.evaluation.model_copy(
                        update={"runtime_ms": 888888.0}
                    )
                }
            )
            for comparison in report.scenario_aware
        )
        return report.model_copy(
            update={
                "created_at": datetime(2099, 1, 1, tzinfo=UTC),
                "baseline": baseline,
                "scenario_aware": scenario_aware,
            }
        )

    _patch_committed_report(monkeypatch, change_volatile_fields)

    assert collect_scarcity_claims(REPO_ROOT) == expected
