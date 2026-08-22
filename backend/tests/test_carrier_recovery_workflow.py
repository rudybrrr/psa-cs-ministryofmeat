from datetime import UTC, datetime

import pytest
from sqlmodel import Session

from backend.app.domain.carrier_recovery import PrepareCarrierRecoveryCaseCommand
from backend.app.domain.enums import DecisionAction, DecisionStatus
from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
from backend.app.storage.repositories import DecisionRepository


def command(incident_id, connection_id: str) -> PrepareCarrierRecoveryCaseCommand:
    return PrepareCarrierRecoveryCaseCommand(
        incident_id=incident_id,
        connection_id=connection_id,
        requested_eta_pta="2026-08-22T08:00:00Z",
        response_deadline="2026-08-22T09:00:00Z",
    )


def test_prepare_reuses_resolved_phase_two_evidence_and_freezes_connection_snapshot(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "JV2"))

    assert case.incident_id == phase_two.incident.id
    assert case.source_evaluation_id == phase_two.report.id
    assert case.connection_id == "JV2"
    assert case.affected_container_ids
    history = workflow.history(case.id)
    assert history.request is not None
    assert history.request.connection_id == "JV2"


def test_prepare_creates_fallback_rolls_with_explicit_current_decision_lineage(
    session: Session,
) -> None:
    phase_two = build_scarce_capacity_workflow(session).run()
    workflow = build_carrier_recovery_workflow(session)
    case = workflow.prepare(command(phase_two.incident.id, "JV2"))
    decisions = DecisionRepository(session).list_for_incident(phase_two.incident.id)
    fallbacks = [
        item for item in decisions
        if item.action is DecisionAction.ROLL and item.container_id in case.affected_container_ids
    ]
    proposal = [item for item in decisions if item.action is DecisionAction.REQUEST_RTA]

    assert len(fallbacks) == len(case.affected_container_ids)
    assert all(item.status is DecisionStatus.APPROVED for item in fallbacks)
    assert all("zero preserved worlds" in (item.supersession_reason or "") or item.supersedes is None for item in fallbacks)
    assert len(proposal) == 1
    assert proposal[0].container_id is None
