from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.app.domain.carrier_recovery import (
    ApprovalBinding,
    AuthorizationSubjectKind,
    CarrierRecoveryCase,
    CarrierRecoveryCaseState,
    CarrierRecoveryCaseStateMachine,
    PrepareCarrierRecoveryCaseCommand,
    parse_explicit_utc,
)
from backend.app.domain.enums import DecisionAction


CASE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
INCIDENT_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
EVALUATION_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
DECISION_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
REQUEST_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")


def at(hour: int) -> datetime:
    return datetime(2026, 8, 22, hour, tzinfo=UTC)


def case() -> CarrierRecoveryCase:
    return CarrierRecoveryCase(
        id=CASE_ID,
        incident_id=INCIDENT_ID,
        connection_id="SYN-CONN-SF1",
        source_evaluation_id=EVALUATION_ID,
        affected_container_ids=("SYN-CNT-001",),
        state=CarrierRecoveryCaseState.PREPARED,
        created_at=at(6),
        updated_at=at(6),
    )


def test_decision_actions_add_only_preserve_via_rta() -> None:
    assert {item.value for item in DecisionAction} == {
        "EXPEDITE", "REQUEST_RTA", "ROLL", "ESCALATE", "PRESERVE_VIA_RTA"
    }


@pytest.mark.parametrize("value", ["2026-08-22T06:00:00Z", "2026-08-22T06:00:00+00:00"])
def test_parse_explicit_utc_accepts_only_explicit_utc(value: str) -> None:
    assert parse_explicit_utc(value).tzinfo is UTC


def test_parse_explicit_utc_rejects_non_utc_offset() -> None:
    with pytest.raises(ValueError):
        parse_explicit_utc("2026-08-22T14:00:00+08:00")


def test_case_snapshot_is_non_empty_and_transition_is_additive() -> None:
    prepared = case()
    transitioned = CarrierRecoveryCaseStateMachine().transition(
        prepared, CarrierRecoveryCaseState.AWAITING_REQUEST_APPROVAL
    )
    assert transitioned.state is CarrierRecoveryCaseState.AWAITING_REQUEST_APPROVAL
    assert transitioned.affected_container_ids == ("SYN-CNT-001",)
    with pytest.raises(ValidationError):
        CarrierRecoveryCase(
            id=CASE_ID,
            incident_id=INCIDENT_ID,
            connection_id="SYN-CONN-SF1",
            source_evaluation_id=EVALUATION_ID,
            affected_container_ids=(),
            state=CarrierRecoveryCaseState.PREPARED,
            created_at=at(6),
            updated_at=at(6),
        )


def test_binding_and_prepare_command_require_explicit_utc_evidence() -> None:
    binding = ApprovalBinding(
        case_id=CASE_ID,
        proposal_decision_id=DECISION_ID,
        subject_kind=AuthorizationSubjectKind.OUTBOUND_REQUEST,
        subject_id=REQUEST_ID,
        payload_fingerprint="a" * 64,
        created_at=at(6),
    )
    command = PrepareCarrierRecoveryCaseCommand(
        incident_id=INCIDENT_ID,
        connection_id="SYN-CONN-SF1",
        requested_eta_pta="2026-08-22T07:00:00Z",
        response_deadline="2026-08-22T08:00:00+00:00",
    )
    assert binding.subject_id == REQUEST_ID
    assert command.requested_eta_pta == at(7)
    assert command.response_deadline == at(8)
