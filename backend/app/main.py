from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.engine import Engine
from sqlmodel import Session

from backend.app.domain.carrier_recovery import (
    CarrierRecoveryCase,
    CarrierRecoveryHistory,
    CarrierSimulationResult,
    CounterApprovalCommand,
    EvaluateTimeoutCommand,
    PrepareCarrierRecoveryCaseCommand,
    RequestApprovalCommand,
    RTARequestContext,
    SimulateCarrierResponseCommand,
)
from backend.app.domain.enums import ApprovalStatus
from backend.app.domain.models import Approval, AuditEvent, Decision, Incident
from backend.app.orchestration.carrier_recovery import (
    CarrierRecoveryConflict,
    build_carrier_recovery_workflow,
)
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
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository
from backend.app.domain.cargo_safety import CargoSafetyEvaluationResult, CargoSafetyReview
from backend.app.orchestration.cargo_safety import CargoSafetyConflict, CargoSafetyWorkflow
from backend.app.services.semantic_safety import SemanticSafetyChecker
from backend.app.storage.cargo_safety import CargoSafetyHistory
from backend.app.domain.agent_runtime import AgentHistory, AgentRun
from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
from backend.app.services.agent_model import AgentModel, OpenAIAgentModel
from backend.app.storage.agent_runtime import AgentRuntimeConflict, AgentRuntimeRepository
from backend.app.domain.dynamic_yard import AllocationRevision, AllocationTradeoffReview, ExpediteCommitment, ExpediteReconsiderationAssessment, YardForecastSnapshot
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness


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


class PrepareCarrierRecoveryBody(BaseModel):
    connection_id: str
    prepared_at: str
    requested_eta_pta: str
    response_deadline: str


class RequestApprovalBody(BaseModel):
    proposal_decision_id: UUID
    request_id: UUID
    expected_payload_fingerprint: str
    operator_id: str
    status: ApprovalStatus


class CounterApprovalBody(BaseModel):
    proposal_decision_id: UUID
    carrier_response_id: UUID
    expected_payload_fingerprint: str
    operator_id: str
    status: ApprovalStatus


class EffectiveAtBody(BaseModel):
    effective_at: str


class CargoSafetyNoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    source: str


class CreateCargoSafetyReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    container_id: str
    note: CargoSafetyNoteBody


SessionDependency = Annotated[Session, Depends(get_session)]


def create_app(*, database_engine: Engine | None = None, cargo_safety_checker: SemanticSafetyChecker | None = None, agent_model: AgentModel | None = None) -> FastAPI:
    active_engine = database_engine if database_engine is not None else engine

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        create_db_and_tables(active_engine)
        yield

    application = FastAPI(
        title="PSA Transshipment Recovery",
        lifespan=lifespan,
    )

    @application.exception_handler(ValidationError)
    async def domain_validation_error(_, error: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": jsonable_encoder(error.errors())})

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

    def cargo_safety_workflow(session: Session) -> CargoSafetyWorkflow:
        return CargoSafetyWorkflow.for_session(session, checker=cargo_safety_checker)

    def agent_runtime(session: Session) -> AgentRuntimeCoordinator:
        configuration = CanonicalAgentRuntimeConfiguration.load()
        return AgentRuntimeCoordinator(session=session, model=agent_model or OpenAIAgentModel(), clock=configuration.clock("before_deadline"), configuration=configuration)

    def dynamic_yard_workflow(session: Session) -> DynamicYardWorkflow:
        return DynamicYardWorkflow.for_session(session)

    @application.post("/synthetic/scenarios/{incident_id}/dynamic-yard/bootstrap", response_model=list[AllocationRevision], status_code=status.HTTP_201_CREATED)
    async def bootstrap_dynamic_yard(incident_id: UUID, session: SessionDependency, request: Request) -> list[AllocationRevision]:
        if await request.body():
            raise HTTPException(status_code=422, detail="Dynamic-yard bootstrap accepts no request body")
        try:
            return list(dynamic_yard_workflow(session).initialize(incident_id, CanonicalDynamicYardHarness().bootstrap_snapshot(incident_id)).revisions)
        except (LookupError, RecordNotFound) as error:
            raise HTTPException(status_code=404, detail="Incident or scarcity evaluation not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/synthetic/scenarios/{incident_id}/dynamic-yard/discharge-active", response_model=ExpediteReconsiderationAssessment, status_code=status.HTTP_201_CREATED)
    async def discharge_active_dynamic_yard(incident_id: UUID, session: SessionDependency, request: Request) -> ExpediteReconsiderationAssessment:
        if await request.body():
            raise HTTPException(status_code=422, detail="Dynamic-yard discharge-active accepts no request body")
        try:
            assessment = dynamic_yard_workflow(session).ingest(CanonicalDynamicYardHarness().discharge_active_snapshot(incident_id))
            if assessment is None: raise HTTPException(status_code=409, detail="No discharge-active assessment was created")
            return assessment
        except (LookupError, RecordNotFound) as error:
            raise HTTPException(status_code=404, detail="Dynamic-yard flow not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.get("/incidents/{incident_id}/yard-forecast-snapshots", response_model=list[YardForecastSnapshot])
    def list_yard_forecast_snapshots(incident_id: UUID, session: SessionDependency) -> list[YardForecastSnapshot]:
        return list(dynamic_yard_workflow(session).history(incident_id).snapshots)

    @application.get("/incidents/{incident_id}/allocation-revisions", response_model=list[AllocationRevision])
    def list_allocation_revisions(incident_id: UUID, session: SessionDependency) -> list[AllocationRevision]:
        return list(dynamic_yard_workflow(session).history(incident_id).revisions)

    @application.get("/incidents/{incident_id}/expedite-commitments", response_model=list[ExpediteCommitment])
    def list_expedite_commitments(incident_id: UUID, session: SessionDependency) -> list[ExpediteCommitment]:
        return list(dynamic_yard_workflow(session).history(incident_id).commitments)

    @application.get("/incidents/{incident_id}/expedite-reconsiderations", response_model=list[ExpediteReconsiderationAssessment])
    def list_expedite_reconsiderations(incident_id: UUID, session: SessionDependency) -> list[ExpediteReconsiderationAssessment]:
        return list(dynamic_yard_workflow(session).history(incident_id).assessments)

    @application.get("/incidents/{incident_id}/allocation-tradeoff-reviews", response_model=list[AllocationTradeoffReview])
    def list_allocation_tradeoff_reviews(incident_id: UUID, session: SessionDependency) -> list[AllocationTradeoffReview]:
        return list(dynamic_yard_workflow(session).history(incident_id).reviews)

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

    @application.post("/incidents/{incident_id}/agent-runs", response_model=AgentRun, status_code=status.HTTP_201_CREATED)
    async def create_agent_run(incident_id: UUID, session: SessionDependency, request: Request) -> AgentRun:
        if await request.body():
            raise HTTPException(status_code=422, detail="Agent run creation accepts no request body")
        try:
            return agent_runtime(session).create_run(incident_id)
        except RecordNotFound as error:
            raise HTTPException(status_code=404, detail="Incident not found") from error
        except AgentRuntimeConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/agent-runs/{run_id}/advance", response_model=AgentRun)
    async def advance_agent_run(run_id: UUID, session: SessionDependency, request: Request) -> AgentRun:
        if await request.body():
            raise HTTPException(status_code=422, detail="Agent advance accepts no request body")
        try:
            return agent_runtime(session).advance(run_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Agent run not found") from error
        except AgentRuntimeConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.get("/incidents/{incident_id}/agent-runs", response_model=list[AgentRun])
    def list_agent_runs(incident_id: UUID, session: SessionDependency) -> list[AgentRun]:
        try:
            IncidentRepository(session).get(incident_id)
            return AgentRuntimeRepository(session).list_runs(incident_id)
        except RecordNotFound as error:
            raise HTTPException(status_code=404, detail="Incident not found") from error

    @application.get("/agent-runs/{run_id}", response_model=AgentRun)
    def get_agent_run(run_id: UUID, session: SessionDependency) -> AgentRun:
        try:
            return AgentRuntimeRepository(session).get_run(run_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Agent run not found") from error

    @application.get("/agent-runs/{run_id}/history", response_model=AgentHistory)
    def get_agent_run_history(run_id: UUID, session: SessionDependency) -> AgentHistory:
        try:
            return AgentRuntimeRepository(session).history(run_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Agent run not found") from error

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

    @application.post("/incidents/{incident_id}/cargo-safety-reviews", response_model=CargoSafetyReview, status_code=status.HTTP_201_CREATED)
    def create_cargo_safety_review(incident_id: UUID, body: CreateCargoSafetyReviewBody, session: SessionDependency) -> CargoSafetyReview:
        try:
            return cargo_safety_workflow(session).create_review(incident_id, body.container_id, body.note.text, body.note.source)
        except RecordNotFound as error:
            raise HTTPException(status_code=404, detail="Incident not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post("/cargo-safety-reviews/{review_id}/evaluate", response_model=CargoSafetyEvaluationResult, status_code=status.HTTP_201_CREATED)
    def evaluate_cargo_safety_review(review_id: UUID, response: Response, session: SessionDependency, body: dict | None = Body(default=None)) -> CargoSafetyEvaluationResult:
        if body is not None:
            raise HTTPException(status_code=422, detail="Cargo safety evaluation accepts no request body")
        workflow = cargo_safety_workflow(session)
        try:
            retry = workflow.get(review_id).state.value == "COMPLETED"
            result = workflow.evaluate(review_id)
            if retry: response.status_code = status.HTTP_200_OK
            return result
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Cargo safety review not found") from error
        except CargoSafetyConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.get("/incidents/{incident_id}/cargo-safety-reviews", response_model=list[CargoSafetyReview])
    def list_cargo_safety_reviews(incident_id: UUID, session: SessionDependency) -> list[CargoSafetyReview]:
        try: return cargo_safety_workflow(session).list(incident_id)
        except RecordNotFound as error: raise HTTPException(status_code=404, detail="Incident not found") from error

    @application.get("/cargo-safety-reviews/{review_id}", response_model=CargoSafetyReview)
    def get_cargo_safety_review(review_id: UUID, session: SessionDependency) -> CargoSafetyReview:
        try: return cargo_safety_workflow(session).get(review_id)
        except LookupError as error: raise HTTPException(status_code=404, detail="Cargo safety review not found") from error

    @application.get("/cargo-safety-reviews/{review_id}/history", response_model=CargoSafetyHistory)
    def get_cargo_safety_history(review_id: UUID, session: SessionDependency) -> CargoSafetyHistory:
        try: return cargo_safety_workflow(session).history(review_id)
        except LookupError as error: raise HTTPException(status_code=404, detail="Cargo safety review not found") from error

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

    @application.post("/incidents/{incident_id}/carrier-recovery-cases", response_model=CarrierRecoveryCase, status_code=status.HTTP_201_CREATED)
    def prepare_carrier_recovery_case(incident_id: UUID, body: PrepareCarrierRecoveryBody, response: Response, session: SessionDependency) -> CarrierRecoveryCase:
        try:
            retry = CarrierRecoveryRepository(session).find_case(incident_id, body.connection_id) is not None
            result = build_carrier_recovery_workflow(session).prepare(PrepareCarrierRecoveryCaseCommand(incident_id=incident_id, **body.model_dump()))
            if retry:
                response.status_code = status.HTTP_200_OK
            return result
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Incident or dependency not found") from error
        except CarrierRecoveryConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/carrier-recovery-cases/{case_id}/request-approval", response_model=Approval, status_code=status.HTTP_201_CREATED)
    def request_carrier_approval(case_id: UUID, body: RequestApprovalBody, response: Response, session: SessionDependency) -> Approval:
        workflow = build_carrier_recovery_workflow(session)
        try:
            retry = any(item.decision_id == body.proposal_decision_id for item in workflow.history(case_id).approvals)
            result = workflow.record_request_approval(RequestApprovalCommand(case_id=case_id, **body.model_dump()))
            if retry:
                response.status_code = status.HTTP_200_OK
            return result
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Carrier recovery case or binding not found") from error
        except CarrierRecoveryConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/carrier-recovery-cases/{case_id}/send", response_model=RTARequestContext, status_code=status.HTTP_201_CREATED)
    def send_carrier_request(case_id: UUID, response: Response, session: SessionDependency) -> RTARequestContext:
        workflow = build_carrier_recovery_workflow(session)
        try:
            history = workflow.history(case_id)
            retry = history.case.state.value == "AWAITING_CARRIER" and history.request is not None and history.request.status.value == "SENT"
            result = workflow.send_authorised_request(case_id)
            if retry:
                response.status_code = status.HTTP_200_OK
            return result
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Carrier recovery case not found") from error
        except CarrierRecoveryConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/carrier-recovery-cases/{case_id}/simulate-carrier-response", response_model=CarrierSimulationResult, status_code=status.HTTP_201_CREATED)
    def simulate_carrier_response(case_id: UUID, body: EffectiveAtBody, response: Response, session: SessionDependency) -> CarrierSimulationResult:
        workflow = build_carrier_recovery_workflow(session)
        try:
            retry = CarrierRecoveryRepository(session).simulation_receipt(case_id) is not None
            result = workflow.simulate_response(SimulateCarrierResponseCommand(case_id=case_id, **body.model_dump()))
            if retry:
                response.status_code = status.HTTP_200_OK
            return result
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Carrier recovery case not found") from error
        except CarrierRecoveryConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/carrier-recovery-cases/{case_id}/counter-approval", response_model=Approval, status_code=status.HTTP_201_CREATED)
    def counter_carrier_approval(case_id: UUID, body: CounterApprovalBody, response: Response, session: SessionDependency) -> Approval:
        workflow = build_carrier_recovery_workflow(session)
        try:
            retry = any(item.decision_id == body.proposal_decision_id for item in workflow.history(case_id).approvals)
            result = workflow.record_counter_approval(CounterApprovalCommand(case_id=case_id, **body.model_dump()))
            if retry:
                response.status_code = status.HTTP_200_OK
            return result
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Carrier recovery case or binding not found") from error
        except CarrierRecoveryConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/carrier-recovery-cases/{case_id}/evaluate-timeout", response_model=CarrierRecoveryCase, status_code=status.HTTP_201_CREATED)
    def evaluate_carrier_timeout(case_id: UUID, body: EffectiveAtBody, response: Response, session: SessionDependency) -> CarrierRecoveryCase:
        workflow = build_carrier_recovery_workflow(session)
        try:
            retry = any(item.event_type == "carrier.response_timed_out" for item in workflow.history(case_id).audit_events)
            result = workflow.evaluate_timeout(EvaluateTimeoutCommand(case_id=case_id, **body.model_dump()))
            if retry:
                response.status_code = status.HTTP_200_OK
            return result
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Carrier recovery case not found") from error
        except CarrierRecoveryConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.get("/incidents/{incident_id}/carrier-recovery-cases", response_model=list[CarrierRecoveryCase])
    def list_carrier_recovery_cases(incident_id: UUID, session: SessionDependency) -> list[CarrierRecoveryCase]:
        try:
            IncidentRepository(session).get(incident_id)
            return CarrierRecoveryRepository(session).list_cases(incident_id)
        except RecordNotFound as error:
            raise HTTPException(status_code=404, detail="Incident not found") from error

    @application.get("/carrier-recovery-cases/{case_id}", response_model=CarrierRecoveryCase)
    def get_carrier_recovery_case(case_id: UUID, session: SessionDependency) -> CarrierRecoveryCase:
        try:
            return CarrierRecoveryRepository(session).get_case(case_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Carrier recovery case not found") from error

    @application.get("/carrier-recovery-cases/{case_id}/history", response_model=CarrierRecoveryHistory)
    def get_carrier_recovery_history(case_id: UUID, session: SessionDependency) -> CarrierRecoveryHistory:
        try:
            return build_carrier_recovery_workflow(session).history(case_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Carrier recovery case not found") from error

    return application


app = create_app()
