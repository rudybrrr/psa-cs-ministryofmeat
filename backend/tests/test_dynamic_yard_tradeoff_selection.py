from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.app.domain.dynamic_yard import (
    AllocationRevision, AllocationTradeoffOption, AllocationTradeoffReview,
    ExpediteCommitment, ExpediteReconsiderationAssessment,
    ReconsiderationDisposition, TradeoffReviewState,
)
from backend.app.domain.scarcity import AllocationPlan, AllocationStrategy
from backend.app.storage.dynamic_yard import DynamicYardRepository
from backend.app.storage.repositories import IncidentRepository


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
    review = AllocationTradeoffReview(id=option.review_id, incident_id=incident_id, reconsideration_assessment_id=assessment.id, option_ids=(option.id,), options_fingerprint="a" * 64, state=TradeoffReviewState.OPEN)
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
