from __future__ import annotations

import hashlib
import json
from datetime import UTC
from uuid import UUID

from sqlmodel import Session

from backend.app.domain.carrier_recovery import (
    ApprovalBinding,
    AuthorizationSubjectKind,
    CarrierRecoveryCase,
    CarrierRecoveryCaseState,
    CarrierRecoveryDecisionLink,
    CarrierRecoveryHistory,
    PrepareCarrierRecoveryCaseCommand,
)
from backend.app.domain.enums import AuditActor, DecisionAction, DecisionStatus, IncidentState, RTARequestStatus
from backend.app.domain.models import AuditEvent, Decision, RTARequest, utc_now
from backend.app.evaluation.scarcity import ScarcityEvaluator, _is_structurally_eligible
from backend.app.services.canonical_incident import SyntheticCanonicalIncidentService
from backend.app.services.scenarios import SeededScenarioGenerator
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository
from backend.app.storage.repositories import DecisionRepository, IncidentRepository, ScarcityEvaluationRepository


class CarrierRecoveryConflict(RuntimeError):
    pass


class CarrierRecoveryWorkflow:
    def __init__(self, *, fixture_service: SyntheticCanonicalIncidentService, scenarios: SeededScenarioGenerator, cases: CarrierRecoveryRepository, incidents: IncidentRepository, evaluations: ScarcityEvaluationRepository, decisions: DecisionRepository) -> None:
        self._fixture_service, self._scenarios, self._cases = fixture_service, scenarios, cases
        self._incidents, self._evaluations, self._decisions = incidents, evaluations, decisions

    def prepare(self, command: PrepareCarrierRecoveryCaseCommand) -> CarrierRecoveryCase:
        incident = self._incidents.get(command.incident_id)
        if incident.state is not IncidentState.RESOLVED:
            raise CarrierRecoveryConflict("carrier recovery requires a resolved Phase 2 incident")
        report = self._evaluations.get_for_incident(command.incident_id)
        fixture = self._fixture_service.load()
        if report.fixture_id != fixture.fixture_id or report.selected_allocation is None:
            raise CarrierRecoveryConflict("persisted scarcity evidence is not eligible for carrier recovery")
        if command.response_deadline <= command.requested_eta_pta:
            raise CarrierRecoveryConflict("response deadline must be later than requested timing")
        scenarios = self._scenarios.generate(fixture, seed=report.seed, world_count=report.scenario_count)
        evaluator = ScarcityEvaluator()
        allocated = set(report.selected_allocation.allocated_container_ids)
        profiles = [profile for profile in fixture.profiles if profile.service_id == command.connection_id]
        if not profiles:
            raise CarrierRecoveryConflict(f"unknown connection {command.connection_id}")
        affected = tuple(profile.container.id for profile in profiles if _is_structurally_eligible(profile) and not any(evaluator.preserves_connection(fixture, profile, world, expedited=profile.container.id in allocated) for world in scenarios.worlds))
        if not affected:
            raise CarrierRecoveryConflict("requested connection has no structurally safe zero-world containers")
        now = utc_now()
        case = CarrierRecoveryCase(incident_id=command.incident_id, connection_id=command.connection_id, source_evaluation_id=report.id, affected_container_ids=affected, state=CarrierRecoveryCaseState.AWAITING_REQUEST_APPROVAL, created_at=now, updated_at=now)
        request = RTARequest(incident_id=command.incident_id, connection_id=command.connection_id, requested_eta_pta=command.requested_eta_pta, status=RTARequestStatus.PENDING, created_at=now)
        payload_fingerprint = hashlib.sha256(json.dumps({"connection_id": command.connection_id, "requested_eta_pta": command.requested_eta_pta.astimezone(UTC).isoformat()}, sort_keys=True).encode()).hexdigest()
        fallback_decisions = []
        historical = self._decisions.list_for_incident(command.incident_id)
        for index, container_id in enumerate(affected):
            container_decisions = [item for item in historical if item.container_id == container_id]
            superseded = {item.supersedes for item in container_decisions if item.supersedes is not None}
            current = [item for item in container_decisions if item.id not in superseded]
            if len(current) > 1:
                raise CarrierRecoveryConflict(f"ambiguous current decision lineage for {container_id}")
            prior = current[0] if current else None
            fallback_decisions.append(Decision(incident_id=command.incident_id, container_id=container_id, action=DecisionAction.ROLL, status=DecisionStatus.APPROVED, rationale="Fallback pending connection-level carrier recovery.", supersedes=prior.id if prior else None, supersession_reason="Phase 3 preparation found zero preserved worlds under original timing with the frozen Phase 2 allocation." if prior else None, created_at=now))
        proposal = Decision(incident_id=command.incident_id, container_id=None, action=DecisionAction.REQUEST_RTA, status=DecisionStatus.PROPOSED, rationale="Connection-level request authorization proposal.", created_at=now)
        persisted = self._decisions.add_many(tuple(fallback_decisions + [proposal]))
        binding = ApprovalBinding(case_id=case.id, proposal_decision_id=persisted[-1].id, subject_kind=AuthorizationSubjectKind.OUTBOUND_REQUEST, subject_id=request.id, payload_fingerprint=payload_fingerprint, created_at=now)
        with self._cases.transaction():
            self._cases.create_case(case)
            from backend.app.domain.carrier_recovery import RTARequestContext
            self._cases.add_request(request, RTARequestContext(case_id=case.id, request_id=request.id, payload_fingerprint=payload_fingerprint, response_deadline=command.response_deadline))
            self._cases.add_approval_binding(binding)
            for decision in persisted[:-1]: self._cases.add_decision_link(CarrierRecoveryDecisionLink(case_id=case.id, decision_id=decision.id, role="FALLBACK_ROLL", created_at=now))
            self._cases.add_decision_link(CarrierRecoveryDecisionLink(case_id=case.id, decision_id=persisted[-1].id, role="REQUEST_RTA_PROPOSAL", created_at=now))
            self._cases.link_audit(case.id, AuditEvent(actor=AuditActor.SYSTEM, actor_id="carrier-recovery-workflow", incident_id=case.incident_id, event_type="carrier_recovery.case_prepared", payload={"recovery_case_id": str(case.id), "connection_id": case.connection_id, "affected_container_ids": list(affected)}, timestamp=now))
        return case

    def history(self, case_id: UUID) -> CarrierRecoveryHistory:
        return self._cases.history(case_id)


def build_carrier_recovery_workflow(session: Session) -> CarrierRecoveryWorkflow:
    return CarrierRecoveryWorkflow(fixture_service=SyntheticCanonicalIncidentService(), scenarios=SeededScenarioGenerator(), cases=CarrierRecoveryRepository(session), incidents=IncidentRepository(session), evaluations=ScarcityEvaluationRepository(session), decisions=DecisionRepository(session))
