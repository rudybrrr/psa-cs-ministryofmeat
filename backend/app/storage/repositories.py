from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Column, JSON
from sqlmodel import Field, Session, SQLModel, select

from backend.app.domain.enums import (
    AuditActor,
    DecisionAction,
    DecisionStatus,
    IncidentState,
)
from backend.app.domain.models import AuditEvent, Decision, Incident
from backend.app.domain.scarcity import ScarcityEvaluationReport


def to_utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def from_utc_text(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


class IncidentRecord(SQLModel, table=True):
    __tablename__ = "incidents"

    id: str = Field(primary_key=True)
    source_event_id: str = Field(index=True)
    state: str
    created_at_utc: str


class DecisionRecord(SQLModel, table=True):
    __tablename__ = "decisions"

    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True)
    container_id: str | None = None
    action: str
    status: str
    rationale: str
    supersedes: str | None = None
    supersession_reason: str | None = None
    created_at_utc: str


class AuditEventRecord(SQLModel, table=True):
    __tablename__ = "audit_events"

    sequence: int | None = Field(default=None, primary_key=True)
    id: str = Field(index=True, unique=True)
    actor: str
    actor_id: str | None = None
    incident_id: str = Field(index=True)
    event_type: str
    payload: dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False)
    )
    timestamp_utc: str


class ScarcityEvaluationRecord(SQLModel, table=True):
    __tablename__ = "scarcity_evaluations"

    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True, unique=True)
    report: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at_utc: str


class RecordNotFound(LookupError):
    pass


class IncidentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, incident: Incident) -> Incident:
        record = IncidentRecord(
            id=str(incident.id),
            source_event_id=incident.source_event_id,
            state=incident.state.value,
            created_at_utc=to_utc_text(incident.created_at),
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return self._to_domain(record)

    def get(self, incident_id: UUID) -> Incident:
        return self._to_domain(self._get_record(incident_id))

    def update_state(
        self,
        incident_id: UUID,
        state: IncidentState,
    ) -> Incident:
        record = self._get_record(incident_id)
        record.state = state.value
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return self._to_domain(record)

    def _get_record(self, incident_id: UUID) -> IncidentRecord:
        record = self._session.get(IncidentRecord, str(incident_id))
        if record is None:
            raise RecordNotFound(f"Incident {incident_id} not found")
        return record

    @staticmethod
    def _to_domain(record: IncidentRecord) -> Incident:
        return Incident(
            id=UUID(record.id),
            source_event_id=record.source_event_id,
            state=IncidentState(record.state),
            created_at=from_utc_text(record.created_at_utc),
        )


class DecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, decision: Decision) -> Decision:
        return self.add_many((decision,))[0]

    def add_many(
        self,
        decisions: tuple[Decision, ...],
    ) -> tuple[Decision, ...]:
        records = tuple(self._to_record(decision) for decision in decisions)
        try:
            self._session.add_all(records)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        for record in records:
            self._session.refresh(record)
        return tuple(self._to_domain(record) for record in records)

    def list_for_incident(self, incident_id: UUID) -> list[Decision]:
        statement = (
            select(DecisionRecord)
            .where(DecisionRecord.incident_id == str(incident_id))
            .order_by(DecisionRecord.created_at_utc, DecisionRecord.id)
        )
        return [
            self._to_domain(record)
            for record in self._session.exec(statement).all()
        ]

    @staticmethod
    def _to_record(decision: Decision) -> DecisionRecord:
        return DecisionRecord(
            id=str(decision.id),
            incident_id=str(decision.incident_id),
            container_id=decision.container_id,
            action=decision.action.value,
            status=decision.status.value,
            rationale=decision.rationale,
            supersedes=(
                str(decision.supersedes)
                if decision.supersedes is not None
                else None
            ),
            supersession_reason=decision.supersession_reason,
            created_at_utc=to_utc_text(decision.created_at),
        )

    @staticmethod
    def _to_domain(record: DecisionRecord) -> Decision:
        return Decision(
            id=UUID(record.id),
            incident_id=UUID(record.incident_id),
            container_id=record.container_id,
            action=DecisionAction(record.action),
            status=DecisionStatus(record.status),
            rationale=record.rationale,
            supersedes=(
                UUID(record.supersedes)
                if record.supersedes is not None
                else None
            ),
            supersession_reason=record.supersession_reason,
            created_at=from_utc_text(record.created_at_utc),
        )


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: AuditEvent) -> AuditEvent:
        record = self.add_uncommitted(event)
        self._session.commit()
        self._session.refresh(record)
        return self._to_domain(record)

    def add_uncommitted(self, event: AuditEvent) -> AuditEventRecord:
        record = AuditEventRecord(
            id=str(event.id),
            actor=event.actor.value,
            actor_id=event.actor_id,
            incident_id=str(event.incident_id),
            event_type=event.event_type,
            payload=dict(event.payload),
            timestamp_utc=to_utc_text(event.timestamp),
        )
        self._session.add(record)
        self._session.flush()
        return record

    def list_for_incident(self, incident_id: UUID) -> list[AuditEvent]:
        statement = (
            select(AuditEventRecord)
            .where(AuditEventRecord.incident_id == str(incident_id))
            .order_by(AuditEventRecord.sequence)
        )
        return [
            self._to_domain(record)
            for record in self._session.exec(statement).all()
        ]

    @staticmethod
    def _to_domain(record: AuditEventRecord) -> AuditEvent:
        return AuditEvent(
            id=UUID(record.id),
            actor=AuditActor(record.actor),
            actor_id=record.actor_id,
            incident_id=UUID(record.incident_id),
            event_type=record.event_type,
            payload=record.payload,
            timestamp=from_utc_text(record.timestamp_utc),
        )


class ScarcityEvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        report: ScarcityEvaluationReport,
    ) -> ScarcityEvaluationReport:
        record = ScarcityEvaluationRecord(
            id=str(report.id),
            incident_id=str(report.incident_id),
            report=report.model_dump(mode="json"),
            created_at_utc=to_utc_text(report.created_at),
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return self._to_domain(record)

    def get_for_incident(
        self,
        incident_id: UUID,
    ) -> ScarcityEvaluationReport:
        statement = select(ScarcityEvaluationRecord).where(
            ScarcityEvaluationRecord.incident_id == str(incident_id)
        )
        record = self._session.exec(statement).one_or_none()
        if record is None:
            raise RecordNotFound(
                f"Scarcity evaluation for incident {incident_id} not found"
            )
        return self._to_domain(record)

    @staticmethod
    def _to_domain(
        record: ScarcityEvaluationRecord,
    ) -> ScarcityEvaluationReport:
        return ScarcityEvaluationReport.model_validate(record.report)
