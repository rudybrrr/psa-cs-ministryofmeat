from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

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
from backend.app.domain.models import (
    Approval,
    AuditEvent,
    CargoProfile,
    CarrierResponse,
    Connection,
    Container,
    Decision,
    ExpediteAllocation,
    Incident,
    RecoveryAlternative,
    RTARequest,
    ScheduleEvent,
    YardForecast,
    utc_now,
)


INCIDENT_ID = UUID("11111111-1111-4111-8111-111111111111")
DECISION_ID = UUID("22222222-2222-4222-8222-222222222222")
RTA_REQUEST_ID = UUID("33333333-3333-4333-8333-333333333333")


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 21, hour, minute, tzinfo=UTC)


def connection() -> Connection:
    return Connection(
        id="SYN-CONN-STRAITS-01",
        outbound_vessel_name="M/V Synthetic Straits Pioneer",
        outbound_voyage="SYN-SP-2108",
        destination_port="IDJKT",
        cutoff_at=at(7, 30),
        departure_at=at(9),
        minimum_transfer_minutes=120,
        expedited_transfer_minutes=45,
    )


def cargo_profile() -> CargoProfile:
    return CargoProfile(
        commodity="Synthetic industrial machinery",
        gross_weight_kg=18_500,
        dangerous_goods=False,
    )


def schedule_event() -> ScheduleEvent:
    return ScheduleEvent(
        id="SYN-EVT-20260821-001",
        vessel_call_id="SYN-VC-SOUTHERN-STAR-01",
        vessel_name="M/V Synthetic Southern Star",
        terminal_id="SYN-TUAS-TERMINAL",
        scheduled_arrival=at(5),
        estimated_arrival=at(6, 30),
        delay_minutes=90,
        occurred_at=at(4, 45),
    )


def incident() -> Incident:
    return Incident(
        id=INCIDENT_ID,
        source_event_id="SYN-EVT-20260821-001",
        state=IncidentState.INCIDENT_RECEIVED,
        created_at=at(4, 46),
    )


def decision() -> Decision:
    return Decision(
        id=DECISION_ID,
        incident_id=INCIDENT_ID,
        container_id="PSAU1234567",
        action=DecisionAction.EXPEDITE,
        status=DecisionStatus.APPROVED,
        rationale="Synthetic yard capacity makes expedition dominant.",
        created_at=at(6, 35),
    )


def rta_request() -> RTARequest:
    return RTARequest(
        id=RTA_REQUEST_ID,
        incident_id=INCIDENT_ID,
        connection_id="SYN-CONN-STRAITS-01",
        requested_eta_pta=at(8),
        status=RTARequestStatus.PENDING,
        created_at=at(6, 40),
    )


def test_all_required_domain_contracts_are_constructible() -> None:
    schedule = schedule_event()
    cargo = cargo_profile()
    onward = connection()
    affected_container = Container(
        id="PSAU1234567",
        origin_port="NLRTM",
        destination_port="IDJKT",
        cargo=cargo,
        inbound_vessel_call_id=schedule.vessel_call_id,
        onward_connection=onward,
    )
    yard = YardForecast(
        id="SYN-YARD-20260821-AM",
        terminal_id="SYN-TUAS-TERMINAL",
        window_start=at(6),
        window_end=at(10),
        available_expedite_slots=4,
        generated_at=at(4, 30),
    )
    alternative = RecoveryAlternative(
        incident_id=INCIDENT_ID,
        container_id=affected_container.id,
        action=DecisionAction.EXPEDITE,
        feasible=True,
        projected_delay_minutes=0,
        rationale="Expedition meets the synthetic cutoff.",
    )
    allocation = ExpediteAllocation(
        incident_id=INCIDENT_ID,
        container_id=affected_container.id,
        yard_forecast_id=yard.id,
        requested_slots=1,
        status=AllocationStatus.PROPOSED,
        created_at=at(6, 36),
    )
    request = rta_request()
    response = CarrierResponse(
        request_id=request.id,
        carrier_id="SYN-CARRIER-01",
        response=CarrierResponseType.ACCEPT,
        message="Synthetic acceptance",
        received_at=at(6, 45),
    )
    recovery_decision = decision()
    approval = Approval(
        decision_id=recovery_decision.id,
        operator_id="SYN-OPERATOR-01",
        status=ApprovalStatus.APPROVED,
        reason="Synthetic approval",
        created_at=at(6, 37),
    )
    audit = AuditEvent(
        actor=AuditActor.SYSTEM,
        incident_id=INCIDENT_ID,
        event_type="incident.created",
        payload={"state": "INCIDENT_RECEIVED"},
        timestamp=at(4, 46),
    )

    contracts = {
        "schedule_event": schedule,
        "incident": incident(),
        "container": affected_container,
        "cargo_profile": cargo,
        "yard_forecast": yard,
        "connection": onward,
        "recovery_alternative": alternative,
        "expedite_allocation": allocation,
        "rta_request": request,
        "carrier_response": response,
        "decision": recovery_decision,
        "approval": approval,
        "audit_event": audit,
    }

    assert set(contracts) == {
        "schedule_event",
        "incident",
        "container",
        "cargo_profile",
        "yard_forecast",
        "connection",
        "recovery_alternative",
        "expedite_allocation",
        "rta_request",
        "carrier_response",
        "decision",
        "approval",
        "audit_event",
    }
    assert schedule.terminal_id == "SYN-TUAS-TERMINAL"
    assert yard.terminal_id == "SYN-TUAS-TERMINAL"


def test_decision_identity_is_immutable() -> None:
    recovery_decision = decision()

    with pytest.raises(ValidationError, match="Instance is frozen"):
        recovery_decision.id = uuid4()

    assert recovery_decision.id == DECISION_ID


def test_decision_rejects_a_naive_created_at() -> None:
    data = decision().model_dump()
    data["created_at"] = datetime(2026, 8, 21, 8, 0)
    with pytest.raises(ValidationError):
        Decision.model_validate(data)


def test_audit_event_rejects_a_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        AuditEvent(
            actor=AuditActor.SYSTEM,
            incident_id=INCIDENT_ID,
            event_type="incident.created",
            payload={},
            timestamp=datetime(2026, 8, 21, 8, 0),
        )


def test_default_timestamps_are_timezone_aware_utc() -> None:
    current = utc_now()

    assert current.tzinfo is UTC
    assert current.utcoffset().total_seconds() == 0


def test_audit_actor_contract_reserves_agent_and_covers_authority_sources() -> None:
    assert {actor.value for actor in AuditActor} == {
        "AGENT",
        "SOLVER",
        "POLICY",
        "OPERATOR",
        "CARRIER",
        "SYSTEM",
    }
    deterministic_event = AuditEvent(
        actor=AuditActor.SYSTEM,
        incident_id=INCIDENT_ID,
        event_type="incident.state_transitioned",
        payload={"to": "COLLECTING_STATE"},
    )
    assert deterministic_event.actor is AuditActor.SYSTEM


def test_carrier_response_uses_accept_or_counter_not_silence() -> None:
    request = rta_request()
    accepted = CarrierResponse(
        request_id=request.id,
        carrier_id="SYN-CARRIER-01",
        response=CarrierResponseType.ACCEPT,
        message="Synthetic acceptance",
    )
    countered = CarrierResponse(
        request_id=request.id,
        carrier_id="SYN-CARRIER-01",
        response=CarrierResponseType.COUNTER,
        counter_eta_pta=at(8, 15),
        message="Synthetic counter",
    )

    assert accepted.response is CarrierResponseType.ACCEPT
    assert accepted.counter_eta_pta is None
    assert countered.response is CarrierResponseType.COUNTER
    assert countered.counter_eta_pta == at(8, 15)

    with pytest.raises(ValidationError):
        CarrierResponse(
            request_id=request.id,
            carrier_id="SYN-CARRIER-01",
            response="SILENCE",
            message="No response is not a carrier response",
        )


def test_carrier_response_does_not_accept_a_boolean_acceptance_field() -> None:
    with pytest.raises(ValidationError, match="accepted"):
        CarrierResponse(
            request_id=RTA_REQUEST_ID,
            carrier_id="SYN-CARRIER-01",
            response=CarrierResponseType.ACCEPT,
            accepted=True,
        )


def test_future_timing_request_action_is_request_rta() -> None:
    assert DecisionAction.REQUEST_RTA.value == "REQUEST_RTA"
