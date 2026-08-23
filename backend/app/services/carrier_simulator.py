from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.domain.enums import CarrierResponseType
from backend.app.domain.models import CarrierResponse, RTARequest
from backend.app.domain.carrier_recovery import parse_explicit_utc


DEFAULT_RESPONSE_PLAN_PATH = (
    Path(__file__).resolve().parents[3]
    / "shared"
    / "fixtures"
    / "canonical-carrier-response-plan.json"
)


class CarrierResponsePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(min_length=1)
    fixture_id: str
    connection_id: str = Field(min_length=1)
    outcome: str
    counter_eta_pta: datetime | None = None

    def outcome_for(self, connection_id: str) -> CarrierResponsePlan:
        if self.connection_id != connection_id:
            raise ValueError(f"carrier demo run {self.run_id} does not cover {connection_id}")
        return self


class CarrierDemoSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    suite_id: str
    fixture_id: str
    runs: tuple[CarrierResponsePlan, ...]

    @model_validator(mode="after")
    def require_runs_to_share_the_suite_fixture(self) -> CarrierDemoSuite:
        if any(run.fixture_id != self.fixture_id for run in self.runs):
            raise ValueError("every carrier demo run fixture_id must match the suite fixture_id")
        return self

    def run_for(self, run_id: str) -> CarrierResponsePlan:
        matches = [item for item in self.runs if item.run_id == run_id]
        if len(matches) != 1:
            raise ValueError(f"no unique carrier demo run for {run_id}")
        return matches[0]


class SyntheticCarrierResponsePlan:
    def __init__(self, fixture_path: Path = DEFAULT_RESPONSE_PLAN_PATH) -> None:
        self._fixture_path = fixture_path

    def load(self) -> CarrierDemoSuite:
        return CarrierDemoSuite.model_validate(
            json.loads(self._fixture_path.read_text(encoding="utf-8"))
        )

    def load_run(self, run_id: str) -> CarrierResponsePlan:
        return self.load().run_for(run_id)


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
