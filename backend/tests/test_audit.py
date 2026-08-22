from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlmodel import Session, create_engine, select
from sqlmodel.pool import StaticPool

from backend.app.audit.service import AuditService
from backend.app.domain.enums import (
    AuditActor,
    DecisionAction,
    DecisionStatus,
    IncidentState,
)
from backend.app.domain.models import AuditEvent, Decision, Incident
from backend.app.domain.scarcity import (
    CanonicalIncidentFixture,
    ScenarioSet,
    ScarcityEvaluationReport,
)
from backend.app.evaluation.scarcity import ScarcityComparisonService
from backend.app.storage import database
from backend.app.storage.repositories import (
    AuditRepository,
    DecisionRepository,
    IncidentRecord,
    IncidentRepository,
    RecordNotFound,
    ScarcityEvaluationRepository,
)


ORIGINAL_DECISION_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SUPERSEDING_DECISION_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 21, hour, minute, tzinfo=UTC)


def test_incident_repository_round_trips_and_updates_only_current_state(
    session: Session,
    incident: Incident,
) -> None:
    repository = IncidentRepository(session)

    created = repository.create(incident)
    updated = repository.update_state(
        incident.id, IncidentState.COLLECTING_STATE
    )

    assert created == incident
    assert updated == incident.model_copy(
        update={"state": IncidentState.COLLECTING_STATE}
    )
    assert repository.get(incident.id) == updated
    assert updated.created_at.tzinfo is UTC


def test_incident_repository_raises_for_an_unknown_incident(
    session: Session,
) -> None:
    unknown_id = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")

    with pytest.raises(RecordNotFound, match=str(unknown_id)):
        IncidentRepository(session).get(unknown_id)


def test_decision_repository_persists_supersession_fields_and_utc(
    session: Session,
    incident: Incident,
) -> None:
    IncidentRepository(session).create(incident)
    original = Decision(
        id=ORIGINAL_DECISION_ID,
        incident_id=incident.id,
        container_id="PSAU1234567",
        action=DecisionAction.EXPEDITE,
        status=DecisionStatus.SUPERSEDED,
        rationale="Original synthetic recovery decision.",
        created_at=at(6, 30),
    )
    replacement = Decision(
        id=SUPERSEDING_DECISION_ID,
        incident_id=incident.id,
        container_id="PSAU1234567",
        action=DecisionAction.ROLL,
        status=DecisionStatus.APPROVED,
        rationale="Synthetic cutoff can no longer be met.",
        supersedes=original.id,
        supersession_reason="Forecast moved beyond the connection cutoff.",
        created_at=at(6, 45),
    )
    repository = DecisionRepository(session)

    repository.add(original)
    repository.add(replacement)
    observed = repository.list_for_incident(incident.id)

    assert observed == [original, replacement]
    assert observed[1].supersedes == ORIGINAL_DECISION_ID
    assert (
        observed[1].supersession_reason
        == "Forecast moved beyond the connection cutoff."
    )
    assert observed[1].created_at.tzinfo is UTC


def test_decision_repository_add_many_is_atomic_and_preserves_input_order(
    session: Session,
    incident: Incident,
) -> None:
    IncidentRepository(session).create(incident)
    first = Decision(
        id=ORIGINAL_DECISION_ID,
        incident_id=incident.id,
        container_id="SYN-CNT-002",
        action=DecisionAction.EXPEDITE,
        status=DecisionStatus.APPROVED,
        rationale="Synthetic scarce-capacity allocation.",
        created_at=at(6, 30),
    )
    second = Decision(
        id=SUPERSEDING_DECISION_ID,
        incident_id=incident.id,
        container_id="SYN-CNT-004",
        action=DecisionAction.EXPEDITE,
        status=DecisionStatus.APPROVED,
        rationale="Synthetic scarce-capacity allocation.",
        created_at=at(6, 31),
    )
    repository = DecisionRepository(session)

    persisted = repository.add_many((first, second))

    assert persisted == (first, second)
    assert repository.list_for_incident(incident.id) == [first, second]


def test_scarcity_report_repository_round_trips_exact_json(
    session: Session,
    incident: Incident,
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    IncidentRepository(session).create(incident)
    report = ScarcityComparisonService().compare(
        incident_id=incident.id,
        fixture=canonical_fixture,
        scenarios=canonical_scenarios,
    )
    repository = ScarcityEvaluationRepository(session)

    persisted = repository.add(report)

    assert persisted == report
    assert repository.get_for_incident(incident.id) == report


def test_scarcity_report_repository_raises_for_unknown_incident(
    session: Session,
) -> None:
    unknown_id = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")

    with pytest.raises(RecordNotFound, match=str(unknown_id)):
        ScarcityEvaluationRepository(session).get_for_incident(unknown_id)


def test_audit_events_are_append_only_ordered_and_preserve_actor_identity(
    session: Session,
    incident: Incident,
) -> None:
    IncidentRepository(session).create(incident)
    repository = AuditRepository(session)
    service = AuditService(repository)
    first = service.record(
        actor=AuditActor.SYSTEM,
        actor_id="incident-state-machine",
        incident_id=incident.id,
        event_type="incident.state_transitioned",
        payload={
            "from": "INCIDENT_RECEIVED",
            "to": "COLLECTING_STATE",
            "attempt": 1,
        },
        timestamp=at(5, 1),
    )
    second = service.record(
        actor=AuditActor.POLICY,
        actor_id=None,
        incident_id=incident.id,
        event_type="policy.evidence_recorded",
        payload={"action": "EXPEDITE"},
        timestamp=at(5, 2),
    )

    observed = repository.list_for_incident(incident.id)

    assert [event.id for event in observed] == [first.id, second.id]
    assert observed[0] == first
    assert observed[0].actor is AuditActor.SYSTEM
    assert observed[0].actor_id == "incident-state-machine"
    assert observed[0].payload["to"] == "COLLECTING_STATE"
    assert observed[0].timestamp.tzinfo is UTC
    assert [event.actor for event in observed] == [
        AuditActor.SYSTEM,
        AuditActor.POLICY,
    ]
    assert AuditActor.AGENT not in {event.actor for event in observed}
    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")

    with pytest.raises(ValidationError, match="Instance is frozen"):
        observed[0].actor = AuditActor.AGENT


def test_audit_service_requires_an_explicit_actor(
    session: Session,
    incident: Incident,
) -> None:
    service = AuditService(AuditRepository(session))

    with pytest.raises(TypeError, match="actor"):
        service.record(
            incident_id=incident.id,
            event_type="incident.state_transitioned",
            payload={"to": "COLLECTING_STATE"},
        )


def test_database_helpers_create_tables_and_yield_a_usable_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(database, "engine", engine)

    database.create_db_and_tables(engine)
    session_iterator = database.get_session()
    yielded_session = next(session_iterator)

    assert set(inspect(engine).get_table_names()) == {
        "audit_events",
        "approval_bindings",
        "approvals",
        "carrier_recovery_audit_links",
        "carrier_recovery_cases",
        "carrier_recovery_decision_links",
        "carrier_responses",
        "container_reconsideration_results",
        "decisions",
        "effective_connection_timings",
        "incidents",
        "rta_request_contexts",
        "rta_requests",
        "scarcity_evaluations",
    }
    assert yielded_session.exec(select(IncidentRecord)).all() == []

    session_iterator.close()
    engine.dispose()


def test_audit_repository_returns_only_the_requested_incident(
    session: Session,
    incident: Incident,
) -> None:
    other_incident = incident.model_copy(
        update={
            "id": uuid4(),
            "source_event_id": "SYN-EVT-PERSIST-002",
        }
    )
    incidents = IncidentRepository(session)
    incidents.create(incident)
    incidents.create(other_incident)
    repository = AuditRepository(session)
    service = AuditService(repository)
    expected = service.record(
        actor=AuditActor.SYSTEM,
        incident_id=incident.id,
        event_type="incident.created",
        payload={},
        timestamp=at(5),
    )
    service.record(
        actor=AuditActor.SYSTEM,
        incident_id=other_incident.id,
        event_type="incident.created",
        payload={},
        timestamp=at(5),
    )

    assert repository.list_for_incident(incident.id) == [expected]


def test_audit_repository_can_add_an_uncommitted_event_for_a_larger_transaction(
    session: Session,
    incident: Incident,
) -> None:
    IncidentRepository(session).create(incident)
    repository = AuditRepository(session)
    event = AuditEvent(
        actor=AuditActor.SYSTEM,
        incident_id=incident.id,
        event_type="carrier_recovery.case_prepared",
        payload={},
        timestamp=at(6),
    )
    record = repository.add_uncommitted(event)

    assert record.id == str(event.id)
    assert repository.list_for_incident(incident.id) == [event]
