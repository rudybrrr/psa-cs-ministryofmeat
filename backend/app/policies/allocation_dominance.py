from backend.app.domain.scarcity import AllocationPlan, StrategyEvaluation


def _is_hard_safe(evaluation: StrategyEvaluation) -> bool:
    return (
        evaluation.capacity_violations == 0
        and evaluation.unsafe_allocations == 0
    )


def _service_totals(evaluation: StrategyEvaluation) -> tuple[tuple[str, int], ...]:
    return tuple(
        (outcome.service_id, outcome.preserved_connection_total)
        for outcome in evaluation.service_outcomes
    )


def _dominates(left: StrategyEvaluation, right: StrategyEvaluation) -> bool:
    if not _is_hard_safe(left) or not _is_hard_safe(right):
        return False

    left_services = _service_totals(left)
    right_services = _service_totals(right)
    if tuple(service_id for service_id, _ in left_services) != tuple(
        service_id for service_id, _ in right_services
    ):
        raise ValueError("dominance requires matching ordered service outcomes")

    comparisons = (
        left.expected_preserved_connections
        >= right.expected_preserved_connections,
        left.p10_preserved_connections >= right.p10_preserved_connections,
        *(
            left_total >= right_total
            for (_, left_total), (_, right_total) in zip(
                left_services,
                right_services,
                strict=True,
            )
        ),
        left.allocation_slot_count <= right.allocation_slot_count,
    )
    strict_comparisons = (
        left.expected_preserved_connections
        > right.expected_preserved_connections,
        left.p10_preserved_connections > right.p10_preserved_connections,
        *(
            left_total > right_total
            for (_, left_total), (_, right_total) in zip(
                left_services,
                right_services,
                strict=True,
            )
        ),
        left.allocation_slot_count < right.allocation_slot_count,
    )
    return all(comparisons) and any(strict_comparisons)


def pareto_front(
    evaluations: tuple[StrategyEvaluation, ...],
) -> tuple[StrategyEvaluation, ...]:
    safe_evaluations = tuple(
        evaluation for evaluation in evaluations if _is_hard_safe(evaluation)
    )
    return tuple(
        candidate
        for candidate in safe_evaluations
        if not any(
            _dominates(other, candidate)
            for other in safe_evaluations
            if other is not candidate
        )
    )


class AllocationDominancePolicy:
    def select(
        self,
        evaluations: tuple[StrategyEvaluation, ...],
    ) -> AllocationPlan | None:
        safe_evaluations = tuple(
            evaluation
            for evaluation in evaluations
            if _is_hard_safe(evaluation)
        )
        if len(safe_evaluations) == 1:
            return safe_evaluations[0].allocation
        for candidate in safe_evaluations:
            if all(
                _dominates(candidate, other)
                for other in safe_evaluations
                if other is not candidate
            ):
                return candidate.allocation
        return None
