from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session

from backend.app.domain.cargo_safety import *
from backend.app.domain.enums import AuditActor, DecisionAction, DecisionStatus
from backend.app.domain.models import AuditEvent, Decision, utc_now
from backend.app.services.canonical_incident import SyntheticCanonicalIncidentService
from backend.app.services.semantic_safety import PROMPT_VERSION, OpenAISemanticSafetyChecker, SemanticSafetyChecker, SemanticSafetyCheckerFailure
from backend.app.storage.cargo_safety import CargoSafetyHistory, CargoSafetyRepository
from backend.app.storage.repositories import DecisionRepository, IncidentRepository, RecordNotFound

ESCALATION_REASON = "Automation blocked because structured cargo declaration and unstructured cargo evidence could not be reconciled safely. Human DG review required."

class CargoSafetyConflict(RuntimeError): pass

class CargoSafetyWorkflow:
    def __init__(self, *, session: Session, checker: SemanticSafetyChecker) -> None:
        self._session = session; self._checker = checker; self._reviews = CargoSafetyRepository(session); self._decisions = DecisionRepository(session); self._incidents = IncidentRepository(session); self._fixture = SyntheticCanonicalIncidentService()
    @classmethod
    def for_session(cls, session: Session, *, checker: SemanticSafetyChecker | None = None) -> "CargoSafetyWorkflow": return cls(session=session, checker=checker or OpenAISemanticSafetyChecker())
    def create_review(self, incident_id: UUID, container_id: str, note_text: str, note_source: str) -> CargoSafetyReview:
        self._incidents.get(incident_id)
        if self._profile(container_id) is None: raise ValueError("container is not canonical evidence")
        note = CargoNote(incident_id=incident_id, container_id=container_id, text=note_text, source=note_source)
        review = CargoSafetyReview(incident_id=incident_id, container_id=container_id, cargo_note_id=note.id)
        return self._reviews.create_note_and_review(note, review)
    def evaluate(self, review_id: UUID) -> CargoSafetyEvaluationResult:
        history = self._reviews.history(review_id)
        if history.review.state is CargoSafetyReviewState.COMPLETED:
            if history.assessment is None or history.policy_result is None: raise CargoSafetyConflict("completed review is missing durable outcome")
            decision = self._decision(history.review.incident_id, history.policy_result.replacement_decision_id)
            return CargoSafetyEvaluationResult(review=history.review, assessment=history.assessment, policy_result=history.policy_result, decision=decision)
        profile = self._profile(history.review.container_id)
        if profile is None: raise CargoSafetyConflict("canonical cargo evidence is unavailable")
        evidence = SemanticSafetyCheckInput(structured_dangerous_goods=profile.dangerous_goods, structured_un_number=profile.un_number, structured_commodity=profile.commodity, note_text=history.note.text)
        now = utc_now()
        try:
            output = self._checker.check(evidence)
            if output.result is SemanticCheckResult.CHECK_FAILED:
                raise SemanticSafetyCheckerFailure(SemanticCheckFailureKind.PROVIDER_ERROR)
            if output.evidence_excerpt is not None and output.evidence_excerpt not in history.note.text:
                raise SemanticSafetyCheckerFailure(SemanticCheckFailureKind.INVALID_OUTPUT)
            assessment = SemanticSafetyAssessment(review_id=history.review.id, incident_id=history.review.incident_id, container_id=history.review.container_id, cargo_note_id=history.note.id, result=output.result, explanation=output.explanation, evidence_excerpt=output.evidence_excerpt, structured_dangerous_goods=evidence.structured_dangerous_goods, structured_un_number=evidence.structured_un_number, structured_commodity=evidence.structured_commodity, checker_kind=self._checker.checker_kind, model_name=self._checker.model_name, prompt_version=PROMPT_VERSION, created_at=now)
            valid = output.result is not SemanticCheckResult.CHECK_FAILED
        except SemanticSafetyCheckerFailure as failure:
            assessment = SemanticSafetyAssessment(review_id=history.review.id, incident_id=history.review.incident_id, container_id=history.review.container_id, cargo_note_id=history.note.id, result=SemanticCheckResult.CHECK_FAILED, explanation="Semantic safety check could not be completed safely.", failure_kind=failure.kind, structured_dangerous_goods=evidence.structured_dangerous_goods, structured_un_number=evidence.structured_un_number, structured_commodity=evidence.structured_commodity, checker_kind=self._checker.checker_kind, model_name=self._checker.model_name, prompt_version=PROMPT_VERSION, created_at=now)
            valid = False
        escalation = assessment.result is not SemanticCheckResult.NO_CONTRADICTION_FOUND
        decision = self._escalation(history.review.incident_id, history.review.container_id, now) if escalation else None
        policy = SemanticSafetyPolicyResult(review_id=history.review.id, assessment_id=assessment.id, incident_id=history.review.incident_id, container_id=history.review.container_id, disposition=SemanticSafetyDisposition.ESCALATE if escalation else SemanticSafetyDisposition.PASS_THROUGH, automation_blocked=escalation, reason=ESCALATION_REASON if escalation else "No semantic contradiction found; this is not a safety determination.", replacement_decision_id=decision.id if decision else None, created_at=now)
        audit = [AuditEvent(actor=AuditActor("AGENT") if valid else AuditActor.SYSTEM, actor_id="cargo-semantic-checker" if valid else "cargo-safety-workflow", incident_id=history.review.incident_id, event_type="cargo.semantic_assessment_completed" if valid else "cargo.semantic_check_failed", payload={"review_id": str(history.review.id), "result": assessment.result.value}, timestamp=now), AuditEvent(actor=AuditActor.POLICY, actor_id="cargo-safety-policy", incident_id=history.review.incident_id, event_type="cargo.semantic_safety_evaluated", payload={"review_id": str(history.review.id), "disposition": policy.disposition.value}, timestamp=now)]
        if decision: audit.append(AuditEvent(actor=AuditActor.POLICY, actor_id="cargo-safety-policy", incident_id=history.review.incident_id, event_type="decision.escalated_for_cargo_review", payload={"review_id": str(history.review.id), "decision_id": str(decision.id), "container_id": decision.container_id}, timestamp=now))
        completed = history.review.model_copy(update={"state": CargoSafetyReviewState.COMPLETED, "updated_at": now})
        self._reviews.complete(completed, assessment, policy, decision, tuple(audit))
        return CargoSafetyEvaluationResult(review=completed, assessment=assessment, policy_result=policy, decision=decision)
    def history(self, review_id: UUID) -> CargoSafetyHistory: return self._reviews.history(review_id)
    def get(self, review_id: UUID) -> CargoSafetyReview: return self._reviews.get_review(review_id)
    def list(self, incident_id: UUID) -> list[CargoSafetyReview]: self._incidents.get(incident_id); return self._reviews.list_reviews(incident_id)
    def _profile(self, container_id: str):
        return next((p.container.cargo for p in self._fixture.load().profiles if p.container.id == container_id), None)
    def _decision(self, incident_id: UUID, decision_id: UUID | None) -> Decision | None:
        if decision_id is None: return None
        return next((d for d in self._decisions.list_for_incident(incident_id) if d.id == decision_id), None)
    def _escalation(self, incident_id: UUID, container_id: str, now: datetime) -> Decision:
        all_decisions = [d for d in self._decisions.list_for_incident(incident_id) if d.container_id == container_id]
        superseded = {d.supersedes for d in all_decisions if d.supersedes is not None}; current = [d for d in all_decisions if d.id not in superseded]
        if len(current) > 1: raise CargoSafetyConflict("ambiguous current decision lineage")
        prior = current[0] if current else None
        return Decision(incident_id=incident_id, container_id=container_id, action=DecisionAction.ESCALATE, status=DecisionStatus.APPROVED, rationale=ESCALATION_REASON, supersedes=prior.id if prior else None, supersession_reason="Cargo semantic safety review blocked automation and requires human DG review." if prior else None, created_at=now)
