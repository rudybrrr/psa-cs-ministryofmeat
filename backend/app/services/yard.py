from datetime import UTC, datetime

from backend.app.domain.models import Container, YardForecast


class SyntheticYardService:
    def forecast(self, container: Container) -> YardForecast:
        del container
        return YardForecast(
            id="SYN-YARD-20260821-AM",
            terminal_id="SYN-TUAS-TERMINAL",
            window_start=datetime(2026, 8, 21, 6, tzinfo=UTC),
            window_end=datetime(2026, 8, 21, 10, tzinfo=UTC),
            available_expedite_slots=4,
            generated_at=datetime(2026, 8, 21, 4, 30, tzinfo=UTC),
        )
