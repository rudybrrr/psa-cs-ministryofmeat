import inspect
from types import ModuleType

from backend.app.evaluation import benchmark, scarcity
from backend.app.optimization import scarcity as optimization
from backend.app.orchestration import scarce_capacity, state_machine
from backend.app.policies import allocation_dominance, baseline, dominance
from backend.app.services import (
    canonical_incident,
    manifest,
    scenarios,
    schedule,
    yard,
)
from backend.app.main import app


PROHIBITED_OPERATIONS = {
    "hold_feeder",
    "change_carrier_schedule",
    "override_dg_rule",
    "set_yard_capacity",
}


def discover_public_callable_names(*modules: ModuleType) -> set[str]:
    names: set[str] = set()
    for module in modules:
        for name, value in vars(module).items():
            if name.startswith("_"):
                continue
            if (
                inspect.isfunction(value) or inspect.isclass(value)
            ) and value.__module__ == module.__name__:
                names.add(name)
            if inspect.isclass(value) and value.__module__ == module.__name__:
                names.update(
                    member_name
                    for member_name, member in inspect.getmembers(value)
                    if not member_name.startswith("_")
                    and callable(member)
                )
    return names


def test_api_and_domain_do_not_expose_external_control_operations() -> None:
    public_callables = discover_public_callable_names(
        schedule,
        manifest,
        yard,
        dominance,
        state_machine,
        canonical_incident,
        scenarios,
        baseline,
        allocation_dominance,
        scarcity,
        optimization,
        scarce_capacity,
        benchmark,
    )
    exposed = public_callables | {
        route.name for route in app.routes
    } | {route.path for route in app.routes}
    normalized = {
        value.lower().replace("-", "_").replace("/", "_")
        for value in exposed
    }

    for prohibited in PROHIBITED_OPERATIONS:
        assert all(prohibited not in value for value in normalized)
