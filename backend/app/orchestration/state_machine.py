from backend.app.domain.enums import IncidentState
from backend.app.domain.models import Incident


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
