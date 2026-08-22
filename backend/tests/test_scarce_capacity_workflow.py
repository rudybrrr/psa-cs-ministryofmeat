from __future__ import annotations

from uuid import UUID

import pytest
from sqlmodel import Session

from backend.app.domain.enums import (
    AuditActor,
    DecisionAction,
    DecisionStatus,
    IncidentState,
)
from backend.app.domain.scarcity import (
    CanonicalIncidentFixture,
    ScenarioSet,
    ScarcityEvaluationReport,
)
from backend.app.evaluation.scarcity import ScarcityComparisonService
from backend.app.optimization.scarcity import ScenarioAwareAllocator
from backend.app.orchestration.scarce_capacity import (
    CanonicalScarceCapacityWorkflow,
    build_scarce_capacity_workflow,
)
from backend.app.policies.baseline import P50GreedyAllocator
from backend.app.services.scenarios import SeededScenarioGenerator
from backend.app.storage.repositories import (
    AuditRepository,
    DecisionRepository,
    ScarcityEvaluationRepository,
)


EXPECTED_ALLOCATION = (
    "SYN-CNT-002",
    "SYN-CNT-004",
    "SYN-CNT-005",
    "SYN-CNT-010",
    "SYN-CNT-011",
    "SYN-CNT-012",
    "SYN-CNT-014",
    "SYN-CNT-015",
)


def test_canonical_workflow_persists_report_and_consistent_outcome(
    session: Session,
) -> None:
    result = build_scarce_capacity_workflow(session).run(
        seed=20260822,
        world_count=50,
    )

    assert ScarcityEvaluationRepository(session).get_for_incident(
        result.incident.id
    ) == result.report
    assert DecisionRepository(session).list_for_incident(
        result.incident.id
    ) == list(result.decisions)
    if result.report.selected_allocation is None:
        assert result.incident.state is IncidentState.ESCALATED
        assert result.decisions == ()
    else:
        assert result.incident.state is IncidentState.RESOLVED
        assert {
            decision.container_id for decision in result.decisions
        } == set(result.report.selected_allocation.allocated_container_ids)
        assert all(
            decision.action is DecisionAction.EXPEDITE
            for decision in result.decisions
        )
        assert all(
            decision.status is DecisionStatus.APPROVED
            for decision in result.decisions
        )


def test_canonical_development_path_resolves_with_ordered_atomic_decisions(
    session: Session,
) -> None:
    result = build_scarce_capacity_workflow(session).run()

    assert result.incident.state is IncidentState.RESOLVED
    assert tuple(
        decision.container_id for decision in result.decisions
    ) == EXPECTED_ALLOCATION
    assert tuple(
        decision.container_id
        for decision in DecisionRepository(session).list_for_incident(
            result.incident.id
        )
    ) == EXPECTED_ALLOCATION
    events = AuditRepository(session).list_for_incident(result.incident.id)
    assert [
        event.payload["to"]
        for event in events
        if event.event_type == "incident.state_transitioned"
    ] == [
        "COLLECTING_STATE",
        "CONSTRAINT_VALIDATION",
        "RECOVERY_ANALYSIS",
        "RESOLVED",
    ]


def test_workflow_audits_system_solver_and_policy_but_never_agent(
    session: Session,
) -> None:
    result = build_scarce_capacity_workflow(session).run()

    events = AuditRepository(session).list_for_incident(result.incident.id)
    actors = {event.actor for event in events}
    event_types = {event.event_type for event in events}

    assert actors == {
        AuditActor.SYSTEM,
        AuditActor.SOLVER,
        AuditActor.POLICY,
    }
    assert AuditActor.AGENT not in actors
    assert all(event.actor_id for event in events)
    assert {
        "canonical.fixture_loaded",
        "canonical.containers_collected",
        "canonical.capacity_collected",
        "scenarios.generated",
        "baseline.evaluated",
        "scenario_aware.optimized",
        "scarcity.pareto_evaluated",
        "scarcity.evaluation_persisted",
        "decision.created",
    } <= event_types


class FixedComparisonService:
    def __init__(
        self,
        template: ScarcityEvaluationReport,
        *,
        selected: bool,
    ) -> None:
        self._template = template
        self._selected = selected

    def compare(
        self,
        *,
        incident_id: UUID,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
    ) -> ScarcityEvaluationReport:
        selected = (
            self._template.pareto_evaluations[0].allocation
            if self._selected
            else None
        )
        return self._template.model_copy(
            update={
                "incident_id": incident_id,
                "selected_allocation": selected,
            }
        )


def build_with_comparison(
    session: Session,
    report: ScarcityEvaluationReport,
    *,
    selected: bool,
) -> CanonicalScarceCapacityWorkflow:
    return build_scarce_capacity_workflow(
        session,
        comparison=FixedComparisonService(report, selected=selected),
    )


def test_injected_dominant_comparison_materializes_decisions_and_resolves(
    session: Session,
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    template = ScarcityComparisonService().compare(
        incident_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        fixture=canonical_fixture,
        scenarios=canonical_scenarios,
    )

    result = build_with_comparison(
        session,
        template,
        selected=True,
    ).run()

    assert result.incident.state is IncidentState.RESOLVED
    assert tuple(
        decision.container_id for decision in result.decisions
    ) == template.pareto_evaluations[0].allocation.allocated_container_ids


def test_injected_tradeoff_persists_frontier_without_decisions_and_escalates(
    session: Session,
    canonical_fixture: CanonicalIncidentFixture,
    canonical_scenarios: ScenarioSet,
) -> None:
    template = ScarcityComparisonService().compare(
        incident_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        fixture=canonical_fixture,
        scenarios=canonical_scenarios,
    )

    result = build_with_comparison(
        session,
        template,
        selected=False,
    ).run()

    assert result.incident.state is IncidentState.ESCALATED
    assert result.decisions == ()
    assert result.report.pareto_evaluations == template.pareto_evaluations
    assert ScarcityEvaluationRepository(session).get_for_incident(
        result.incident.id
    ) == result.report
    assert DecisionRepository(session).list_for_incident(
        result.incident.id
    ) == []
    events = AuditRepository(session).list_for_incident(result.incident.id)
    assert [
        event.payload["to"]
        for event in events
        if event.event_type == "incident.state_transitioned"
    ][-1] == "ESCALATED"


def test_real_comparison_passes_the_exact_generated_scenario_object_to_both_allocators(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
) -> None:
    observed: dict[str, ScenarioSet] = {}
    original_baseline = P50GreedyAllocator.allocate
    original_solver = ScenarioAwareAllocator.solve

    def baseline_spy(self, fixture, scenarios):
        observed["baseline"] = scenarios
        return original_baseline(self, fixture, scenarios)

    def solver_spy(self, fixture, scenarios):
        observed["solver"] = scenarios
        return original_solver(self, fixture, scenarios)

    monkeypatch.setattr(P50GreedyAllocator, "allocate", baseline_spy)
    monkeypatch.setattr(ScenarioAwareAllocator, "solve", solver_spy)

    build_scarce_capacity_workflow(session).run()

    assert observed["baseline"] is observed["solver"]
