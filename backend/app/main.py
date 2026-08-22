from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.engine import Engine
from sqlmodel import Session

from backend.app.domain.models import AuditEvent, Decision, Incident
from backend.app.domain.scarcity import (
    CanonicalIncidentFixture,
    ScarcityEvaluationReport,
)
from backend.app.orchestration.scarce_capacity import (
    build_scarce_capacity_workflow,
)
from backend.app.orchestration.state_machine import build_workflow
from backend.app.services.canonical_incident import (
    SyntheticCanonicalIncidentService,
)
from backend.app.storage.database import (
    create_db_and_tables,
    engine,
    get_session,
)
from backend.app.storage.repositories import (
    AuditRepository,
    DecisionRepository,
    IncidentRepository,
    RecordNotFound,
    ScarcityEvaluationRepository,
)


class TriggerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    incident_id: UUID
    decision_id: UUID


class ScarcityTriggerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    incident_id: UUID
    evaluation_id: UUID
    decision_ids: tuple[UUID, ...]
    reproducibility_key: str


SessionDependency = Annotated[Session, Depends(get_session)]


def create_app(*, database_engine: Engine | None = None) -> FastAPI:
    active_engine = database_engine if database_engine is not None else engine

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        create_db_and_tables(active_engine)
        yield

    application = FastAPI(
        title="PSA Transshipment Recovery",
        lifespan=lifespan,
    )

    @application.post(
        "/synthetic/scenarios/schedule-delay",
        response_model=TriggerResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def trigger_synthetic_schedule_delay(
        session: SessionDependency,
    ) -> TriggerResponse:
        workflow = build_workflow(session)
        result = workflow.run(workflow.schedule.delay_event())
        if result.decision is None:
            raise RuntimeError(
                "Canonical synthetic schedule-delay scenario produced no decision"
            )
        return TriggerResponse(
            incident_id=result.incident.id,
            decision_id=result.decision.id,
        )

    @application.post(
        "/synthetic/scenarios/canonical-scarcity",
        response_model=ScarcityTriggerResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def trigger_canonical_scarcity(
        session: SessionDependency,
    ) -> ScarcityTriggerResponse:
        result = build_scarce_capacity_workflow(session).run(
            seed=20260822,
            world_count=50,
        )
        return ScarcityTriggerResponse(
            incident_id=result.incident.id,
            evaluation_id=result.report.id,
            decision_ids=tuple(
                decision.id for decision in result.decisions
            ),
            reproducibility_key=result.report.reproducibility_key,
        )

    @application.get(
        "/synthetic/scenarios/canonical-scarcity/fixture",
        response_model=CanonicalIncidentFixture,
    )
    def get_canonical_scarcity_fixture() -> CanonicalIncidentFixture:
        return SyntheticCanonicalIncidentService().load()

    @application.get(
        "/incidents/{incident_id}",
        response_model=Incident,
    )
    def get_incident(
        incident_id: UUID,
        session: SessionDependency,
    ) -> Incident:
        try:
            return IncidentRepository(session).get(incident_id)
        except RecordNotFound as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            ) from error

    @application.get(
        "/incidents/{incident_id}/decisions",
        response_model=list[Decision],
    )
    def get_decisions(
        incident_id: UUID,
        session: SessionDependency,
    ) -> list[Decision]:
        return DecisionRepository(session).list_for_incident(incident_id)

    @application.get(
        "/incidents/{incident_id}/audit-events",
        response_model=list[AuditEvent],
    )
    def get_audit_events(
        incident_id: UUID,
        session: SessionDependency,
    ) -> list[AuditEvent]:
        return AuditRepository(session).list_for_incident(incident_id)

    @application.get(
        "/incidents/{incident_id}/scarcity-evaluation",
        response_model=ScarcityEvaluationReport,
    )
    def get_scarcity_evaluation(
        incident_id: UUID,
        session: SessionDependency,
    ) -> ScarcityEvaluationReport:
        try:
            return ScarcityEvaluationRepository(session).get_for_incident(
                incident_id
            )
        except RecordNotFound as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scarcity evaluation not found",
            ) from error

    return application


app = create_app()
