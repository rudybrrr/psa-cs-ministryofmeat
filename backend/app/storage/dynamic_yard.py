from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
import json
from typing import Iterator
from uuid import UUID

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, Session, SQLModel, select

from backend.app.domain.dynamic_yard import (
    AllocationRevision,
    AllocationTradeoffHistory,
    AllocationTradeoffOption,
    AllocationTradeoffReview,
    AllocationTradeoffSelection,
    ContainerReadyForecast,
    ExpediteCommitment,
    ExpediteCommitmentStatus,
    ExpediteReconsiderationAssessment,
    ForecastStage,
    ReconsiderationCandidate,
    ReconsiderationDisposition,
    TradeoffReviewState,
    YardForecastSnapshot,
    allowed_commitment_transition,
)
from backend.app.storage.repositories import from_utc_text, to_utc_text


class YardForecastSnapshotRecord(SQLModel, table=True):
    __tablename__ = "yard_forecast_snapshots"
    __table_args__ = (UniqueConstraint("incident_id", "stage"),)
    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True)
    stage: str
    source: str
    fingerprint: str
    snapshot_json: dict = Field(sa_column=Column(JSON, nullable=False))
    generated_at_utc: str


class AllocationRevisionRecord(SQLModel, table=True):
    __tablename__ = "allocation_revisions"
    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True)
    source_phase2_evaluation_id: str
    source_forecast_snapshot_id: str
    parent_revision_id: str | None = None
    allocated_container_ids_json: list[str] = Field(sa_column=Column(JSON, nullable=False))
    locked_container_ids_json: list[str] = Field(sa_column=Column(JSON, nullable=False))
    preserved_connection_total: int
    expected_preserved_connections: float
    reason: str
    created_at_utc: str


class ExpediteCommitmentRecord(SQLModel, table=True):
    __tablename__ = "expedite_commitments"
    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True)
    origin_revision_id: str
    container_id: str
    status: str
    created_at_utc: str
    updated_at_utc: str


class ExpediteReconsiderationAssessmentRecord(SQLModel, table=True):
    __tablename__ = "expedite_reconsideration_assessments"
    __table_args__ = (UniqueConstraint("source_snapshot_id"),)
    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True)
    source_snapshot_id: str
    prior_allocation_revision_id: str
    locked_container_ids_json: list[str] = Field(sa_column=Column(JSON, nullable=False))
    candidate_options_json: list[dict] = Field(sa_column=Column(JSON, nullable=False))
    preserved_connection_total_before: int
    preserved_connection_total_after: int
    expected_preserved_connections_before: float
    expected_preserved_connections_after: float
    disposition: str
    reason: str
    handled_at_utc: str | None = None
    created_at_utc: str


class AllocationTradeoffReviewRecord(SQLModel, table=True):
    __tablename__ = "allocation_tradeoff_reviews"
    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True)
    reconsideration_assessment_id: str = Field(unique=True)
    option_ids_json: list[str] = Field(sa_column=Column(JSON, nullable=False))
    options_fingerprint: str
    state: str
    created_at_utc: str


class AllocationTradeoffOptionRecord(SQLModel, table=True):
    __tablename__ = "allocation_tradeoff_options"
    __table_args__ = (UniqueConstraint("review_id", "id"),)
    id: str = Field(primary_key=True)
    review_id: str = Field(index=True)
    allocated_container_ids_json: list[str] = Field(sa_column=Column(JSON, nullable=False))
    preserved_connection_total: int
    expected_preserved_connections: float


class AllocationTradeoffSelectionRecord(SQLModel, table=True):
    __tablename__ = "allocation_tradeoff_selections"
    review_id: str = Field(primary_key=True)
    id: str = Field(unique=True)
    selected_option_id: str
    expected_options_fingerprint: str
    operator_id: str
    created_at_utc: str


class DynamicYardConflict(ValueError):
    pass


class DynamicYardRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._transaction_depth = 0

    @contextmanager
    def transaction(self) -> Iterator[None]:
        outermost = self._transaction_depth == 0
        self._transaction_depth += 1
        try:
            yield
            if outermost:
                self._session.commit()
        except Exception:
            if outermost:
                self._session.rollback()
            raise
        finally:
            self._transaction_depth -= 1

    def _persist(self, record: SQLModel) -> None:
        self._session.add(record)
        if self._transaction_depth == 0:
            try:
                self._session.commit()
            except Exception:
                self._session.rollback()
                raise

    @staticmethod
    def _fingerprint(value: object) -> str:
        if hasattr(value, "model_dump"):
            payload = value.model_dump(mode="json", exclude={"id"})
        else:
            payload = value
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def add_snapshot(self, snapshot: YardForecastSnapshot) -> YardForecastSnapshot:
        existing = self._session.exec(select(YardForecastSnapshotRecord).where(
            YardForecastSnapshotRecord.incident_id == str(snapshot.incident_id),
            YardForecastSnapshotRecord.stage == snapshot.stage.value,
        )).one_or_none()
        fingerprint = self._fingerprint(snapshot)
        if existing is not None:
            if existing.fingerprint != fingerprint:
                raise DynamicYardConflict("contradictory duplicate forecast stage")
            return self._snapshot(existing)
        self._persist(YardForecastSnapshotRecord(
            id=str(snapshot.id), incident_id=str(snapshot.incident_id), stage=snapshot.stage.value,
            source=snapshot.source, fingerprint=fingerprint, snapshot_json=snapshot.model_dump(mode="json"),
            generated_at_utc=to_utc_text(snapshot.generated_at),
        ))
        return snapshot

    def get_snapshot_for_stage(self, incident_id: UUID, stage: ForecastStage) -> YardForecastSnapshot | None:
        record = self._session.exec(select(YardForecastSnapshotRecord).where(
            YardForecastSnapshotRecord.incident_id == str(incident_id),
            YardForecastSnapshotRecord.stage == stage.value,
        )).one_or_none()
        return None if record is None else self._snapshot(record)

    def list_snapshots(self, incident_id: UUID) -> tuple[YardForecastSnapshot, ...]:
        records = self._session.exec(select(YardForecastSnapshotRecord).where(
            YardForecastSnapshotRecord.incident_id == str(incident_id)
        ).order_by(YardForecastSnapshotRecord.generated_at_utc)).all()
        return tuple(self._snapshot(record) for record in records)

    def add_revision(self, revision: AllocationRevision) -> AllocationRevision:
        if self._session.get(AllocationRevisionRecord, str(revision.id)) is not None:
            raise DynamicYardConflict("allocation revision already exists")
        self._persist(AllocationRevisionRecord(
            id=str(revision.id), incident_id=str(revision.incident_id),
            source_phase2_evaluation_id=str(revision.source_phase2_evaluation_id),
            source_forecast_snapshot_id=str(revision.source_forecast_snapshot_id),
            parent_revision_id=str(revision.parent_revision_id) if revision.parent_revision_id else None,
            allocated_container_ids_json=list(revision.allocated_container_ids),
            locked_container_ids_json=list(revision.locked_container_ids),
            preserved_connection_total=revision.preserved_connection_total,
            expected_preserved_connections=revision.expected_preserved_connections,
            reason=revision.reason, created_at_utc=to_utc_text(revision.created_at),
        ))
        return revision

    def active_revision(self, incident_id: UUID) -> AllocationRevision | None:
        records = self._session.exec(select(AllocationRevisionRecord).where(
            AllocationRevisionRecord.incident_id == str(incident_id)
        ).order_by(AllocationRevisionRecord.created_at_utc, AllocationRevisionRecord.id)).all()
        return None if not records else self._revision(records[-1])

    def list_revisions(self, incident_id: UUID) -> tuple[AllocationRevision, ...]:
        records = self._session.exec(select(AllocationRevisionRecord).where(
            AllocationRevisionRecord.incident_id == str(incident_id)
        ).order_by(AllocationRevisionRecord.created_at_utc, AllocationRevisionRecord.id)).all()
        return tuple(self._revision(record) for record in records)

    def add_commitment(self, commitment: ExpediteCommitment) -> ExpediteCommitment:
        self._persist(ExpediteCommitmentRecord(
            id=str(commitment.id), incident_id=str(commitment.incident_id),
            origin_revision_id=str(commitment.origin_revision_id), container_id=commitment.container_id,
            status=commitment.status.value, created_at_utc=to_utc_text(commitment.created_at),
            updated_at_utc=to_utc_text(commitment.updated_at),
        ))
        return commitment

    def list_commitments(self, incident_id: UUID) -> tuple[ExpediteCommitment, ...]:
        records = self._session.exec(select(ExpediteCommitmentRecord).where(
            ExpediteCommitmentRecord.incident_id == str(incident_id)
        ).order_by(ExpediteCommitmentRecord.created_at_utc, ExpediteCommitmentRecord.id)).all()
        return tuple(self._commitment(record) for record in records)

    def transition_commitment(self, commitment_id: UUID, target: ExpediteCommitmentStatus) -> ExpediteCommitment:
        record = self._session.get(ExpediteCommitmentRecord, str(commitment_id))
        if record is None:
            raise LookupError(f"expedite commitment {commitment_id} not found")
        current = ExpediteCommitmentStatus(record.status)
        if not allowed_commitment_transition(current, target):
            raise DynamicYardConflict("invalid expedite commitment transition")
        record.status = target.value
        record.updated_at_utc = to_utc_text(datetime.now().astimezone())
        self._persist(record)
        return self._commitment(record)

    def add_assessment(self, assessment: ExpediteReconsiderationAssessment) -> ExpediteReconsiderationAssessment:
        existing = self._session.exec(select(ExpediteReconsiderationAssessmentRecord).where(
            ExpediteReconsiderationAssessmentRecord.source_snapshot_id == str(assessment.source_snapshot_id)
        )).one_or_none()
        if existing is not None:
            if self._assessment(existing) != assessment:
                raise DynamicYardConflict("contradictory reconsideration assessment")
            return self._assessment(existing)
        self._persist(ExpediteReconsiderationAssessmentRecord(
            id=str(assessment.id), incident_id=str(assessment.incident_id),
            source_snapshot_id=str(assessment.source_snapshot_id), prior_allocation_revision_id=str(assessment.prior_allocation_revision_id),
            locked_container_ids_json=list(assessment.locked_container_ids),
            candidate_options_json=[candidate.model_dump(mode="json") for candidate in assessment.candidate_options],
            preserved_connection_total_before=assessment.preserved_connection_total_before,
            preserved_connection_total_after=assessment.preserved_connection_total_after,
            expected_preserved_connections_before=assessment.expected_preserved_connections_before,
            expected_preserved_connections_after=assessment.expected_preserved_connections_after,
            disposition=assessment.disposition.value, reason=assessment.reason,
            handled_at_utc=to_utc_text(assessment.handled_at) if assessment.handled_at else None,
            created_at_utc=to_utc_text(assessment.created_at),
        ))
        return assessment

    def latest_unhandled_assessment(self, incident_id: UUID) -> ExpediteReconsiderationAssessment | None:
        records = self._session.exec(select(ExpediteReconsiderationAssessmentRecord).where(
            ExpediteReconsiderationAssessmentRecord.incident_id == str(incident_id),
            ExpediteReconsiderationAssessmentRecord.handled_at_utc.is_(None),
        ).order_by(ExpediteReconsiderationAssessmentRecord.created_at_utc)).all()
        return None if not records else self._assessment(records[-1])

    def mark_assessment_handled(self, assessment_id: UUID, handled_at: datetime) -> ExpediteReconsiderationAssessment:
        record = self._session.get(ExpediteReconsiderationAssessmentRecord, str(assessment_id))
        if record is None: raise LookupError(f"assessment {assessment_id} not found")
        if record.handled_at_utc is None:
            record.handled_at_utc = to_utc_text(handled_at)
            self._persist(record)
        return self._assessment(record)

    def list_assessments(self, incident_id: UUID) -> tuple[ExpediteReconsiderationAssessment, ...]:
        records = self._session.exec(select(ExpediteReconsiderationAssessmentRecord).where(
            ExpediteReconsiderationAssessmentRecord.incident_id == str(incident_id)
        ).order_by(ExpediteReconsiderationAssessmentRecord.created_at_utc)).all()
        return tuple(self._assessment(record) for record in records)

    def create_tradeoff_review(self, review: AllocationTradeoffReview, options: tuple[AllocationTradeoffOption, ...]) -> AllocationTradeoffReview:
        existing = self._session.get(AllocationTradeoffReviewRecord, str(review.id))
        if existing is not None:
            return self._review(existing)
        if tuple(option.id for option in options) != review.option_ids or any(option.review_id != review.id for option in options):
            raise DynamicYardConflict("review options do not exactly match review IDs")
        self._persist(AllocationTradeoffReviewRecord(
            id=str(review.id), incident_id=str(review.incident_id),
            reconsideration_assessment_id=str(review.reconsideration_assessment_id),
            option_ids_json=[str(option_id) for option_id in review.option_ids],
            options_fingerprint=review.options_fingerprint, state=review.state.value,
            created_at_utc=to_utc_text(review.created_at),
        ))
        for option in options:
            self._persist(AllocationTradeoffOptionRecord(
                id=str(option.id), review_id=str(option.review_id),
                allocated_container_ids_json=list(option.allocated_container_ids),
                preserved_connection_total=option.preserved_connection_total,
                expected_preserved_connections=option.expected_preserved_connections,
            ))
        return review

    def select_tradeoff_option(self, review_id: UUID, *, selected_option_id: UUID, expected_options_fingerprint: str, operator_id: str) -> AllocationTradeoffSelection:
        review = self._session.get(AllocationTradeoffReviewRecord, str(review_id))
        if review is None: raise LookupError(f"tradeoff review {review_id} not found")
        if review.options_fingerprint != expected_options_fingerprint:
            raise DynamicYardConflict("tradeoff options fingerprint is stale")
        if review.state != TradeoffReviewState.OPEN.value:
            raise DynamicYardConflict("tradeoff review is not open")
        if str(selected_option_id) not in review.option_ids_json:
            raise DynamicYardConflict("selected option does not belong to review")
        selection = AllocationTradeoffSelection(
            review_id=review_id, selected_option_id=selected_option_id,
            expected_options_fingerprint=expected_options_fingerprint, operator_id=operator_id,
        )
        self._persist(AllocationTradeoffSelectionRecord(
            review_id=str(review_id), id=str(selection.id), selected_option_id=str(selected_option_id),
            expected_options_fingerprint=expected_options_fingerprint, operator_id=operator_id,
            created_at_utc=to_utc_text(selection.created_at),
        ))
        review.state = TradeoffReviewState.RESOLVED.value
        self._persist(review)
        return selection

    def list_reviews(self, incident_id: UUID) -> tuple[AllocationTradeoffReview, ...]:
        records = self._session.exec(select(AllocationTradeoffReviewRecord).where(
            AllocationTradeoffReviewRecord.incident_id == str(incident_id)
        ).order_by(AllocationTradeoffReviewRecord.created_at_utc)).all()
        return tuple(self._review(record) for record in records)

    def history(self, incident_id: UUID) -> AllocationTradeoffHistory:
        reviews = self.list_reviews(incident_id)
        review_ids = [str(review.id) for review in reviews]
        options = () if not review_ids else tuple(self._option(record) for record in self._session.exec(
            select(AllocationTradeoffOptionRecord).where(AllocationTradeoffOptionRecord.review_id.in_(review_ids))
        ).all())
        selections = () if not review_ids else tuple(self._selection(record) for record in self._session.exec(
            select(AllocationTradeoffSelectionRecord).where(AllocationTradeoffSelectionRecord.review_id.in_(review_ids))
        ).all())
        return AllocationTradeoffHistory(snapshots=self.list_snapshots(incident_id), revisions=self.list_revisions(incident_id), commitments=self.list_commitments(incident_id), assessments=self.list_assessments(incident_id), reviews=reviews, options=options, selections=selections)

    @staticmethod
    def _snapshot(record: YardForecastSnapshotRecord) -> YardForecastSnapshot:
        return YardForecastSnapshot.model_validate(record.snapshot_json)

    @staticmethod
    def _revision(record: AllocationRevisionRecord) -> AllocationRevision:
        return AllocationRevision(id=UUID(record.id), incident_id=UUID(record.incident_id), source_phase2_evaluation_id=UUID(record.source_phase2_evaluation_id), source_forecast_snapshot_id=UUID(record.source_forecast_snapshot_id), parent_revision_id=UUID(record.parent_revision_id) if record.parent_revision_id else None, allocated_container_ids=tuple(record.allocated_container_ids_json), locked_container_ids=tuple(record.locked_container_ids_json), preserved_connection_total=record.preserved_connection_total, expected_preserved_connections=record.expected_preserved_connections, reason=record.reason, created_at=from_utc_text(record.created_at_utc))

    @staticmethod
    def _commitment(record: ExpediteCommitmentRecord) -> ExpediteCommitment:
        return ExpediteCommitment(id=UUID(record.id), incident_id=UUID(record.incident_id), origin_revision_id=UUID(record.origin_revision_id), container_id=record.container_id, status=ExpediteCommitmentStatus(record.status), created_at=from_utc_text(record.created_at_utc), updated_at=from_utc_text(record.updated_at_utc))

    @staticmethod
    def _assessment(record: ExpediteReconsiderationAssessmentRecord) -> ExpediteReconsiderationAssessment:
        return ExpediteReconsiderationAssessment(id=UUID(record.id), incident_id=UUID(record.incident_id), source_snapshot_id=UUID(record.source_snapshot_id), prior_allocation_revision_id=UUID(record.prior_allocation_revision_id), locked_container_ids=tuple(record.locked_container_ids_json), candidate_options=tuple(ReconsiderationCandidate.model_validate(item) for item in record.candidate_options_json), preserved_connection_total_before=record.preserved_connection_total_before, preserved_connection_total_after=record.preserved_connection_total_after, expected_preserved_connections_before=record.expected_preserved_connections_before, expected_preserved_connections_after=record.expected_preserved_connections_after, disposition=ReconsiderationDisposition(record.disposition), reason=record.reason, handled_at=from_utc_text(record.handled_at_utc) if record.handled_at_utc else None, created_at=from_utc_text(record.created_at_utc))

    @staticmethod
    def _review(record: AllocationTradeoffReviewRecord) -> AllocationTradeoffReview:
        return AllocationTradeoffReview(id=UUID(record.id), incident_id=UUID(record.incident_id), reconsideration_assessment_id=UUID(record.reconsideration_assessment_id), option_ids=tuple(UUID(item) for item in record.option_ids_json), options_fingerprint=record.options_fingerprint, state=TradeoffReviewState(record.state), created_at=from_utc_text(record.created_at_utc))

    @staticmethod
    def _option(record: AllocationTradeoffOptionRecord) -> AllocationTradeoffOption:
        return AllocationTradeoffOption(id=UUID(record.id), review_id=UUID(record.review_id), allocated_container_ids=tuple(record.allocated_container_ids_json), preserved_connection_total=record.preserved_connection_total, expected_preserved_connections=record.expected_preserved_connections)

    @staticmethod
    def _selection(record: AllocationTradeoffSelectionRecord) -> AllocationTradeoffSelection:
        return AllocationTradeoffSelection(id=UUID(record.id), review_id=UUID(record.review_id), selected_option_id=UUID(record.selected_option_id), expected_options_fingerprint=record.expected_options_fingerprint, operator_id=record.operator_id, created_at=from_utc_text(record.created_at_utc))
