from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.app.domain.dynamic_yard import (
    AllocationRevision, AllocationTradeoffOption, AllocationTradeoffReview,
    ExpediteCommitment, ExpediteReconsiderationAssessment,
    ReconsiderationCandidate, ReconsiderationDisposition, TradeoffReviewState,
)
from backend.app.domain.scarcity import AllocationPlan, AllocationStrategy
from backend.app.storage.dynamic_yard import DynamicYardRepository
from backend.app.storage.repositories import IncidentRepository
from backend.app.storage.repositories import AuditRepository
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow


def _pending_review(session: Session, incident_id):
    repository = DynamicYardRepository(session)
    source_snapshot_id = uuid4()
    r0 = repository.add_revision(AllocationRevision(
        incident_id=incident_id, source_phase2_evaluation_id=uuid4(), source_forecast_snapshot_id=source_snapshot_id,
        allocated_container_ids=("SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-005"), locked_container_ids=("SYN-CNT-002", "SYN-CNT-004"),
        preserved_connection_total=601, expected_preserved_connections=12.02, reason="R0",
    ))
    for container_id in r0.allocated_container_ids:
        commitment = repository.add_commitment(ExpediteCommitment(incident_id=incident_id, origin_revision_id=r0.id, container_id=container_id))
        if container_id in r0.locked_container_ids:
            from backend.app.domain.dynamic_yard import ExpediteCommitmentStatus
            repository.transition_commitment(commitment.id, ExpediteCommitmentStatus.COMMITTED)
    assessment = repository.add_assessment(ExpediteReconsiderationAssessment(
        incident_id=incident_id, source_snapshot_id=source_snapshot_id, prior_allocation_revision_id=r0.id,
        locked_container_ids=r0.locked_container_ids, preserved_connection_total_before=601, preserved_connection_total_after=602,
        expected_preserved_connections_before=12.02, expected_preserved_connections_after=12.04,
        disposition=ReconsiderationDisposition.HUMAN_REVIEW_REQUIRED, reason="exact human choice required",
    ))
    option = AllocationTradeoffOption(review_id=uuid4(), allocated_container_ids=("SYN-CNT-001", "SYN-CNT-002", "SYN-CNT-004"), preserved_connection_total=602, expected_preserved_connections=12.04)
    review = AllocationTradeoffReview(id=option.review_id, incident_id=incident_id, reconsideration_assessment_id=assessment.id, option_ids=(option.id,), options_fingerprint=DynamicYardWorkflow._options_fingerprint((option,)), state=TradeoffReviewState.OPEN)
    repository.create_tradeoff_review(review, (option,))
    return review, option


def test_selection_api_applies_only_persisted_option_atomically(client: TestClient, api_engine, incident) -> None:
    with Session(api_engine) as session:
        IncidentRepository(session).create(incident)
        review, option = _pending_review(session, incident.id)

    response = client.post(f"/allocation-tradeoff-reviews/{review.id}/selection", json={
        "selected_option_id": str(option.id), "expected_options_fingerprint": review.options_fingerprint, "operator_id": "operator-1",
    })

    assert response.status_code == 201
    with Session(api_engine) as session:
        history = DynamicYardRepository(session).history(incident.id)
    assert history.reviews[0].state is TradeoffReviewState.RESOLVED
    assert len(history.selections) == 1
    assert history.revisions[-1].parent_revision_id == history.revisions[0].id
    assert history.revisions[-1].allocated_container_ids == option.allocated_container_ids
    events = AuditRepository(session).list_for_incident(incident.id)
    child_revision_id = str(history.revisions[-1].id)
    assert len([event for event in events if event.actor.value == "OPERATOR" and event.event_type == "allocation_tradeoff.option_selected"]) == 1
    assert len([event for event in events if event.actor.value == "POLICY" and event.event_type == "allocation_revision.applied" and event.payload["child_revision_id"] == child_revision_id]) == 1


def test_human_review_fingerprint_matches_exact_persisted_options(session, incident) -> None:
    IncidentRepository(session).create(incident)
    repository = DynamicYardRepository(session)
    source_snapshot_id = uuid4()
    r0 = repository.add_revision(AllocationRevision(incident_id=incident.id, source_phase2_evaluation_id=uuid4(), source_forecast_snapshot_id=source_snapshot_id, allocated_container_ids=("SYN-CNT-002",), locked_container_ids=(), preserved_connection_total=601, expected_preserved_connections=12.02, reason="R0"))
    assessment = repository.add_assessment(ExpediteReconsiderationAssessment(incident_id=incident.id, source_snapshot_id=source_snapshot_id, prior_allocation_revision_id=r0.id, locked_container_ids=(), candidate_options=(ReconsiderationCandidate(allocated_container_ids=("SYN-CNT-001",), preserved_connection_total=602, expected_preserved_connections=12.04),), preserved_connection_total_before=601, preserved_connection_total_after=602, expected_preserved_connections_before=12.02, expected_preserved_connections_after=12.04, disposition=ReconsiderationDisposition.HUMAN_REVIEW_REQUIRED, reason="exact human choice required"))

    review = DynamicYardWorkflow.for_session(session).apply_latest_assessment(incident.id)

    assert review is not None
    history = DynamicYardRepository(session).history(incident.id)
    persisted_options = tuple(option for option in history.options if option.review_id == review.id)
    assert review.reconsideration_assessment_id == assessment.id
    assert DynamicYardWorkflow._options_fingerprint(persisted_options) == review.options_fingerprint


def test_selection_api_rejects_stale_foreign_duplicate_and_missing(client: TestClient, api_engine, incident) -> None:
    with Session(api_engine) as session:
        IncidentRepository(session).create(incident)
        review, option = _pending_review(session, incident.id)
    path = f"/allocation-tradeoff-reviews/{review.id}/selection"
    body = {"selected_option_id": str(option.id), "expected_options_fingerprint": "b" * 64, "operator_id": "operator-1"}
    assert client.post(path, json=body).status_code == 409
    body["expected_options_fingerprint"] = review.options_fingerprint
    body["selected_option_id"] = str(uuid4())
    assert client.post(path, json=body).status_code == 409
    body["selected_option_id"] = str(option.id)
    assert client.post(path, json=body).status_code == 201
    assert client.post(path, json=body).status_code == 409
    assert client.post(f"/allocation-tradeoff-reviews/{uuid4()}/selection", json=body).status_code == 404
    assert client.post(path, json={"operator_id": "operator-1"}).status_code == 422


def test_selection_rolls_back_selection_revision_commitments_and_audit(session, incident, monkeypatch) -> None:
    IncidentRepository(session).create(incident)
    review, option = _pending_review(session, incident.id)
    workflow = DynamicYardWorkflow.for_session(session)
    original = workflow._repository.add_revision
    calls = 0

    def fail_child_revision(revision):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("forced crash after staged selection")
        return original(revision)

    monkeypatch.setattr(workflow._repository, "add_revision", fail_child_revision)
    with pytest.raises(RuntimeError, match="forced crash"):
        workflow.select_tradeoff(review.id, selected_option_id=option.id, expected_options_fingerprint=review.options_fingerprint, operator_id="operator-1")
    history = DynamicYardRepository(session).history(incident.id)
    assert history.reviews[0].state is TradeoffReviewState.OPEN
    assert not history.selections
    assert len(history.revisions) == 1
    assert not AuditRepository(session).list_for_incident(incident.id)
    monkeypatch.setattr(workflow._repository, "add_revision", original)
    workflow.select_tradeoff(review.id, selected_option_id=option.id, expected_options_fingerprint=review.options_fingerprint, operator_id="operator-1")
    assert len(DynamicYardRepository(session).history(incident.id).selections) == 1
