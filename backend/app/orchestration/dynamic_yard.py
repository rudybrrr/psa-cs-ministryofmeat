from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session

from backend.app.domain.dynamic_yard import (
    AllocationRevision,
    AllocationTradeoffHistory,
    AllocationTradeoffOption,
    AllocationTradeoffReview,
    ExpediteCommitment,
    ExpediteCommitmentStatus,
    ExpediteReconsiderationAssessment,
    ForecastStage,
    ReconsiderationDisposition,
    TradeoffReviewState,
    YardForecastSnapshot,
)
from backend.app.domain.scarcity import AllocationPlan, AllocationStrategy
from backend.app.domain.enums import AuditActor
from backend.app.domain.models import AuditEvent
from backend.app.evaluation.dynamic_yard import connection_is_phase3_compatible, reconstruct_phase2_worlds
from backend.app.optimization.dynamic_yard import assess_reconsideration
from backend.app.services.canonical_incident import SyntheticCanonicalIncidentService
from backend.app.storage.dynamic_yard import DynamicYardRepository
from backend.app.storage.repositories import ScarcityEvaluationRepository
from backend.app.storage.repositories import AuditRepository


class DynamicYardWorkflow:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = DynamicYardRepository(session)
        self._evaluations = ScarcityEvaluationRepository(session)
        self._fixture = SyntheticCanonicalIncidentService()

    @classmethod
    def for_session(cls, session: Session) -> "DynamicYardWorkflow":
        return cls(session)

    def initialize(self, incident_id: UUID, snapshot: YardForecastSnapshot) -> AllocationTradeoffHistory:
        if snapshot.incident_id != incident_id or snapshot.stage is not ForecastStage.PRE_DISCHARGE:
            raise ValueError("dynamic-yard initialization requires its PRE_DISCHARGE snapshot")
        report = self._evaluations.get_for_incident(incident_id)
        if report.selected_allocation is None:
            raise ValueError("dynamic-yard initialization requires selected Phase 2 allocation")
        persisted_snapshot = self._repository.add_snapshot(snapshot)
        existing = self._repository.active_revision(incident_id)
        if existing is not None:
            return self._repository.history(incident_id)
        fixture = self._fixture.load()
        scenarios = reconstruct_phase2_worlds(report, fixture)
        from backend.app.evaluation.dynamic_yard import DynamicYardEvaluator
        evaluated = DynamicYardEvaluator().evaluate_allocation(fixture, scenarios, snapshot, report.selected_allocation)
        with self._repository.transaction():
            persisted = persisted_snapshot
            revision = AllocationRevision(
                incident_id=incident_id, source_phase2_evaluation_id=report.id,
                source_forecast_snapshot_id=persisted.id,
                allocated_container_ids=report.selected_allocation.allocated_container_ids,
                locked_container_ids=("SYN-CNT-002", "SYN-CNT-004"),
                preserved_connection_total=evaluated.preserved_connection_total,
                expected_preserved_connections=evaluated.expected_preserved_connections,
                reason="R0 derives from frozen Phase 2 selected allocation",
            )
            self._repository.add_revision(revision)
            commitments = []
            for container_id in revision.allocated_container_ids:
                commitment = self._repository.add_commitment(ExpediteCommitment(incident_id=incident_id, origin_revision_id=revision.id, container_id=container_id))
                if container_id in revision.locked_container_ids:
                    commitment = self._repository.transition_commitment(commitment.id, ExpediteCommitmentStatus.COMMITTED)
                commitments.append(commitment)
        return self._repository.history(incident_id)

    def ingest(self, snapshot: YardForecastSnapshot) -> ExpediteReconsiderationAssessment | None:
        history = self._repository.history(snapshot.incident_id)
        if not history.revisions:
            raise ValueError("dynamic-yard flow must be initialized before ingestion")
        if snapshot.stage is ForecastStage.PRE_DISCHARGE:
            self._repository.add_snapshot(snapshot)
            return None
        if not any(item.stage is ForecastStage.PRE_DISCHARGE for item in history.snapshots):
            raise ValueError("DISCHARGE_ACTIVE requires PRE_DISCHARGE evidence")
        persisted_snapshot = self._repository.add_snapshot(snapshot)
        existing_assessment = self._repository.get_assessment_for_snapshot(persisted_snapshot.id)
        if existing_assessment is not None:
            return existing_assessment
        report = self._evaluations.get_for_incident(snapshot.incident_id)
        fixture = self._fixture.load()
        scenarios = reconstruct_phase2_worlds(report, fixture)
        prior = history.revisions[-1]
        locked = tuple(commitment.container_id for commitment in history.commitments if commitment.status in {ExpediteCommitmentStatus.COMMITTED, ExpediteCommitmentStatus.EXECUTED})
        with self._repository.transaction():
            persisted = persisted_snapshot
            assessment = assess_reconsideration(snapshot.incident_id, persisted, prior, fixture, scenarios, locked)
            return self._repository.add_assessment(assessment)

    def apply_latest_assessment(self, incident_id: UUID, run_id: UUID | None = None) -> AllocationRevision | AllocationTradeoffReview | None:
        assessment = self._repository.latest_unhandled_assessment(incident_id)
        if assessment is None:
            return None
        if assessment.disposition is ReconsiderationDisposition.NO_CHANGE:
            self._repository.mark_assessment_handled(assessment.id, datetime.now(UTC))
            return None
        if assessment.disposition is ReconsiderationDisposition.HUMAN_REVIEW_REQUIRED:
            existing = next((review for review in self._repository.list_reviews(incident_id) if review.reconsideration_assessment_id == assessment.id), None)
            if existing is not None:
                return existing
            options = tuple(AllocationTradeoffOption(id=candidate.id, review_id=UUID(int=0), allocated_container_ids=candidate.allocated_container_ids, preserved_connection_total=candidate.preserved_connection_total, expected_preserved_connections=candidate.expected_preserved_connections) for candidate in assessment.candidate_options)
            review = AllocationTradeoffReview(incident_id=incident_id, reconsideration_assessment_id=assessment.id, option_ids=tuple(option.id for option in options), options_fingerprint=self._options_fingerprint(options), state=TradeoffReviewState.OPEN)
            options = tuple(option.model_copy(update={"review_id": review.id}) for option in options)
            with self._repository.transaction():
                self._repository.create_tradeoff_review(review, options)
            return review
        candidate = assessment.candidate_options[0]
        return self._apply_candidate(incident_id, assessment, candidate.allocated_container_ids, candidate.preserved_connection_total, candidate.expected_preserved_connections)

    def _apply_candidate(self, incident_id: UUID, assessment: ExpediteReconsiderationAssessment, allocated: tuple[str, ...], total: int, expected: float) -> AllocationRevision:
        prior = self._repository.active_revision(incident_id)
        if prior is None: raise ValueError("missing allocation revision")
        with self._repository.transaction():
            revision = AllocationRevision(incident_id=incident_id, source_phase2_evaluation_id=prior.source_phase2_evaluation_id, source_forecast_snapshot_id=assessment.source_snapshot_id, parent_revision_id=prior.id, allocated_container_ids=allocated, locked_container_ids=assessment.locked_container_ids, preserved_connection_total=total, expected_preserved_connections=expected, reason=assessment.reason)
            self._repository.add_revision(revision)
            active = self._repository.list_commitments(incident_id)
            for commitment in active:
                if commitment.status is ExpediteCommitmentStatus.PLANNED and commitment.container_id not in allocated:
                    self._repository.transition_commitment(commitment.id, ExpediteCommitmentStatus.CANCELLED)
            present = {item.container_id for item in active if item.status is not ExpediteCommitmentStatus.CANCELLED}
            for container_id in allocated:
                if container_id not in present:
                    self._repository.add_commitment(ExpediteCommitment(incident_id=incident_id, origin_revision_id=revision.id, container_id=container_id))
            self._repository.mark_assessment_handled(assessment.id, datetime.now(UTC))
        return revision

    def phase3_compatible(self, incident_id: UUID, connection_id: str) -> bool:
        history = self._repository.history(incident_id)
        if not history.revisions or not history.snapshots: return True
        report = self._evaluations.get_for_incident(incident_id)
        active_snapshot = history.snapshots[-1]
        fixture = self._fixture.load()
        return connection_is_phase3_compatible(fixture, reconstruct_phase2_worlds(report, fixture), active_snapshot, AllocationPlan(strategy=AllocationStrategy.SCENARIO_AWARE, allocated_container_ids=history.revisions[-1].allocated_container_ids), report.selected_allocation, connection_id)

    def compatible_connection_ids(self, incident_id: UUID) -> tuple[str, ...]:
        fixture = self._fixture.load()
        return tuple(connection.id for connection in sorted({profile.container.onward_connection for profile in fixture.profiles}, key=lambda item: item.id) if self.phase3_compatible(incident_id, connection.id))

    def history(self, incident_id: UUID) -> AllocationTradeoffHistory:
        return self._repository.history(incident_id)

    def latest_unhandled_assessment(self, incident_id: UUID):
        return self._repository.latest_unhandled_assessment(incident_id)

    def get_tradeoff_review(self, review_id: UUID) -> AllocationTradeoffReview:
        return self._repository.get_review(review_id)

    def select_tradeoff(
        self,
        review_id: UUID,
        *,
        selected_option_id: UUID,
        expected_options_fingerprint: str,
        operator_id: str,
    ) -> AllocationRevision:
        review = self._repository.get_review(review_id)
        history = self._repository.history(review.incident_id)
        option = next((item for item in history.options if item.id == selected_option_id and item.review_id == review.id), None)
        if option is None:
            from backend.app.storage.dynamic_yard import DynamicYardConflict
            raise DynamicYardConflict("selected option does not belong to review")
        assessment = next((item for item in history.assessments if item.id == review.reconsideration_assessment_id), None)
        if assessment is None:
            raise LookupError("tradeoff reconsideration assessment not found")
        with self._repository.transaction():
            selection = self._repository.select_tradeoff_option(review.id, selected_option_id=selected_option_id, expected_options_fingerprint=expected_options_fingerprint, operator_id=operator_id)
            revision = self._apply_candidate(review.incident_id, assessment, option.allocated_container_ids, option.preserved_connection_total, option.expected_preserved_connections)
            audit = AuditRepository(self._session)
            audit.add_uncommitted(AuditEvent(actor=AuditActor.OPERATOR, actor_id=operator_id, incident_id=review.incident_id, event_type="allocation_tradeoff.option_selected", payload={"review_id": str(review.id), "selected_option_id": str(selection.selected_option_id), "options_fingerprint": review.options_fingerprint}))
            audit.add_uncommitted(AuditEvent(actor=AuditActor.POLICY, actor_id="allocation-dominance-policy", incident_id=review.incident_id, event_type="allocation_revision.applied", payload={"review_id": str(review.id), "assessment_id": str(assessment.id), "parent_revision_id": str(revision.parent_revision_id), "child_revision_id": str(revision.id), "allocated_container_ids": list(revision.allocated_container_ids)}))
            return revision

    @staticmethod
    def _options_fingerprint(options: tuple[AllocationTradeoffOption, ...]) -> str:
        from hashlib import sha256
        import json
        return sha256(json.dumps([option.model_dump(mode="json") for option in options], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
