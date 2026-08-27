from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.domain.evidence import (
    ClaimStatus,
    CoverageRole,
    DeterministicRuntimeMetrics,
    EvidenceClaim,
    EvidenceInvariantFailure,
    EvidenceReference,
    EvidenceReportBody,
    ProvenanceEntry,
    assert_verified,
)


def ref(
    record_id: str | None = "runtime-uuid",
    *,
    source: str = "AgentRuntimeRepository.history",
) -> EvidenceReference:
    return EvidenceReference(
        record_type="AgentHistory",
        stable_key="canonical-run:agent-history",
        source=source,
        record_id=record_id,
    )


def verified_claim(*, claim_id: str = "agent_terminal_state") -> EvidenceClaim:
    return EvidenceClaim(
        claim_id=claim_id,
        statement="Canonical run terminates safely.",
        status=ClaimStatus.VERIFIED,
        observed_value={"state": "ESCALATED"},
        evidence_refs=(ref(),),
        caveat="Credential-free canonical replay only.",
    )


def provenance(claim_id: str = "agent_terminal_state") -> ProvenanceEntry:
    reference = ref()
    return ProvenanceEntry(
        claim_id=claim_id,
        record_type=reference.record_type,
        stable_key=reference.stable_key,
        source=reference.source,
        record_id=reference.record_id,
        coverage_role=CoverageRole.TYPED_HISTORY,
    )


def runtime(
    *,
    repetitions: int = 1,
    run_durations_ms: tuple[float, ...] | None = None,
) -> DeterministicRuntimeMetrics:
    return DeterministicRuntimeMetrics(
        repetitions=repetitions,
        run_durations_ms=(
            tuple(10.0 for _ in range(repetitions))
            if run_durations_ms is None
            else run_durations_ms
        ),
        canonical_run_wall_clock_ms=10.0,
        p50_local_runtime_ms=10.0,
        p95_local_runtime_ms=10.0,
        step_count=6,
        successful_tool_call_count=5,
        python_version="3.12-test",
        platform="test-platform",
    )


def report_body(
    *,
    claims: tuple[EvidenceClaim, ...],
    provenance_rows: tuple[ProvenanceEntry, ...],
) -> EvidenceReportBody:
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
        claims=claims,
        provenance=provenance_rows,
        runtime=runtime(),
    )


def test_verified_claim_requires_observation_and_reference() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            claim_id="agent_terminal_state",
            statement="Canonical run terminates safely.",
            status=ClaimStatus.VERIFIED,
            observed_value=None,
            evidence_refs=(),
            caveat="Credential-free canonical replay only.",
        )


def test_deferred_claim_rejects_fabricated_numeric_value() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            claim_id="live_model_cost",
            statement="Live model cost is measured.",
            status=ClaimStatus.DEFERRED,
            observed_value=0,
            evidence_refs=(),
            caveat="DEFERRED_TO_PHASE_9",
        )


def test_verified_claim_rejects_missing_reference_with_observation() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            claim_id="agent_terminal_state",
            statement="Canonical run terminates safely.",
            status=ClaimStatus.VERIFIED,
            observed_value={"state": "ESCALATED"},
            evidence_refs=(),
            caveat="Credential-free canonical replay only.",
        )


def test_not_established_claim_requires_partial_observation() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            claim_id="full_terminal_classification",
            statement="All terminal outcomes are classified.",
            status=ClaimStatus.NOT_ESTABLISHED,
            observed_value=None,
            evidence_refs=(),
            caveat="Complete durable classification is unavailable.",
        )


def test_deferred_claim_requires_later_phase_owner() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            claim_id="live_model_cost",
            statement="Live model cost is measured.",
            status=ClaimStatus.DEFERRED,
            observed_value="not measured",
            evidence_refs=(),
            caveat="Live credentials are unavailable.",
        )


def test_deferred_claim_accepts_non_numeric_phase_marker() -> None:
    claim = EvidenceClaim(
        claim_id="live_model_cost",
        statement="Live model cost is measured.",
        status=ClaimStatus.DEFERRED,
        observed_value="DEFERRED_TO_PHASE_9",
        evidence_refs=(),
        caveat="DEFERRED_TO_PHASE_9",
    )

    assert claim.status is ClaimStatus.DEFERRED


def test_claim_rejects_duplicate_reference_identity() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            claim_id="agent_terminal_state",
            statement="Canonical run terminates safely.",
            status=ClaimStatus.VERIFIED,
            observed_value={"state": "ESCALATED"},
            evidence_refs=(ref(), ref(source="another.repository.accessor")),
            caveat="Credential-free canonical replay only.",
        )


def test_runtime_duration_count_must_match_repetitions() -> None:
    with pytest.raises(ValidationError):
        runtime(repetitions=2, run_durations_ms=(10.0,))


def test_report_rejects_duplicate_claim_ids() -> None:
    claim = verified_claim()
    with pytest.raises(ValidationError):
        report_body(
            claims=(claim, claim),
            provenance_rows=(provenance(),),
        )


def test_report_requires_provenance_for_every_non_deferred_reference() -> None:
    with pytest.raises(ValidationError):
        report_body(claims=(verified_claim(),), provenance_rows=())


def test_report_rejects_provenance_without_matching_claim_reference() -> None:
    unrelated = provenance().model_copy(update={"stable_key": "unrelated:key"})
    with pytest.raises(ValidationError):
        report_body(
            claims=(verified_claim(),),
            provenance_rows=(provenance(), unrelated),
        )


def test_assert_verified_raises_claim_scoped_failure() -> None:
    with pytest.raises(EvidenceInvariantFailure, match="agent_step_count: observed 7") as exc:
        assert_verified(False, "agent_step_count", "observed 7")

    assert exc.value.claim_id == "agent_step_count"
