from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator
from uuid import UUID

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, Session, SQLModel, select

from backend.app.domain.carrier_recovery import (
    ApprovalBinding,
    CarrierRecoveryCase,
    CarrierRecoveryCaseState,
    CarrierRecoveryDecisionLink,
    CarrierRecoveryHistory,
    ContainerReconsiderationResult,
    EffectiveConnectionTiming,
    RTARequestContext,
)
from backend.app.domain.enums import ApprovalStatus, CarrierResponseType, RTARequestStatus
from backend.app.domain.models import Approval, AuditEvent, CarrierResponse, RTARequest
from backend.app.storage.repositories import AuditEventRecord, AuditRepository, DecisionRepository, from_utc_text, to_utc_text


class CarrierRecoveryCaseRecord(SQLModel, table=True):
    __tablename__ = "carrier_recovery_cases"
    __table_args__ = (UniqueConstraint("incident_id", "connection_id"),)
    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True)
    connection_id: str
    source_evaluation_id: str
    affected_container_ids: list[str] = Field(sa_column=Column(JSON, nullable=False))
    state: str
    created_at_utc: str
    updated_at_utc: str


class RTARequestRecord(SQLModel, table=True):
    __tablename__ = "rta_requests"
    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True)
    connection_id: str
    requested_eta_pta_utc: str
    status: str
    created_at_utc: str


class RTARequestContextRecord(SQLModel, table=True):
    __tablename__ = "rta_request_contexts"
    __table_args__ = (UniqueConstraint("case_id"),)
    case_id: str = Field(primary_key=True)
    request_id: str = Field(unique=True)
    payload_fingerprint: str
    response_deadline_utc: str
    sent_at_utc: str | None = None
    closed_at_utc: str | None = None


class ApprovalRecord(SQLModel, table=True):
    __tablename__ = "approvals"
    id: str = Field(primary_key=True)
    decision_id: str = Field(index=True, unique=True)
    operator_id: str
    status: str
    reason: str | None = None
    created_at_utc: str


class ApprovalBindingRecord(SQLModel, table=True):
    __tablename__ = "approval_bindings"
    proposal_decision_id: str = Field(primary_key=True)
    case_id: str = Field(index=True)
    subject_kind: str
    subject_id: str
    payload_fingerprint: str
    created_at_utc: str


class CarrierResponseRecord(SQLModel, table=True):
    __tablename__ = "carrier_responses"
    request_id: str = Field(primary_key=True)
    id: str = Field(unique=True)
    carrier_id: str
    response: str
    counter_eta_pta_utc: str | None = None
    message: str | None = None
    received_at_utc: str


class CarrierSimulationReceiptRecord(SQLModel, table=True):
    __tablename__ = "carrier_simulation_receipts"
    case_id: str = Field(primary_key=True)
    effective_at_utc: str
    carrier_response_id: str | None = None
    no_response_emitted: bool


class EffectiveConnectionTimingRecord(SQLModel, table=True):
    __tablename__ = "effective_connection_timings"
    id: str = Field(primary_key=True)
    case_id: str = Field(index=True)
    request_id: str
    carrier_response_id: str = Field(unique=True)
    effective_eta_pta_utc: str
    created_at_utc: str


class CarrierRecoveryDecisionLinkRecord(SQLModel, table=True):
    __tablename__ = "carrier_recovery_decision_links"
    decision_id: str = Field(primary_key=True)
    case_id: str = Field(index=True)
    role: str
    created_at_utc: str


class ContainerReconsiderationResultRecord(SQLModel, table=True):
    __tablename__ = "container_reconsideration_results"
    __table_args__ = (UniqueConstraint("case_id", "container_id"),)
    id: str = Field(primary_key=True)
    case_id: str = Field(index=True)
    container_id: str
    disposition: str
    prior_decision_id: str
    replacement_decision_id: str | None = None
    preserved_world_count: int
    world_count: int
    hard_constraints_satisfied: bool
    created_at_utc: str


class CarrierRecoveryAuditLinkRecord(SQLModel, table=True):
    __tablename__ = "carrier_recovery_audit_links"
    audit_event_id: str = Field(primary_key=True)
    case_id: str = Field(index=True)


class CarrierRecoveryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._transaction_depth = 0

    def session_bind(self):
        return self._session.get_bind()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        outermost = self._transaction_depth == 0
        self._transaction_depth += 1
        try:
            yield
            self._transaction_depth -= 1
            if outermost:
                self._session.commit()
        except Exception:
            self._transaction_depth -= 1
            if outermost:
                self._session.rollback()
            raise

    def _persist(self, record: SQLModel) -> None:
        self._session.add(record)
        if self._transaction_depth == 0:
            try:
                self._session.commit()
            except Exception:
                self._session.rollback()
                raise

    def create_case(self, case: CarrierRecoveryCase) -> CarrierRecoveryCase:
        self._persist(CarrierRecoveryCaseRecord(
            id=str(case.id), incident_id=str(case.incident_id), connection_id=case.connection_id,
            source_evaluation_id=str(case.source_evaluation_id), affected_container_ids=list(case.affected_container_ids),
            state=case.state.value, created_at_utc=to_utc_text(case.created_at), updated_at_utc=to_utc_text(case.updated_at),
        ))
        return case

    def get_case(self, case_id: UUID) -> CarrierRecoveryCase:
        record = self._session.get(CarrierRecoveryCaseRecord, str(case_id))
        if record is None:
            raise LookupError(f"carrier recovery case {case_id} not found")
        return self._case(record)

    def list_cases(self, incident_id: UUID) -> list[CarrierRecoveryCase]:
        records = self._session.exec(select(CarrierRecoveryCaseRecord).where(CarrierRecoveryCaseRecord.incident_id == str(incident_id)).order_by(CarrierRecoveryCaseRecord.created_at_utc)).all()
        return [self._case(record) for record in records]

    def update_case(self, case: CarrierRecoveryCase) -> CarrierRecoveryCase:
        record = self._session.get(CarrierRecoveryCaseRecord, str(case.id))
        if record is None:
            raise LookupError(f"carrier recovery case {case.id} not found")
        record.state, record.updated_at_utc = case.state.value, to_utc_text(case.updated_at)
        self._persist(record)
        return case

    def add_request(self, request: RTARequest, context: RTARequestContext) -> RTARequest:
        self._persist(RTARequestRecord(id=str(request.id), incident_id=str(request.incident_id), connection_id=request.connection_id, requested_eta_pta_utc=to_utc_text(request.requested_eta_pta), status=request.status.value, created_at_utc=to_utc_text(request.created_at)))
        self._persist(RTARequestContextRecord(case_id=str(context.case_id), request_id=str(context.request_id), payload_fingerprint=context.payload_fingerprint, response_deadline_utc=to_utc_text(context.response_deadline), sent_at_utc=to_utc_text(context.sent_at) if context.sent_at else None, closed_at_utc=to_utc_text(context.closed_at) if context.closed_at else None))
        return request

    def get_request_context(self, case_id: UUID) -> RTARequestContext:
        record = self._session.get(RTARequestContextRecord, str(case_id))
        if record is None: raise LookupError(f"request context for {case_id} not found")
        return RTARequestContext(case_id=UUID(record.case_id), request_id=UUID(record.request_id), payload_fingerprint=record.payload_fingerprint, response_deadline=from_utc_text(record.response_deadline_utc), sent_at=from_utc_text(record.sent_at_utc) if record.sent_at_utc else None, closed_at=from_utc_text(record.closed_at_utc) if record.closed_at_utc else None)

    def update_request(self, request: RTARequest) -> RTARequest:
        record = self._session.get(RTARequestRecord, str(request.id))
        if record is None:
            raise LookupError(f"request {request.id} not found")
        record.status = request.status.value
        self._persist(record)
        return request

    def update_request_context(self, context: RTARequestContext) -> RTARequestContext:
        record = self._session.get(RTARequestContextRecord, str(context.case_id))
        if record is None:
            raise LookupError(f"request context for {context.case_id} not found")
        record.sent_at_utc = to_utc_text(context.sent_at) if context.sent_at else None
        record.closed_at_utc = to_utc_text(context.closed_at) if context.closed_at else None
        self._persist(record)
        return context

    def add_approval_binding(self, binding: ApprovalBinding) -> ApprovalBinding:
        self._persist(ApprovalBindingRecord(proposal_decision_id=str(binding.proposal_decision_id), case_id=str(binding.case_id), subject_kind=binding.subject_kind.value, subject_id=str(binding.subject_id), payload_fingerprint=binding.payload_fingerprint, created_at_utc=to_utc_text(binding.created_at)))
        return binding

    def add_decision_link(self, link: CarrierRecoveryDecisionLink) -> CarrierRecoveryDecisionLink:
        self._persist(CarrierRecoveryDecisionLinkRecord(decision_id=str(link.decision_id), case_id=str(link.case_id), role=link.role, created_at_utc=to_utc_text(link.created_at)))
        return link

    def add_approval(self, approval: Approval) -> Approval:
        self._persist(ApprovalRecord(id=str(approval.id), decision_id=str(approval.decision_id), operator_id=approval.operator_id, status=approval.status.value, reason=approval.reason, created_at_utc=to_utc_text(approval.created_at)))
        return approval


    def get_approval_for_proposal(self, proposal_decision_id: UUID) -> Approval | None:
        record = self._session.exec(select(ApprovalRecord).where(ApprovalRecord.decision_id == str(proposal_decision_id))).one_or_none()
        if record is None:
            return None
        return Approval(id=UUID(record.id), decision_id=UUID(record.decision_id), operator_id=record.operator_id, status=ApprovalStatus(record.status), reason=record.reason, created_at=from_utc_text(record.created_at_utc))

    def get_binding_for_proposal(self, proposal_decision_id: UUID) -> ApprovalBinding:
        record = self._session.get(ApprovalBindingRecord, str(proposal_decision_id))
        if record is None: raise LookupError(f"approval binding {proposal_decision_id} not found")
        return ApprovalBinding(case_id=UUID(record.case_id), proposal_decision_id=UUID(record.proposal_decision_id), subject_kind=record.subject_kind, subject_id=UUID(record.subject_id), payload_fingerprint=record.payload_fingerprint, created_at=from_utc_text(record.created_at_utc))

    def add_result(self, result: ContainerReconsiderationResult) -> ContainerReconsiderationResult:
        self._persist(ContainerReconsiderationResultRecord(id=str(result.id), case_id=str(result.case_id), container_id=result.container_id, disposition=result.disposition.value, prior_decision_id=str(result.prior_decision_id), replacement_decision_id=str(result.replacement_decision_id) if result.replacement_decision_id else None, preserved_world_count=result.preserved_world_count, world_count=result.world_count, hard_constraints_satisfied=result.hard_constraints_satisfied, created_at_utc=to_utc_text(result.created_at)))
        return result

    def add_carrier_response(self, response: CarrierResponse) -> CarrierResponse:
        self._persist(CarrierResponseRecord(request_id=str(response.request_id), id=str(response.id), carrier_id=response.carrier_id, response=response.response.value, counter_eta_pta_utc=to_utc_text(response.counter_eta_pta) if response.counter_eta_pta else None, message=response.message, received_at_utc=to_utc_text(response.received_at)))
        return response

    def simulation_receipt(self, case_id: UUID) -> tuple[datetime, UUID | None, bool] | None:
        record = self._session.get(CarrierSimulationReceiptRecord, str(case_id))
        if record is None:
            return None
        return (
            from_utc_text(record.effective_at_utc),
            UUID(record.carrier_response_id) if record.carrier_response_id else None,
            record.no_response_emitted,
        )

    def add_simulation_receipt(
        self, case_id: UUID, effective_at: datetime, carrier_response_id: UUID | None, no_response_emitted: bool
    ) -> None:
        self._persist(CarrierSimulationReceiptRecord(
            case_id=str(case_id), effective_at_utc=to_utc_text(effective_at),
            carrier_response_id=str(carrier_response_id) if carrier_response_id else None,
            no_response_emitted=no_response_emitted,
        ))

    def responses_for_request(self, request_id: UUID) -> tuple[CarrierResponse, ...]:
        records = self._session.exec(select(CarrierResponseRecord).where(CarrierResponseRecord.request_id == str(request_id))).all()
        return tuple(CarrierResponse(id=UUID(record.id), request_id=UUID(record.request_id), carrier_id=record.carrier_id, response=CarrierResponseType(record.response), counter_eta_pta=from_utc_text(record.counter_eta_pta_utc) if record.counter_eta_pta_utc else None, message=record.message, received_at=from_utc_text(record.received_at_utc)) for record in records)

    def add_effective_timing(self, timing: EffectiveConnectionTiming) -> EffectiveConnectionTiming:
        self._persist(EffectiveConnectionTimingRecord(id=str(timing.id), case_id=str(timing.case_id), request_id=str(timing.request_id), carrier_response_id=str(timing.carrier_response_id), effective_eta_pta_utc=to_utc_text(timing.effective_eta_pta), created_at_utc=to_utc_text(timing.created_at)))
        return timing

    def link_audit(self, case_id: UUID, event: AuditEvent) -> AuditEvent:
        AuditRepository(self._session).add_uncommitted(event)
        self._persist(CarrierRecoveryAuditLinkRecord(audit_event_id=str(event.id), case_id=str(case_id)))
        return event

    def history(self, case_id: UUID) -> CarrierRecoveryHistory:
        links = self._session.exec(select(CarrierRecoveryAuditLinkRecord).where(CarrierRecoveryAuditLinkRecord.case_id == str(case_id))).all()
        ids = [link.audit_event_id for link in links]
        events = [] if not ids else [AuditRepository._to_domain(record) for record in self._session.exec(select(AuditEventRecord).where(AuditEventRecord.id.in_(ids)).order_by(AuditEventRecord.sequence)).all()]
        context_record = self._session.get(RTARequestContextRecord, str(case_id))
        context = None if context_record is None else self.get_request_context(case_id)
        request_record = None if context is None else self._session.get(RTARequestRecord, str(context.request_id))
        request = None if request_record is None else RTARequest(id=UUID(request_record.id), incident_id=UUID(request_record.incident_id), connection_id=request_record.connection_id, requested_eta_pta=from_utc_text(request_record.requested_eta_pta_utc), status=RTARequestStatus(request_record.status), created_at=from_utc_text(request_record.created_at_utc))
        binding_records = self._session.exec(select(ApprovalBindingRecord).where(ApprovalBindingRecord.case_id == str(case_id))).all()
        bindings = tuple(ApprovalBinding(case_id=UUID(record.case_id), proposal_decision_id=UUID(record.proposal_decision_id), subject_kind=record.subject_kind, subject_id=UUID(record.subject_id), payload_fingerprint=record.payload_fingerprint, created_at=from_utc_text(record.created_at_utc)) for record in binding_records)
        approvals = tuple(item for item in (self.get_approval_for_proposal(binding.proposal_decision_id) for binding in bindings) if item is not None)
        carrier_responses = () if request is None else self.responses_for_request(request.id)
        timing_records = self._session.exec(select(EffectiveConnectionTimingRecord).where(EffectiveConnectionTimingRecord.case_id == str(case_id))).all()
        effective_timings = tuple(EffectiveConnectionTiming(id=UUID(record.id), case_id=UUID(record.case_id), request_id=UUID(record.request_id), carrier_response_id=UUID(record.carrier_response_id), effective_eta_pta=from_utc_text(record.effective_eta_pta_utc), created_at=from_utc_text(record.created_at_utc)) for record in timing_records)
        result_records = self._session.exec(select(ContainerReconsiderationResultRecord).where(ContainerReconsiderationResultRecord.case_id == str(case_id)).order_by(ContainerReconsiderationResultRecord.container_id)).all()
        results = tuple(ContainerReconsiderationResult(id=UUID(record.id), case_id=UUID(record.case_id), container_id=record.container_id, disposition=record.disposition, prior_decision_id=UUID(record.prior_decision_id), replacement_decision_id=UUID(record.replacement_decision_id) if record.replacement_decision_id else None, preserved_world_count=record.preserved_world_count, world_count=record.world_count, hard_constraints_satisfied=record.hard_constraints_satisfied, created_at=from_utc_text(record.created_at_utc)) for record in result_records)
        link_records = self._session.exec(select(CarrierRecoveryDecisionLinkRecord).where(CarrierRecoveryDecisionLinkRecord.case_id == str(case_id))).all()
        decision_links = tuple(CarrierRecoveryDecisionLink(case_id=UUID(record.case_id), decision_id=UUID(record.decision_id), role=record.role, created_at=from_utc_text(record.created_at_utc)) for record in link_records)
        linked_ids = {link.decision_id for link in decision_links}
        decisions = tuple(decision for decision in DecisionRepository(self._session).list_for_incident(self.get_case(case_id).incident_id) if decision.id in linked_ids)
        return CarrierRecoveryHistory(case=self.get_case(case_id), request=request, request_context=context, bindings=bindings, approvals=approvals, carrier_responses=carrier_responses, effective_timings=effective_timings, decision_links=decision_links, decisions=decisions, results=results, audit_events=tuple(events))

    @staticmethod
    def _case(record: CarrierRecoveryCaseRecord) -> CarrierRecoveryCase:
        return CarrierRecoveryCase(id=UUID(record.id), incident_id=UUID(record.incident_id), connection_id=record.connection_id, source_evaluation_id=UUID(record.source_evaluation_id), affected_container_ids=tuple(record.affected_container_ids), state=CarrierRecoveryCaseState(record.state), created_at=from_utc_text(record.created_at_utc), updated_at=from_utc_text(record.updated_at_utc))
