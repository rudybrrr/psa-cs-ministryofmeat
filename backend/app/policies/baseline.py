from backend.app.domain.scarcity import (
    AllocationPlan,
    AllocationStrategy,
    CanonicalIncidentFixture,
    ScenarioSet,
)
from backend.app.evaluation.scarcity import ScarcityEvaluator


class P50GreedyAllocator:
    def allocate(
        self,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
    ) -> AllocationPlan:
        evaluator = ScarcityEvaluator()
        beneficiary_ids = set(
            evaluator.p50_beneficiary_ids(fixture, scenarios)
        )
        services = {
            service.service_id: service for service in fixture.services
        }
        beneficiary_profiles = sorted(
            (
                profile
                for profile in fixture.profiles
                if profile.container.id in beneficiary_ids
            ),
            key=lambda profile: (
                services[profile.service_id].ready_boundary,
                profile.container.id,
            ),
        )
        selected: list[str] = []

        for profile in beneficiary_profiles:
            proposed = AllocationPlan(
                strategy=AllocationStrategy.P50_GREEDY,
                allocated_container_ids=tuple(selected + [profile.container.id]),
            )
            if evaluator.constraint_diagnostics(fixture, proposed) == (0, 0):
                selected.append(profile.container.id)

        return AllocationPlan(
            strategy=AllocationStrategy.P50_GREEDY,
            allocated_container_ids=tuple(selected),
        )
