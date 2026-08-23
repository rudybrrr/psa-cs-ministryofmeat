from contextlib import contextmanager
from datetime import datetime
from typing import Iterator
from uuid import UUID

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel, Session, select

from backend.app.domain.cargo_safety import (
    CargoNote, CargoSafetyReview, CargoSafetyReviewState, SemanticCheckFailureKind,
    SemanticCheckResult, SemanticSafetyAssessment, SemanticSafetyDisposition,
    SemanticSafetyPolicyResult,
)
from backend.app.domain.models import FrozenContract
from backend.app.domain.models import AuditEvent, Decision
from backend.app.storage.repositories import AuditEventRecord, AuditRepository, DecisionRepository, from_utc_text, to_utc_text


class CargoNoteRecord(SQLModel, table=True):
    __tablename__ = "cargo_notes"
    id: str = Field(primary_key=True); incident_id: str = Field(index=True); container_id: str = Field(index=True); text: str; source: str; created_at_utc: str

class CargoSafetyReviewRecord(SQLModel, table=True):
    __tablename__ = "cargo_safety_reviews"
    __table_args__ = (UniqueConstraint("cargo_note_id"),)
    id: str = Field(primary_key=True); incident_id: str = Field(index=True); container_id: str = Field(index=True); cargo_note_id: str = Field(unique=True); state: str; created_at_utc: str; updated_at_utc: str

class SemanticSafetyAssessmentRecord(SQLModel, table=True):
    __tablename__ = "semantic_safety_assessments"
    review_id: str = Field(primary_key=True); id: str = Field(unique=True); incident_id: str = Field(index=True); container_id: str; cargo_note_id: str; result: str; explanation: str; evidence_excerpt: str | None = None; failure_kind: str | None = None; structured_dangerous_goods: bool; structured_un_number: str | None = None; structured_commodity: str; checker_kind: str; model_name: str | None = None; prompt_version: str; latency_ms: int | None = None; input_tokens: int | None = None; output_tokens: int | None = None; created_at_utc: str

class SemanticSafetyPolicyResultRecord(SQLModel, table=True):
    __tablename__ = "semantic_safety_policy_results"
    review_id: str = Field(primary_key=True); id: str = Field(unique=True); assessment_id: str = Field(unique=True); incident_id: str = Field(index=True); container_id: str; disposition: str; automation_blocked: bool; reason: str; replacement_decision_id: str | None = None; created_at_utc: str

class CargoSafetyAuditLinkRecord(SQLModel, table=True):
    __tablename__ = "cargo_safety_audit_links"
    audit_event_id: str = Field(primary_key=True); review_id: str = Field(index=True)

class CargoSafetyHistory(FrozenContract):
    review: CargoSafetyReview
    note: CargoNote
    assessment: SemanticSafetyAssessment | None = None
    policy_result: SemanticSafetyPolicyResult | None = None
    audit_events: tuple[AuditEvent, ...] = ()

class CargoSafetyRepository:
    def __init__(self, session: Session) -> None: self._session = session
    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield; self._session.commit()
        except Exception:
            self._session.rollback(); raise
    def create_note_and_review(self, note: CargoNote, review: CargoSafetyReview) -> CargoSafetyReview:
        with self.transaction():
            self._session.add(CargoNoteRecord(id=str(note.id), incident_id=str(note.incident_id), container_id=note.container_id, text=note.text, source=note.source, created_at_utc=to_utc_text(note.created_at)))
            self._session.add(CargoSafetyReviewRecord(id=str(review.id), incident_id=str(review.incident_id), container_id=review.container_id, cargo_note_id=str(review.cargo_note_id), state=review.state.value, created_at_utc=to_utc_text(review.created_at), updated_at_utc=to_utc_text(review.updated_at)))
        return review
    def get_review(self, review_id: UUID) -> CargoSafetyReview:
        record = self._session.get(CargoSafetyReviewRecord, str(review_id))
        if record is None: raise LookupError("cargo safety review not found")
        return self._review(record)
    def get_note(self, note_id: UUID) -> CargoNote:
        record = self._session.get(CargoNoteRecord, str(note_id))
        if record is None: raise LookupError("cargo note not found")
        return CargoNote(id=UUID(record.id), incident_id=UUID(record.incident_id), container_id=record.container_id, text=record.text, source=record.source, created_at=from_utc_text(record.created_at_utc))
    def list_reviews(self, incident_id: UUID) -> list[CargoSafetyReview]:
        return [self._review(r) for r in self._session.exec(select(CargoSafetyReviewRecord).where(CargoSafetyReviewRecord.incident_id == str(incident_id)).order_by(CargoSafetyReviewRecord.created_at_utc)).all()]
    def complete(self, review: CargoSafetyReview, assessment: SemanticSafetyAssessment, policy: SemanticSafetyPolicyResult, decision: Decision | None, events: tuple[AuditEvent, ...]) -> None:
        record = self._session.get(CargoSafetyReviewRecord, str(review.id))
        if record is None: raise LookupError("cargo safety review not found")
        with self.transaction():
            record.state = CargoSafetyReviewState.COMPLETED.value; record.updated_at_utc = to_utc_text(review.updated_at); self._session.add(record)
            self._session.add(SemanticSafetyAssessmentRecord(review_id=str(assessment.review_id), **self._assessment_values(assessment)))
            self._session.add(SemanticSafetyPolicyResultRecord(review_id=str(policy.review_id), **self._policy_values(policy)))
            if decision is not None: DecisionRepository(self._session).add_many_uncommitted((decision,))
            for event in events:
                AuditRepository(self._session).add_uncommitted(event)
                self._session.add(CargoSafetyAuditLinkRecord(audit_event_id=str(event.id), review_id=str(review.id)))
    def history(self, review_id: UUID) -> CargoSafetyHistory:
        review = self.get_review(review_id); note = self.get_note(review.cargo_note_id)
        assessment_record = self._session.get(SemanticSafetyAssessmentRecord, str(review_id)); policy_record = self._session.get(SemanticSafetyPolicyResultRecord, str(review_id))
        links = self._session.exec(select(CargoSafetyAuditLinkRecord).where(CargoSafetyAuditLinkRecord.review_id == str(review_id))).all(); ids = [x.audit_event_id for x in links]
        events = () if not ids else tuple(AuditRepository._to_domain(x) for x in self._session.exec(select(AuditEventRecord).where(AuditEventRecord.id.in_(ids)).order_by(AuditEventRecord.sequence)).all())
        return CargoSafetyHistory(review=review, note=note, assessment=self._assessment(assessment_record) if assessment_record else None, policy_result=self._policy(policy_record) if policy_record else None, audit_events=events)
    @staticmethod
    def _review(r): return CargoSafetyReview(id=UUID(r.id), incident_id=UUID(r.incident_id), container_id=r.container_id, cargo_note_id=UUID(r.cargo_note_id), state=CargoSafetyReviewState(r.state), created_at=from_utc_text(r.created_at_utc), updated_at=from_utc_text(r.updated_at_utc))
    @staticmethod
    def _assessment_values(a): return dict(id=str(a.id), incident_id=str(a.incident_id), container_id=a.container_id, cargo_note_id=str(a.cargo_note_id), result=a.result.value, explanation=a.explanation, evidence_excerpt=a.evidence_excerpt, failure_kind=a.failure_kind.value if a.failure_kind else None, structured_dangerous_goods=a.structured_dangerous_goods, structured_un_number=a.structured_un_number, structured_commodity=a.structured_commodity, checker_kind=a.checker_kind, model_name=a.model_name, prompt_version=a.prompt_version, latency_ms=a.latency_ms, input_tokens=a.input_tokens, output_tokens=a.output_tokens, created_at_utc=to_utc_text(a.created_at))
    @staticmethod
    def _assessment(r): return SemanticSafetyAssessment(id=UUID(r.id), review_id=UUID(r.review_id), incident_id=UUID(r.incident_id), container_id=r.container_id, cargo_note_id=UUID(r.cargo_note_id), result=SemanticCheckResult(r.result), explanation=r.explanation, evidence_excerpt=r.evidence_excerpt, failure_kind=SemanticCheckFailureKind(r.failure_kind) if r.failure_kind else None, structured_dangerous_goods=r.structured_dangerous_goods, structured_un_number=r.structured_un_number, structured_commodity=r.structured_commodity, checker_kind=r.checker_kind, model_name=r.model_name, prompt_version=r.prompt_version, latency_ms=r.latency_ms, input_tokens=r.input_tokens, output_tokens=r.output_tokens, created_at=from_utc_text(r.created_at_utc))
    @staticmethod
    def _policy_values(p): return dict(id=str(p.id), assessment_id=str(p.assessment_id), incident_id=str(p.incident_id), container_id=p.container_id, disposition=p.disposition.value, automation_blocked=p.automation_blocked, reason=p.reason, replacement_decision_id=str(p.replacement_decision_id) if p.replacement_decision_id else None, created_at_utc=to_utc_text(p.created_at))
    @staticmethod
    def _policy(r): return SemanticSafetyPolicyResult(id=UUID(r.id), review_id=UUID(r.review_id), assessment_id=UUID(r.assessment_id), incident_id=UUID(r.incident_id), container_id=r.container_id, disposition=SemanticSafetyDisposition(r.disposition), automation_blocked=r.automation_blocked, reason=r.reason, replacement_decision_id=UUID(r.replacement_decision_id) if r.replacement_decision_id else None, created_at=from_utc_text(r.created_at_utc))
