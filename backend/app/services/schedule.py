from datetime import UTC, datetime, timedelta

from backend.app.domain.enums import IncidentState
from backend.app.domain.models import Connection, Incident, ScheduleEvent


class SyntheticScheduleService:
    def delay_event(self) -> ScheduleEvent:
        return ScheduleEvent(
            id="SYN-EVT-20260821-001",
            vessel_call_id="SYN-VC-SOUTHERN-STAR-01",
            vessel_name="M/V Synthetic Southern Star",
            terminal_id="SYN-TUAS-TERMINAL",
            scheduled_arrival=datetime(2026, 8, 21, 5, tzinfo=UTC),
            estimated_arrival=datetime(
                2026, 8, 21, 6, 30, tzinfo=UTC
            ),
            delay_minutes=90,
            occurred_at=datetime(2026, 8, 21, 4, 45, tzinfo=UTC),
        )

    def create_incident(self, event: ScheduleEvent) -> Incident:
        return Incident(
            source_event_id=event.id,
            state=IncidentState.INCIDENT_RECEIVED,
            created_at=event.occurred_at,
        )

    def normal_connection_feasible(
        self,
        event: ScheduleEvent,
        connection: Connection,
    ) -> bool:
        ready_at = event.estimated_arrival + timedelta(
            minutes=connection.minimum_transfer_minutes
        )
        return ready_at <= connection.cutoff_at

    def expedited_connection_feasible(
        self,
        event: ScheduleEvent,
        connection: Connection,
    ) -> bool:
        ready_at = event.estimated_arrival + timedelta(
            minutes=connection.expedited_transfer_minutes
        )
        return ready_at <= connection.cutoff_at
