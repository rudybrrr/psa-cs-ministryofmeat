from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue

from backend.app.domain.enums import (
    AllocationStatus,
    ApprovalStatus,
    AuditActor,
    CarrierResponseType,
    DecisionAction,
    DecisionStatus,
    IncidentState,
    RTARequestStatus,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScheduleEvent(FrozenContract):
    id: str
    vessel_call_id: str
    vessel_name: str
    terminal_id: str
    scheduled_arrival: AwareDatetime
    estimated_arrival: AwareDatetime
    delay_minutes: int = Field(gt=0)
    occurred_at: AwareDatetime


class Incident(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    source_event_id: str
    state: IncidentState
    created_at: AwareDatetime = Field(default_factory=utc_now)


class CargoProfile(FrozenContract):
    commodity: str
    gross_weight_kg: float = Field(gt=0)
    dangerous_goods: bool
    un_number: str | None = None


class Connection(FrozenContract):
    id: str
    outbound_vessel_name: str
    outbound_voyage: str
    destination_port: str
    cutoff_at: AwareDatetime
    departure_at: AwareDatetime
    minimum_transfer_minutes: int = Field(gt=0)
    expedited_transfer_minutes: int = Field(gt=0)


class Container(FrozenContract):
    id: str
    origin_port: str
    destination_port: str
    cargo: CargoProfile
    inbound_vessel_call_id: str
    onward_connection: Connection


class YardForecast(FrozenContract):
    id: str
    terminal_id: str
    window_start: AwareDatetime
    window_end: AwareDatetime
    available_expedite_slots: int = Field(ge=0)
    generated_at: AwareDatetime


class RecoveryAlternative(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    container_id: str
    action: DecisionAction
    feasible: bool
    projected_delay_minutes: int = Field(ge=0)
    rationale: str


class ExpediteAllocation(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    container_id: str
    yard_forecast_id: str
    requested_slots: int = Field(gt=0)
    status: AllocationStatus
    created_at: AwareDatetime = Field(default_factory=utc_now)


class RTARequest(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    connection_id: str
    requested_eta_pta: AwareDatetime
    status: RTARequestStatus
    created_at: AwareDatetime = Field(default_factory=utc_now)


class CarrierResponse(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    carrier_id: str
    response: CarrierResponseType
    counter_eta_pta: AwareDatetime | None = None
    message: str | None = None
    received_at: AwareDatetime = Field(default_factory=utc_now)


class Decision(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    container_id: str | None = None
    action: DecisionAction
    status: DecisionStatus
    rationale: str
    supersedes: UUID | None = None
    supersession_reason: str | None = None
    created_at: AwareDatetime = Field(default_factory=utc_now)


class Approval(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    decision_id: UUID
    operator_id: str
    status: ApprovalStatus
    reason: str | None = None
    created_at: AwareDatetime = Field(default_factory=utc_now)


class AuditEvent(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    actor: AuditActor
    actor_id: str | None = None
    incident_id: UUID
    event_type: str
    payload: dict[str, JsonValue]
    timestamp: AwareDatetime = Field(default_factory=utc_now)
