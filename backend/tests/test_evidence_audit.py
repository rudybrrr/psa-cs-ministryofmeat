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


def test_coverage_references_real_dynamic_and_tradeoff_audit_chains(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)

    claim = collect_audit_claims(canonical_evidence_run)[0]
    references = {
        (reference.record_type, reference.stable_key, reference.source)
        for reference in claim.evidence_refs
    }

    assert {
        "AllocationTradeoffReview",
        "AllocationTradeoffOption",
        "AllocationTradeoffSelection",
    } <= {reference.record_type for reference in claim.evidence_refs}
    assert {
        (
            "AuditEvent",
            "canonical-run:audit:scarcity.evaluation_persisted",
            "AuditRepository.list_for_incident",
        ),
        (
            "AuditEvent",
            "canonical-run:audit:expedite_reconsideration.assessed",
            "AuditRepository.list_for_incident",
        ),
        (
            "AuditEvent",
            "canonical-run:audit:allocation_revision.applied",
            "AuditRepository.list_for_incident",
        ),
        (
            "AuditEvent",
            "supplemental-tradeoff:audit:option_selected",
            "AuditRepository.list_for_incident",
        ),
    } <= references
    canonical_event_ids = {
        str(event.id) for event in canonical_evidence_run.dynamic_audit_events
    }
    supplemental_event_ids = {
        str(event.id)
        for event in canonical_evidence_run.supplemental_tradeoff_evidence.audit_events
    }
    audit_rows = [
        row
        for row in claim.evidence_refs
        if row.record_type == "AuditEvent"
        and row.source == "AuditRepository.list_for_incident"
    ]
    assert all(
        row.record_id in canonical_event_ids | supplemental_event_ids
        for row in audit_rows
    )


def test_broken_replacement_link_fails_coverage(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)
    fallback = next(
        decision
        for decision in canonical_evidence_run.carrier_history.decisions
        if decision.supersedes is None
    )
    broken_links = tuple(
        link.model_copy(update={"decision_id": fallback.id})
        for link in canonical_evidence_run.carrier_history.decision_links
    )
    broken = canonical_evidence_run.model_copy(
        update={
            "carrier_history": canonical_evidence_run.carrier_history.model_copy(
                update={"decision_links": broken_links}
            )
        }
    )

    with pytest.raises(EvidenceInvariantFailure, match="carrier_recovery_replacement"):
        collect_audit_claims(broken)


def test_safety_escalation_requires_matching_decision_audit_event(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)
    broken_events = tuple(
        event.model_copy(update={"payload": {"decision_id": "wrong-decision"}})
        if event.event_type == "decision.escalated_for_cargo_review"
        else event
        for event in canonical_evidence_run.safety_history.audit_events
    )
    broken = canonical_evidence_run.model_copy(
        update={
            "safety_history": canonical_evidence_run.safety_history.model_copy(
                update={"audit_events": broken_events}
            )
        }
    )

    with pytest.raises(EvidenceInvariantFailure, match="safety_escalation"):
        collect_audit_claims(broken)


def test_missing_response_without_timeout_evidence_fails_without_indexing(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)
    broken = canonical_evidence_run.model_copy(
        update={
            "carrier_history": canonical_evidence_run.carrier_history.model_copy(
                update={"carrier_responses": ()}
            )
        }
    )

    with pytest.raises(EvidenceInvariantFailure, match="carrier_response_timeout"):
        collect_audit_claims(broken)


def test_carrier_response_audit_event_must_identify_the_persisted_response(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)
    broken_events = tuple(
        event.model_copy(
            update={
                "payload": {
                    **event.payload,
                    "carrier_response_id": "wrong-response",
                }
            }
        )
        if event.event_type == "carrier.response_received"
        else event
        for event in canonical_evidence_run.carrier_history.audit_events
    )
    broken = canonical_evidence_run.model_copy(
        update={
            "carrier_history": canonical_evidence_run.carrier_history.model_copy(
                update={"audit_events": broken_events}
            )
        }
    )

    with pytest.raises(EvidenceInvariantFailure, match="carrier_response_timeout"):
        collect_audit_claims(broken)


def test_safety_escalation_audit_event_must_identify_its_review(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)
    broken_events = tuple(
        event.model_copy(
            update={"payload": {**event.payload, "review_id": "wrong-review"}}
        )
        if event.event_type == "decision.escalated_for_cargo_review"
        else event
        for event in canonical_evidence_run.safety_history.audit_events
    )
    broken = canonical_evidence_run.model_copy(
        update={
            "safety_history": canonical_evidence_run.safety_history.model_copy(
                update={"audit_events": broken_events}
            )
        }
    )

    with pytest.raises(EvidenceInvariantFailure, match="safety_escalation"):
        collect_audit_claims(broken)


def test_canonical_reconsideration_requires_events_linked_to_its_durable_records(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)
    broken_events = tuple(
        event.model_copy(
            update={"payload": {**event.payload, "evaluation_id": "wrong-report"}}
        )
        if event.event_type == "scarcity.evaluation_persisted"
        else event
        for event in canonical_evidence_run.dynamic_audit_events
    )
    broken = canonical_evidence_run.model_copy(
        update={"dynamic_audit_events": broken_events}
    )

    with pytest.raises(EvidenceInvariantFailure, match="allocation_reconsideration"):
        collect_audit_claims(broken)


def test_provenance_uses_audited_dynamic_lineage_not_history_position(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)
    reordered = canonical_evidence_run.model_copy(
        update={
            "dynamic_history": canonical_evidence_run.dynamic_history.model_copy(
                update={
                    "revisions": tuple(
                        reversed(canonical_evidence_run.dynamic_history.revisions)
                    )
                }
            )
        }
    )

    claim = collect_audit_claims(reordered)[0]
    revision_event = next(
        event
        for event in reordered.dynamic_audit_events
        if event.event_type == "allocation_revision.applied"
    )
    revision_reference = next(
        reference
        for reference in claim.evidence_refs
        if reference.stable_key == "canonical-run:allocation-revision"
    )

    assert revision_reference.record_id == revision_event.payload["child_revision_id"]


def test_tradeoff_probe_requires_review_option_selection_and_revision_lineage(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)
    tradeoff_evidence = canonical_evidence_run.supplemental_tradeoff_evidence
    tradeoff_history = tradeoff_evidence.history
    selection = tradeoff_history.selections[-1]
    broken_selection = selection.model_copy(update={"selected_option_id": selection.id})
    broken_history = tradeoff_history.model_copy(
        update={"selections": (*tradeoff_history.selections[:-1], broken_selection)}
    )
    broken = canonical_evidence_run.model_copy(
        update={
            "supplemental_tradeoff_evidence": tradeoff_evidence.model_copy(
                update={"history": broken_history}
            )
        }
    )

    with pytest.raises(
        EvidenceInvariantFailure, match="allocation_supersession_tradeoff"
    ):
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
