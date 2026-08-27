"""Audit coverage and provenance projections for a canonical evidence run."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

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
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.orchestration.scarce_capacity import (
    ScarcityRecoveryResult,
    build_scarce_capacity_workflow,
)
from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness
from backend.app.storage.repositories import AuditRepository


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
    recovery: ScarcityRecoveryResult
    history: object
    audit_events: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class _TradeoffAuditProbe:
    history: object
    audit_events: tuple[object, ...]


def collect_audit_claims(result: CanonicalEvidenceRun) -> tuple[EvidenceClaim, ...]:
    """Verify the durable coverage rule against records from the canonical run."""

    dynamic_probe = _dynamic_audit_probe()
    tradeoff_probe = _tradeoff_audit_probe()
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


def _missing_categories(
    result: CanonicalEvidenceRun,
    dynamic_probe: _DynamicAuditProbe,
    tradeoff_probe: _TradeoffAuditProbe,
) -> tuple[str, ...]:
    dynamic = result.dynamic_history
    carrier = result.carrier_history
    safety = result.safety_history
    carrier_events = {event.event_type for event in carrier.audit_events}
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
        "carrier_response_timeout": _has_carrier_response_or_timeout(
            carrier,
        ),
        "carrier_recovery_replacement": (
            replacement_chain is not None
        ),
        "safety_escalation": _safety_escalation_is_linked(safety),
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


def _coverage_references(
    result: CanonicalEvidenceRun,
    dynamic_probe: _DynamicAuditProbe,
    tradeoff_probe: _TradeoffAuditProbe,
) -> tuple[EvidenceReference, ...]:
    carrier = result.carrier_history
    safety = result.safety_history
    probe_history = dynamic_probe.history
    latest_revision = probe_history.revisions[-1]
    latest_assessment = probe_history.assessments[-1]
    tradeoff_history = tradeoff_probe.history
    tradeoff_review = tradeoff_history.reviews[-1]
    tradeoff_option = tradeoff_history.options[-1]
    tradeoff_selection = tradeoff_history.selections[-1]
    tradeoff_revision = next(
        revision
        for revision in reversed(tradeoff_history.revisions)
        if revision.parent_revision_id is not None
    )
    replacement_chain = _carrier_replacement_chain(carrier)
    request = carrier.request
    request_context = carrier.request_context
    assessment = safety.assessment
    policy = safety.policy_result

    if (
        request is None
        or request_context is None
        or assessment is None
        or policy is None
        or replacement_chain is None
    ):
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
            "deterministic-audit-probe:phase2-evaluation",
            "build_scarce_capacity_workflow.run",
            dynamic_probe.recovery.report.id,
        ),
        _reference(
            "Decision",
            "deterministic-audit-probe:phase2-decision",
            "build_scarce_capacity_workflow.run",
            dynamic_probe.recovery.decisions[-1].id,
        ),
        _reference(
            "YardForecastSnapshot",
            "deterministic-audit-probe:yard-snapshot",
            "DynamicYardRepository.history",
            probe_history.snapshots[-1].id,
        ),
        _reference(
            "AllocationRevision",
            "deterministic-audit-probe:allocation-revision",
            "DynamicYardRepository.history",
            latest_revision.id,
        ),
        _reference(
            "ExpediteCommitment",
            "deterministic-audit-probe:expedite-commitment",
            "DynamicYardRepository.history",
            probe_history.commitments[0].id,
        ),
        _reference(
            "ExpediteReconsiderationAssessment",
            "deterministic-audit-probe:reconsideration-assessment",
            "DynamicYardRepository.history",
            latest_assessment.id,
        ),
        _reference(
            "AllocationTradeoffHistory",
            "deterministic-audit-probe:dynamic-history",
            "DynamicYardWorkflow.history",
            dynamic_probe.recovery.incident.id,
        ),
        _reference(
            "AllocationTradeoffReview",
            "deterministic-tradeoff:review",
            "DynamicYardWorkflow.select_tradeoff",
            tradeoff_review.id,
        ),
        _reference(
            "AllocationTradeoffOption",
            "deterministic-tradeoff:option",
            "DynamicYardWorkflow.select_tradeoff",
            tradeoff_option.id,
        ),
        _reference(
            "AllocationTradeoffSelection",
            "deterministic-tradeoff:selection",
            "DynamicYardWorkflow.select_tradeoff",
            tradeoff_selection.id,
        ),
        _reference(
            "AllocationRevision",
            "deterministic-tradeoff:child-revision",
            "DynamicYardWorkflow.select_tradeoff",
            tradeoff_revision.id,
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
            "ContainerReconsiderationResult",
            "canonical-run:carrier-reconsideration-result",
            "CarrierRecoveryRepository.history",
            replacement_chain[0].id,
        ),
        _reference(
            "CarrierRecoveryDecisionLink",
            "canonical-run:carrier-decision-link",
            "CarrierRecoveryRepository.history",
            replacement_chain[2].decision_id,
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
            "Decision",
            "canonical-run:safety-escalation-decision",
            "CargoSafetyHistory.policy_result",
            policy.replacement_decision_id,
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
    if carrier.carrier_responses:
        references.append(
            _reference(
                "CarrierResponse",
                "canonical-run:carrier-response",
                "CarrierRecoveryRepository.history",
                carrier.carrier_responses[-1].id,
            )
        )
    else:
        references.append(
            _reference(
                "RTARequestContext",
                "canonical-run:carrier-timeout-context",
                "CarrierRecoveryRepository.history",
                request_context.case_id,
            )
        )

    replacement_result = replacement_chain[0]
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
        _reference(
            "AuditEvent",
            f"audit:{event.event_type}",
            "AuditRepository.list_for_incident",
            event.id,
        )
        for event in _unique_events(
            dynamic_probe.audit_events,
            {
                "incident.created",
                "scarcity.evaluation_persisted",
                "decision.created",
                "yard_forecast.snapshot_ingested",
                "expedite_reconsideration.assessed",
                "allocation_revision.applied",
            },
        )
    )
    references.extend(
        _reference(
            "AuditEvent",
            (
                f"audit:{event.event_type}"
                if event.event_type == "allocation_tradeoff.option_selected"
                else f"audit:tradeoff:{event.event_type}"
            ),
            "AuditRepository.list_for_incident",
            event.id,
        )
        for event in _unique_events(
            tradeoff_probe.audit_events,
            {
                "allocation_tradeoff.option_selected",
                "allocation_revision.applied",
            },
        )
    )
    references.extend(
        _reference(
            "AuditEvent",
            f"audit:{event.event_type}",
            "CarrierRecoveryRepository.history",
            event.id,
        )
        for event in carrier.audit_events
        if event.event_type
        in {
            "carrier_recovery.request_approval_recorded",
            "carrier.counter_approval_recorded",
            "carrier.response_received",
            "carrier.response_timed_out",
            "carrier_recovery.replacement_recorded",
        }
    )
    references.extend(
        _reference(
            "AuditEvent",
            f"audit:{event.event_type}",
            "CargoSafetyRepository.history",
            event.id,
        )
        for event in safety.audit_events
    )
    return tuple(references)


def _has_carrier_response_or_timeout(carrier) -> bool:
    if carrier.carrier_responses:
        return any(
            event.event_type == "carrier.response_received"
            and event.payload.get("recovery_case_id") == str(carrier.case.id)
            and event.payload.get("request_id") == str(response.request_id)
            and event.payload.get("carrier_response_id") == str(response.id)
            for response in carrier.carrier_responses
            for event in carrier.audit_events
        )
    context = carrier.request_context
    return (
        context is not None
        and context.timeout_observed_at is not None
        and context.close_reason is not None
        and context.close_reason.value == "RESPONSE_TIMEOUT"
        and any(
            event.event_type == "carrier.response_timed_out"
            and event.payload.get("recovery_case_id") == str(carrier.case.id)
            and event.payload.get("request_id") == str(context.request_id)
            for event in carrier.audit_events
        )
    )


def _dynamic_reconsideration_audit_is_linked(probe: _DynamicAuditProbe) -> bool:
    """Require scarcity and yard events to identify one persisted revision chain."""

    history = probe.history
    events = probe.audit_events
    if not _incident_recovery_audit_is_linked(probe):
        return False

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
        if (
            parent is None
            or child is None
            or assessment.source_snapshot_id not in snapshots
        ):
            continue
        snapshot_event = any(
            event.event_type == "yard_forecast.snapshot_ingested"
            and event.payload.get("snapshot_id") == str(assessment.source_snapshot_id)
            for event in events
        )
        assessment_event = any(
            event.event_type == "expedite_reconsideration.assessed"
            and event.payload.get("assessment_id") == str(assessment.id)
            and event.payload.get("source_snapshot_id")
            == str(assessment.source_snapshot_id)
            and event.payload.get("prior_revision_id") == str(parent.id)
            for event in events
        )
        revision_event = any(
            event.event_type == "allocation_revision.applied"
            and event.payload.get("assessment_id") == str(assessment.id)
            and event.payload.get("parent_revision_id") == str(parent.id)
            and event.payload.get("child_revision_id") == str(child.id)
            for event in events
        )
        if snapshot_event and assessment_event and revision_event:
            return True
    return False


def _incident_recovery_audit_is_linked(probe: _DynamicAuditProbe) -> bool:
    """Require the explicit scarcity probe's incident, report, and decision events."""

    events = probe.audit_events
    incident_id = probe.recovery.incident.id
    return (
        any(
            event.event_type == "incident.created" and event.incident_id == incident_id
            for event in events
        )
        and any(
            event.event_type == "scarcity.evaluation_persisted"
            and event.incident_id == incident_id
            and event.payload.get("evaluation_id") == str(probe.recovery.report.id)
            for event in events
        )
        and any(
            event.event_type == "decision.created"
            and event.incident_id == incident_id
            and event.payload.get("decision_id")
            in {str(decision.id) for decision in probe.recovery.decisions}
            for event in events
        )
    )


def _tradeoff_chain_is_linked(probe: _TradeoffAuditProbe) -> bool:
    """Require a selected human option and its audited child allocation revision."""

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
            selection_event = any(
                event.event_type == "allocation_tradeoff.option_selected"
                and event.payload.get("review_id") == str(review.id)
                and event.payload.get("selected_option_id") == str(option.id)
                and event.payload.get("options_fingerprint")
                == review.options_fingerprint
                for event in events
            )
            revision_event = any(
                event.event_type == "allocation_revision.applied"
                and event.payload.get("assessment_id") == str(assessment.id)
                and event.payload.get("parent_revision_id") == str(parent.id)
                and event.payload.get("child_revision_id") == str(child.id)
                for event in events
            )
            if selection_event and revision_event:
                return True
    return False


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


def _safety_escalation_is_linked(safety) -> bool:
    """Validate the policy's durable escalation decision ID against its audit event."""

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
        return False
    required_events = {
        "cargo.semantic_assessment_completed",
        "cargo.semantic_safety_evaluated",
    }
    if not required_events.issubset(
        event.event_type for event in safety.audit_events
    ):
        return False
    return any(
        event.event_type == "decision.escalated_for_cargo_review"
        and event.incident_id == safety.review.incident_id
        and event.payload.get("review_id") == str(safety.review.id)
        and event.payload.get("decision_id") == str(policy.replacement_decision_id)
        and event.payload.get("container_id") == safety.review.container_id
        for event in safety.audit_events
    )


def _unique_events(events, required_event_types: set[str]) -> tuple[object, ...]:
    selected: list[object] = []
    observed_types: set[str] = set()
    for event in events:
        if (
            event.event_type in required_event_types
            and event.event_type not in observed_types
        ):
            selected.append(event)
            observed_types.add(event.event_type)
    return tuple(selected)


@contextmanager
def _isolated_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def _dynamic_audit_probe() -> _DynamicAuditProbe:
    """Capture real scarcity and dynamic-yard audit rows from one local run."""

    with _isolated_session() as session:
        recovery = build_scarce_capacity_workflow(session).run()
        yard = DynamicYardWorkflow.for_session(session)
        harness = CanonicalDynamicYardHarness()
        yard.initialize(
            recovery.incident.id,
            harness.bootstrap_snapshot(recovery.incident.id),
        )
        yard.ingest(harness.discharge_active_snapshot(recovery.incident.id))
        yard.apply_latest_assessment(recovery.incident.id)
        return _DynamicAuditProbe(
            recovery=recovery,
            history=yard.history(recovery.incident.id),
            audit_events=tuple(
                AuditRepository(session).list_for_incident(recovery.incident.id)
            ),
        )


def _tradeoff_audit_probe() -> _TradeoffAuditProbe:
    """Persist and select the deterministic human-tradeoff fixture honestly."""

    from backend.app.evaluation.evidence_authority import _human_review_fixture

    with _isolated_session() as session:
        incident, _baseline = _human_review_fixture(session)
        workflow = DynamicYardWorkflow.for_session(session)
        workflow.apply_latest_assessment(incident.id)
        opened = workflow.history(incident.id)
        review = opened.reviews[-1]
        option = opened.options[-1]
        workflow.select_tradeoff(
            review.id,
            selected_option_id=option.id,
            expected_options_fingerprint=review.options_fingerprint,
            operator_id="evidence-operator",
        )
        return _TradeoffAuditProbe(
            history=workflow.history(incident.id),
            audit_events=tuple(AuditRepository(session).list_for_incident(incident.id)),
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
