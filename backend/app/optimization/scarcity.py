from ortools.sat.python import cp_model

from backend.app.domain.scarcity import (
    AllocationPlan,
    AllocationStrategy,
    CanonicalIncidentFixture,
    CargoKind,
    ScenarioSet,
)
from backend.app.evaluation.scarcity import ScarcityEvaluator


class ScarcityOptimizationError(RuntimeError):
    """Raised when CP-SAT cannot prove or enumerate the optimum."""


class _OptimalAllocationCollector(cp_model.CpSolverSolutionCallback):
    def __init__(self, variables: dict[str, cp_model.IntVar]) -> None:
        super().__init__()
        self._variables = variables
        self.allocations: set[tuple[str, ...]] = set()

    def on_solution_callback(self) -> None:
        self.allocations.add(
            tuple(
                container_id
                for container_id, variable in self._variables.items()
                if self.boolean_value(variable)
            )
        )


def _configured_solver(*, enumerate_all_solutions: bool) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.enumerate_all_solutions = enumerate_all_solutions
    return solver


def _build_model(
    fixture: CanonicalIncidentFixture,
    candidate_ids: tuple[str, ...],
    coefficients: dict[str, int],
) -> tuple[cp_model.CpModel, dict[str, cp_model.IntVar], cp_model.LinearExprT]:
    profiles = {
        profile.container.id: profile for profile in fixture.profiles
    }
    model = cp_model.CpModel()
    variables = {
        container_id: model.new_bool_var(f"expedite_{container_id}")
        for container_id in candidate_ids
    }
    model.add(sum(variables.values()) <= fixture.capacity.total_slots)

    for limit in fixture.capacity.handling_group_limits:
        group_variables = [
            variables[container_id]
            for container_id in candidate_ids
            if profiles[container_id].handling_group_id == limit.handling_group_id
        ]
        if group_variables:
            model.add(sum(group_variables) <= limit.slots)

    reefer_variables = [
        variables[container_id]
        for container_id in candidate_ids
        if profiles[container_id].cargo_kind is CargoKind.REEFER
    ]
    if reefer_variables:
        model.add(
            sum(reefer_variables) <= fixture.capacity.max_reefer_slots
        )

    dg_variables = [
        variables[container_id]
        for container_id in candidate_ids
        if profiles[container_id].cargo_kind is CargoKind.DG
    ]
    if dg_variables:
        model.add(sum(dg_variables) <= fixture.capacity.max_dg_slots)

    objective_expression = sum(
        coefficients[container_id] * variables[container_id]
        for container_id in candidate_ids
    )
    return model, variables, objective_expression


class ScenarioAwareAllocator:
    def solve(
        self,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
    ) -> tuple[AllocationPlan, ...]:
        evaluator = ScarcityEvaluator()
        candidate_ids = evaluator.stochastic_candidate_ids(fixture, scenarios)
        coefficients = {
            container_id: evaluator.incremental_preservation_count(
                fixture,
                scenarios,
                container_id,
            )
            for container_id in candidate_ids
        }
        if any(coefficient <= 0 for coefficient in coefficients.values()):
            raise ScarcityOptimizationError(
                "all scenario-aware candidates must have positive incremental preservation"
            )

        optimization_model, _, objective = _build_model(
            fixture,
            candidate_ids,
            coefficients,
        )
        optimization_model.maximize(objective)
        optimization_solver = _configured_solver(enumerate_all_solutions=False)
        optimization_status = optimization_solver.solve(optimization_model)
        if optimization_status != cp_model.OPTIMAL:
            raise ScarcityOptimizationError(
                "CP-SAT did not prove an optimal scarcity allocation"
            )
        optimum = int(round(optimization_solver.objective_value))

        enumeration_model, variables, enumeration_objective = _build_model(
            fixture,
            candidate_ids,
            coefficients,
        )
        enumeration_model.add(enumeration_objective == optimum)
        collector = _OptimalAllocationCollector(variables)
        enumeration_solver = _configured_solver(enumerate_all_solutions=True)
        enumeration_status = enumeration_solver.solve(
            enumeration_model,
            collector,
        )
        if enumeration_status != cp_model.OPTIMAL:
            raise ScarcityOptimizationError(
                "CP-SAT did not completely enumerate optimal scarcity allocations"
            )

        return tuple(
            AllocationPlan(
                strategy=AllocationStrategy.SCENARIO_AWARE,
                allocated_container_ids=allocation,
            )
            for allocation in sorted(collector.allocations)
        )
