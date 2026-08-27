from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from backend.app.domain.agent_runtime import AgentToolInvocationStatus
from backend.app.domain.evidence import (
    ClaimStatus,
    CoverageRole,
    EvidenceReportBody,
    ProvenanceEntry,
    evidence_fingerprint,
    normalized_evidence_payload,
)
from backend.app.evaluation.evidence_runtime import (
    local_runtime_claim,
    measure_local_runtime,
    nearest_rank_percentile,
)


def canonical_result(*, step_count: int = 6, tool_count: int = 5):
    return SimpleNamespace(
        agent_run=SimpleNamespace(step_count=step_count),
        agent_history=SimpleNamespace(
            tool_invocations=tuple(
                SimpleNamespace(status=AgentToolInvocationStatus.SUCCEEDED)
                for _ in range(tool_count)
            )
        ),
    )


def test_percentiles_use_median_for_p50_and_nearest_rank_for_p95() -> None:
    values = tuple(float(value) for value in range(1, 21))

    assert nearest_rank_percentile(values, 0.5) == 10.5
    assert nearest_rank_percentile(values, 0.95) == 19.0


@pytest.mark.parametrize("percentile", (0, -0.1, 1.1))
def test_percentile_rejects_values_outside_open_closed_unit_interval(
    percentile: float,
) -> None:
    with pytest.raises(ValueError, match="percentile"):
        nearest_rank_percentile((1.0,), percentile)


def test_measurement_records_complete_canonical_runs_and_local_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.evaluation import evidence_runtime

    ticks = iter((1_000_000, 3_000_000, 10_000_000, 14_000_000, 20_000_000, 29_000_000))
    monkeypatch.setattr(evidence_runtime, "perf_counter_ns", lambda: next(ticks))
    monkeypatch.setattr(evidence_runtime.sys, "version", "3.12.0-test")
    monkeypatch.setattr(evidence_runtime.platform, "platform", lambda: "test-platform")

    metrics = measure_local_runtime(lambda: canonical_result(), repetitions=3)

    assert metrics.repetitions == 3
    assert metrics.run_durations_ms == (2.0, 4.0, 9.0)
    assert metrics.canonical_run_wall_clock_ms == 2.0
    assert metrics.p50_local_runtime_ms == 4.0
    assert metrics.p95_local_runtime_ms == 9.0
    assert metrics.step_count == 6
    assert metrics.successful_tool_call_count == 5
    assert metrics.label == "LOCAL_MACHINE_DEPENDENT"
    assert metrics.production_sla_claimed is False
    assert metrics.python_version == "3.12.0-test"
    assert metrics.platform == "test-platform"


def test_measurement_rejects_invalid_repetition_count() -> None:
    with pytest.raises(ValueError, match="repetitions"):
        measure_local_runtime(lambda: canonical_result(), repetitions=0)


def test_measurement_rejects_a_noncanonical_run() -> None:
    with pytest.raises(RuntimeError, match="agent_step_count"):
        measure_local_runtime(lambda: canonical_result(step_count=7), repetitions=1)


def test_local_runtime_claim_is_volatile_verified_evidence_without_a_duplicate_count() -> None:
    metrics = measure_local_runtime(lambda: canonical_result(), repetitions=1)

    claim = local_runtime_claim(metrics)

    assert claim.status is ClaimStatus.VERIFIED
    assert claim.reproducibility is not None
    assert claim.reproducibility.deterministic is False
    assert claim.reproducibility.included_in_fingerprint is False
    assert "LOCAL_MACHINE_DEPENDENT" in claim.caveat
    assert "SLA" in claim.caveat
    assert "deterministic_tool_call_count" not in claim.claim_id
    assert "successful_tool_call_count" not in claim.observed_value


def report_with_runtime(runtime) -> EvidenceReportBody:
    claim = local_runtime_claim(runtime)
    reference = claim.evidence_refs[0]
    return EvidenceReportBody(
        evaluation_base_sha="71716a0eee8413358dfc1e125a942945fc4be18c",
        source_revision="a" * 40,
        generated_at=datetime(2026, 8, 26, tzinfo=UTC),
        command="python -m backend.app.evaluation.evidence",
        cli_version="phase8-evidence-v1",
        fixture_ids=("SYN-CANONICAL-24-V1",),
        seed_manifest_id="SYN-CANONICAL-24-HOLDOUT-V1",
        canonical_model_identity="canonical-replay-agent-v1",
        canonical_checker_identity="canonical-replay-deterministic",
        claims=(claim,),
        provenance=(
            ProvenanceEntry(
                claim_id=claim.claim_id,
                record_type=reference.record_type,
                stable_key=reference.stable_key,
                source=reference.source,
                record_id=reference.record_id,
                coverage_role=CoverageRole.FROZEN_ARTIFACT,
            ),
        ),
        runtime=runtime,
    )


def test_runtime_measurements_serialize_differently_but_do_not_change_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.evaluation import evidence_runtime

    first_ticks = iter((0, 1_000_000, 2_000_000, 4_000_000))
    monkeypatch.setattr(evidence_runtime, "perf_counter_ns", lambda: next(first_ticks))
    monkeypatch.setattr(evidence_runtime.platform, "platform", lambda: "first-platform")
    monkeypatch.setattr(evidence_runtime.sys, "version", "3.12-first")
    first = report_with_runtime(measure_local_runtime(lambda: canonical_result(), 2))

    second_ticks = iter((0, 9_000_000, 10_000_000, 30_000_000))
    monkeypatch.setattr(evidence_runtime, "perf_counter_ns", lambda: next(second_ticks))
    monkeypatch.setattr(evidence_runtime.platform, "platform", lambda: "second-platform")
    monkeypatch.setattr(evidence_runtime.sys, "version", "3.12-second")
    second = report_with_runtime(measure_local_runtime(lambda: canonical_result(), 2))

    assert first.runtime.model_dump(mode="json") != second.runtime.model_dump(mode="json")
    assert normalized_evidence_payload(first) == normalized_evidence_payload(second)
    assert evidence_fingerprint(first) == evidence_fingerprint(second)
