from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.app.domain.carrier_recovery import PrepareCarrierRecoveryCaseCommand, parse_explicit_utc


class AgentRuntimeClock(Protocol):
    def now(self) -> datetime: ...


class FixedAgentRuntimeClock:
    def __init__(self, value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("agent runtime clock must be UTC")
        self._value = value.astimezone(UTC)

    def now(self) -> datetime:
        return self._value


class CanonicalAgentRuntimeConfiguration:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    @classmethod
    def load(cls) -> "CanonicalAgentRuntimeConfiguration":
        root = Path(__file__).resolve().parents[3]
        path = root / "shared" / "fixtures" / "canonical-agent-runtime-config.json"
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def prepare_command(self, incident_id: UUID, connection_id: str) -> PrepareCarrierRecoveryCaseCommand:
        try:
            values = self._payload["rta_preparation"][connection_id]
        except KeyError as error:
            raise ValueError(f"no trusted RTA preparation configuration for {connection_id}") from error
        return PrepareCarrierRecoveryCaseCommand(
            incident_id=incident_id,
            connection_id=connection_id,
            prepared_at=values["prepared_at"],
            requested_eta_pta=values["requested_eta_pta"],
            response_deadline=values["response_deadline"],
        )

    def clock(self, name: str) -> FixedAgentRuntimeClock:
        return FixedAgentRuntimeClock(parse_explicit_utc(self._payload["synthetic_clock"][name]))
