from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, timedelta
from uuid import UUID

from sqlmodel import Session
from sqlalchemy.exc import IntegrityError

from backend.app.domain.carrier_recovery import (
    ApprovalBinding,
    AuthorizationSubjectKind,
    CarrierRecoveryCase,
    CarrierRecoveryCaseState,
    CarrierRecoveryDecisionLink,
    CarrierRecoveryHistory,
    PrepareCarrierRecoveryCaseCommand,
    RequestApprovalCommand,
    RTARequestContext,
    SimulateCarrierResponseCommand,
    CarrierSimulationResult,
    EffectiveConnectionTiming,
    CounterApprovalCommand,
    EvaluateTimeoutCommand,
    CarrierRecoveryDisposition,
    ContainerReconsiderationResult,
    ReconsiderationEvidenceKind,
    RequestCloseReason,
)
from backend.app.domain.enums import ApprovalStatus, AuditActor, DecisionAction, DecisionStatus, IncidentState, RTARequestStatus
from backend.app.domain.models import Approval, AuditEvent, Decision, RTARequest, utc_now
from backend.app.evaluation.scarcity import ScarcityEvaluator, _is_structurally_eligible
from backend.app.services.canonical_incident import SyntheticCanonicalIncidentService
from backend.app.services.scenarios import SeededScenarioGenerator
from backend.app.services.carrier_simulator import (
    DeterministicCarrierSimulator,
    SyntheticCarrierResponsePlan,
)
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository
from backend.app.storage.repositories import DecisionRepository, IncidentRepository, ScarcityEvaluationRepository


class CarrierRecoveryConflict(RuntimeError):
    pass


class CarrierRecoveryWorkflow:
    def __init__(self, *, fixture_service: SyntheticCanonicalIncidentService, scenarios: SeededScenarioGenerator, cases: CarrierRecoveryRepository, incidents: IncidentRepository, evaluations: ScarcityEvaluationRepository, decisions: DecisionRepository, simulator: DeterministicCarrierSimulator) -> None:
        self._fixture_service, self._scenarios, self._cases = fixture_service, scenarios, cases
        self._incidents, self._evaluations, self._decisions = incidents, evaluations, decisions
        self._simulator = simulator

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
        profiles = [
            profile
            for profile in fixture.profiles
            if profile.container.onward_connection.id == command.connection_id
        ]
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
        binding = ApprovalBinding(case_id=case.id, proposal_decision_id=proposal.id, subject_kind=AuthorizationSubjectKind.OUTBOUND_REQUEST, subject_id=request.id, payload_fingerprint=payload_fingerprint, created_at=now)
        with self._cases.transaction():
            self._decisions.add_many_uncommitted(
                tuple(fallback_decisions + [proposal])
            )
            self._cases.create_case(case)
            from backend.app.domain.carrier_recovery import RTARequestContext
            self._cases.add_request(request, RTARequestContext(case_id=case.id, request_id=request.id, payload_fingerprint=payload_fingerprint, response_deadline=command.response_deadline))
            self._cases.add_approval_binding(binding)
            for decision in fallback_decisions: self._cases.add_decision_link(CarrierRecoveryDecisionLink(case_id=case.id, decision_id=decision.id, role="FALLBACK_ROLL", created_at=now))
            self._cases.add_decision_link(CarrierRecoveryDecisionLink(case_id=case.id, decision_id=proposal.id, role="REQUEST_RTA_PROPOSAL", created_at=now))
            self._cases.link_audit(case.id, AuditEvent(actor=AuditActor.SYSTEM, actor_id="carrier-recovery-workflow", incident_id=case.incident_id, event_type="carrier_recovery.case_prepared", payload={"recovery_case_id": str(case.id), "connection_id": case.connection_id, "affected_container_ids": list(affected)}, timestamp=now))
        return case

    def history(self, case_id: UUID) -> CarrierRecoveryHistory:
        return self._cases.history(case_id)

    def record_request_approval(self, command: RequestApprovalCommand) -> Approval:
        try:
            return self._record_request_approval_once(command)
        except IntegrityError as error:
            if not self._is_approval_uniqueness_race(error):
                raise
            with Session(self._cases.session_bind()) as fresh_session:
                return build_carrier_recovery_workflow(
                    fresh_session, simulator=self._simulator
                ).record_request_approval(command)

    def _record_request_approval_once(self, command: RequestApprovalCommand) -> Approval:
        case = self._cases.get_case(command.case_id)
        history = self._cases.history(command.case_id)
        binding = self._cases.get_binding_for_proposal(command.proposal_decision_id)
        existing = self._cases.get_approval_for_proposal(command.proposal_decision_id)
        if existing is not None:
            if (binding.case_id == command.case_id and binding.subject_kind is AuthorizationSubjectKind.OUTBOUND_REQUEST and binding.subject_id == command.request_id and binding.payload_fingerprint == command.expected_payload_fingerprint and existing.operator_id == command.operator_id and existing.status is command.status):
                return existing
            raise CarrierRecoveryConflict("contradictory approval retry")
        if case.state is not CarrierRecoveryCaseState.AWAITING_REQUEST_APPROVAL:
            raise CarrierRecoveryConflict("case is not awaiting request approval")
        if (binding.case_id != command.case_id or binding.subject_kind is not AuthorizationSubjectKind.OUTBOUND_REQUEST or binding.subject_id != command.request_id or binding.payload_fingerprint != command.expected_payload_fingerprint or not command.operator_id.strip()):
            raise CarrierRecoveryConflict("approval command does not match its immutable authorization subject")
        now = utc_now()
        approval = Approval(decision_id=command.proposal_decision_id, operator_id=command.operator_id, status=command.status, created_at=now)
        updated_case = case if command.status is ApprovalStatus.APPROVED else case.model_copy(update={"state": CarrierRecoveryCaseState.RECOMPUTING, "updated_at": now})
        with self._cases.transaction():
            self._cases.add_approval(approval)
            if updated_case is not case:
                if history.request is None or history.request_context is None:
                    raise CarrierRecoveryConflict("rejected request is missing immutable context")
                self._cases.update_request(
                    history.request.model_copy(update={"status": RTARequestStatus.CLOSED})
                )
                self._cases.update_request_context(
                    history.request_context.model_copy(update={"closed_at": now, "close_reason": RequestCloseReason.REQUEST_REJECTED})
                )
                self._cases.update_case(updated_case)
            self._cases.link_audit(case.id, AuditEvent(actor=AuditActor.OPERATOR, actor_id=command.operator_id, incident_id=case.incident_id, event_type="carrier_recovery.request_approval_recorded", payload={"recovery_case_id": str(case.id), "proposal_decision_id": str(command.proposal_decision_id), "subject_id": str(command.request_id), "payload_fingerprint": command.expected_payload_fingerprint, "status": command.status.value}, timestamp=now))
            if command.status is ApprovalStatus.REJECTED:
                self.recompute(case.id)
        return approval

    @staticmethod
    def _is_approval_uniqueness_race(error: IntegrityError) -> bool:
        return (
            isinstance(error.orig, sqlite3.IntegrityError)
            and "UNIQUE constraint failed: approvals.decision_id" in str(error.orig)
        )

    def send_authorised_request(self, case_id: UUID) -> RTARequestContext:
        case = self._cases.get_case(case_id)
        history = self._cases.history(case_id)
        request, context = history.request, history.request_context
        if request is None or context is None:
            raise CarrierRecoveryConflict("case is missing its immutable RTA request context")
        if case.state is CarrierRecoveryCaseState.AWAITING_CARRIER:
            if request.status is RTARequestStatus.SENT and context.sent_at is not None:
                return context
            raise CarrierRecoveryConflict("contradictory prior dispatch state")
        if case.state is not CarrierRecoveryCaseState.AWAITING_REQUEST_APPROVAL:
            raise CarrierRecoveryConflict("case is not awaiting request authorization")
        if request.status is not RTARequestStatus.PENDING or context.sent_at is not None or context.closed_at is not None:
            raise CarrierRecoveryConflict("request is no longer pending")
        matching = [binding for binding in history.bindings if binding.subject_kind is AuthorizationSubjectKind.OUTBOUND_REQUEST and binding.subject_id == request.id and binding.payload_fingerprint == context.payload_fingerprint]
        if len(matching) != 1:
            raise CarrierRecoveryConflict("exact outbound request binding is missing or ambiguous")
        approval = self._cases.get_approval_for_proposal(matching[0].proposal_decision_id)
        if approval is None or approval.status is not ApprovalStatus.APPROVED:
            raise CarrierRecoveryConflict("exact outbound request authorization is not approved")
        now = utc_now()
        sent_context = context.model_copy(update={"sent_at": now})
        sent_request = request.model_copy(update={"status": RTARequestStatus.SENT})
        sent_case = case.model_copy(update={"state": CarrierRecoveryCaseState.AWAITING_CARRIER, "updated_at": now})
        with self._cases.transaction():
            self._cases.update_request(sent_request)
            self._cases.update_request_context(sent_context)
            self._cases.update_case(sent_case)
            self._cases.link_audit(case_id, AuditEvent(actor=AuditActor.SYSTEM, actor_id="carrier-recovery-workflow", incident_id=case.incident_id, event_type="rta.request_sent", payload={"recovery_case_id": str(case_id), "request_id": str(request.id), "payload_fingerprint": context.payload_fingerprint}, timestamp=now))
        return sent_context

    def record_counter_approval(self, command: CounterApprovalCommand) -> Approval:
        try:
            return self._record_counter_approval_once(command)
        except IntegrityError as error:
            if not self._is_approval_uniqueness_race(error):
                raise
            with Session(self._cases.session_bind()) as fresh_session:
                return build_carrier_recovery_workflow(
                    fresh_session, simulator=self._simulator
                ).record_counter_approval(command)

    def _record_counter_approval_once(self, command: CounterApprovalCommand) -> Approval:
        history = self._cases.history(command.case_id)
        case = history.case
        binding = self._cases.get_binding_for_proposal(command.proposal_decision_id)
        existing = self._cases.get_approval_for_proposal(command.proposal_decision_id)
        if existing is not None:
            if (binding.case_id == command.case_id and binding.subject_kind is AuthorizationSubjectKind.COUNTER_PROPOSAL and binding.subject_id == command.carrier_response_id and binding.payload_fingerprint == command.expected_payload_fingerprint and existing.operator_id == command.operator_id and existing.status is command.status):
                return existing
            raise CarrierRecoveryConflict("contradictory counter approval retry")
        if (case.state is not CarrierRecoveryCaseState.AWAITING_COUNTER_APPROVAL or binding.case_id != command.case_id or binding.subject_kind is not AuthorizationSubjectKind.COUNTER_PROPOSAL or binding.subject_id != command.carrier_response_id or binding.payload_fingerprint != command.expected_payload_fingerprint or not command.operator_id.strip()):
            raise CarrierRecoveryConflict("counter approval does not match its immutable authorization subject")
        response = next((item for item in history.carrier_responses if item.id == command.carrier_response_id), None)
        if response is None or response.counter_eta_pta is None:
            raise CarrierRecoveryConflict("counter response is missing its persisted timing")
        now = utc_now()
        approval = Approval(decision_id=command.proposal_decision_id, operator_id=command.operator_id, status=command.status, created_at=now)
        target_case = case.model_copy(update={"state": CarrierRecoveryCaseState.RECOMPUTING, "updated_at": now})
        timing = EffectiveConnectionTiming(case_id=case.id, request_id=response.request_id, carrier_response_id=response.id, effective_eta_pta=response.counter_eta_pta, created_at=now) if command.status is ApprovalStatus.APPROVED else None
        with self._cases.transaction():
            self._cases.add_approval(approval)
            self._cases.update_case(target_case)
            if timing is not None:
                self._cases.add_effective_timing(timing)
                self._cases.link_audit(case.id, AuditEvent(actor=AuditActor.SYSTEM, actor_id="carrier-recovery-workflow", incident_id=case.incident_id, event_type="carrier.timing_effective", payload={"recovery_case_id": str(case.id), "carrier_response_id": str(response.id), "effective_eta_pta": response.counter_eta_pta.astimezone(UTC).isoformat()}, timestamp=now))
            self._cases.link_audit(case.id, AuditEvent(actor=AuditActor.OPERATOR, actor_id=command.operator_id, incident_id=case.incident_id, event_type="carrier.counter_approval_recorded", payload={"recovery_case_id": str(case.id), "proposal_decision_id": str(command.proposal_decision_id), "carrier_response_id": str(response.id), "payload_fingerprint": command.expected_payload_fingerprint, "status": command.status.value}, timestamp=now))
            self.recompute(case.id)
        return approval

    def evaluate_timeout(
        self,
        command: EvaluateTimeoutCommand,
    ) -> CarrierRecoveryCase:
        history = self._cases.history(command.case_id)
        case, request, context = history.case, history.request, history.request_context
        effective_at = command.effective_at.astimezone(UTC)
        existing = [
            event
            for event in history.audit_events
            if event.event_type == "carrier.response_timed_out"
        ]
        if existing:
            if (
                len(existing) == 1
                and existing[0].payload.get("effective_at")
                == effective_at.isoformat()
            ):
                return case
            raise CarrierRecoveryConflict("contradictory timeout retry")
        if (
            request is None
            or context is None
            or case.state is not CarrierRecoveryCaseState.AWAITING_CARRIER
            or request.status is not RTARequestStatus.SENT
            or context.sent_at is None
            or context.closed_at is not None
            or history.carrier_responses
            or effective_at < context.response_deadline
        ):
            raise CarrierRecoveryConflict("timeout is not valid for this request state or deadline")
        closed_request = request.model_copy(update={"status": RTARequestStatus.CLOSED})
        closed_context = context.model_copy(update={"closed_at": effective_at, "close_reason": RequestCloseReason.RESPONSE_TIMEOUT, "timeout_observed_at": effective_at})
        timed_out_case = case.model_copy(update={"state": CarrierRecoveryCaseState.RECOMPUTING, "updated_at": effective_at})
        with self._cases.transaction():
            self._cases.update_request(closed_request)
            self._cases.update_request_context(closed_context)
            self._cases.update_case(timed_out_case)
            self._cases.link_audit(case.id, AuditEvent(actor=AuditActor.SYSTEM, actor_id="carrier-recovery-workflow", incident_id=case.incident_id, event_type="carrier.response_timed_out", payload={"recovery_case_id": str(case.id), "request_id": str(request.id), "effective_at": effective_at.isoformat()}, timestamp=effective_at))
            self.recompute(case.id)
        return self._cases.get_case(case.id)

    def recompute(self, case_id: UUID) -> CarrierRecoveryCase:
        history = self._cases.history(case_id)
        case = history.case
        if history.results:
            return case
        if case.state is not CarrierRecoveryCaseState.RECOMPUTING:
            raise CarrierRecoveryConflict("case is not awaiting frozen-evidence recomputation")
        report = self._evaluations.get_for_incident(case.incident_id)
        fixture = self._fixture_service.load()
        if report.fixture_id != fixture.fixture_id or report.selected_allocation is None:
            raise CarrierRecoveryConflict("source scarcity evidence is incomplete")
        scenarios = self._scenarios.generate(fixture, seed=report.seed, world_count=report.scenario_count)
        profiles = {profile.container.id: profile for profile in fixture.profiles if profile.container.onward_connection.id == case.connection_id}
        allocation = set(report.selected_allocation.allocated_container_ids)
        timing = history.effective_timings[0] if history.effective_timings else None
        evidence_kind, timing_id, approval_id, timeout_context_id = self._reconsideration_evidence(history)
        fallback_links = {link.decision_id for link in history.decision_links if link.role == "FALLBACK_ROLL"}
        decisions = {decision.id: decision for decision in self._decisions.list_for_incident(case.incident_id)}
        fallback_by_container = {decisions[decision_id].container_id: decisions[decision_id] for decision_id in fallback_links if decision_id in decisions}
        created_at = utc_now()
        replacements: list[Decision] = []
        pending_results: list[tuple[str, CarrierRecoveryDisposition, int, bool, Decision, Decision | None]] = []
        for container_id in case.affected_container_ids:
            profile = profiles.get(container_id)
            fallback = fallback_by_container.get(container_id)
            if profile is None or fallback is None:
                raise CarrierRecoveryConflict("case snapshot fallback lineage is incomplete")
            hard_safe = profile is not None and _is_structurally_eligible(profile)
            if not hard_safe:
                disposition, preserved = CarrierRecoveryDisposition.ESCALATE, 0
            elif timing is None:
                disposition, preserved = CarrierRecoveryDisposition.STILL_ROLL, 0
            else:
                boundary = timing.effective_eta_pta + timedelta(minutes=35)
                preserved = sum(
                    ScarcityEvaluator().ready_at(profile, world, expedited=container_id in allocation) <= boundary
                    for world in scenarios.worlds
                )
                if preserved * 10 >= len(scenarios.worlds) * 9:
                    disposition = CarrierRecoveryDisposition.PRESERVED_VIA_RTA
                elif preserved == 0:
                    disposition = CarrierRecoveryDisposition.STILL_ROLL
                else:
                    disposition = CarrierRecoveryDisposition.ESCALATE
            replacement = None
            if disposition is not CarrierRecoveryDisposition.STILL_ROLL:
                action = DecisionAction.PRESERVE_VIA_RTA if disposition is CarrierRecoveryDisposition.PRESERVED_VIA_RTA else DecisionAction.ESCALATE
                replacement = Decision(incident_id=case.incident_id, container_id=container_id, action=action, status=DecisionStatus.APPROVED, rationale="Frozen-evidence Phase 3 p90 carrier recovery recomputation.", supersedes=fallback.id, supersession_reason=f"Phase 3 frozen-evidence result: {disposition.value}; preserved worlds {preserved}/{len(scenarios.worlds)}." if timing is not None else "Phase 3 frozen-evidence hard-constraint escalation.", created_at=created_at)
                replacements.append(replacement)
            pending_results.append((container_id, disposition, preserved, hard_safe, fallback, replacement))
        has_escalation = any(item[1] is CarrierRecoveryDisposition.ESCALATE for item in pending_results)
        terminal = CarrierRecoveryCaseState.ESCALATED if has_escalation else CarrierRecoveryCaseState.COMPLETED
        completed_case = case.model_copy(update={"state": terminal, "updated_at": created_at})
        with self._cases.transaction():
            if replacements:
                self._decisions.add_many_uncommitted(tuple(replacements))
            for container_id, disposition, preserved, hard_safe, fallback, replacement in pending_results:
                result = ContainerReconsiderationResult(case_id=case.id, container_id=container_id, disposition=disposition, prior_decision_id=fallback.id, replacement_decision_id=replacement.id if replacement else None, preserved_world_count=preserved, world_count=len(scenarios.worlds), hard_constraints_satisfied=hard_safe, reconsideration_evidence_kind=evidence_kind, effective_connection_timing_id=timing_id, rejected_approval_id=approval_id, timeout_request_context_id=timeout_context_id, created_at=created_at)
                self._cases.add_result(result)
                if replacement is not None:
                    self._cases.add_decision_link(CarrierRecoveryDecisionLink(case_id=case.id, decision_id=replacement.id, role=disposition.value, created_at=created_at))
            self._cases.update_case(completed_case)
            self._cases.link_audit(case.id, AuditEvent(actor=AuditActor.SYSTEM, actor_id="carrier-recovery-workflow", incident_id=case.incident_id, event_type="carrier_recovery.recomputation_completed", payload={"recovery_case_id": str(case.id), "seed": report.seed, "world_count": report.scenario_count, "selected_allocation": list(report.selected_allocation.allocated_container_ids)}, timestamp=created_at))
            self._cases.link_audit(case.id, AuditEvent(actor=AuditActor.POLICY, actor_id="synthetic-p90-policy", incident_id=case.incident_id, event_type="carrier_recovery.disposition_recorded", payload={"recovery_case_id": str(case.id), "state": terminal.value}, timestamp=created_at))
        return completed_case

    @staticmethod
    def _reconsideration_evidence(history: CarrierRecoveryHistory):
        if history.effective_timings:
            return (ReconsiderationEvidenceKind.EFFECTIVE_CONNECTION_TIMING, history.effective_timings[0].id, None, None)
        for binding in history.bindings:
            approval = next((item for item in history.approvals if item.decision_id == binding.proposal_decision_id), None)
            if approval is not None and approval.status is ApprovalStatus.REJECTED:
                kind = ReconsiderationEvidenceKind.REQUEST_REJECTED if binding.subject_kind is AuthorizationSubjectKind.OUTBOUND_REQUEST else ReconsiderationEvidenceKind.COUNTER_REJECTED
                return (kind, None, approval.id, None)
        if history.request_context and history.request_context.close_reason is RequestCloseReason.RESPONSE_TIMEOUT:
            return (ReconsiderationEvidenceKind.RESPONSE_TIMEOUT, None, None, history.request_context.case_id)
        raise CarrierRecoveryConflict("recomputation lacks durable reconsideration evidence")

    def simulate_response(
        self,
        command: SimulateCarrierResponseCommand,
    ) -> CarrierSimulationResult:
        receipt = self._cases.simulation_receipt(command.case_id)
        if receipt is not None:
            effective_at, carrier_response_id, no_response_emitted = receipt
            if effective_at == command.effective_at:
                return CarrierSimulationResult(
                    case_id=command.case_id,
                    carrier_response_id=carrier_response_id,
                    no_response_emitted=no_response_emitted,
                )
            raise CarrierRecoveryConflict("contradictory carrier simulation retry")
        history = self._cases.history(command.case_id)
        case, request, context = history.case, history.request, history.request_context
        if (
            request is None
            or context is None
            or case.state is not CarrierRecoveryCaseState.AWAITING_CARRIER
            or request.status is not RTARequestStatus.SENT
            or context.sent_at is None
            or command.effective_at >= context.response_deadline
            or history.carrier_responses
        ):
            raise CarrierRecoveryConflict("carrier simulation is not valid for this request state or deadline")
        response = self._simulator.emit(request, command.effective_at)
        if response is None:
            with self._cases.transaction():
                self._cases.add_simulation_receipt(
                    case.id, command.effective_at, None, True
                )
            return CarrierSimulationResult(case_id=case.id, no_response_emitted=True)
        now = command.effective_at
        closed_request = request.model_copy(update={"status": RTARequestStatus.CLOSED})
        closed_context = context.model_copy(update={"closed_at": now})
        if response.response.value == "ACCEPT":
            effective_timing = EffectiveConnectionTiming(
                case_id=case.id,
                request_id=request.id,
                carrier_response_id=response.id,
                effective_eta_pta=request.requested_eta_pta,
                created_at=now,
            )
            target_case = case.model_copy(update={"state": CarrierRecoveryCaseState.RECOMPUTING, "updated_at": now})
            proposal = None
            binding = None
        else:
            if response.counter_eta_pta is None:
                raise CarrierRecoveryConflict("counter response requires explicit counter timing")
            proposal = Decision(incident_id=case.incident_id, container_id=None, action=DecisionAction.REQUEST_RTA, status=DecisionStatus.PROPOSED, rationale="Connection-level counter timing authorization proposal.", created_at=now)
            fingerprint = hashlib.sha256(json.dumps({"carrier_response_id": str(response.id), "counter_eta_pta": response.counter_eta_pta.astimezone(UTC).isoformat()}, sort_keys=True).encode()).hexdigest()
            binding = ApprovalBinding(case_id=case.id, proposal_decision_id=proposal.id, subject_kind=AuthorizationSubjectKind.COUNTER_PROPOSAL, subject_id=response.id, payload_fingerprint=fingerprint, created_at=now)
            effective_timing = None
            target_case = case.model_copy(update={"state": CarrierRecoveryCaseState.AWAITING_COUNTER_APPROVAL, "updated_at": now})
        with self._cases.transaction():
            self._cases.add_simulation_receipt(
                case.id, command.effective_at, response.id, False
            )
            if proposal is not None:
                self._decisions.add_many_uncommitted((proposal,))
            self._cases.add_carrier_response(response)
            self._cases.update_request(closed_request)
            self._cases.update_request_context(closed_context)
            self._cases.update_case(target_case)
            if effective_timing is not None:
                self._cases.add_effective_timing(effective_timing)
                self._cases.link_audit(case.id, AuditEvent(actor=AuditActor.SYSTEM, actor_id="carrier-recovery-workflow", incident_id=case.incident_id, event_type="carrier.timing_effective", payload={"recovery_case_id": str(case.id), "request_id": str(request.id), "effective_eta_pta": request.requested_eta_pta.astimezone(UTC).isoformat()}, timestamp=now))
            if binding is not None and proposal is not None:
                self._cases.add_approval_binding(binding)
                self._cases.add_decision_link(CarrierRecoveryDecisionLink(case_id=case.id, decision_id=proposal.id, role="COUNTER_RTA_PROPOSAL", created_at=now))
                self._cases.link_audit(case.id, AuditEvent(actor=AuditActor.SYSTEM, actor_id="carrier-recovery-workflow", incident_id=case.incident_id, event_type="carrier.counter_awaiting_approval", payload={"recovery_case_id": str(case.id), "proposal_decision_id": str(proposal.id), "carrier_response_id": str(response.id)}, timestamp=now))
            self._cases.link_audit(case.id, AuditEvent(actor=AuditActor.CARRIER, actor_id=response.carrier_id, incident_id=case.incident_id, event_type="carrier.response_received", payload={"recovery_case_id": str(case.id), "request_id": str(request.id), "carrier_response_id": str(response.id), "response": response.response.value}, timestamp=now))
            if response.response.value == "ACCEPT":
                self.recompute(case.id)
        return CarrierSimulationResult(
            case_id=case.id,
            carrier_response_id=response.id,
            no_response_emitted=False,
        )


def build_carrier_recovery_workflow(
    session: Session,
    *,
    simulator: DeterministicCarrierSimulator | None = None,
) -> CarrierRecoveryWorkflow:
    return CarrierRecoveryWorkflow(fixture_service=SyntheticCanonicalIncidentService(), scenarios=SeededScenarioGenerator(), cases=CarrierRecoveryRepository(session), incidents=IncidentRepository(session), evaluations=ScarcityEvaluationRepository(session), decisions=DecisionRepository(session), simulator=simulator or DeterministicCarrierSimulator(SyntheticCarrierResponsePlan().load()))
