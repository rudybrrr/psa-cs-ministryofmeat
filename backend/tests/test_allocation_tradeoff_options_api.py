from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.app.domain.dynamic_yard import (
    AllocationRevision,
    AllocationTradeoffReview,
    ExpediteCommitment,
    ExpediteCommitmentStatus,
    ExpediteReconsiderationAssessment,
    ReconsiderationCandidate,
    ReconsiderationDisposition,
)
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.storage.dynamic_yard import DynamicYardRepository
from backend.app.storage.repositories import AuditRepository, IncidentRepository


def test_allocation_tradeoff_options_unknown_incident_is_not_found(client: TestClient) -> None:
    response = client.get("/incidents/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/allocation-tradeoff-options")
    assert response.status_code == 404


def test_allocation_tradeoff_options_is_empty_and_read_only_before_phase_5b(client: TestClient) -> None:
    incident_id = client.post("/synthetic/scenarios/canonical-scarcity").json()["incident_id"]
    paths = [
        "yard-forecast-snapshots", "allocation-revisions", "expedite-commitments",
        "expedite-reconsiderations", "allocation-tradeoff-reviews",
        "allocation-tradeoff-options", "allocation-tradeoff-selections", "audit-events",
    ]
    before = {path: client.get(f"/incidents/{incident_id}/{path}").json() for path in paths}
    response = client.get(f"/incidents/{incident_id}/allocation-tradeoff-options")
    after = {path: client.get(f"/incidents/{incident_id}/{path}").json() for path in paths}
    assert response.status_code == 200
    assert response.json() == []
    assert after == before


def _persist_phase5b_review(engine, incident_id: UUID) -> AllocationTradeoffReview:
    """Persist R0 revision, commitments, and an unhandled HUMAN_REVIEW_REQUIRED
    assessment via repositories, then create the review/options through the
    production DynamicYardWorkflow path."""
    with Session(engine) as session:
        IncidentRepository(session).get(incident_id)
        repository = DynamicYardRepository(session)
        source_snapshot_id = uuid4()
        revision = repository.add_revision(AllocationRevision(
            incident_id=incident_id,
            source_phase2_evaluation_id=uuid4(),
            source_forecast_snapshot_id=source_snapshot_id,
            allocated_container_ids=("SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-005"),
            locked_container_ids=("SYN-CNT-002", "SYN-CNT-004"),
            preserved_connection_total=601,
            expected_preserved_connections=12.02,
            reason="R0 derives from frozen Phase 2 selected allocation",
        ))
        for container_id in revision.allocated_container_ids:
            commitment = repository.add_commitment(ExpediteCommitment(
                incident_id=incident_id, origin_revision_id=revision.id,
                container_id=container_id,
            ))
            if container_id in revision.locked_container_ids:
                repository.transition_commitment(commitment.id, ExpediteCommitmentStatus.COMMITTED)
        repository.add_assessment(ExpediteReconsiderationAssessment(
            incident_id=incident_id,
            source_snapshot_id=source_snapshot_id,
            prior_allocation_revision_id=revision.id,
            locked_container_ids=revision.locked_container_ids,
            candidate_options=(
                ReconsiderationCandidate(
                    allocated_container_ids=("SYN-CNT-001", "SYN-CNT-002", "SYN-CNT-004"),
                    preserved_connection_total=602,
                    expected_preserved_connections=12.04,
                ),
                ReconsiderationCandidate(
                    allocated_container_ids=("SYN-CNT-003", "SYN-CNT-002", "SYN-CNT-004"),
                    preserved_connection_total=602,
                    expected_preserved_connections=11.98,
                ),
            ),
            preserved_connection_total_before=601,
            preserved_connection_total_after=602,
            expected_preserved_connections_before=12.02,
            expected_preserved_connections_after=12.04,
            disposition=ReconsiderationDisposition.HUMAN_REVIEW_REQUIRED,
            reason="authorised policy leaves multiple non-dominated feasible options",
        ))
        review = DynamicYardWorkflow.for_session(session).apply_latest_assessment(incident_id)
        assert isinstance(review, AllocationTradeoffReview)
        return review


def _dynamic_yard_state(engine, incident_id: UUID) -> dict:
    with Session(engine) as session:
        history = DynamicYardRepository(session).history(incident_id)
        audit = AuditRepository(session).list_for_incident(incident_id)
        return {
            "snapshots": [item.model_dump(mode="json") for item in history.snapshots],
            "revisions": [item.model_dump(mode="json") for item in history.revisions],
            "commitments": [item.model_dump(mode="json") for item in history.commitments],
            "assessments": [item.model_dump(mode="json") for item in history.assessments],
            "reviews": [item.model_dump(mode="json") for item in history.reviews],
            "options": sorted(
                (item.model_dump(mode="json") for item in history.options),
                key=lambda item: item["id"],
            ),
            "selections": [item.model_dump(mode="json") for item in history.selections],
            "audit_events": [item.model_dump(mode="json") for item in audit],
        }


def test_allocation_tradeoff_options_returns_exact_persisted_options_without_mutation(
    client: TestClient, api_engine, incident
) -> None:
    incident_id = client.post("/synthetic/scenarios/canonical-scarcity").json()["incident_id"]
    _persist_phase5b_review(api_engine, UUID(incident_id))

    with Session(api_engine) as session:
        persisted_options = DynamicYardRepository(session).history(UUID(incident_id)).options
    expected = sorted(
        (option.model_dump(mode="json") for option in persisted_options),
        key=lambda option: option["id"],
    )
    assert len(expected) == 2

    before = _dynamic_yard_state(api_engine, UUID(incident_id))
    response = client.get(f"/incidents/{incident_id}/allocation-tradeoff-options")
    after = _dynamic_yard_state(api_engine, UUID(incident_id))

    assert response.status_code == 200
    assert sorted(response.json(), key=lambda option: option["id"]) == expected
    assert after == before
