from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from backend.app.domain.dynamic_yard import ContainerReadyForecast, ForecastStage, YardForecastSnapshot
from backend.app.services.canonical_incident import SyntheticCanonicalIncidentService


ACTIVE_HALF_WIDTH_MINUTES = 17.987433384504683


class CanonicalDynamicYardHarness:
    def __init__(self, fixture_service: SyntheticCanonicalIncidentService | None = None) -> None:
        self._fixture_service = fixture_service or SyntheticCanonicalIncidentService()

    def bootstrap_snapshot(self, incident_id: UUID) -> YardForecastSnapshot:
        return self._snapshot(incident_id, ForecastStage.PRE_DISCHARGE, 30.0)

    def discharge_active_snapshot(self, incident_id: UUID) -> YardForecastSnapshot:
        return self._snapshot(incident_id, ForecastStage.DISCHARGE_ACTIVE, ACTIVE_HALF_WIDTH_MINUTES)

    def _snapshot(self, incident_id: UUID, stage: ForecastStage, width: float) -> YardForecastSnapshot:
        forecasts = []
        for profile in self._fixture_service.load().profiles:
            p50 = profile.base_ready_at
            if stage is ForecastStage.DISCHARGE_ACTIVE and profile.container.id == "SYN-CNT-005":
                p50 = p50 - timedelta(minutes=3)
            forecasts.append(ContainerReadyForecast(container_id=profile.container.id, p10_ready_at=p50 - timedelta(minutes=width), p50_ready_at=p50, p90_ready_at=p50 + timedelta(minutes=width)))
        generated_at = datetime(2026, 8, 22, 4 if stage is ForecastStage.PRE_DISCHARGE else 5, 0, tzinfo=UTC)
        return YardForecastSnapshot(incident_id=incident_id, stage=stage, generated_at=generated_at, source="synthetic-canonical-dynamic-yard", container_forecasts=tuple(forecasts))
