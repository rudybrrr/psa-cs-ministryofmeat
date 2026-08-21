from datetime import UTC, datetime

from backend.app.domain.models import (
    CargoProfile,
    Connection,
    Container,
    ScheduleEvent,
)


class SyntheticManifestService:
    def affected_container(self, event: ScheduleEvent) -> Container:
        connection = Connection(
            id="SYN-CONN-STRAITS-01",
            outbound_vessel_name="M/V Synthetic Straits Pioneer",
            outbound_voyage="SYN-SP-2108",
            destination_port="IDJKT",
            cutoff_at=datetime(2026, 8, 21, 7, 30, tzinfo=UTC),
            departure_at=datetime(2026, 8, 21, 9, tzinfo=UTC),
            minimum_transfer_minutes=120,
            expedited_transfer_minutes=45,
        )
        cargo = CargoProfile(
            commodity="Synthetic industrial machinery",
            gross_weight_kg=18_500,
            dangerous_goods=False,
        )
        return Container(
            id="PSAU1234567",
            origin_port="NLRTM",
            destination_port="IDJKT",
            cargo=cargo,
            inbound_vessel_call_id=event.vessel_call_id,
            onward_connection=connection,
        )
