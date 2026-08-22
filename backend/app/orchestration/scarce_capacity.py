from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from sqlmodel import Session

from backend.app.audit.service import AuditService
from backend.app.domain.enums import (
    AuditActor,
    DecisionAction,
    DecisionStatus,
    IncidentState,
)
from backend.app.domain.models import Decision, Incident
from backend.app.domain.scarcity import (
    CanonicalIncidentFixture,
    ScenarioSet,
    ScarcityEvaluationReport,
)
from backend.app.evaluation.scarcity import ScarcityComparisonService
from backend.app.orchestration.state_machine import IncidentStateMachine
from backend.app.services.canonical_incident import (
    SyntheticCanonicalIncidentService,
)
from backend.app.services.scenarios import SeededScenarioGenerator
from backend.app.storage.repositories import (
    AuditRepository,
    DecisionRepository,
    IncidentRepository,
    ScarcityEvaluationRepository,
)


class ComparisonService(Protocol):
    def compare(
        self,
        *,
        incident_id,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
    ) -> ScarcityEvaluationReport: ...


@dataclass(frozen=True, slots=True)
class ScarcityRecoveryResult:
    incident: Incident
    report: ScarcityEvaluationReport
    decisions: tuple[Decision, ...]


class CanonicalScarceCapacityWorkflow:
    def __init__(
        self,
        *,
        fixture_service: SyntheticCanonicalIncidentService,
        scenario_generator: SeededScenarioGenerator,
        comparison: ComparisonService,
        state_machine: IncidentStateMachine,
        incidents: IncidentRepository,
        decisions: DecisionRepository,
        evaluations: ScarcityEvaluationRepository,
        audit: AuditService,
    ) -> None:
        self._fixture_service = fixture_service
        self._scenario_generator = scenario_generator
        self._comparison = comparison
        self._state_machine = state_machine
        self._incidents = incidents
        self._decisions = decisions
        self._evaluations = evaluations
        self._audit = audit

    def run(
        self,
        *,
        seed: int = 20260822,
        world_count: int = 50,
    ) -> ScarcityRecoveryResult:
        fixture = self._fixture_service.load()
        incident = self._incidents.create(
            Incident(
                source_event_id=fixture.event.id,
                state=IncidentState.INCIDENT_RECEIVED,
                created_at=fixture.event.occurred_at,
            )
        )
        self._record_system(
            incident,
            actor_id="canonical-scarcity-workflow",
            event_type="incident.created",
            payload={"state": incident.state.value},
        )
        self._record_system(
            incident,
            actor_id="synthetic-canonical-incident-service",
            event_type="canonical.fixture_loaded",
            payload={
                "fixture_id": fixture.fixture_id,
                "terminal_id": fixture.event.terminal_id,
            },
        )

        incident = self._transition(incident, IncidentState.COLLECTING_STATE)
        self._record_system(
            incident,
            actor_id="synthetic-canonical-incident-service",
            event_type="canonical.containers_collected",
            payload={
                "fixture_id": fixture.fixture_id,
                "container_count": len(fixture.profiles),
            },
        )
        self._record_system(
            incident,
            actor_id="synthetic-canonical-incident-service",
            event_type="canonical.capacity_collected",
            payload={
                "capacity_id": fixture.capacity.id,
                "total_slots": fixture.capacity.total_slots,
                "overlap_service_ids": list(
                    fixture.capacity.overlap_service_ids
                ),
            },
        )

        incident = self._transition(
            incident,
            IncidentState.CONSTRAINT_VALIDATION,
        )
        scenarios = self._scenario_generator.generate(
            fixture,
            seed=seed,
            world_count=world_count,
        )
        self._record_system(
            incident,
            actor_id="seeded-scenario-generator",
            event_type="scenarios.generated",
            payload={
                "seed": seed,
                "world_count": world_count,
                "shared_std_minutes": (
                    scenarios.assumptions.shared_std_minutes
                ),
                "handling_group_std_minutes": (
                    scenarios.assumptions.handling_group_std_minutes
                ),
                "container_noise_std_minutes": (
                    scenarios.assumptions.container_noise_std_minutes
                ),
                "antithetic_pairs": (
                    scenarios.assumptions.antithetic_pairs
                ),
            },
        )

        incident = self._transition(
            incident,
            IncidentState.RECOVERY_ANALYSIS,
        )
        report = self._comparison.compare(
            incident_id=incident.id,
            fixture=fixture,
            scenarios=scenarios,
        )
        self._audit.record(
            actor=AuditActor.POLICY,
            actor_id="p50-greedy-baseline",
            incident_id=incident.id,
            event_type="baseline.evaluated",
            payload={
                "allocation": list(
                    report.baseline.allocation.allocated_container_ids
                ),
                "expected_preserved_connections": (
                    report.baseline.expected_preserved_connections
                ),
                "capacity_violations": report.baseline.capacity_violations,
                "unsafe_allocations": report.baseline.unsafe_allocations,
            },
        )
        self._audit.record(
            actor=AuditActor.SOLVER,
            actor_id="scenario-aware-cp-sat",
            incident_id=incident.id,
            event_type="scenario_aware.optimized",
            payload={
                "candidate_count": len(report.scenario_aware_evaluations),
                "allocations": [
                    list(evaluation.allocation.allocated_container_ids)
                    for evaluation in report.scenario_aware_evaluations
                ],
            },
        )
        self._audit.record(
            actor=AuditActor.POLICY,
            actor_id="allocation-dominance-policy",
            incident_id=incident.id,
            event_type="scarcity.pareto_evaluated",
            payload={
                "pareto_count": len(report.pareto_evaluations),
                "selected": report.selected_allocation is not None,
            },
        )
        report = self._evaluations.add(report)
        self._audit.record(
            actor=AuditActor.POLICY,
            actor_id="scarcity-comparison-service",
            incident_id=incident.id,
            event_type="scarcity.evaluation_persisted",
            payload={
                "evaluation_id": str(report.id),
                "reproducibility_key": report.reproducibility_key,
            },
        )

        if report.selected_allocation is None:
            incident = self._transition(incident, IncidentState.ESCALATED)
            return ScarcityRecoveryResult(
                incident=incident,
                report=report,
                decisions=(),
            )

        proposed_decisions = tuple(
            Decision(
                incident_id=incident.id,
                container_id=container_id,
                action=DecisionAction.EXPEDITE,
                status=DecisionStatus.APPROVED,
                rationale=(
                    "Selected by deterministic dominance from the synthetic "
                    "scenario-aware scarce-capacity alternatives."
                ),
                created_at=report.created_at + timedelta(microseconds=index),
            )
            for index, container_id in enumerate(
                report.selected_allocation.allocated_container_ids
            )
        )
        decisions = self._decisions.add_many(proposed_decisions)
        for decision in decisions:
            self._audit.record(
                actor=AuditActor.POLICY,
                actor_id="allocation-dominance-policy",
                incident_id=incident.id,
                event_type="decision.created",
                payload={
                    "decision_id": str(decision.id),
                    "container_id": decision.container_id,
                    "action": decision.action.value,
                    "status": decision.status.value,
                },
            )
        incident = self._transition(incident, IncidentState.RESOLVED)
        return ScarcityRecoveryResult(
            incident=incident,
            report=report,
            decisions=decisions,
        )

    def _record_system(
        self,
        incident: Incident,
        *,
        actor_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        self._audit.record(
            actor=AuditActor.SYSTEM,
            actor_id=actor_id,
            incident_id=incident.id,
            event_type=event_type,
            payload=payload,
        )

    def _transition(
        self,
        incident: Incident,
        target: IncidentState,
    ) -> Incident:
        source = incident.state
        transitioned = self._state_machine.transition(incident, target)
        persisted = self._incidents.update_state(
            incident.id,
            transitioned.state,
        )
        self._record_system(
            persisted,
            actor_id="canonical-scarcity-workflow",
            event_type="incident.state_transitioned",
            payload={"from": source.value, "to": target.value},
        )
        return persisted


def build_scarce_capacity_workflow(
    session: Session,
    *,
    comparison: ComparisonService | None = None,
    fixture_service: SyntheticCanonicalIncidentService | None = None,
    scenario_generator: SeededScenarioGenerator | None = None,
) -> CanonicalScarceCapacityWorkflow:
    return CanonicalScarceCapacityWorkflow(
        fixture_service=(
            fixture_service or SyntheticCanonicalIncidentService()
        ),
        scenario_generator=(scenario_generator or SeededScenarioGenerator()),
        comparison=comparison or ScarcityComparisonService(),
        state_machine=IncidentStateMachine(),
        incidents=IncidentRepository(session),
        decisions=DecisionRepository(session),
        evaluations=ScarcityEvaluationRepository(session),
        audit=AuditService(AuditRepository(session)),
    )
