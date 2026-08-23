from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator
from uuid import UUID

from sqlalchemy import Column, JSON, Index, text
from sqlmodel import Field, SQLModel, Session, select

from backend.app.domain.agent_runtime import (
    AgentHistory,
    AgentRun,
    AgentRunState,
    AgentStep,
    AgentStepKind,
    AgentToolInvocation,
    AgentToolInvocationStatus,
)
from backend.app.storage.repositories import from_utc_text, to_utc_text


_ACTIVE_STATES = "'CREATED', 'RUNNING', 'WAITING'"


class AgentRunRecord(SQLModel, table=True):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index(
            "uq_agent_runs_active_incident",
            "incident_id",
            unique=True,
            sqlite_where=text(f"state IN ({_ACTIVE_STATES})"),
        ),
    )

    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True)
    state: str = Field(index=True)
    model_name: str
    prompt_version: str
    step_count: int
    max_steps: int
    wait_kind: str | None = None
    wait_subject_id: str | None = None
    escalation_reason: str | None = None
    started_at_utc: str
    updated_at_utc: str
    completed_at_utc: str | None = None


class AgentStepRecord(SQLModel, table=True):
    __tablename__ = "agent_steps"
    __table_args__ = (Index("uq_agent_steps_run_number", "run_id", "step_number", unique=True),)

    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    step_number: int
    kind: str
    action_summary: str
    evidence_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    model_name: str
    prompt_version: str
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    created_at_utc: str


class AgentToolInvocationRecord(SQLModel, table=True):
    __tablename__ = "agent_tool_invocations"

    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    step_id: str = Field(index=True)
    tool_name: str
    arguments_json: str
    status: str
    result_summary: str | None = None
    error_kind: str | None = None
    started_at_utc: str
    completed_at_utc: str | None = None


class AgentAuditLinkRecord(SQLModel, table=True):
    __tablename__ = "agent_audit_links"

    audit_event_id: str = Field(primary_key=True)
    run_id: str = Field(index=True)


class AgentRuntimeConflict(RuntimeError):
    pass


class AgentRuntimeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def create_run(self, run: AgentRun) -> AgentRun:
        active = self._session.exec(
            select(AgentRunRecord).where(
                AgentRunRecord.incident_id == str(run.incident_id),
                AgentRunRecord.state.in_((state.value for state in AgentRunState if state in {AgentRunState.CREATED, AgentRunState.RUNNING, AgentRunState.WAITING})),
            )
        ).first()
        if active is not None:
            raise AgentRuntimeConflict("incident already has an active agent run")
        with self.transaction():
            self._session.add(self._run_record(run))
        return run

    def get_run(self, run_id: UUID) -> AgentRun:
        record = self._session.get(AgentRunRecord, str(run_id))
        if record is None:
            raise LookupError("agent run not found")
        return self._run(record)

    def list_runs(self, incident_id: UUID) -> list[AgentRun]:
        records = self._session.exec(
            select(AgentRunRecord)
            .where(AgentRunRecord.incident_id == str(incident_id))
            .order_by(AgentRunRecord.started_at_utc)
        ).all()
        return [self._run(record) for record in records]

    def add_step(self, step: AgentStep) -> AgentStep:
        with self.transaction():
            self._session.add(self._step_record(step))
        return step

    def add_invocation_pending(self, run_id: UUID, step_id: UUID, tool_name: str, arguments: dict) -> AgentToolInvocation:
        invocation = AgentToolInvocation(run_id=run_id, step_id=step_id, tool_name=tool_name, arguments=arguments)
        with self.transaction():
            self._session.add(self._invocation_record(invocation))
        return invocation

    def complete_invocation(self, invocation: AgentToolInvocation) -> AgentToolInvocation:
        record = self._session.get(AgentToolInvocationRecord, str(invocation.id))
        if record is None:
            raise LookupError("agent tool invocation not found")
        if record.status != AgentToolInvocationStatus.PENDING.value:
            raise AgentRuntimeConflict("agent tool invocation is already terminal")
        with self.transaction():
            values = self._invocation_record(invocation)
            record.status = values.status
            record.result_summary = values.result_summary
            record.error_kind = values.error_kind
            record.completed_at_utc = values.completed_at_utc
            self._session.add(record)
        return invocation

    def history(self, run_id: UUID) -> AgentHistory:
        run = self.get_run(run_id)
        steps = self._session.exec(
            select(AgentStepRecord).where(AgentStepRecord.run_id == str(run_id)).order_by(AgentStepRecord.step_number)
        ).all()
        invocations = self._session.exec(
            select(AgentToolInvocationRecord)
            .where(AgentToolInvocationRecord.run_id == str(run_id))
            .order_by(AgentToolInvocationRecord.started_at_utc)
        ).all()
        return AgentHistory(run=run, steps=tuple(self._step(record) for record in steps), tool_invocations=tuple(self._invocation(record) for record in invocations))

    @staticmethod
    def _run_record(run: AgentRun) -> AgentRunRecord:
        return AgentRunRecord(id=str(run.id), incident_id=str(run.incident_id), state=run.state.value, model_name=run.model_name, prompt_version=run.prompt_version, step_count=run.step_count, max_steps=run.max_steps, wait_kind=run.wait_kind.value if run.wait_kind else None, wait_subject_id=run.wait_subject_id, escalation_reason=run.escalation_reason.value if run.escalation_reason else None, started_at_utc=to_utc_text(run.started_at), updated_at_utc=to_utc_text(run.updated_at), completed_at_utc=to_utc_text(run.completed_at) if run.completed_at else None)

    @staticmethod
    def _run(record: AgentRunRecord) -> AgentRun:
        from backend.app.domain.agent_runtime import AgentEscalationReason, AgentWaitKind
        return AgentRun(id=UUID(record.id), incident_id=UUID(record.incident_id), state=AgentRunState(record.state), model_name=record.model_name, prompt_version=record.prompt_version, step_count=record.step_count, max_steps=record.max_steps, wait_kind=AgentWaitKind(record.wait_kind) if record.wait_kind else None, wait_subject_id=record.wait_subject_id, escalation_reason=AgentEscalationReason(record.escalation_reason) if record.escalation_reason else None, started_at=from_utc_text(record.started_at_utc), updated_at=from_utc_text(record.updated_at_utc), completed_at=from_utc_text(record.completed_at_utc) if record.completed_at_utc else None)

    @staticmethod
    def _step_record(step: AgentStep) -> AgentStepRecord:
        return AgentStepRecord(id=str(step.id), run_id=str(step.run_id), step_number=step.step_number, kind=step.kind.value, action_summary=step.action_summary, evidence_refs=list(step.evidence_refs), model_name=step.model_name, prompt_version=step.prompt_version, latency_ms=step.latency_ms, input_tokens=step.input_tokens, output_tokens=step.output_tokens, created_at_utc=to_utc_text(step.created_at))

    @staticmethod
    def _step(record: AgentStepRecord) -> AgentStep:
        return AgentStep(id=UUID(record.id), run_id=UUID(record.run_id), step_number=record.step_number, kind=AgentStepKind(record.kind), action_summary=record.action_summary, evidence_refs=tuple(record.evidence_refs), model_name=record.model_name, prompt_version=record.prompt_version, latency_ms=record.latency_ms, input_tokens=record.input_tokens, output_tokens=record.output_tokens, created_at=from_utc_text(record.created_at_utc))

    @staticmethod
    def _invocation_record(invocation: AgentToolInvocation) -> AgentToolInvocationRecord:
        return AgentToolInvocationRecord(id=str(invocation.id), run_id=str(invocation.run_id), step_id=str(invocation.step_id), tool_name=invocation.tool_name, arguments_json=invocation.model_dump_json(include={"arguments"}), status=invocation.status.value, result_summary=invocation.result_summary, error_kind=invocation.error_kind, started_at_utc=to_utc_text(invocation.started_at), completed_at_utc=to_utc_text(invocation.completed_at) if invocation.completed_at else None)

    @staticmethod
    def _invocation(record: AgentToolInvocationRecord) -> AgentToolInvocation:
        import json
        return AgentToolInvocation(id=UUID(record.id), run_id=UUID(record.run_id), step_id=UUID(record.step_id), tool_name=record.tool_name, arguments=json.loads(record.arguments_json)["arguments"], status=AgentToolInvocationStatus(record.status), result_summary=record.result_summary, error_kind=record.error_kind, started_at=from_utc_text(record.started_at_utc), completed_at=from_utc_text(record.completed_at_utc) if record.completed_at_utc else None)
