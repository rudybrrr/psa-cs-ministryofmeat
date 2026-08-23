from uuid import UUID

from backend.app.domain.cargo_safety import SemanticCheckResult
from backend.app.domain.enums import AuditActor, DecisionAction, DecisionStatus
from backend.app.domain.models import Decision
from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
from backend.app.services.semantic_safety import FakeSemanticSafetyChecker
from backend.app.storage.repositories import DecisionRepository, IncidentRepository


def test_contradiction_supersedes_current_container_decision(session, incident) -> None:
    IncidentRepository(session).create(incident)
    prior = Decision(incident_id=incident.id, container_id="SYN-CNT-010", action=DecisionAction.ROLL, status=DecisionStatus.APPROVED, rationale="Prior recovery.")
    DecisionRepository(session).add(prior)
    workflow = CargoSafetyWorkflow.for_session(session, checker=FakeSemanticSafetyChecker(result=SemanticCheckResult.CONTRADICTION_FOUND))
    review = workflow.create_review(incident.id, "SYN-CNT-010", "Shipment includes UN 3480 lithium-ion batteries packed separately.", "hero")
    result = workflow.evaluate(review.id)
    assert result.policy_result.automation_blocked is True
    assert result.decision is not None
    assert result.decision.action is DecisionAction.ESCALATE
    assert result.decision.supersedes == prior.id
    assert [event.actor for event in workflow.history(review.id).audit_events] == [AuditActor.AGENT, AuditActor.POLICY, AuditActor.POLICY]


def test_pass_through_preserves_current_decision_and_completed_retry_is_idempotent(session, incident) -> None:
    IncidentRepository(session).create(incident)
    prior = Decision(incident_id=incident.id, container_id="SYN-CNT-010", action=DecisionAction.ROLL, status=DecisionStatus.APPROVED, rationale="Prior recovery.")
    DecisionRepository(session).add(prior)
    checker = FakeSemanticSafetyChecker(result=SemanticCheckResult.NO_CONTRADICTION_FOUND)
    workflow = CargoSafetyWorkflow.for_session(session, checker=checker)
    review = workflow.create_review(incident.id, "SYN-CNT-010", "Documentation confirms pallet count.", "ops")
    first = workflow.evaluate(review.id)
    second = workflow.evaluate(review.id)
    assert first.policy_result.automation_blocked is False
    assert first.decision is None and second == first
    assert checker.calls == 1
    assert DecisionRepository(session).list_for_incident(incident.id) == [prior]
