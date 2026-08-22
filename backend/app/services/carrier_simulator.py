from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.enums import CarrierResponseType
from backend.app.domain.models import CarrierResponse, RTARequest
from backend.app.domain.carrier_recovery import parse_explicit_utc


DEFAULT_RESPONSE_PLAN_PATH = (
    Path(__file__).resolve().parents[3]
    / "shared"
    / "fixtures"
    / "canonical-carrier-response-plan.json"
)


class CarrierResponsePlanEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    connection_id: str = Field(min_length=1)
    outcome: str
    counter_eta_pta: datetime | None = None


class CarrierResponsePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    plan_id: str
    fixture_id: str
    responses: tuple[CarrierResponsePlanEntry, ...]

    def outcome_for(self, connection_id: str) -> CarrierResponsePlanEntry:
        matches = [item for item in self.responses if item.connection_id == connection_id]
        if len(matches) != 1:
            raise ValueError(f"no unique carrier response plan for {connection_id}")
        return matches[0]


class SyntheticCarrierResponsePlan:
    def __init__(self, fixture_path: Path = DEFAULT_RESPONSE_PLAN_PATH) -> None:
        self._fixture_path = fixture_path

    def load(self) -> CarrierResponsePlan:
        return CarrierResponsePlan.model_validate(
            json.loads(self._fixture_path.read_text(encoding="utf-8"))
        )


class DeterministicCarrierSimulator:
    def __init__(self, plan: CarrierResponsePlan) -> None:
        self._plan = plan

    def emit(self, request: RTARequest, effective_at: datetime) -> CarrierResponse | None:
        entry = self._plan.outcome_for(request.connection_id)
        if entry.outcome == "SILENT":
            return None
        if entry.outcome == "ACCEPT":
            return CarrierResponse(
                request_id=request.id,
                carrier_id="SYN-CARRIER-RTA",
                response=CarrierResponseType.ACCEPT,
                received_at=effective_at,
            )
        if entry.outcome == "COUNTER" and entry.counter_eta_pta is not None:
            return CarrierResponse(
                request_id=request.id,
                carrier_id="SYN-CARRIER-RTA",
                response=CarrierResponseType.COUNTER,
                counter_eta_pta=entry.counter_eta_pta,
                received_at=effective_at,
            )
        raise ValueError(f"invalid carrier response plan outcome {entry.outcome}")
