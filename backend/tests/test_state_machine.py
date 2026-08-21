from datetime import UTC, datetime
from uuid import UUID

import pytest

from backend.app.domain.enums import IncidentState
from backend.app.domain.models import Incident
from backend.app.orchestration.state_machine import (
    IncidentStateMachine,
    InvalidIncidentTransition,
)


INCIDENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

EXPECTED_STATES = [
    IncidentState.INCIDENT_RECEIVED,
    IncidentState.COLLECTING_STATE,
    IncidentState.CONSTRAINT_VALIDATION,
    IncidentState.RECOVERY_ANALYSIS,
    IncidentState.RESOLVED,
]


def received_incident() -> Incident:
    return Incident(
        id=INCIDENT_ID,
        source_event_id="SYN-EVT-STATE-001",
        state=IncidentState.INCIDENT_RECEIVED,
        created_at=datetime(2026, 8, 21, 5, 0, tzinfo=UTC),
    )


def incident_in(state: IncidentState) -> Incident:
    return received_incident().model_copy(update={"state": state})


def test_state_machine_accepts_the_vertical_slice_path_without_mutating_input() -> None:
    machine = IncidentStateMachine()
    original = received_incident()
    current = original
    observed = [current.state]

    for target in EXPECTED_STATES[1:]:
        current = machine.transition(current, target)
        observed.append(current.state)

    assert observed == EXPECTED_STATES
    assert original.state is IncidentState.INCIDENT_RECEIVED
    assert current.id == original.id


@pytest.mark.parametrize(
    "source",
    [
        IncidentState.COLLECTING_STATE,
        IncidentState.CONSTRAINT_VALIDATION,
        IncidentState.RECOVERY_ANALYSIS,
    ],
)
def test_state_machine_allows_escalation_from_active_states(
    source: IncidentState,
) -> None:
    escalated = IncidentStateMachine().transition(
        incident_in(source), IncidentState.ESCALATED
    )

    assert escalated.state is IncidentState.ESCALATED


def test_state_machine_rejects_skipping_recovery_analysis() -> None:
    with pytest.raises(InvalidIncidentTransition):
        IncidentStateMachine().transition(
            received_incident(), IncidentState.RESOLVED
        )


@pytest.mark.parametrize(
    "terminal",
    [IncidentState.RESOLVED, IncidentState.ESCALATED],
)
def test_state_machine_rejects_transitions_from_terminal_states(
    terminal: IncidentState,
) -> None:
    with pytest.raises(InvalidIncidentTransition):
        IncidentStateMachine().transition(
            incident_in(terminal), IncidentState.COLLECTING_STATE
        )
