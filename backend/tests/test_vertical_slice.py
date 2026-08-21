from datetime import UTC, datetime

import pytest
from sqlmodel import Session

from backend.app.domain.enums import (
    AuditActor,
    DecisionAction,
    DecisionStatus,
    IncidentState,
)
from backend.app.orchestration.state_machine import build_workflow
from backend.app.policies.dominance import DominancePolicy
from backend.app.services.manifest import SyntheticManifestService
from backend.app.services.schedule import SyntheticScheduleService
from backend.app.services.yard import SyntheticYardService
from backend.app.storage.repositories import (
    AuditRepository,
    DecisionRepository,
    IncidentRepository,
)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 21, hour, minute, tzinfo=UTC)


def test_synthetic_schedule_delay_creates_a_received_tuas_incident() -> None:
    service = SyntheticScheduleService()

    event = service.delay_event()
    incident = service.create_incident(event)

    assert event.id == "SYN-EVT-20260821-001"
    assert event.vessel_call_id == "SYN-VC-SOUTHERN-STAR-01"
    assert event.vessel_name == "M/V Synthetic Southern Star"
    assert event.terminal_id == "SYN-TUAS-TERMINAL"
    assert event.scheduled_arrival == at(5)
    assert event.estimated_arrival == at(6, 30)
    assert event.delay_minutes == 90
    assert event.occurred_at == at(4, 45)
    assert incident.source_event_id == event.id
    assert incident.state is IncidentState.INCIDENT_RECEIVED
    assert incident.created_at == event.occurred_at


def test_synthetic_manifest_returns_the_one_affected_container() -> None:
    event = SyntheticScheduleService().delay_event()

    container = SyntheticManifestService().affected_container(event)

    assert container.id == "PSAU1234567"
    assert container.origin_port == "NLRTM"
    assert container.destination_port == "IDJKT"
    assert container.inbound_vessel_call_id == event.vessel_call_id
    assert container.cargo.commodity == "Synthetic industrial machinery"
    assert container.cargo.gross_weight_kg == 18_500
    assert container.cargo.dangerous_goods is False
    assert container.cargo.un_number is None
    assert container.onward_connection.id == "SYN-CONN-STRAITS-01"
    assert (
        container.onward_connection.outbound_vessel_name
        == "M/V Synthetic Straits Pioneer"
    )
    assert container.onward_connection.outbound_voyage == "SYN-SP-2108"
    assert container.onward_connection.destination_port == "IDJKT"
    assert container.onward_connection.cutoff_at == at(7, 30)
    assert container.onward_connection.departure_at == at(9)
    assert container.onward_connection.minimum_transfer_minutes == 120
    assert container.onward_connection.expedited_transfer_minutes == 45


def test_synthetic_yard_returns_the_tuas_service_forecast() -> None:
    event = SyntheticScheduleService().delay_event()
    container = SyntheticManifestService().affected_container(event)

    forecast = SyntheticYardService().forecast(container)

    assert forecast.id == "SYN-YARD-20260821-AM"
    assert forecast.terminal_id == "SYN-TUAS-TERMINAL"
    assert forecast.window_start == at(6)
    assert forecast.window_end == at(10)
    assert forecast.available_expedite_slots == 4
    assert forecast.generated_at == at(4, 30)


def test_normal_transfer_is_infeasible_after_the_schedule_delay() -> None:
    schedule = SyntheticScheduleService()
    event = schedule.delay_event()
    connection = SyntheticManifestService().affected_container(
        event
    ).onward_connection

    feasible = schedule.normal_connection_feasible(event, connection)

    assert feasible is False


def test_expedited_transfer_is_feasible_after_the_schedule_delay() -> None:
    schedule = SyntheticScheduleService()
    event = schedule.delay_event()
    connection = SyntheticManifestService().affected_container(
        event
    ).onward_connection

    feasible = schedule.expedited_connection_feasible(event, connection)

    assert feasible is True


def test_dominance_policy_selects_expedite_for_the_synthetic_facts() -> None:
    schedule = SyntheticScheduleService()
    event = schedule.delay_event()
    incident = schedule.create_incident(event)
    container = SyntheticManifestService().affected_container(event)
    forecast = SyntheticYardService().forecast(container)

    selected = DominancePolicy().decide(
        incident=incident,
        container=container,
        yard_forecast=forecast,
        original_connection_feasible=False,
        expedited_connection_feasible=True,
    )

    assert selected is not None
    alternative, decision = selected
    assert alternative.incident_id == incident.id
    assert alternative.container_id == container.id
    assert alternative.action is DecisionAction.EXPEDITE
    assert alternative.feasible is True
    assert alternative.projected_delay_minutes == 0
    assert decision.incident_id == incident.id
    assert decision.container_id == container.id
    assert decision.action is DecisionAction.EXPEDITE
    assert decision.status is DecisionStatus.APPROVED
    assert "synthetic yard forecast has capacity" in decision.rationale


@pytest.mark.parametrize(
    (
        "normal_feasible",
        "expedited_feasible",
        "available_slots",
    ),
    [
        (True, True, 4),
        (False, False, 4),
        (False, True, 0),
    ],
    ids=[
        "normal-transfer-already-feasible",
        "expedited-transfer-infeasible",
        "no-expedite-capacity",
    ],
)
def test_dominance_policy_returns_no_decision_without_all_conditions(
    normal_feasible: bool,
    expedited_feasible: bool,
    available_slots: int,
) -> None:
    schedule = SyntheticScheduleService()
    event = schedule.delay_event()
    incident = schedule.create_incident(event)
    container = SyntheticManifestService().affected_container(event)
    forecast = SyntheticYardService().forecast(container).model_copy(
        update={"available_expedite_slots": available_slots}
    )

    selected = DominancePolicy().decide(
        incident=incident,
        container=container,
        yard_forecast=forecast,
        original_connection_feasible=normal_feasible,
        expedited_connection_feasible=expedited_feasible,
    )

    assert selected is None


def test_one_container_completes_the_persisted_recovery_vertical_slice(
    session: Session,
) -> None:
    workflow = build_workflow(session)
    event = workflow.schedule.delay_event()

    result = workflow.run(event)

    assert result.incident.source_event_id == event.id
    assert result.incident.state is IncidentState.RESOLVED
    assert result.container.id == "PSAU1234567"
    assert result.yard_forecast.terminal_id == "SYN-TUAS-TERMINAL"
    assert result.yard_forecast.available_expedite_slots == 4
    assert result.original_connection_feasible is False
    assert result.expedited_connection_feasible is True
    assert result.alternative is not None
    assert result.alternative.action is DecisionAction.EXPEDITE
    assert result.decision is not None
    assert result.decision.action is DecisionAction.EXPEDITE
    assert result.decision.status is DecisionStatus.APPROVED

    assert IncidentRepository(session).get(result.incident.id) == result.incident
    persisted_decisions = DecisionRepository(session).list_for_incident(
        result.incident.id
    )
    assert persisted_decisions == [result.decision]

    audit = AuditRepository(session).list_for_incident(result.incident.id)
    assert [audit_event.event_type for audit_event in audit] == [
        "schedule.delay_ingested",
        "incident.created",
        "incident.state_transitioned",
        "manifest.container_loaded",
        "yard.forecast_retrieved",
        "incident.state_transitioned",
        "connection.feasibility_evaluated",
        "incident.state_transitioned",
        "decision.created",
        "incident.state_transitioned",
    ]
    assert [audit_event.actor for audit_event in audit] == [
        AuditActor.SYSTEM,
        AuditActor.SYSTEM,
        AuditActor.SYSTEM,
        AuditActor.SYSTEM,
        AuditActor.SYSTEM,
        AuditActor.SYSTEM,
        AuditActor.POLICY,
        AuditActor.SYSTEM,
        AuditActor.POLICY,
        AuditActor.SYSTEM,
    ]
    assert AuditActor.AGENT not in {event.actor for event in audit}
    assert [
        audit_event.payload["to"]
        for audit_event in audit
        if audit_event.event_type == "incident.state_transitioned"
    ] == [
        "COLLECTING_STATE",
        "CONSTRAINT_VALIDATION",
        "RECOVERY_ANALYSIS",
        "RESOLVED",
    ]
    feasibility = next(
        audit_event
        for audit_event in audit
        if audit_event.event_type == "connection.feasibility_evaluated"
    )
    assert feasibility.payload == {
        "connection_id": "SYN-CONN-STRAITS-01",
        "normal_feasible": False,
        "expedited_feasible": True,
    }


class NoCapacityYardService(SyntheticYardService):
    def forecast(self, container):
        return super().forecast(container).model_copy(
            update={"available_expedite_slots": 0}
        )


def test_workflow_escalates_without_inventing_a_decision_when_none_dominates(
    session: Session,
) -> None:
    workflow = build_workflow(session, yard=NoCapacityYardService())

    result = workflow.run(workflow.schedule.delay_event())

    assert result.incident.state is IncidentState.ESCALATED
    assert result.alternative is None
    assert result.decision is None
    assert DecisionRepository(session).list_for_incident(
        result.incident.id
    ) == []
    audit = AuditRepository(session).list_for_incident(result.incident.id)
    assert [
        event.payload["to"]
        for event in audit
        if event.event_type == "incident.state_transitioned"
    ] == [
        "COLLECTING_STATE",
        "CONSTRAINT_VALIDATION",
        "RECOVERY_ANALYSIS",
        "ESCALATED",
    ]
    assert not any(event.event_type == "decision.created" for event in audit)
    assert AuditActor.AGENT not in {event.actor for event in audit}
