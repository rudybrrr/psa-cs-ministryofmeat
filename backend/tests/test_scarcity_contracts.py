from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.app.domain.models import CargoProfile, Connection, Container, ScheduleEvent
from backend.app.domain.scarcity import (
    AllocationPlan,
    AllocationStrategy,
    CanonicalIncidentFixture,
    CargoKind,
    ContainerRecoveryProfile,
    EvaluationSeedManifest,
    ExpediteCapacityPlan,
    HandlingGroupLimit,
    HoldoutAllocationComparison,
    NamedFactor,
    ScenarioAssumptions,
    ScenarioSet,
    ScenarioWorld,
    ScarcityBenchmarkReport,
    ScarcityEvaluationReport,
    ServiceOutcome,
    ServiceWindow,
    StrategyEvaluation,
)


INCIDENT_ID = UUID("11111111-1111-4111-8111-111111111111")


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 22, hour, minute, tzinfo=UTC)


def connection() -> Connection:
    return Connection(
        id="SYN-CONN-SF1",
        outbound_vessel_name="M/V Synthetic Feeder One",
        outbound_voyage="SYN-SF1-0822",
        destination_port="MYPKG",
        cutoff_at=at(5, 35),
        departure_at=at(6, 30),
        minimum_transfer_minutes=90,
        expedited_transfer_minutes=60,
    )


def container() -> Container:
    onward_connection = connection()
    return Container(
        id="SYN-CNT-001",
        origin_port="NLRTM",
        destination_port=onward_connection.destination_port,
        cargo=CargoProfile(
            commodity="Synthetic dry cargo",
            gross_weight_kg=12_100,
            dangerous_goods=False,
        ),
        inbound_vessel_call_id="SYN-ASX17-TUAS-001",
        onward_connection=onward_connection,
    )


def schedule_event() -> ScheduleEvent:
    return ScheduleEvent(
        id="SYN-EVT-ASX17-20260822-001",
        vessel_call_id="SYN-ASX17-TUAS-001",
        vessel_name="M/V Synthetic Meridian",
        terminal_id="SYN-TUAS-TERMINAL",
        scheduled_arrival=at(1),
        estimated_arrival=at(4, 15),
        delay_minutes=195,
        occurred_at=at(4, 15),
    )


def phase_2_contracts() -> dict[str, object]:
    service = ServiceWindow(
        service_id="SF1",
        connection=connection(),
        planned_time_of_arrival=at(5),
        ready_boundary=at(5, 35),
    )
    profile = ContainerRecoveryProfile(
        container=container(),
        service_id="SF1",
        handling_group_id="SYN-A-EQ1",
        cargo_kind=CargoKind.DRY,
        base_ready_at=at(5, 37),
        expedite_minutes_saved=30,
        reefer_continuity_available=True,
        dg_structurally_cleared=True,
    )
    group_limit = HandlingGroupLimit(
        handling_group_id="SYN-A-EQ1",
        slots=4,
    )
    capacity = ExpediteCapacityPlan(
        id="SYN-CAPACITY-SF1-JV2",
        terminal_id="SYN-TUAS-TERMINAL",
        window_start=at(5),
        window_end=at(5, 55),
        overlap_service_ids=("SF1", "JV2"),
        total_slots=8,
        handling_group_limits=(group_limit,),
        max_reefer_slots=3,
        max_dg_slots=1,
    )
    fixture = CanonicalIncidentFixture(
        fixture_id="SYN-CANONICAL-24-V1",
        event=schedule_event(),
        services=(service,),
        profiles=(profile,),
        capacity=capacity,
    )
    assumptions = ScenarioAssumptions(
        seed=20260822,
        world_count=50,
        shared_std_minutes=12,
        handling_group_std_minutes=7,
        container_noise_std_minutes=2,
        antithetic_pairs=True,
    )
    shared_factor = NamedFactor(key="SYN-SHARED", minutes=3)
    group_factor = NamedFactor(key="SYN-A-EQ1", minutes=-1)
    container_factor = NamedFactor(key="SYN-CNT-001", minutes=1)
    world = ScenarioWorld(
        index=0,
        shared_discharge_factor_minutes=shared_factor.minutes,
        handling_group_factors=(group_factor,),
        container_noise_factors=(container_factor,),
    )
    scenarios = ScenarioSet(assumptions=assumptions, worlds=(world,))
    allocation = AllocationPlan(
        strategy=AllocationStrategy.P50_GREEDY,
        allocated_container_ids=("SYN-CNT-001",),
    )
    service_outcome = ServiceOutcome(
        service_id="SF1",
        preserved_connection_total=40,
    )
    evaluation = StrategyEvaluation(
        allocation=allocation,
        world_count=50,
        preserved_connection_total=40,
        expected_preserved_connections=0.8,
        rollover_total=10,
        expected_rollovers=0.2,
        p10_preserved_connections=0,
        allocation_slot_count=1,
        capacity_violations=0,
        unsafe_allocations=0,
        runtime_ms=1.25,
        service_outcomes=(service_outcome,),
    )
    report = ScarcityEvaluationReport(
        incident_id=INCIDENT_ID,
        fixture_id=fixture.fixture_id,
        seed=assumptions.seed,
        scenario_count=assumptions.world_count,
        baseline=evaluation,
        scenario_aware_evaluations=(evaluation,),
        pareto_evaluations=(evaluation,),
        selected_allocation=None,
        reproducibility_key="a" * 64,
        created_at=at(8),
    )
    seed_manifest = EvaluationSeedManifest(
        manifest_id="SYN-CANONICAL-24-HOLDOUT-V1",
        fixture_id=fixture.fixture_id,
        worlds_per_seed=50,
        seeds=(3309398482, 3951398951),
    )
    holdout_comparison = HoldoutAllocationComparison(
        evaluation=evaluation,
        observed_expected_preserved_delta_vs_baseline=-0.25,
    )
    benchmark = ScarcityBenchmarkReport(
        fixture_id=fixture.fixture_id,
        development_seed=assumptions.seed,
        evaluation_seed_manifest_id=seed_manifest.manifest_id,
        evaluation_seeds=seed_manifest.seeds,
        worlds_per_seed=seed_manifest.worlds_per_seed,
        baseline=evaluation,
        scenario_aware=(holdout_comparison,),
        reproducibility_key="b" * 64,
        created_at=at(9),
    )
    return {
        "service_window": service,
        "container_recovery_profile": profile,
        "handling_group_limit": group_limit,
        "expedite_capacity_plan": capacity,
        "canonical_incident_fixture": fixture,
        "scenario_assumptions": assumptions,
        "named_factor": shared_factor,
        "scenario_world": world,
        "scenario_set": scenarios,
        "allocation_plan": allocation,
        "service_outcome": service_outcome,
        "strategy_evaluation": evaluation,
        "scarcity_evaluation_report": report,
        "evaluation_seed_manifest": seed_manifest,
        "holdout_allocation_comparison": holdout_comparison,
        "scarcity_benchmark_report": benchmark,
    }


def test_service_window_requires_pta_plus_35_minutes() -> None:
    window = ServiceWindow(
        service_id="SF1",
        connection=connection(),
        planned_time_of_arrival=at(5),
        ready_boundary=at(5, 35),
    )

    assert window.ready_boundary - window.planned_time_of_arrival == timedelta(
        minutes=35
    )


def test_service_window_rejects_a_different_boundary() -> None:
    with pytest.raises(ValidationError, match="PTA plus 35 minutes"):
        ServiceWindow(
            service_id="SF1",
            connection=connection(),
            planned_time_of_arrival=at(5),
            ready_boundary=at(5, 34),
        )


def test_existing_container_contract_remains_unchanged() -> None:
    assert set(Container.model_fields) == {
        "id",
        "origin_port",
        "destination_port",
        "cargo",
        "inbound_vessel_call_id",
        "onward_connection",
    }


def test_phase_2_enums_have_only_the_approved_values() -> None:
    assert {kind.value for kind in CargoKind} == {"DRY", "REEFER", "DG"}
    assert {strategy.value for strategy in AllocationStrategy} == {
        "P50_GREEDY",
        "SCENARIO_AWARE",
    }


@pytest.mark.parametrize("contract", phase_2_contracts().values())
def test_every_phase_2_contract_is_frozen(contract: object) -> None:
    field_name = next(iter(type(contract).model_fields))

    with pytest.raises(ValidationError, match="Instance is frozen"):
        setattr(contract, field_name, getattr(contract, field_name))


@pytest.mark.parametrize("contract", phase_2_contracts().values())
def test_every_phase_2_contract_rejects_unknown_fields(contract: object) -> None:
    data = contract.model_dump()
    data["unexpected_business_field"] = "not allowed"

    with pytest.raises(ValidationError, match="unexpected_business_field"):
        type(contract).model_validate(data)


def test_collection_fields_are_immutable_tuples() -> None:
    contracts = phase_2_contracts()

    assert isinstance(
        contracts["expedite_capacity_plan"].overlap_service_ids, tuple
    )
    assert isinstance(
        contracts["expedite_capacity_plan"].handling_group_limits, tuple
    )
    assert isinstance(contracts["canonical_incident_fixture"].services, tuple)
    assert isinstance(contracts["canonical_incident_fixture"].profiles, tuple)
    assert isinstance(contracts["scenario_world"].handling_group_factors, tuple)
    assert isinstance(contracts["scenario_world"].container_noise_factors, tuple)
    assert isinstance(contracts["scenario_set"].worlds, tuple)
    assert isinstance(contracts["allocation_plan"].allocated_container_ids, tuple)
    assert isinstance(contracts["strategy_evaluation"].service_outcomes, tuple)
    assert isinstance(
        contracts["scarcity_evaluation_report"].scenario_aware_evaluations, tuple
    )
    assert isinstance(
        contracts["scarcity_evaluation_report"].pareto_evaluations, tuple
    )
    assert isinstance(contracts["evaluation_seed_manifest"].seeds, tuple)
    assert isinstance(contracts["scarcity_benchmark_report"].evaluation_seeds, tuple)
    assert isinstance(contracts["scarcity_benchmark_report"].scenario_aware, tuple)


@pytest.mark.parametrize(
    ("contract_name", "timestamp_field"),
    [
        ("service_window", "planned_time_of_arrival"),
        ("service_window", "ready_boundary"),
        ("container_recovery_profile", "base_ready_at"),
        ("expedite_capacity_plan", "window_start"),
        ("expedite_capacity_plan", "window_end"),
        ("scarcity_evaluation_report", "created_at"),
        ("scarcity_benchmark_report", "created_at"),
    ],
)
def test_phase_2_contracts_reject_naive_timestamps(
    contract_name: str, timestamp_field: str
) -> None:
    contract = phase_2_contracts()[contract_name]
    data = contract.model_dump()
    data[timestamp_field] = datetime(2026, 8, 22, 5, 0)

    with pytest.raises(ValidationError):
        type(contract).model_validate(data)


def test_default_report_timestamps_are_timezone_aware_utc() -> None:
    evaluation = phase_2_contracts()["strategy_evaluation"]
    report = ScarcityEvaluationReport(
        incident_id=INCIDENT_ID,
        fixture_id="SYN-CANONICAL-24-V1",
        seed=20260822,
        scenario_count=50,
        baseline=evaluation,
        scenario_aware_evaluations=(evaluation,),
        pareto_evaluations=(evaluation,),
        selected_allocation=None,
        reproducibility_key="c" * 64,
    )
    benchmark = ScarcityBenchmarkReport(
        fixture_id="SYN-CANONICAL-24-V1",
        development_seed=20260822,
        evaluation_seed_manifest_id="SYN-CANONICAL-24-HOLDOUT-V1",
        evaluation_seeds=(3309398482,),
        worlds_per_seed=50,
        baseline=evaluation,
        scenario_aware=(),
        reproducibility_key="d" * 64,
    )

    assert report.created_at.utcoffset().total_seconds() == 0
    assert benchmark.created_at.utcoffset().total_seconds() == 0


def test_evaluation_contracts_report_metrics_without_encoding_a_winner() -> None:
    assert set(StrategyEvaluation.model_fields) == {
        "allocation",
        "world_count",
        "preserved_connection_total",
        "expected_preserved_connections",
        "rollover_total",
        "expected_rollovers",
        "p10_preserved_connections",
        "allocation_slot_count",
        "capacity_violations",
        "unsafe_allocations",
        "runtime_ms",
        "service_outcomes",
    }
    assert set(ScarcityEvaluationReport.model_fields) == {
        "id",
        "incident_id",
        "fixture_id",
        "seed",
        "scenario_count",
        "baseline",
        "scenario_aware_evaluations",
        "pareto_evaluations",
        "selected_allocation",
        "reproducibility_key",
        "created_at",
    }
    comparison = phase_2_contracts()["holdout_allocation_comparison"]

    assert comparison.observed_expected_preserved_delta_vs_baseline == -0.25


def test_phase_2_contracts_do_not_encode_arbitrary_business_weights() -> None:
    forbidden_fields = {
        "cargo_priority_score",
        "service_priority_score",
        "downstream_impact_weight",
        "preference_coefficient",
    }

    for contract in phase_2_contracts().values():
        assert forbidden_fields.isdisjoint(type(contract).model_fields)


@pytest.mark.parametrize(
    "report_name",
    ["scarcity_evaluation_report", "scarcity_benchmark_report"],
)
def test_reproducibility_keys_require_exactly_64_characters(
    report_name: str,
) -> None:
    report = phase_2_contracts()[report_name]
    data = report.model_dump()
    data["reproducibility_key"] = "too-short"

    with pytest.raises(ValidationError, match="at least 64 characters"):
        type(report).model_validate(data)


@pytest.mark.parametrize(
    ("contract_name", "field_name", "invalid_value"),
    [
        ("handling_group_limit", "slots", -1),
        ("expedite_capacity_plan", "total_slots", -1),
        ("scenario_assumptions", "world_count", 0),
        ("scenario_assumptions", "shared_std_minutes", 0),
        ("scenario_world", "index", -1),
        ("strategy_evaluation", "preserved_connection_total", -1),
        ("strategy_evaluation", "runtime_ms", -1),
        ("evaluation_seed_manifest", "worlds_per_seed", 0),
    ],
)
def test_numeric_contract_boundaries_reject_invalid_values(
    contract_name: str, field_name: str, invalid_value: int
) -> None:
    contract = phase_2_contracts()[contract_name]
    data = contract.model_dump()
    data[field_name] = invalid_value

    with pytest.raises(ValidationError):
        type(contract).model_validate(data)
