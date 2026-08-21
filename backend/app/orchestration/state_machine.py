from dataclasses import dataclass

from sqlmodel import Session

from backend.app.audit.service import AuditService
from backend.app.domain.enums import AuditActor, IncidentState
from backend.app.domain.models import (
    Container,
    Decision,
    Incident,
    RecoveryAlternative,
    ScheduleEvent,
    YardForecast,
)
from backend.app.policies.dominance import DominancePolicy
from backend.app.services.manifest import SyntheticManifestService
from backend.app.services.schedule import SyntheticScheduleService
from backend.app.services.yard import SyntheticYardService
from backend.app.storage.repositories import (
    AuditRepository,
    DecisionRepository,
    IncidentRepository,
)


ALLOWED_TRANSITIONS: dict[IncidentState, frozenset[IncidentState]] = {
    IncidentState.INCIDENT_RECEIVED: frozenset(
        {IncidentState.COLLECTING_STATE}
    ),
    IncidentState.COLLECTING_STATE: frozenset(
        {IncidentState.CONSTRAINT_VALIDATION, IncidentState.ESCALATED}
    ),
    IncidentState.CONSTRAINT_VALIDATION: frozenset(
        {IncidentState.RECOVERY_ANALYSIS, IncidentState.ESCALATED}
    ),
    IncidentState.RECOVERY_ANALYSIS: frozenset(
        {IncidentState.RESOLVED, IncidentState.ESCALATED}
    ),
    IncidentState.RESOLVED: frozenset(),
    IncidentState.ESCALATED: frozenset(),
}


class InvalidIncidentTransition(ValueError):
    def __init__(self, source: IncidentState, target: IncidentState) -> None:
        self.source = source
        self.target = target
        super().__init__(f"Cannot transition incident from {source} to {target}")


class IncidentStateMachine:
    def transition(self, incident: Incident, target: IncidentState) -> Incident:
        if target not in ALLOWED_TRANSITIONS[incident.state]:
            raise InvalidIncidentTransition(incident.state, target)
        return incident.model_copy(update={"state": target})


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    incident: Incident
    container: Container
    yard_forecast: YardForecast
    original_connection_feasible: bool
    expedited_connection_feasible: bool
    alternative: RecoveryAlternative | None
    decision: Decision | None


class TransshipmentRecoveryWorkflow:
    def __init__(
        self,
        *,
        schedule: SyntheticScheduleService,
        manifest: SyntheticManifestService,
        yard: SyntheticYardService,
        policy: DominancePolicy,
        state_machine: IncidentStateMachine,
        incidents: IncidentRepository,
        decisions: DecisionRepository,
        audit: AuditService,
    ) -> None:
        self.schedule = schedule
        self._manifest = manifest
        self._yard = yard
        self._policy = policy
        self._state_machine = state_machine
        self._incidents = incidents
        self._decisions = decisions
        self._audit = audit

    def run(self, event: ScheduleEvent) -> RecoveryResult:
        incident = self._incidents.create(
            self.schedule.create_incident(event)
        )
        self._audit.record(
            actor=AuditActor.SYSTEM,
            actor_id="synthetic-schedule-service",
            incident_id=incident.id,
            event_type="schedule.delay_ingested",
            payload={
                "event_id": event.id,
                "vessel_call_id": event.vessel_call_id,
                "terminal_id": event.terminal_id,
                "delay_minutes": event.delay_minutes,
            },
        )
        self._audit.record(
            actor=AuditActor.SYSTEM,
            actor_id="transshipment-recovery-workflow",
            incident_id=incident.id,
            event_type="incident.created",
            payload={"state": incident.state.value},
        )

        incident = self._transition(
            incident, IncidentState.COLLECTING_STATE
        )
        container = self._manifest.affected_container(event)
        self._audit.record(
            actor=AuditActor.SYSTEM,
            actor_id="synthetic-manifest-service",
            incident_id=incident.id,
            event_type="manifest.container_loaded",
            payload={
                "container_id": container.id,
                "connection_id": container.onward_connection.id,
            },
        )
        yard_forecast = self._yard.forecast(container)
        self._audit.record(
            actor=AuditActor.SYSTEM,
            actor_id="synthetic-yard-service",
            incident_id=incident.id,
            event_type="yard.forecast_retrieved",
            payload={
                "forecast_id": yard_forecast.id,
                "terminal_id": yard_forecast.terminal_id,
                "available_expedite_slots": (
                    yard_forecast.available_expedite_slots
                ),
            },
        )

        incident = self._transition(
            incident, IncidentState.CONSTRAINT_VALIDATION
        )
        connection = container.onward_connection
        original_feasible = self.schedule.normal_connection_feasible(
            event, connection
        )
        expedited_feasible = self.schedule.expedited_connection_feasible(
            event, connection
        )
        self._audit.record(
            actor=AuditActor.POLICY,
            actor_id="connection-feasibility-policy",
            incident_id=incident.id,
            event_type="connection.feasibility_evaluated",
            payload={
                "connection_id": connection.id,
                "normal_feasible": original_feasible,
                "expedited_feasible": expedited_feasible,
            },
        )

        incident = self._transition(
            incident, IncidentState.RECOVERY_ANALYSIS
        )
        selected = self._policy.decide(
            incident=incident,
            container=container,
            yard_forecast=yard_forecast,
            original_connection_feasible=original_feasible,
            expedited_connection_feasible=expedited_feasible,
        )
        if selected is None:
            incident = self._transition(
                incident, IncidentState.ESCALATED
            )
            return RecoveryResult(
                incident=incident,
                container=container,
                yard_forecast=yard_forecast,
                original_connection_feasible=original_feasible,
                expedited_connection_feasible=expedited_feasible,
                alternative=None,
                decision=None,
            )

        alternative, decision = selected
        decision = self._decisions.add(decision)
        self._audit.record(
            actor=AuditActor.POLICY,
            actor_id="dominance-policy",
            incident_id=incident.id,
            event_type="decision.created",
            payload={
                "decision_id": str(decision.id),
                "alternative_id": str(alternative.id),
                "container_id": container.id,
                "action": decision.action.value,
                "status": decision.status.value,
            },
        )
        incident = self._transition(incident, IncidentState.RESOLVED)
        return RecoveryResult(
            incident=incident,
            container=container,
            yard_forecast=yard_forecast,
            original_connection_feasible=original_feasible,
            expedited_connection_feasible=expedited_feasible,
            alternative=alternative,
            decision=decision,
        )

    def _transition(
        self,
        incident: Incident,
        target: IncidentState,
    ) -> Incident:
        source = incident.state
        transitioned = self._state_machine.transition(incident, target)
        persisted = self._incidents.update_state(
            incident.id, transitioned.state
        )
        self._audit.record(
            actor=AuditActor.SYSTEM,
            actor_id="transshipment-recovery-workflow",
            incident_id=incident.id,
            event_type="incident.state_transitioned",
            payload={"from": source.value, "to": target.value},
        )
        return persisted


def build_workflow(
    session: Session,
    *,
    yard: SyntheticYardService | None = None,
) -> TransshipmentRecoveryWorkflow:
    return TransshipmentRecoveryWorkflow(
        schedule=SyntheticScheduleService(),
        manifest=SyntheticManifestService(),
        yard=yard or SyntheticYardService(),
        policy=DominancePolicy(),
        state_machine=IncidentStateMachine(),
        incidents=IncidentRepository(session),
        decisions=DecisionRepository(session),
        audit=AuditService(AuditRepository(session)),
    )
