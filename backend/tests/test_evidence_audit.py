from __future__ import annotations

import pytest

from backend.app.domain.evidence import (
    ClaimStatus,
    EvidenceClaim,
    EvidenceInvariantFailure,
    EvidenceReference,
)
from backend.app.evaluation.evidence_audit import (
    build_provenance_map,
    collect_audit_claims,
)
from backend.app.evaluation.evidence_safety_agent import (
    run_canonical_evidence_scenario,
)


def test_material_action_coverage_is_complete(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)

    claims = {
        claim.claim_id: claim for claim in collect_audit_claims(canonical_evidence_run)
    }

    assert claims["audit_material_action_coverage"].observed_value == {
        "required_categories": 8,
        "covered_categories": 8,
        "missing_categories": [],
    }


def test_missing_agent_invocation_history_fails_verified_coverage(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)
    broken = canonical_evidence_run.model_copy(
        update={
            "agent_history": canonical_evidence_run.agent_history.model_copy(
                update={"tool_invocations": ()}
            )
        }
    )

    with pytest.raises(EvidenceInvariantFailure, match="agent_orchestration"):
        collect_audit_claims(broken)


def test_provenance_map_sorts_roles_and_omits_deferred_references() -> None:
    verified = EvidenceClaim(
        claim_id="audit_material_action_coverage",
        statement="Every material action has durable provenance.",
        status=ClaimStatus.VERIFIED,
        observed_value=True,
        caveat="Deterministic evidence only.",
        evidence_refs=(
            EvidenceReference(
                record_type="AuditEvent",
                stable_key="event:recovery",
                source="AuditRepository.list_for_incident",
                record_id="event-id",
            ),
            EvidenceReference(
                record_type="CarrierRecoveryHistory",
                stable_key="history:carrier",
                source="CarrierRecoveryRepository.history",
                record_id="case-id",
            ),
            EvidenceReference(
                record_type="Approval",
                stable_key="approval:request",
                source="CarrierRecoveryRepository.history",
                record_id="approval-id",
            ),
            EvidenceReference(
                record_type="EvaluationSeedManifest",
                stable_key="manifest:holdout",
                source="load_evaluation_seed_manifest",
                record_id="manifest-id",
            ),
        ),
    )
    deferred = EvidenceClaim(
        claim_id="live_model_cost",
        statement="Live model cost remains outside this phase.",
        status=ClaimStatus.DEFERRED,
        observed_value=None,
        caveat="DEFERRED_TO_PHASE_9",
        evidence_refs=(
            EvidenceReference(
                record_type="AgentHistory",
                stable_key="history:deferred",
                source="AgentRuntimeRepository.history",
                record_id="not-a-row",
            ),
        ),
    )

    rows = build_provenance_map((deferred, verified))

    assert [
        (row.record_type, row.stable_key, row.source, row.record_id, row.coverage_role)
        for row in rows
    ] == [
        (
            "Approval",
            "approval:request",
            "CarrierRecoveryRepository.history",
            "approval-id",
            "PRIMARY_RECORD",
        ),
        (
            "AuditEvent",
            "event:recovery",
            "AuditRepository.list_for_incident",
            "event-id",
            "AUDIT_EVENT",
        ),
        (
            "CarrierRecoveryHistory",
            "history:carrier",
            "CarrierRecoveryRepository.history",
            "case-id",
            "TYPED_HISTORY",
        ),
        (
            "EvaluationSeedManifest",
            "manifest:holdout",
            "load_evaluation_seed_manifest",
            "manifest-id",
            "FROZEN_ARTIFACT",
        ),
    ]
