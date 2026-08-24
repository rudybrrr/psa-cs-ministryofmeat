from __future__ import annotations

from uuid import UUID

from ortools.sat.python import cp_model

from backend.app.domain.dynamic_yard import (
    AllocationRevision,
    ExpediteReconsiderationAssessment,
    ReconsiderationCandidate,
    ReconsiderationDisposition,
    YardForecastSnapshot,
)
from backend.app.domain.scarcity import AllocationPlan, AllocationStrategy, CanonicalIncidentFixture, ScenarioSet
from backend.app.evaluation.dynamic_yard import DynamicYardEvaluator
from backend.app.optimization.scarcity import _OptimalAllocationCollector, _build_model, _configured_solver
from backend.app.policies.allocation_dominance import AllocationDominancePolicy, pareto_front


class LockedAllocationSolver:
    def solve(
        self,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
        snapshot: YardForecastSnapshot,
        locked_container_ids: tuple[str, ...],
        evaluator: DynamicYardEvaluator,
    ) -> tuple[AllocationPlan, ...]:
        candidates = tuple(profile.container.id for profile in fixture.profiles)
        base = evaluator.evaluate_allocation(
            fixture, scenarios, snapshot,
            AllocationPlan(strategy=AllocationStrategy.SCENARIO_AWARE, allocated_container_ids=()),
        )
        coefficients = {}
        for container_id in candidates:
            evaluated = evaluator.evaluate_allocation(
                fixture, scenarios, snapshot,
                AllocationPlan(strategy=AllocationStrategy.SCENARIO_AWARE, allocated_container_ids=(container_id,)),
            )
            coefficients[container_id] = evaluated.preserved_connection_total - base.preserved_connection_total
        model, _, objective = _build_model(
            fixture, candidates, coefficients, fixed_true_ids=locked_container_ids
        )
        model.maximize(objective)
        solver = _configured_solver(enumerate_all_solutions=False)
        if solver.solve(model) != cp_model.OPTIMAL:
            raise RuntimeError("CP-SAT did not prove locked allocation optimum")
        optimum = int(round(solver.objective_value))
        enumeration, variables, enum_objective = _build_model(
            fixture, candidates, coefficients, fixed_true_ids=locked_container_ids
        )
        enumeration.add(enum_objective == optimum)
        collector = _OptimalAllocationCollector(variables)
        enum_solver = _configured_solver(enumerate_all_solutions=True)
        if enum_solver.solve(enumeration, collector) != cp_model.OPTIMAL:
            raise RuntimeError("CP-SAT did not enumerate locked allocation optimum")
        return tuple(AllocationPlan(strategy=AllocationStrategy.SCENARIO_AWARE, allocated_container_ids=ids) for ids in sorted(collector.allocations))


def assess_reconsideration(
    incident_id: UUID,
    source_snapshot: YardForecastSnapshot,
    prior_revision: AllocationRevision,
    fixture: CanonicalIncidentFixture,
    scenarios: ScenarioSet,
    locked_container_ids: tuple[str, ...],
) -> ExpediteReconsiderationAssessment:
    evaluator = DynamicYardEvaluator()
    current = evaluator.evaluate_allocation(
        fixture, scenarios, source_snapshot,
        AllocationPlan(strategy=AllocationStrategy.SCENARIO_AWARE, allocated_container_ids=prior_revision.allocated_container_ids),
    )
    plans = LockedAllocationSolver().solve(fixture, scenarios, source_snapshot, locked_container_ids, evaluator)
    evaluations = tuple(evaluator.evaluate_allocation(fixture, scenarios, source_snapshot, plan) for plan in plans)
    improving = tuple(item for item in evaluations if item.preserved_connection_total > current.preserved_connection_total)
    options = tuple(ReconsiderationCandidate(allocated_container_ids=item.allocation.allocated_container_ids, preserved_connection_total=item.preserved_connection_total, expected_preserved_connections=item.expected_preserved_connections) for item in improving)
    if not improving:
        disposition, after, reason = ReconsiderationDisposition.NO_CHANGE, current, "no feasible allocation strictly improves preserved connections"
    else:
        frontier = pareto_front(improving)
        selected = AllocationDominancePolicy().select(frontier)
        if selected is None:
            disposition, after, reason = ReconsiderationDisposition.HUMAN_REVIEW_REQUIRED, max(improving, key=lambda item: item.preserved_connection_total), "authorised policy leaves multiple non-dominated feasible options"
        else:
            disposition = ReconsiderationDisposition.AUTO_SUPERSEDE
            after = next(item for item in improving if item.allocation == selected)
            reason = "feasible locked allocation strictly improves preserved connections"
    return ExpediteReconsiderationAssessment(
        incident_id=incident_id, source_snapshot_id=source_snapshot.id,
        prior_allocation_revision_id=prior_revision.id, locked_container_ids=locked_container_ids,
        candidate_options=options, preserved_connection_total_before=current.preserved_connection_total,
        preserved_connection_total_after=after.preserved_connection_total,
        expected_preserved_connections_before=current.expected_preserved_connections,
        expected_preserved_connections_after=after.expected_preserved_connections,
        disposition=disposition, reason=reason,
    )
