from datetime import UTC, datetime

from backend.app.domain.evidence import (
    ClaimReproducibility,
    ClaimStatus,
    CoverageRole,
    DeterministicRuntimeMetrics,
    EvidenceClaim,
    EvidenceReference,
    EvidenceReportBody,
    ProvenanceEntry,
    evidence_fingerprint,
    normalized_evidence_payload,
)


def ref(record_id: str | None = "runtime-uuid") -> EvidenceReference:
    return EvidenceReference(
        record_type="AgentHistory",
        stable_key="canonical-run:agent-history",
        source="AgentRuntimeRepository.history",
        record_id=record_id,
    )


def make_report_body(
    *,
    source_revision: str = "a" * 40,
    generated_at: datetime = datetime(2026, 8, 26, tzinfo=UTC),
    record_id: str = "11111111-1111-4111-8111-111111111111",
    local_runtime_ms: float = 10.0,
    observed_value: object = None,
) -> EvidenceReportBody:
    value = {"step_count": 6} if observed_value is None else observed_value
    reference = ref(record_id)
    claim = EvidenceClaim(
        claim_id="agent_step_count",
        statement="Canonical run has the exact deterministic step count.",
        status=ClaimStatus.VERIFIED,
        observed_value=value,
        evidence_refs=(reference,),
        caveat="Credential-free canonical replay only.",
    )
    provenance = ProvenanceEntry(
        claim_id=claim.claim_id,
        record_type=reference.record_type,
        stable_key=reference.stable_key,
        source=reference.source,
        record_id=reference.record_id,
        coverage_role=CoverageRole.TYPED_HISTORY,
    )
    runtime = DeterministicRuntimeMetrics(
        repetitions=1,
        run_durations_ms=(local_runtime_ms,),
        canonical_run_wall_clock_ms=local_runtime_ms,
        p50_local_runtime_ms=local_runtime_ms,
        p95_local_runtime_ms=local_runtime_ms,
        step_count=6,
        successful_tool_call_count=5,
        python_version="3.12-test",
        platform="test-platform",
    )
    return EvidenceReportBody(
        evaluation_base_sha="71716a0eee8413358dfc1e125a942945fc4be18c",
        source_revision=source_revision,
        generated_at=generated_at,
        command="python -m backend.app.evaluation.evidence",
        cli_version="phase8-evidence-v1",
        fixture_ids=("SYN-CANONICAL-24-V1",),
        seed_manifest_id="SYN-CANONICAL-24-HOLDOUT-V1",
        canonical_model_identity="canonical-replay-agent-v1",
        canonical_checker_identity="canonical-replay-deterministic",
        claims=(claim,),
        provenance=(provenance,),
        runtime=runtime,
    )


def test_fingerprint_ignores_runtime_ids_timestamps_source_sha_and_timings() -> None:
    first = make_report_body(
        source_revision="a" * 40,
        generated_at=datetime(2026, 8, 26, tzinfo=UTC),
        record_id="11111111-1111-4111-8111-111111111111",
        local_runtime_ms=10.0,
    )
    second = make_report_body(
        source_revision="b" * 40,
        generated_at=datetime(2026, 8, 27, tzinfo=UTC),
        record_id="22222222-2222-4222-8222-222222222222",
        local_runtime_ms=999.0,
    )
    assert normalized_evidence_payload(first) == normalized_evidence_payload(second)
    assert evidence_fingerprint(first) == evidence_fingerprint(second)


def test_fingerprint_changes_when_deterministic_observation_changes() -> None:
    first = make_report_body(observed_value={"step_count": 6})
    second = make_report_body(observed_value={"step_count": 7})
    assert evidence_fingerprint(first) != evidence_fingerprint(second)


def test_fingerprint_omits_observation_marked_as_volatile() -> None:
    reproducibility = ClaimReproducibility(
        deterministic=False,
        included_in_fingerprint=False,
    )
    first = make_report_body(observed_value={"runtime_ms": 10.0})
    second = make_report_body(observed_value={"runtime_ms": 999.0})
    first_claim = first.claims[0].model_copy(
        update={"reproducibility": reproducibility}
    )
    second_claim = second.claims[0].model_copy(
        update={"reproducibility": reproducibility}
    )
    first = first.model_copy(update={"claims": (first_claim,)})
    second = second.model_copy(update={"claims": (second_claim,)})

    payload = normalized_evidence_payload(first)
    assert "observed_value" not in payload["claims"][0]
    assert payload == normalized_evidence_payload(second)
    assert evidence_fingerprint(first) == evidence_fingerprint(second)
