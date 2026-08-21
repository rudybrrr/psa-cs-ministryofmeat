from backend.app.domain.enums import DecisionAction, DecisionStatus
from backend.app.domain.models import (
    Container,
    Decision,
    Incident,
    RecoveryAlternative,
    YardForecast,
)


class DominancePolicy:
    def decide(
        self,
        *,
        incident: Incident,
        container: Container,
        yard_forecast: YardForecast,
        original_connection_feasible: bool,
        expedited_connection_feasible: bool,
    ) -> tuple[RecoveryAlternative, Decision] | None:
        expedite_is_dominant = (
            not original_connection_feasible
            and expedited_connection_feasible
            and yard_forecast.available_expedite_slots >= 1
        )
        if not expedite_is_dominant:
            return None

        rationale = (
            "Normal transfer misses the synthetic cutoff; expedited "
            "transfer meets it and the synthetic yard forecast has capacity."
        )
        alternative = RecoveryAlternative(
            incident_id=incident.id,
            container_id=container.id,
            action=DecisionAction.EXPEDITE,
            feasible=True,
            projected_delay_minutes=0,
            rationale=rationale,
        )
        decision = Decision(
            incident_id=incident.id,
            container_id=container.id,
            action=DecisionAction.EXPEDITE,
            status=DecisionStatus.APPROVED,
            rationale=rationale,
        )
        return alternative, decision
