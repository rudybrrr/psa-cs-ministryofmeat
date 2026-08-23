from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from backend.app.domain.carrier_recovery import CarrierRecoveryDisposition
from backend.app.domain.scarcity import CanonicalIncidentFixture, ScenarioSet
from backend.app.evaluation.scarcity import ScarcityEvaluator, _is_structurally_eligible


@dataclass(frozen=True)
class FrozenRecoveryEvaluation:
    container_id: str
    disposition: CarrierRecoveryDisposition
    preserved_world_count: int
    world_count: int
    hard_constraints_satisfied: bool


class FrozenCarrierRecoveryEvaluator:
    """Deterministically evaluates only the frozen Phase 2 evidence."""

    def evaluate(
        self,
        *,
        fixture: CanonicalIncidentFixture,
        scenarios: ScenarioSet,
        selected_allocation: Iterable[str],
        affected_container_ids: Iterable[str],
        connection_id: str,
        effective_eta_pta=None,
    ) -> tuple[FrozenRecoveryEvaluation, ...]:
        profiles = {
            profile.container.id: profile
            for profile in fixture.profiles
            if profile.container.onward_connection.id == connection_id
        }
        allocation = set(selected_allocation)
        evaluator = ScarcityEvaluator()
        results = []
        for container_id in affected_container_ids:
            profile = profiles.get(container_id)
            if profile is None:
                raise ValueError("affected snapshot is not on the requested connection")
            hard_safe = _is_structurally_eligible(profile)
            if not hard_safe:
                disposition, preserved = CarrierRecoveryDisposition.ESCALATE, 0
            elif effective_eta_pta is None:
                disposition, preserved = CarrierRecoveryDisposition.STILL_ROLL, 0
            else:
                boundary = effective_eta_pta + timedelta(minutes=35)
                preserved = sum(evaluator.ready_at(profile, world, expedited=container_id in allocation) <= boundary for world in scenarios.worlds)
                disposition = (
                    CarrierRecoveryDisposition.PRESERVED_VIA_RTA if preserved * 10 >= len(scenarios.worlds) * 9
                    else CarrierRecoveryDisposition.STILL_ROLL if preserved == 0
                    else CarrierRecoveryDisposition.ESCALATE
                )
            results.append(FrozenRecoveryEvaluation(container_id, disposition, preserved, len(scenarios.worlds), hard_safe))
        return tuple(results)
