from __future__ import annotations

from math import isclose
from pathlib import Path
from typing import Any
from uuid import UUID

from backend.app.domain.evidence import (
    ClaimReproducibility,
    ClaimStatus,
    EvidenceClaim,
    EvidenceReference,
    assert_verified,
)
from backend.app.domain.scarcity import ScarcityBenchmarkReport
from backend.app.evaluation.benchmark import (
    HoldoutBenchmarkService,
    load_evaluation_seed_manifest,
)
from backend.app.evaluation.scarcity import ScarcityComparisonService
from backend.app.services.canonical_incident import (
    SyntheticCanonicalIncidentService,
)
from backend.app.services.scenarios import SeededScenarioGenerator


_ARTIFACT_SOURCE = "docs/evaluations/2026-08-22-scarcity-benchmark.json"
_FIXTURE_ID = "SYN-CANONICAL-24-V1"
_MANIFEST_ID = "SYN-CANONICAL-24-HOLDOUT-V1"
_REPRODUCIBILITY_KEY = (
    "d0dc76fb9239f4f77320f4b0a0fd5572d0b9a86a80da0448892d5336f205fe21"
)
_VOLATILE_REPORT_FIELDS: dict[str, Any] = {
    "created_at": True,
    "baseline": {"runtime_ms"},
    "scenario_aware": {"__all__": {"evaluation": {"runtime_ms"}}},
}


def _normalized_report(report: ScarcityBenchmarkReport) -> dict[str, Any]:
    return report.model_dump(
        mode="json",
        exclude=_VOLATILE_REPORT_FIELDS,
    )


def _assert_frozen_facts(report: ScarcityBenchmarkReport) -> None:
    assert_verified(
        report.fixture_id == _FIXTURE_ID,
        "scarcity_holdout_world_count",
        "canonical fixture ID drifted",
    )
    assert_verified(
        report.development_seed == 20260822,
        "scarcity_holdout_world_count",
        "development seed drifted",
    )
    assert_verified(
        report.evaluation_seed_manifest_id == _MANIFEST_ID,
        "scarcity_holdout_world_count",
        "holdout manifest ID drifted",
    )
    assert_verified(
        len(report.evaluation_seeds) == 50,
        "scarcity_holdout_world_count",
        "holdout seed count drifted",
    )
    assert_verified(
        report.worlds_per_seed == 50,
        "scarcity_holdout_world_count",
        "worlds per seed drifted",
    )
    assert_verified(
        report.baseline.world_count == 2500,
        "scarcity_holdout_world_count",
        "baseline holdout world count drifted",
    )
    assert_verified(
        len(report.scenario_aware) == 1,
        "scarcity_scenario_aware_beats_p50",
        "expected exactly one frozen scenario-aware comparison",
    )

    scenario = report.scenario_aware[0]
    baseline = report.baseline
    scenario_evaluation = scenario.evaluation

    assert_verified(
        scenario_evaluation.world_count == 2500,
        "scarcity_holdout_world_count",
        "scenario-aware holdout world count drifted",
    )
    assert_verified(
        baseline.preserved_connection_total == 30034,
        "scarcity_scenario_aware_beats_p50",
        "P50_GREEDY preserved total drifted",
    )
    assert_verified(
        scenario_evaluation.preserved_connection_total == 31272,
        "scarcity_scenario_aware_beats_p50",
        "SCENARIO_AWARE preserved total drifted",
    )
    assert_verified(
        scenario_evaluation.preserved_connection_total
        > baseline.preserved_connection_total,
        "scarcity_scenario_aware_beats_p50",
        "SCENARIO_AWARE no longer beats P50_GREEDY",
    )
    assert_verified(
        baseline.expected_preserved_connections == 12.0136,
        "scarcity_expected_preserved_delta",
        "P50_GREEDY expected preserved value drifted",
    )
    assert_verified(
        baseline.expected_rollovers == 11.9864,
        "scarcity_expected_preserved_delta",
        "P50_GREEDY expected rollover value drifted",
    )
    assert_verified(
        scenario_evaluation.expected_preserved_connections == 12.5088,
        "scarcity_expected_preserved_delta",
        "SCENARIO_AWARE expected preserved value drifted",
    )
    assert_verified(
        scenario_evaluation.expected_rollovers == 11.4912,
        "scarcity_expected_preserved_delta",
        "SCENARIO_AWARE expected rollover value drifted",
    )
    assert_verified(
        scenario.observed_expected_preserved_delta_vs_baseline
        == 0.49520000000000053,
        "scarcity_expected_preserved_delta",
        "expected-preserved delta drifted",
    )
    relative_improvement_percent = (
        scenario.observed_expected_preserved_delta_vs_baseline
        / baseline.expected_preserved_connections
        * 100
    )
    assert_verified(
        isclose(
            relative_improvement_percent,
            4.12199507225145,
            rel_tol=0,
            abs_tol=1e-14,
        ),
        "scarcity_expected_preserved_delta",
        "relative expected-preserved improvement drifted",
    )
    assert_verified(
        baseline.allocation_slot_count == 8,
        "scarcity_expedite_slot_cap",
        "P50_GREEDY allocation slot count drifted",
    )
    assert_verified(
        scenario_evaluation.allocation_slot_count == 8,
        "scarcity_expedite_slot_cap",
        "SCENARIO_AWARE allocation slot count drifted",
    )
    assert_verified(
        baseline.capacity_violations == 0,
        "scarcity_zero_capacity_violations",
        "P50_GREEDY capacity violations are nonzero",
    )
    assert_verified(
        scenario_evaluation.capacity_violations == 0,
        "scarcity_zero_capacity_violations",
        "SCENARIO_AWARE capacity violations are nonzero",
    )
    assert_verified(
        baseline.unsafe_allocations == 0,
        "scarcity_zero_unsafe_allocations",
        "P50_GREEDY unsafe allocations are nonzero",
    )
    assert_verified(
        scenario_evaluation.unsafe_allocations == 0,
        "scarcity_zero_unsafe_allocations",
        "SCENARIO_AWARE unsafe allocations are nonzero",
    )
    assert_verified(
        report.reproducibility_key == _REPRODUCIBILITY_KEY,
        "scarcity_reproducibility_key",
        "frozen holdout reproducibility key drifted",
    )


def collect_scarcity_claims(repo_root: Path) -> tuple[EvidenceClaim, ...]:
    fixture = SyntheticCanonicalIncidentService().load()
    development_scenarios = SeededScenarioGenerator().generate(
        fixture,
        seed=20260822,
        world_count=50,
    )
    development = ScarcityComparisonService().compare(
        incident_id=UUID("00000000-0000-4000-8000-000000000000"),
        fixture=fixture,
        scenarios=development_scenarios,
    )
    manifest = load_evaluation_seed_manifest()
    regenerated = HoldoutBenchmarkService().evaluate(
        fixture,
        development,
        manifest,
    )
    committed = ScarcityBenchmarkReport.model_validate_json(
        (repo_root / _ARTIFACT_SOURCE).read_text(encoding="utf-8")
    )

    _assert_frozen_facts(regenerated)
    _assert_frozen_facts(committed)
    assert_verified(
        _normalized_report(regenerated) == _normalized_report(committed),
        "scarcity_frozen_artifact_match",
        "regenerated deterministic report differs from frozen artifact",
    )

    scenario = regenerated.scenario_aware[0]
    baseline = regenerated.baseline
    scenario_evaluation = scenario.evaluation
    relative_improvement_percent = (
        scenario.observed_expected_preserved_delta_vs_baseline
        / baseline.expected_preserved_connections
        * 100
    )
    reference = EvidenceReference(
        record_type="ScarcityBenchmarkReport",
        stable_key=f"scarcity-holdout:{_MANIFEST_ID}",
        source=_ARTIFACT_SOURCE,
    )
    reproducibility = ClaimReproducibility(
        deterministic=True,
        included_in_fingerprint=True,
        fixture_ids=(_FIXTURE_ID,),
        seed_manifest_id=_MANIFEST_ID,
        benchmark_reproducibility_key=_REPRODUCIBILITY_KEY,
    )
    shared = {
        "status": ClaimStatus.VERIFIED,
        "evidence_refs": (reference,),
        "caveat": "Synthetic canonical fixture and frozen holdout manifest only.",
        "reproducibility": reproducibility,
    }

    return (
        EvidenceClaim(
            claim_id="scarcity_holdout_world_count",
            statement="The frozen scarcity holdout evaluates exactly 2,500 worlds.",
            observed_value={
                "seed_count": len(regenerated.evaluation_seeds),
                "worlds_per_seed": regenerated.worlds_per_seed,
                "world_count": baseline.world_count,
            },
            **shared,
        ),
        EvidenceClaim(
            claim_id="scarcity_scenario_aware_beats_p50",
            statement=(
                "The frozen scenario-aware allocation preserves more connections "
                "than P50_GREEDY."
            ),
            observed_value={
                "baseline_preserved_total": baseline.preserved_connection_total,
                "scenario_aware_preserved_total": (
                    scenario_evaluation.preserved_connection_total
                ),
                "scenario_aware_beats_p50": (
                    scenario_evaluation.preserved_connection_total
                    > baseline.preserved_connection_total
                ),
            },
            **shared,
        ),
        EvidenceClaim(
            claim_id="scarcity_expected_preserved_delta",
            statement=(
                "The frozen scenario-aware allocation improves expected preserved "
                "connections by the exact benchmark delta."
            ),
            observed_value={
                "baseline_expected_preserved": (
                    baseline.expected_preserved_connections
                ),
                "scenario_aware_expected_preserved": (
                    scenario_evaluation.expected_preserved_connections
                ),
                "delta": scenario.observed_expected_preserved_delta_vs_baseline,
                "relative_improvement_percent": relative_improvement_percent,
            },
            **shared,
        ),
        EvidenceClaim(
            claim_id="scarcity_expedite_slot_cap",
            statement="Both frozen allocations respect the eight-slot expedite cap.",
            observed_value={
                "slot_cap": 8,
                "baseline_slot_count": baseline.allocation_slot_count,
                "scenario_aware_slot_count": (
                    scenario_evaluation.allocation_slot_count
                ),
            },
            **shared,
        ),
        EvidenceClaim(
            claim_id="scarcity_zero_capacity_violations",
            statement="Both frozen allocations have zero capacity violations.",
            observed_value={
                "baseline": baseline.capacity_violations,
                "scenario_aware": scenario_evaluation.capacity_violations,
            },
            **shared,
        ),
        EvidenceClaim(
            claim_id="scarcity_zero_unsafe_allocations",
            statement="Both frozen allocations have zero unsafe allocations.",
            observed_value={
                "baseline": baseline.unsafe_allocations,
                "scenario_aware": scenario_evaluation.unsafe_allocations,
            },
            **shared,
        ),
        EvidenceClaim(
            claim_id="scarcity_reproducibility_key",
            statement="The regenerated frozen holdout has the exact benchmark key.",
            observed_value=regenerated.reproducibility_key,
            **shared,
        ),
    )
