"""Audit coverage and provenance projections for a canonical evidence run."""

from __future__ import annotations

from collections.abc import Sequence

from backend.app.domain.evidence import (
    ClaimReproducibility,
    ClaimStatus,
    CoverageRole,
    EvidenceClaim,
    EvidenceInvariantFailure,
    EvidenceReference,
    ProvenanceEntry,
)
from backend.app.evaluation.evidence_safety_agent import CanonicalEvidenceRun


REQUIRED_MATERIAL_COVERAGE = (
    "incident_recovery_decisions",
    "allocation_reconsideration",
    "allocation_supersession_tradeoff",
    "operator_approvals",
    "carrier_response_timeout",
    "carrier_recovery_replacement",
    "safety_escalation",
    "agent_orchestration",
)

_FIXTURE_ID = "SYN-CANONICAL-24-V1"


def collect_audit_claims(result: CanonicalEvidenceRun) -> tuple[EvidenceClaim, ...]:
    """Verify the durable coverage rule against records from the canonical run."""

    missing = _missing_categories(result)
    if missing:
        raise EvidenceInvariantFailure(
            "audit_material_action_coverage",
            f"missing coverage: {', '.join(missing)}",
        )

    return (
        EvidenceClaim(
            claim_id="audit_material_action_coverage",
            statement=(
                "Every material action in the canonical recovery journey has a "
                "durable primary record and linked audit or typed-history provenance."
            ),
            status=ClaimStatus.VERIFIED,
            observed_value={
                "required_categories": len(REQUIRED_MATERIAL_COVERAGE),
                "covered_categories": len(REQUIRED_MATERIAL_COVERAGE),
                "missing_categories": [],
            },
            evidence_refs=_coverage_references(result),
            caveat="Credential-free deterministic canonical replay only.",
            reproducibility=ClaimReproducibility(
                deterministic=True,
                included_in_fingerprint=True,
                fixture_ids=(_FIXTURE_ID,),
            ),
        ),
    )


def coverage_role_for(record_type: str) -> CoverageRole:
    if record_type == "AuditEvent":
        return CoverageRole.AUDIT_EVENT
    if record_type.endswith("History"):
        return CoverageRole.TYPED_HISTORY
    if record_type in {"ScarcityBenchmarkReport", "EvaluationSeedManifest"}:
        return CoverageRole.FROZEN_ARTIFACT
    return CoverageRole.PRIMARY_RECORD


def build_provenance_map(
    claims: Sequence[EvidenceClaim],
) -> tuple[ProvenanceEntry, ...]:
    """Flatten non-deferred claim references into stable provenance rows."""

    rows = [
        ProvenanceEntry(
            claim_id=claim.claim_id,
            record_type=reference.record_type,
            stable_key=reference.stable_key,
            source=reference.source,
            record_id=reference.record_id,
            coverage_role=coverage_role_for(reference.record_type),
        )
        for claim in claims
        if claim.status is not ClaimStatus.DEFERRED
        for reference in claim.evidence_refs
    ]
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.claim_id,
                row.record_type,
                row.stable_key,
                row.source,
            ),
        )
    )


def _missing_categories(result: CanonicalEvidenceRun) -> tuple[str, ...]:
    dynamic = result.dynamic_history
    carrier = result.carrier_history
    safety = result.safety_history
    carrier_events = {event.event_type for event in carrier.audit_events}
    safety_events = {event.event_type for event in safety.audit_events}

    covered = {
        "incident_recovery_decisions": (
            result.agent_run.incident_id == result.incident_id
            and bool(dynamic.revisions)
            and bool(carrier.decisions)
            and all(
                revision.source_phase2_evaluation_id
                for revision in dynamic.revisions
            )
        ),
        "allocation_reconsideration": (
            bool(dynamic.snapshots)
            and bool(dynamic.revisions)
            and bool(dynamic.commitments)
            and bool(dynamic.assessments)
            and any(
                assessment.prior_allocation_revision_id
                in {revision.id for revision in dynamic.revisions}
                for assessment in dynamic.assessments
            )
        ),
        "allocation_supersession_tradeoff": (
            any(revision.parent_revision_id is not None for revision in dynamic.revisions)
            and any(assessment.handled_at is not None for assessment in dynamic.assessments)
        ),
        "operator_approvals": (
            carrier.request is not None
            and carrier.request_context is not None
            and bool(carrier.bindings)
            and bool(carrier.approvals)
            and {
                "carrier_recovery.request_approval_recorded",
                "carrier.counter_approval_recorded",
            }.issubset(carrier_events)
        ),
        "carrier_response_timeout": (
            bool(carrier.carrier_responses)
            and "carrier.response_received" in carrier_events
        )
        or (
            carrier.request_context is not None
            and carrier.request_context.timeout_observed_at is not None
            and "carrier.response_timed_out" in carrier_events
        ),
        "carrier_recovery_replacement": (
            bool(carrier.effective_timings)
            and bool(carrier.results)
            and bool(carrier.decision_links)
            and any(
                item.replacement_decision_id is not None for item in carrier.results
            )
            and any(
                decision.supersedes is not None for decision in carrier.decisions
            )
            and "carrier_recovery.replacement_recorded" in carrier_events
        ),
        "safety_escalation": (
            safety.review.cargo_note_id == safety.note.id
            and safety.assessment is not None
            and safety.policy_result is not None
            and safety.policy_result.replacement_decision_id is not None
            and {
                "cargo.semantic_assessment_completed",
                "cargo.semantic_safety_evaluated",
                "decision.escalated_for_cargo_review",
            }.issubset(safety_events)
        ),
        "agent_orchestration": (
            bool(result.agent_history.steps)
            and bool(result.agent_history.tool_invocations)
            and {step.id for step in result.agent_history.steps}.issuperset(
                invocation.step_id
                for invocation in result.agent_history.tool_invocations
            )
            and result.agent_history.run.id == result.agent_run.id
        ),
    }
    return tuple(
        category for category in REQUIRED_MATERIAL_COVERAGE if not covered[category]
    )


def _coverage_references(result: CanonicalEvidenceRun) -> tuple[EvidenceReference, ...]:
    dynamic = result.dynamic_history
    carrier = result.carrier_history
    safety = result.safety_history
    latest_revision = dynamic.revisions[-1]
    latest_assessment = dynamic.assessments[-1]
    request = carrier.request
    request_context = carrier.request_context
    assessment = safety.assessment
    policy = safety.policy_result

    if request is None or request_context is None or assessment is None or policy is None:
        raise EvidenceInvariantFailure(
            "audit_material_action_coverage",
            "coverage references require complete canonical durable histories",
        )

    references = [
        _reference(
            "Incident",
            "canonical-run:incident",
            "CanonicalEvidenceRun",
            result.incident_id,
        ),
        _reference(
            "ScarcityEvaluationReport",
            "canonical-run:phase2-evaluation",
            "AllocationRevision.source_phase2_evaluation_id",
            latest_revision.source_phase2_evaluation_id,
        ),
        _reference(
            "Decision",
            "canonical-run:carrier-decision",
            "CarrierRecoveryRepository.history",
            carrier.decisions[-1].id,
        ),
        _reference(
            "YardForecastSnapshot",
            "canonical-run:yard-snapshot",
            "DynamicYardRepository.history",
            dynamic.snapshots[-1].id,
        ),
        _reference(
            "AllocationRevision",
            "canonical-run:allocation-revision",
            "DynamicYardRepository.history",
            latest_revision.id,
        ),
        _reference(
            "ExpediteCommitment",
            "canonical-run:expedite-commitment",
            "DynamicYardRepository.history",
            dynamic.commitments[0].id,
        ),
        _reference(
            "ExpediteReconsiderationAssessment",
            "canonical-run:reconsideration-assessment",
            "DynamicYardRepository.history",
            latest_assessment.id,
        ),
        _reference(
            "AllocationTradeoffHistory",
            "canonical-run:dynamic-history",
            "DynamicYardWorkflow.history",
            result.incident_id,
        ),
        _reference(
            "ApprovalBinding",
            "canonical-run:approval-binding",
            "CarrierRecoveryRepository.history",
            carrier.bindings[0].proposal_decision_id,
        ),
        _reference(
            "Approval",
            "canonical-run:operator-approval",
            "CarrierRecoveryRepository.history",
            carrier.approvals[-1].id,
        ),
        _reference(
            "RTARequest",
            "canonical-run:rta-request",
            "CarrierRecoveryRepository.history",
            request.id,
        ),
        _reference(
            "RTARequestContext",
            "canonical-run:rta-request-context",
            "CarrierRecoveryRepository.history",
            request_context.case_id,
        ),
        _reference(
            "CarrierResponse",
            "canonical-run:carrier-response",
            "CarrierRecoveryRepository.history",
            carrier.carrier_responses[-1].id,
        ),
        _reference(
            "EffectiveConnectionTiming",
            "canonical-run:effective-connection-timing",
            "CarrierRecoveryRepository.history",
            carrier.effective_timings[-1].id,
        ),
        _reference(
            "ContainerReconsiderationResult",
            "canonical-run:carrier-reconsideration-result",
            "CarrierRecoveryRepository.history",
            carrier.results[-1].id,
        ),
        _reference(
            "CarrierRecoveryDecisionLink",
            "canonical-run:carrier-decision-link",
            "CarrierRecoveryRepository.history",
            carrier.decision_links[-1].decision_id,
        ),
        _reference(
            "CarrierRecoveryHistory",
            "canonical-run:carrier-history",
            "CarrierRecoveryRepository.history",
            carrier.case.id,
        ),
        _reference(
            "CargoNote",
            "canonical-run:cargo-note",
            "CargoSafetyRepository.history",
            safety.note.id,
        ),
        _reference(
            "CargoSafetyReview",
            "canonical-run:cargo-safety-review",
            "CargoSafetyRepository.history",
            safety.review.id,
        ),
        _reference(
            "SemanticSafetyAssessment",
            "canonical-run:semantic-safety-assessment",
            "CargoSafetyRepository.history",
            assessment.id,
        ),
        _reference(
            "SemanticSafetyPolicyResult",
            "canonical-run:semantic-safety-policy",
            "CargoSafetyRepository.history",
            policy.id,
        ),
        _reference(
            "CargoSafetyHistory",
            "canonical-run:safety-history",
            "CargoSafetyRepository.history",
            safety.review.id,
        ),
        _reference(
            "AgentRun",
            "canonical-run:agent-run",
            "AgentRuntimeRepository.history",
            result.agent_run.id,
        ),
        _reference(
            "AgentStep",
            "canonical-run:agent-step",
            "AgentRuntimeRepository.history",
            result.agent_history.steps[-1].id,
        ),
        _reference(
            "AgentToolInvocation",
            "canonical-run:agent-tool-invocation",
            "AgentRuntimeRepository.history",
            result.agent_history.tool_invocations[-1].id,
        ),
        _reference(
            "AgentHistory",
            "canonical-run:agent-history",
            "AgentRuntimeRepository.history",
            result.agent_run.id,
        ),
    ]
    references.extend(
        _reference(
            "AuditEvent",
            f"canonical-run:audit:{event.event_type}",
            "CarrierRecoveryRepository.history",
            event.id,
        )
        for event in carrier.audit_events
        if event.event_type
        in {
            "carrier_recovery.request_approval_recorded",
            "carrier.counter_approval_recorded",
            "carrier.response_received",
            "carrier_recovery.replacement_recorded",
        }
    )
    references.extend(
        _reference(
            "AuditEvent",
            f"canonical-run:audit:{event.event_type}",
            "CargoSafetyRepository.history",
            event.id,
        )
        for event in safety.audit_events
    )
    return tuple(references)


def _reference(
    record_type: str,
    stable_key: str,
    source: str,
    record_id: object,
) -> EvidenceReference:
    return EvidenceReference(
        record_type=record_type,
        stable_key=stable_key,
        source=source,
        record_id=str(record_id),
    )
