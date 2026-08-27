"""Audit coverage and provenance projections for a canonical evidence run."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class _DynamicAuditProbe:
    incident_id: object
    report_id: object
    decisions: tuple[object, ...]
    history: object
    audit_events: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class _TradeoffAuditProbe:
    history: object
    audit_events: tuple[object, ...]


def collect_audit_claims(result: CanonicalEvidenceRun) -> tuple[EvidenceClaim, ...]:
    """Verify the durable coverage rule against records from the canonical run."""

    dynamic_probe = _dynamic_audit_evidence(result)
    tradeoff_probe = _tradeoff_audit_evidence(result)
    missing = _missing_categories(result, dynamic_probe, tradeoff_probe)
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
            evidence_refs=_coverage_references(
                result,
                dynamic_probe,
                tradeoff_probe,
            ),
            caveat=(
                "Credential-free deterministic canonical replay with a retained "
                "same-session supplemental human-tradeoff fixture."
            ),
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


def _missing_categories(
    result: CanonicalEvidenceRun,
    dynamic_probe: _DynamicAuditProbe,
    tradeoff_probe: _TradeoffAuditProbe,
) -> tuple[str, ...]:
    dynamic = result.dynamic_history
    carrier = result.carrier_history
    safety = result.safety_history
    replacement_chain = _carrier_replacement_chain(carrier)

    covered = {
        "incident_recovery_decisions": (
            result.agent_run.incident_id == result.incident_id
            and bool(dynamic.revisions)
            and bool(carrier.decisions)
            and all(
                revision.source_phase2_evaluation_id
                for revision in dynamic.revisions
            )
            and _incident_recovery_audit_is_linked(dynamic_probe)
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
            and _dynamic_reconsideration_audit_is_linked(dynamic_probe)
        ),
        "allocation_supersession_tradeoff": _tradeoff_chain_is_linked(
            tradeoff_probe
        ),
        "operator_approvals": _operator_approval_lineage(carrier) is not None,
        "carrier_response_timeout": _has_carrier_response_or_timeout(
            carrier,
        ),
        "carrier_recovery_replacement": (
            replacement_chain is not None
        ),
        "safety_escalation": _safety_escalation_is_linked(safety),
        "agent_orchestration": _agent_orchestration_lineage(result) is not None,
    }
    return tuple(
        category for category in REQUIRED_MATERIAL_COVERAGE if not covered[category]
    )


def _coverage_references(
    result: CanonicalEvidenceRun,
    dynamic_probe: _DynamicAuditProbe,
    tradeoff_probe: _TradeoffAuditProbe,
) -> tuple[EvidenceReference, ...]:
    carrier = result.carrier_history
    safety = result.safety_history
    dynamic_lineage = _dynamic_reconsideration_audit_is_linked(dynamic_probe)
    tradeoff_lineage = _tradeoff_chain_is_linked(tradeoff_probe)
    replacement_chain = _carrier_replacement_chain(carrier)
    response_lineage = _has_carrier_response_or_timeout(carrier)
    approval_lineage = _operator_approval_lineage(carrier)
    safety_lineage = _safety_escalation_is_linked(safety)
    agent_lineage = _agent_orchestration_lineage(result)
    request = carrier.request
    request_context = carrier.request_context
    assessment = safety.assessment
    policy = safety.policy_result

    if (
        request is None
        or request_context is None
        or assessment is None
        or policy is None
        or dynamic_lineage is None
        or tradeoff_lineage is None
        or replacement_chain is None
        or response_lineage is None
        or approval_lineage is None
        or safety_lineage is None
        or agent_lineage is None
    ):
        raise EvidenceInvariantFailure(
            "audit_material_action_coverage",
            "coverage references require complete canonical durable histories",
        )

    (
        incident_lineage,
        dynamic_snapshot,
        dynamic_parent_revision,
        dynamic_commitment,
        dynamic_assessment,
        dynamic_child_revision,
        dynamic_snapshot_event,
        dynamic_assessment_event,
        dynamic_revision_event,
    ) = dynamic_lineage
    (
        phase2_decision,
        incident_event,
        scarcity_event,
        phase2_decision_event,
    ) = incident_lineage
    (
        tradeoff_review,
        tradeoff_option,
        tradeoff_selection,
        tradeoff_parent_revision,
        tradeoff_revision,
        tradeoff_selection_event,
        tradeoff_revision_event,
    ) = tradeoff_lineage
    request_binding, request_approval, counter_binding, counter_approval, request_event, counter_event = approval_lineage
    response, response_context, response_event = response_lineage
    (
        safety_note,
        safety_review,
        safety_assessment,
        safety_policy,
        safety_assessment_event,
        safety_policy_event,
        safety_decision_event,
    ) = safety_lineage
    agent_step, agent_invocation = agent_lineage
    (
        replacement_result,
        replacement_decision,
        replacement_link,
        replacement_event,
    ) = replacement_chain

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
            "build_scarce_capacity_workflow.run",
            dynamic_probe.report_id,
        ),
        _reference(
            "Decision",
            "canonical-run:phase2-decision",
            "build_scarce_capacity_workflow.run",
            phase2_decision.id,
        ),
        _reference(
            "YardForecastSnapshot",
            "canonical-run:yard-snapshot",
            "DynamicYardRepository.history",
            dynamic_snapshot.id,
        ),
        _reference(
            "AllocationRevision",
            "canonical-run:allocation-revision",
            "DynamicYardRepository.history",
            dynamic_child_revision.id,
        ),
        _reference(
            "ExpediteCommitment",
            "canonical-run:expedite-commitment",
            "DynamicYardRepository.history",
            dynamic_commitment.id,
        ),
        _reference(
            "ExpediteReconsiderationAssessment",
            "canonical-run:reconsideration-assessment",
            "DynamicYardRepository.history",
            dynamic_assessment.id,
        ),
        _reference(
            "AllocationTradeoffHistory",
            "canonical-run:dynamic-history",
            "DynamicYardWorkflow.history",
            dynamic_probe.incident_id,
        ),
        _reference(
            "AllocationTradeoffReview",
            "supplemental-tradeoff:review",
            "DynamicYardWorkflow.select_tradeoff",
            tradeoff_review.id,
        ),
        _reference(
            "AllocationTradeoffOption",
            "supplemental-tradeoff:option",
            "DynamicYardWorkflow.select_tradeoff",
            tradeoff_option.id,
        ),
        _reference(
            "AllocationTradeoffSelection",
            "supplemental-tradeoff:selection",
            "DynamicYardWorkflow.select_tradeoff",
            tradeoff_selection.id,
        ),
        _reference(
            "AllocationRevision",
            "supplemental-tradeoff:child-revision",
            "DynamicYardWorkflow.select_tradeoff",
            tradeoff_revision.id,
        ),
        _reference(
            "ApprovalBinding",
            "canonical-run:approval-binding",
            "CarrierRecoveryRepository.history",
            request_binding.proposal_decision_id,
        ),
        _reference(
            "Approval",
            "canonical-run:operator-approval",
            "CarrierRecoveryRepository.history",
            request_approval.id,
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
            response_context.case_id,
        ),
        _reference(
            "ContainerReconsiderationResult",
            "canonical-run:carrier-reconsideration-result",
            "CarrierRecoveryRepository.history",
            replacement_result.id,
        ),
        _reference(
            "Decision",
            "canonical-run:carrier-replacement-decision",
            "CarrierRecoveryRepository.history",
            replacement_decision.id,
        ),
        _reference(
            "CarrierRecoveryDecisionLink",
            "canonical-run:carrier-decision-link",
            "CarrierRecoveryRepository.history",
            replacement_link.decision_id,
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
            safety_note.id,
        ),
        _reference(
            "CargoSafetyReview",
            "canonical-run:cargo-safety-review",
            "CargoSafetyRepository.history",
            safety_review.id,
        ),
        _reference(
            "SemanticSafetyAssessment",
            "canonical-run:semantic-safety-assessment",
            "CargoSafetyRepository.history",
            safety_assessment.id,
        ),
        _reference(
            "SemanticSafetyPolicyResult",
            "canonical-run:semantic-safety-policy",
            "CargoSafetyRepository.history",
            safety_policy.id,
        ),
        _reference(
            "CargoSafetyHistory",
            "canonical-run:safety-history",
            "CargoSafetyRepository.history",
            safety_review.id,
        ),
        _reference(
            "Decision",
            "canonical-run:safety-escalation-decision",
            "CargoSafetyHistory.policy_result",
            safety_policy.replacement_decision_id,
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
            agent_step.id,
        ),
        _reference(
            "AgentToolInvocation",
            "canonical-run:agent-tool-invocation",
            "AgentRuntimeRepository.history",
            agent_invocation.id,
        ),
        _reference(
            "AgentHistory",
            "canonical-run:agent-history",
            "AgentRuntimeRepository.history",
            result.agent_run.id,
        ),
    ]
    if response is not None:
        references.append(
            _reference(
                "CarrierResponse",
                "canonical-run:carrier-response",
                "CarrierRecoveryRepository.history",
                response.id,
            )
        )
    else:
        references.append(
            _reference(
                "RTARequestContext",
                "canonical-run:carrier-timeout-context",
                "CarrierRecoveryRepository.history",
                response_context.case_id,
            )
        )

    timing = next(
        (
            item
            for item in carrier.effective_timings
            if item.id == replacement_result.effective_connection_timing_id
            and item.case_id == carrier.case.id
            and item.request_id == request.id
        ),
        None,
    )
    if timing is not None:
        references.append(
            _reference(
                "EffectiveConnectionTiming",
                "canonical-run:effective-connection-timing",
                "CarrierRecoveryRepository.history",
                timing.id,
            )
        )
    elif replacement_result.timeout_request_context_id is not None:
        references.append(
            _reference(
                "RTARequestContext",
                "canonical-run:replacement-timeout-context",
                "CarrierRecoveryRepository.history",
                replacement_result.timeout_request_context_id,
            )
        )
    elif replacement_result.rejected_approval_id is not None:
        references.append(
            _reference(
                "Approval",
                "canonical-run:replacement-rejected-approval",
                "CarrierRecoveryRepository.history",
                replacement_result.rejected_approval_id,
            )
        )

    references.extend(
        (
            _reference("AuditEvent", "canonical-run:audit:incident.created", "AuditRepository.list_for_incident", incident_event.id),
            _reference("AuditEvent", "canonical-run:audit:scarcity.evaluation_persisted", "AuditRepository.list_for_incident", scarcity_event.id),
            _reference("AuditEvent", "canonical-run:audit:decision.created", "AuditRepository.list_for_incident", phase2_decision_event.id),
            _reference("AuditEvent", "canonical-run:audit:yard_forecast.snapshot_ingested", "AuditRepository.list_for_incident", dynamic_snapshot_event.id),
            _reference("AuditEvent", "canonical-run:audit:expedite_reconsideration.assessed", "AuditRepository.list_for_incident", dynamic_assessment_event.id),
            _reference("AuditEvent", "canonical-run:audit:allocation_revision.applied", "AuditRepository.list_for_incident", dynamic_revision_event.id),
            _reference("AuditEvent", "supplemental-tradeoff:audit:option_selected", "AuditRepository.list_for_incident", tradeoff_selection_event.id),
            _reference("AuditEvent", "supplemental-tradeoff:audit:allocation_revision.applied", "AuditRepository.list_for_incident", tradeoff_revision_event.id),
            _reference("AuditEvent", f"canonical-run:audit:{request_event.event_type}", "CarrierRecoveryRepository.history", request_event.id),
            _reference("AuditEvent", f"canonical-run:audit:{counter_event.event_type}", "CarrierRecoveryRepository.history", counter_event.id),
            _reference("AuditEvent", f"canonical-run:audit:{response_event.event_type}", "CarrierRecoveryRepository.history", response_event.id),
            _reference("AuditEvent", "canonical-run:audit:carrier_recovery.replacement_recorded", "CarrierRecoveryRepository.history", replacement_event.id),
            _reference("AuditEvent", "canonical-run:audit:cargo.semantic_assessment_completed", "CargoSafetyRepository.history", safety_assessment_event.id),
            _reference("AuditEvent", "canonical-run:audit:cargo.semantic_safety_evaluated", "CargoSafetyRepository.history", safety_policy_event.id),
            _reference("AuditEvent", "canonical-run:audit:decision.escalated_for_cargo_review", "CargoSafetyRepository.history", safety_decision_event.id),
        )
    )
    return tuple(references)


def _has_carrier_response_or_timeout(carrier):
    if carrier.carrier_responses:
        return next(
            (
                (response, carrier.request_context, event)
                for response in carrier.carrier_responses
                for event in carrier.audit_events
                if event.event_type == "carrier.response_received"
                and event.payload.get("recovery_case_id") == str(carrier.case.id)
                and event.payload.get("request_id") == str(response.request_id)
                and event.payload.get("carrier_response_id") == str(response.id)
            ),
            None,
        )
    context = carrier.request_context
    if (
        context is None
        or context.timeout_observed_at is None
        or context.close_reason is None
        or context.close_reason.value != "RESPONSE_TIMEOUT"
    ):
        return None
    return next(
        (
            (None, context, event)
            for event in carrier.audit_events
            if event.event_type == "carrier.response_timed_out"
            and event.payload.get("recovery_case_id") == str(carrier.case.id)
            and event.payload.get("request_id") == str(context.request_id)
        ),
        None,
    )


def _operator_approval_lineage(carrier):
    """Return both durable approval bindings with their matching audit events."""

    request_binding = next(
        (
            binding
            for binding in carrier.bindings
            if binding.subject_kind.value == "OUTBOUND_REQUEST"
            and carrier.request is not None
            and binding.subject_id == carrier.request.id
        ),
        None,
    )
    counter_binding = next(
        (
            binding
            for binding in carrier.bindings
            if binding.subject_kind.value == "COUNTER_PROPOSAL"
        ),
        None,
    )
    if request_binding is None or counter_binding is None:
        return None
    request_approval = next(
        (
            approval
            for approval in carrier.approvals
            if approval.decision_id == request_binding.proposal_decision_id
        ),
        None,
    )
    counter_approval = next(
        (
            approval
            for approval in carrier.approvals
            if approval.decision_id == counter_binding.proposal_decision_id
        ),
        None,
    )
    request_event = next(
        (
            event
            for event in carrier.audit_events
            if event.event_type == "carrier_recovery.request_approval_recorded"
            and event.payload.get("recovery_case_id") == str(carrier.case.id)
            and event.payload.get("proposal_decision_id")
            == str(request_binding.proposal_decision_id)
            and event.payload.get("subject_id") == str(request_binding.subject_id)
        ),
        None,
    )
    counter_event = next(
        (
            event
            for event in carrier.audit_events
            if event.event_type == "carrier.counter_approval_recorded"
            and event.payload.get("recovery_case_id") == str(carrier.case.id)
            and event.payload.get("proposal_decision_id")
            == str(counter_binding.proposal_decision_id)
            and event.payload.get("carrier_response_id")
            == str(counter_binding.subject_id)
        ),
        None,
    )
    if request_approval and counter_approval and request_event and counter_event:
        return (
            request_binding,
            request_approval,
            counter_binding,
            counter_approval,
            request_event,
            counter_event,
        )
    return None


def _agent_orchestration_lineage(result: CanonicalEvidenceRun):
    """Return a persisted invocation joined to its step, never an array position."""

    if result.agent_history.run.id != result.agent_run.id:
        return None
    steps = {step.id: step for step in result.agent_history.steps}
    invocation = next(
        (
            item
            for item in result.agent_history.tool_invocations
            if item.step_id in steps
        ),
        None,
    )
    if invocation is None:
        return None
    return steps[invocation.step_id], invocation


def _dynamic_reconsideration_audit_is_linked(probe: _DynamicAuditProbe):
    """Return the exact scarcity and yard records joined by audit payload IDs."""

    history = probe.history
    events = probe.audit_events
    incident_lineage = _incident_recovery_audit_is_linked(probe)
    if incident_lineage is None:
        return None

    snapshots = {snapshot.id: snapshot for snapshot in history.snapshots}
    revisions = {revision.id: revision for revision in history.revisions}
    for assessment in history.assessments:
        parent = revisions.get(assessment.prior_allocation_revision_id)
        child = next(
            (
                revision
                for revision in history.revisions
                if revision.parent_revision_id == assessment.prior_allocation_revision_id
                and revision.source_forecast_snapshot_id == assessment.source_snapshot_id
            ),
            None,
        )
        commitment = next(
            (
                item
                for item in history.commitments
                if item.origin_revision_id == assessment.prior_allocation_revision_id
            ),
            None,
        )
        if (
            parent is None
            or child is None
            or commitment is None
            or assessment.source_snapshot_id not in snapshots
        ):
            continue
        snapshot_event = next(
            (
                event
                for event in events
                if event.event_type == "yard_forecast.snapshot_ingested"
                and event.payload.get("snapshot_id") == str(assessment.source_snapshot_id)
            ),
            None,
        )
        assessment_event = next(
            (
                event
                for event in events
                if event.event_type == "expedite_reconsideration.assessed"
                and event.payload.get("assessment_id") == str(assessment.id)
                and event.payload.get("source_snapshot_id")
                == str(assessment.source_snapshot_id)
                and event.payload.get("prior_revision_id") == str(parent.id)
            ),
            None,
        )
        revision_event = next(
            (
                event
                for event in events
                if event.event_type == "allocation_revision.applied"
                and event.payload.get("assessment_id") == str(assessment.id)
                and event.payload.get("parent_revision_id") == str(parent.id)
                and event.payload.get("child_revision_id") == str(child.id)
            ),
            None,
        )
        if snapshot_event and assessment_event and revision_event:
            return (
                incident_lineage,
                snapshots[assessment.source_snapshot_id],
                parent,
                commitment,
                assessment,
                child,
                snapshot_event,
                assessment_event,
                revision_event,
            )
    return None


def _incident_recovery_audit_is_linked(probe: _DynamicAuditProbe):
    """Return the exact canonical incident/report/decision audit lineage."""

    events = probe.audit_events
    incident_id = probe.incident_id
    incident_event = next(
        (
            event
            for event in events
            if event.event_type == "incident.created" and event.incident_id == incident_id
        ),
        None,
    )
    report_event = next(
        (
            event
            for event in events
            if event.event_type == "scarcity.evaluation_persisted"
            and event.incident_id == incident_id
            and event.payload.get("evaluation_id") == str(probe.report_id)
        ),
        None,
    )
    decision = next(
        (
            item
            for item in probe.decisions
            if any(
                event.event_type == "decision.created"
                and event.incident_id == incident_id
                and event.payload.get("decision_id") == str(item.id)
                for event in events
            )
        ),
        None,
    )
    decision_event = None if decision is None else next(
        (
            event
            for event in events
            if event.event_type == "decision.created"
            and event.incident_id == incident_id
            and event.payload.get("decision_id") == str(decision.id)
        ),
        None,
    )
    if incident_event and report_event and decision and decision_event:
        return decision, incident_event, report_event, decision_event
    return None


def _tradeoff_chain_is_linked(probe: _TradeoffAuditProbe):
    """Return one human selection and its audited child allocation revision."""

    history = probe.history
    events = probe.audit_events
    assessments = {assessment.id: assessment for assessment in history.assessments}
    revisions = {revision.id: revision for revision in history.revisions}
    options = {option.id: option for option in history.options}
    for review in history.reviews:
        assessment = assessments.get(review.reconsideration_assessment_id)
        if assessment is None or review.state.value != "RESOLVED":
            continue
        for selection in history.selections:
            option = options.get(selection.selected_option_id)
            if (
                selection.review_id != review.id
                or option is None
                or option.review_id != review.id
                or option.id not in review.option_ids
                or selection.expected_options_fingerprint != review.options_fingerprint
            ):
                continue
            child = next(
                (
                    revision
                    for revision in history.revisions
                    if revision.parent_revision_id
                    == assessment.prior_allocation_revision_id
                    and revision.source_forecast_snapshot_id
                    == assessment.source_snapshot_id
                    and revision.allocated_container_ids == option.allocated_container_ids
                ),
                None,
            )
            parent = revisions.get(assessment.prior_allocation_revision_id)
            if child is None or parent is None:
                continue
            selection_event = next(
                (
                    event
                    for event in events
                    if event.event_type == "allocation_tradeoff.option_selected"
                and event.payload.get("review_id") == str(review.id)
                and event.payload.get("selected_option_id") == str(option.id)
                and event.payload.get("options_fingerprint")
                == review.options_fingerprint
                ),
                None,
            )
            revision_event = next(
                (
                    event
                    for event in events
                    if event.event_type == "allocation_revision.applied"
                and event.payload.get("assessment_id") == str(assessment.id)
                and event.payload.get("parent_revision_id") == str(parent.id)
                and event.payload.get("child_revision_id") == str(child.id)
                ),
                None,
            )
            if selection_event and revision_event:
                return (
                    review,
                    option,
                    selection,
                    parent,
                    child,
                    selection_event,
                    revision_event,
                )
    return None


def _carrier_replacement_chain(carrier):
    """Return one result/decision/link/event chain, never independent records."""

    decisions = {decision.id: decision for decision in carrier.decisions}
    links = {link.decision_id: link for link in carrier.decision_links}
    for result in carrier.results:
        if (
            result.case_id != carrier.case.id
            or result.replacement_decision_id is None
        ):
            continue
        decision = decisions.get(result.replacement_decision_id)
        link = links.get(result.replacement_decision_id)
        if (
            decision is None
            or link is None
            or link.case_id != carrier.case.id
            or decision.incident_id != carrier.case.incident_id
            or decision.container_id != result.container_id
            or decision.supersedes != result.prior_decision_id
        ):
            continue
        event = next(
            (
                item
                for item in carrier.audit_events
                if item.event_type == "carrier_recovery.replacement_recorded"
                and item.payload.get("recovery_case_id") == str(carrier.case.id)
                and item.payload.get("container_id") == result.container_id
                and item.payload.get("prior_decision_id")
                == str(result.prior_decision_id)
                and item.payload.get("replacement_decision_id") == str(decision.id)
            ),
            None,
        )
        if event is not None:
            return result, decision, link, event
    return None


def _safety_escalation_is_linked(safety):
    """Return the safety records and events tied to the escalation Decision ID."""

    assessment = safety.assessment
    policy = safety.policy_result
    if (
        assessment is None
        or policy is None
        or policy.replacement_decision_id is None
        or safety.review.cargo_note_id != safety.note.id
        or assessment.review_id != safety.review.id
        or assessment.cargo_note_id != safety.note.id
        or assessment.incident_id != safety.review.incident_id
        or assessment.container_id != safety.review.container_id
        or policy.review_id != safety.review.id
        or policy.assessment_id != assessment.id
        or policy.incident_id != safety.review.incident_id
        or policy.container_id != safety.review.container_id
        or not policy.automation_blocked
    ):
        return None
    assessment_event = next(
        (
            event
            for event in safety.audit_events
            if event.event_type == "cargo.semantic_assessment_completed"
            and event.payload.get("review_id") == str(safety.review.id)
        ),
        None,
    )
    policy_event = next(
        (
            event
            for event in safety.audit_events
            if event.event_type == "cargo.semantic_safety_evaluated"
            and event.payload.get("review_id") == str(safety.review.id)
        ),
        None,
    )
    escalation_event = next(
        (
            event
            for event in safety.audit_events
            if event.event_type == "decision.escalated_for_cargo_review"
        and event.incident_id == safety.review.incident_id
        and event.payload.get("review_id") == str(safety.review.id)
        and event.payload.get("decision_id") == str(policy.replacement_decision_id)
        and event.payload.get("container_id") == safety.review.container_id
        ),
        None,
    )
    if assessment_event and policy_event and escalation_event:
        return (
            safety.note,
            safety.review,
            assessment,
            policy,
            assessment_event,
            policy_event,
            escalation_event,
        )
    return None


def _dynamic_audit_evidence(result: CanonicalEvidenceRun) -> _DynamicAuditProbe:
    """Project audit evidence persisted alongside the canonical recovery incident."""

    return _DynamicAuditProbe(
        incident_id=result.incident_id,
        report_id=result.phase2_report_id,
        decisions=tuple(result.phase2_decisions),
        history=result.dynamic_history,
        audit_events=tuple(result.dynamic_audit_events),
    )


def _tradeoff_audit_evidence(result: CanonicalEvidenceRun) -> _TradeoffAuditProbe:
    """Project the explicitly retained supplemental tradeoff evidence."""

    return _TradeoffAuditProbe(
        history=result.supplemental_tradeoff_evidence.history,
        audit_events=tuple(result.supplemental_tradeoff_evidence.audit_events),
    )


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
