# Canonical Scarce-Capacity Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the completed one-container foundation into the clearly synthetic canonical 24-container incident, compare a deterministic p50 greedy baseline with a seeded scenario-aware eight-slot allocation, and persist and expose reproducible results without introducing an LLM, carrier negotiation, or DG semantic reasoning.

**Architecture:** Preserve the frozen Task 1 contracts and existing one-container workflow/API. Add Phase 2 contracts in a separate module, load one canonical JSON fixture, pre-generate one immutable set of correlated scenario worlds, and pass that exact set to both allocators and the evaluator. Scenario generation and ready-time arithmetic remain plain Python; OR-Tools CP-SAT receives precomputed integer preservation coefficients and enforces only allocation/feasibility constraints. A separate canonical workflow persists the comparison report and creates `EXPEDITE` decisions only when deterministic dominance identifies one technically dominant allocation; otherwise it preserves Pareto-efficient alternatives and escalates for later human judgment.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLModel, SQLite, pytest, HTTPX/TestClient, Python `random.Random`, OR-Tools CP-SAT, `pyproject.toml`, and `uv.lock`.

**Spec:** `docs/specs/psa-code-sprint-final-plan.md`, with frozen decisions in `docs/coordination/DECISIONS.md`.

## Global Constraints

- The approved product direction, authority model, current architecture, and four hard requirements in the Final Plan remain frozen.
- Existing Task 1 domain contracts are not mutated. New Phase 2 contracts live in `backend/app/domain/scarcity.py`. If execution proves an existing frozen contract must change, stop, propose the minimum change in the append-only `docs/coordination/DECISIONS.md`, and wait for approval.
- Preserve the existing one-container workflow, its four API routes, and all current tests. The canonical workflow is additive.
- Use Python `>=3.12,<3.13`. Add OR-Tools as a runtime dependency and lock the resolved version; do not add NumPy, SciPy, simulation frameworks, or a graph framework.
- Use OR-Tools CP-SAT only for allocation and feasibility. Generate and freeze all scenario worlds before constructing a CP-SAT model.
- Development and debugging use the fixed seeds `20260822`, `20260823`, and `20260824`; the canonical development decision set uses seed `20260822` and exactly 50 scenario worlds. Baseline and scenario-aware strategies consume the same `ScenarioSet` instance.
- The final empirical benchmark uses 50 distinct frozen holdout seeds from `shared/fixtures/scarcity-evaluation-seeds.json`. Each holdout seed generates 50 worlds, for 2,500 evaluation worlds in total. Apart from manifest identity/count/uniqueness validation, these seeds are never executed by development tests or used for fixture shaping, generator tuning, policy tuning, allocation selection, or solver tie-breaking.
- Freeze the baseline allocation and every scenario-aware Pareto candidate using only the canonical development decision set before loading any holdout worlds. Evaluate those fixed allocations against the same holdout worlds; never re-solve or choose a candidate after seeing holdout results.
- Report every observed holdout delta against the greedy baseline honestly, whether positive, zero, or negative. No test may require the scenario-aware allocator to beat the baseline.
- Never sample an independent ready time per container. Each world contains one shared discharge factor, one factor per block/equipment handling group, and a smaller per-container noise factor.
- Compute ready time as `base_ready_at - shared_discharge_factor - block_equipment_factor - per_container_noise`; an allocated container then subtracts its fixed expedite saving.
- Factor distributions and all fixture values are synthetic experimental assumptions, not PSA-calibrated forecasts.
- Persist timestamps as timezone-aware UTC. Document Singapore display times alongside UTC fixture values.
- The primary optimization objective is only the integer total of preserved connections across the supplied development decision worlds. Cargo priority, service preference, and downstream consequence never appear as arbitrary weights.
- Equipment, handling-group, total-slot, reefer-continuity, and structural DG eligibility are hard constraints. No allocation exceeds eight critical-overlap slots.
- Deterministic orchestration and synthetic retrieval use `AuditActor.SYSTEM`; CP-SAT uses `AuditActor.SOLVER`; baseline, evaluation, Pareto filtering, dominance, and deterministic decision creation use `AuditActor.POLICY`. `AuditActor.AGENT` remains unused.
- No callable or route may expose `hold_feeder`, `change_carrier_schedule`, `override_dg_rule`, or `set_yard_capacity`.
- Do not implement LLM orchestration, prompts, agent endpoints, RTA ACCEPT/COUNTER/timeout behavior, carrier simulation, DG semantic mismatch analysis, frontend, authentication, deployment, WebSockets, background workers, or reset.
- Runtime is measured but inherently non-deterministic. Reproducibility comparisons and reproducibility keys exclude UUIDs, timestamps, and runtime while including fixture version, development seed, holdout seed-manifest identity where applicable, scenario assumptions, allocations, and semantic metrics.
- Every behavior follows RED → GREEN → focused verification before its task commit. Run the full existing suite at every task boundary.

## Canonical Synthetic Assumptions

- Fixture ID: `SYN-CANONICAL-24-V1`
- Terminal: `SYN-TUAS-TERMINAL`
- Inbound service/vessel call: `ASX-17` / `SYN-ASX17-TUAS-001`
- Inbound vessel name: `M/V Synthetic Meridian`
- Event: `SYN-EVT-ASX17-20260822-001`
- Scheduled/estimated arrival: `2026-08-22T01:00:00Z` / `2026-08-22T04:15:00Z` (09:00 / 12:15 Singapore), a 195-minute delay
- SF1 PTA/boundary: `2026-08-22T05:00:00Z` / `2026-08-22T05:35:00Z`
- JV2 PTA/boundary: `2026-08-22T05:20:00Z` / `2026-08-22T05:55:00Z`
- EC3 PTA/boundary: `2026-08-22T07:00:00Z` / `2026-08-22T07:35:00Z`
- SF1 connection: `SYN-CONN-SF1`, `M/V Synthetic Feeder One`, voyage `SYN-SF1-0822`, destination `MYPKG`, departure `2026-08-22T06:30:00Z`
- JV2 connection: `SYN-CONN-JV2`, `M/V Synthetic Java Venture`, voyage `SYN-JV2-0822`, destination `IDJKT`, departure `2026-08-22T07:00:00Z`
- EC3 connection: `SYN-CONN-EC3`, `M/V Synthetic Eastern Connector`, voyage `SYN-EC3-0822`, destination `CNSHA`, departure `2026-08-22T09:00:00Z`
- Existing `Connection.cutoff_at` equals the service ready boundary; existing normal/expedited transfer fields are fixed synthetic metadata at 90/60 minutes and are not used by the Phase 2 ready-time evaluator.
- Every container has origin `NLRTM`, the service destination, inbound call `SYN-ASX17-TUAS-001`, gross weight `12_000 + 100 * numeric_container_suffix` kilograms, and commodity text `Synthetic dry cargo`, `Synthetic chilled cargo`, or `Synthetic declared DG cargo`. Only DG rows set `dangerous_goods=true`, and their synthetic declaration uses `UN1993` without semantic interpretation.
- Expedite saving: 30 minutes per structurally eligible allocation
- Capacity window: `2026-08-22T05:00:00Z`–`2026-08-22T05:55:00Z` for the critical SF1/JV2 overlap; eight total slots; group limits `SYN-A-EQ1=4`, `SYN-B-EQ2=3`, `SYN-C-EQ3=3`; at most three reefers and one structurally cleared DG container
- Scenario assumptions: shared standard deviation 12 minutes, block/equipment standard deviation 7 minutes, per-container standard deviation 2 minutes; each development or holdout set generates 25 seeded samples plus antithetic mirrors for 50 coherent worlds and an exact synthetic p50 of zero
- Benchmark protocol: make all implementation decisions with the development/debug seeds only; then evaluate the already-fixed greedy allocation and already-fixed scenario-aware Pareto candidates over 50 separately seeded holdout sets. The distributions are synthetic experimental assumptions, and no outcome direction or effect size is predeclared.

`base_ready_at` is each service boundary plus the offset below. A p50 beneficiary has `offset > 0` and `offset - 30 <= 0`, subject to structural eligibility.

| Container | Service | Cargo | Group | Offset | Reefer continuity | DG cleared | Classification |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| `SYN-CNT-001` | SF1 | DRY | SYN-A-EQ1 | 2 | true | true | expedite benefit |
| `SYN-CNT-002` | SF1 | REEFER | SYN-A-EQ1 | 4 | true | true | expedite benefit |
| `SYN-CNT-003` | SF1 | DRY | SYN-B-EQ2 | 6 | true | true | expedite benefit |
| `SYN-CNT-004` | SF1 | DG | SYN-B-EQ2 | 14 | true | true | expedite benefit |
| `SYN-CNT-005` | SF1 | DRY | SYN-A-EQ1 | 24 | true | true | expedite benefit |
| `SYN-CNT-006` | SF1 | REEFER | SYN-C-EQ3 | 26 | true | true | expedite benefit |
| `SYN-CNT-007` | SF1 | DRY | SYN-C-EQ3 | 28 | true | true | expedite benefit |
| `SYN-CNT-008` | SF1 | DRY | SYN-A-EQ1 | -20 | true | true | no expedite needed |
| `SYN-CNT-009` | SF1 | DG | SYN-B-EQ2 | 45 | true | false | expedition cannot preserve |
| `SYN-CNT-010` | JV2 | DRY | SYN-A-EQ1 | 8 | true | true | expedite benefit |
| `SYN-CNT-011` | JV2 | REEFER | SYN-A-EQ1 | 10 | true | true | expedite benefit |
| `SYN-CNT-012` | JV2 | DRY | SYN-B-EQ2 | 12 | true | true | expedite benefit |
| `SYN-CNT-013` | JV2 | DG | SYN-B-EQ2 | 16 | true | true | expedite benefit |
| `SYN-CNT-014` | JV2 | DRY | SYN-C-EQ3 | 18 | true | true | expedite benefit |
| `SYN-CNT-015` | JV2 | REEFER | SYN-C-EQ3 | 20 | true | true | expedite benefit |
| `SYN-CNT-016` | JV2 | DRY | SYN-A-EQ1 | -18 | true | true | no expedite needed |
| `SYN-CNT-017` | JV2 | DRY | SYN-B-EQ2 | 45 | true | true | expedition cannot preserve |
| `SYN-CNT-018` | EC3 | DRY | SYN-A-EQ1 | -25 | true | true | no expedite needed |
| `SYN-CNT-019` | EC3 | REEFER | SYN-B-EQ2 | -20 | true | true | no expedite needed |
| `SYN-CNT-020` | EC3 | DRY | SYN-C-EQ3 | -15 | true | true | no expedite needed |
| `SYN-CNT-021` | EC3 | DRY | SYN-A-EQ1 | 45 | true | true | expedition cannot preserve |
| `SYN-CNT-022` | EC3 | DG | SYN-B-EQ2 | 50 | true | false | expedition cannot preserve |
| `SYN-CNT-023` | EC3 | REEFER | SYN-C-EQ3 | 55 | false | true | expedition cannot preserve |
| `SYN-CNT-024` | EC3 | DRY | SYN-A-EQ1 | 60 | true | true | expedition cannot preserve |

This yields service counts 9/8/7, cargo counts DRY/REEFER/DG = 14/6/4, 13 beneficiaries = 7 SF1 + 6 JV2, five needing no expedition, and six not preserved by expedition alone. Later RTA and DG-semantic phases may change downstream outcomes; this plan does not claim the Final Plan's ultimate 18/5/1 outcome.

## File Map

- `pyproject.toml`, `uv.lock`: Add and lock Python 3.12-compatible OR-Tools.
- `backend/app/domain/scarcity.py`: Additive frozen Phase 2 contracts and enums only.
- `shared/fixtures/canonical-24-container.json`, `shared/fixtures/scarcity-evaluation-seeds.json`, `shared/fixtures/README.md`: Exact synthetic fixture, assumptions, and frozen final-benchmark seed manifest.
- `backend/app/services/canonical_incident.py`: Read-only fixture loader.
- `backend/app/services/scenarios.py`: Correlated seeded world generation; no OR-Tools import.
- `backend/app/evaluation/__init__.py`, `backend/app/evaluation/scarcity.py`, `backend/app/evaluation/benchmark.py`: Evaluation package plus ready arithmetic, beneficiaries, constraints, outcomes, metrics, comparison, holdout benchmarking, and reproducibility keys.
- `backend/app/policies/baseline.py`: Deterministic p50 greedy baseline.
- `backend/app/optimization/__init__.py`, `backend/app/optimization/scarcity.py`: Optimization package plus CP-SAT allocation and optimal-set enumeration only.
- `backend/app/policies/allocation_dominance.py`: Pareto filtering and deterministic dominance.
- `backend/app/storage/repositories.py`: Scarcity report persistence and atomic batch decisions.
- `backend/app/orchestration/scarce_capacity.py`: Canonical stateful workflow and audit.
- `backend/app/main.py`: Two minimal canonical trigger/inspection routes.
- `backend/tests/conftest.py`: Shared canonical fixture and canonical scenario-set fixtures for focused tests.
- `backend/tests/test_scarcity_contracts.py`, `test_canonical_incident.py`, `test_scenario_worlds.py`, `test_scarcity_evaluation.py`, `test_baseline_allocator.py`, `test_scarcity_optimizer.py`, `test_allocation_dominance.py`, `test_scarcity_benchmark.py`, `test_scarce_capacity_workflow.py`, `test_scarcity_api.py`: Focused Phase 2 behavior.
- `backend/tests/test_audit.py`, `backend/tests/test_authority_boundaries.py`: New table/repository checks and expanded authority regression.

---

### Task 1: Additive Phase 2 Contracts

**Files:**
- Create: `backend/app/domain/scarcity.py`
- Create: `backend/tests/test_scarcity_contracts.py`

**Interfaces:**
- Consumes: Existing `FrozenContract`, `ScheduleEvent`, `Connection`, `Container`, and UTC helpers unchanged.
- Produces: `CargoKind`, `AllocationStrategy`, `ServiceWindow`, `ContainerRecoveryProfile`, `HandlingGroupLimit`, `ExpediteCapacityPlan`, `CanonicalIncidentFixture`, `ScenarioAssumptions`, `NamedFactor`, `ScenarioWorld`, `ScenarioSet`, `AllocationPlan`, `ServiceOutcome`, `StrategyEvaluation`, `ScarcityEvaluationReport`, `EvaluationSeedManifest`, `HoldoutAllocationComparison`, and `ScarcityBenchmarkReport`.

- [ ] **Step 1: Write failing additive-contract tests**

```python
def test_service_window_requires_pta_plus_35_minutes(sf1_connection):
    window = ServiceWindow(
        service_id="SF1",
        connection=sf1_connection,
        planned_time_of_arrival=at(5),
        ready_boundary=at(5, 35),
    )
    assert window.ready_boundary - window.planned_time_of_arrival == timedelta(minutes=35)


def test_service_window_rejects_a_different_boundary(sf1_connection):
    with pytest.raises(ValidationError, match="PTA plus 35 minutes"):
        ServiceWindow(
            service_id="SF1",
            connection=sf1_connection,
            planned_time_of_arrival=at(5),
            ready_boundary=at(5, 34),
        )


def test_existing_container_contract_remains_unchanged():
    assert set(Container.model_fields) == {
        "id", "origin_port", "destination_port", "cargo",
        "inbound_vessel_call_id", "onward_connection",
    }
```

Also test every new contract is frozen, extra fields are forbidden, factor collections are tuples, timestamps reject naive values, and report fields carry every required metric.

- [ ] **Step 2: Run RED**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_contracts.py -q`

Expected: collection fails because `backend.app.domain.scarcity` does not exist.

- [ ] **Step 3: Implement only the additive contracts**

```python
class CargoKind(StrEnum):
    DRY = "DRY"
    REEFER = "REEFER"
    DG = "DG"


class AllocationStrategy(StrEnum):
    P50_GREEDY = "P50_GREEDY"
    SCENARIO_AWARE = "SCENARIO_AWARE"


class ServiceWindow(FrozenContract):
    service_id: str
    connection: Connection
    planned_time_of_arrival: AwareDatetime
    ready_boundary: AwareDatetime

    @model_validator(mode="after")
    def validate_ready_boundary(self) -> "ServiceWindow":
        if self.ready_boundary != self.planned_time_of_arrival + timedelta(minutes=35):
            raise ValueError("ready_boundary must be PTA plus 35 minutes")
        return self


class ContainerRecoveryProfile(FrozenContract):
    container: Container
    service_id: str
    handling_group_id: str
    cargo_kind: CargoKind
    base_ready_at: AwareDatetime
    expedite_minutes_saved: int = Field(gt=0)
    reefer_continuity_available: bool
    dg_structurally_cleared: bool


class HandlingGroupLimit(FrozenContract):
    handling_group_id: str
    slots: int = Field(ge=0)


class ExpediteCapacityPlan(FrozenContract):
    id: str
    terminal_id: str
    window_start: AwareDatetime
    window_end: AwareDatetime
    overlap_service_ids: tuple[str, ...]
    total_slots: int = Field(ge=0)
    handling_group_limits: tuple[HandlingGroupLimit, ...]
    max_reefer_slots: int = Field(ge=0)
    max_dg_slots: int = Field(ge=0)


class CanonicalIncidentFixture(FrozenContract):
    fixture_id: str
    event: ScheduleEvent
    services: tuple[ServiceWindow, ...]
    profiles: tuple[ContainerRecoveryProfile, ...]
    capacity: ExpediteCapacityPlan


class ScenarioAssumptions(FrozenContract):
    seed: int
    world_count: int = Field(gt=0)
    shared_std_minutes: float = Field(gt=0)
    handling_group_std_minutes: float = Field(gt=0)
    container_noise_std_minutes: float = Field(gt=0)
    antithetic_pairs: bool


class NamedFactor(FrozenContract):
    key: str
    minutes: int


class ScenarioWorld(FrozenContract):
    index: int = Field(ge=0)
    shared_discharge_factor_minutes: int
    handling_group_factors: tuple[NamedFactor, ...]
    container_noise_factors: tuple[NamedFactor, ...]


class ScenarioSet(FrozenContract):
    assumptions: ScenarioAssumptions
    worlds: tuple[ScenarioWorld, ...]


class AllocationPlan(FrozenContract):
    strategy: AllocationStrategy
    allocated_container_ids: tuple[str, ...]


class ServiceOutcome(FrozenContract):
    service_id: str
    preserved_connection_total: int = Field(ge=0)


class StrategyEvaluation(FrozenContract):
    allocation: AllocationPlan
    world_count: int = Field(gt=0)
    preserved_connection_total: int = Field(ge=0)
    expected_preserved_connections: float = Field(ge=0)
    rollover_total: int = Field(ge=0)
    expected_rollovers: float = Field(ge=0)
    p10_preserved_connections: int = Field(ge=0)
    allocation_slot_count: int = Field(ge=0)
    capacity_violations: int = Field(ge=0)
    unsafe_allocations: int = Field(ge=0)
    runtime_ms: float = Field(ge=0)
    service_outcomes: tuple[ServiceOutcome, ...]


class ScarcityEvaluationReport(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    fixture_id: str
    seed: int
    scenario_count: int = Field(gt=0)
    baseline: StrategyEvaluation
    scenario_aware_evaluations: tuple[StrategyEvaluation, ...]
    pareto_evaluations: tuple[StrategyEvaluation, ...]
    selected_allocation: AllocationPlan | None
    reproducibility_key: str = Field(min_length=64, max_length=64)
    created_at: AwareDatetime = Field(default_factory=utc_now)


class EvaluationSeedManifest(FrozenContract):
    manifest_id: str
    fixture_id: str
    worlds_per_seed: int = Field(gt=0)
    seeds: tuple[int, ...]


class HoldoutAllocationComparison(FrozenContract):
    evaluation: StrategyEvaluation
    observed_expected_preserved_delta_vs_baseline: float


class ScarcityBenchmarkReport(FrozenContract):
    fixture_id: str
    development_seed: int
    evaluation_seed_manifest_id: str
    evaluation_seeds: tuple[int, ...]
    worlds_per_seed: int = Field(gt=0)
    baseline: StrategyEvaluation
    scenario_aware: tuple[HoldoutAllocationComparison, ...]
    reproducibility_key: str = Field(min_length=64, max_length=64)
    created_at: AwareDatetime = Field(default_factory=utc_now)
```

- [ ] **Step 4: Run GREEN and full verification**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_contracts.py -q`

Expected: PASS.

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/domain/scarcity.py backend/tests/test_scarcity_contracts.py
git commit -m "feat: add scarce-capacity domain contracts"
```

Execution checkpoint: present the additive contracts for review and do not begin Task 2 until they are approved. No entry in `DECISIONS.md` is needed unless review requests a mutation to a frozen pre-Phase-2 contract.

### Task 2: Canonical 24-Container Fixture

**Files:**
- Create: `shared/fixtures/canonical-24-container.json`
- Modify: `shared/fixtures/README.md`
- Create: `backend/app/services/canonical_incident.py`
- Create: `backend/tests/test_canonical_incident.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: Phase 2 fixture contracts and existing schedule/container contracts.
- Produces: `SyntheticCanonicalIncidentService.load() -> CanonicalIncidentFixture`.

- [ ] **Step 1: Write failing fixture tests**

```python
def test_canonical_fixture_has_the_approved_shape():
    fixture = SyntheticCanonicalIncidentService().load()
    assert fixture.fixture_id == "SYN-CANONICAL-24-V1"
    assert fixture.event.delay_minutes == 195
    assert fixture.event.terminal_id == "SYN-TUAS-TERMINAL"
    assert [service.service_id for service in fixture.services] == ["SF1", "JV2", "EC3"]
    assert Counter(profile.service_id for profile in fixture.profiles) == {
        "SF1": 9, "JV2": 8, "EC3": 7,
    }
    assert Counter(profile.cargo_kind for profile in fixture.profiles) == {
        CargoKind.DRY: 14, CargoKind.REEFER: 6, CargoKind.DG: 4,
    }


def test_fixture_has_thirteen_beneficiaries_and_eight_slots():
    fixture = SyntheticCanonicalIncidentService().load()
    services = {item.service_id: item for item in fixture.services}
    beneficiaries = [
        profile for profile in fixture.profiles
        if profile.base_ready_at > services[profile.service_id].ready_boundary
        and profile.base_ready_at - timedelta(minutes=profile.expedite_minutes_saved)
        <= services[profile.service_id].ready_boundary
        and (profile.cargo_kind is not CargoKind.REEFER or profile.reefer_continuity_available)
        and (profile.cargo_kind is not CargoKind.DG or profile.dg_structurally_cleared)
    ]
    assert Counter(item.service_id for item in beneficiaries) == {"SF1": 7, "JV2": 6}
    assert fixture.capacity.total_slots == 8
    assert fixture.capacity.overlap_service_ids == ("SF1", "JV2")
```

Pin exact UTC PTA/boundaries, 24 unique `SYN-CNT-` IDs, group limits 4/3/3, reefer limit 3, DG limit 1, DG structural flags, reefer continuity flags, and absence of Pasir Panjang identifiers. For every service assert `connection.cutoff_at == ready_boundary`; for every profile assert its embedded connection ID matches its `service_id`, destination matches the service connection, and `CargoKind.DG` exactly matches `cargo.dangerous_goods`.

- [ ] **Step 2: Run RED**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_canonical_incident.py -q`

Expected: collection fails because the loader and JSON do not exist.

- [ ] **Step 3: Create the exact JSON and read-only loader**

Encode the table in this plan. Resolve the default path relative to the repository:

```python
DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "shared" / "fixtures" / "canonical-24-container.json"
)


class SyntheticCanonicalIncidentService:
    def __init__(self, fixture_path: Path = DEFAULT_FIXTURE_PATH) -> None:
        self._fixture_path = fixture_path

    def load(self) -> CanonicalIncidentFixture:
        data = json.loads(self._fixture_path.read_text(encoding="utf-8"))
        return CanonicalIncidentFixture.model_validate(data)
```

- [ ] **Step 4: Run GREEN and full verification**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_canonical_incident.py -q`

Expected: PASS with 24 containers, 13 beneficiaries, and eight slots.

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add shared/fixtures/canonical-24-container.json shared/fixtures/README.md backend/app/services/canonical_incident.py backend/tests/conftest.py backend/tests/test_canonical_incident.py
git commit -m "feat: add canonical synthetic incident fixture"
```

### Task 3: Correlated Seeded Scenario Worlds

**Files:**
- Create: `backend/app/services/scenarios.py`
- Create: `backend/tests/test_scenario_worlds.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: `CanonicalIncidentFixture` and scenario contracts.
- Produces: `SeededScenarioGenerator.generate(fixture, *, seed=20260822, world_count=50) -> ScenarioSet`.

The seeds in this task are development/debug seeds only. Development behavior tests never load the frozen final-benchmark seed manifest; the manifest gets only schema/uniqueness validation before the final benchmark.

- [ ] **Step 1: Write failing correlation and reproducibility tests**

```python
def test_same_seed_generates_identical_worlds(canonical_fixture):
    generator = SeededScenarioGenerator()
    first = generator.generate(canonical_fixture, seed=20260822, world_count=50)
    second = generator.generate(canonical_fixture, seed=20260822, world_count=50)
    different = generator.generate(canonical_fixture, seed=20260823, world_count=50)
    assert first == second
    assert first != different
    assert len(first.worlds) == 50


def test_shared_and_group_factors_create_correlation(canonical_fixture):
    worlds = SeededScenarioGenerator().generate(
        canonical_fixture, seed=20260822, world_count=500
    )
    same_a = factor_series(worlds, canonical_fixture, "SYN-CNT-001")
    same_b = factor_series(worlds, canonical_fixture, "SYN-CNT-002")
    cross = factor_series(worlds, canonical_fixture, "SYN-CNT-006")
    assert correlation(same_a, same_b) > correlation(same_a, cross)
    assert correlation(same_a, cross) > 0.5
```

Define the test helper directly and import `correlation` from Python's `statistics` module:

```python
def factor_series(
    scenarios: ScenarioSet,
    fixture: CanonicalIncidentFixture,
    container_id: str,
) -> list[int]:
    profile = next(
        item for item in fixture.profiles if item.container.id == container_id
    )
    return [
        world.shared_discharge_factor_minutes
        + next(
            factor.minutes
            for factor in world.handling_group_factors
            if factor.key == profile.handling_group_id
        )
        + next(
            factor.minutes
            for factor in world.container_noise_factors
            if factor.key == container_id
        )
        for world in scenarios.worlds
    ]
```

Assert one shared factor, three group factors, 24 noise factors per world; `12 > 7 > 2`; mirrored factors sum to zero; odd/non-positive world counts are rejected; and the module does not import OR-Tools.

- [ ] **Step 2: Run RED**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scenario_worlds.py -q`

Expected: collection fails because the generator does not exist.

- [ ] **Step 3: Implement generation outside the solver**

```python
shared = int(round(rng.gauss(0.0, 12.0)))
groups = tuple(
    NamedFactor(key=key, minutes=int(round(rng.gauss(0.0, 7.0))))
    for key in sorted(group_ids)
)
noise = tuple(
    NamedFactor(key=key, minutes=int(round(rng.gauss(0.0, 2.0))))
    for key in sorted(container_ids)
)
```

Generate half the worlds using local `random.Random(seed)`, mirror every factor for the other half, assign stable indices, and return one immutable `ScenarioSet`.

- [ ] **Step 4: Run GREEN and full verification**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scenario_worlds.py -q`

Expected: PASS.

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/scenarios.py backend/tests/conftest.py backend/tests/test_scenario_worlds.py
git commit -m "feat: generate correlated recovery scenarios"
```

### Task 4: Ready-Time Arithmetic and Allocation Evaluation

**Files:**
- Create: `backend/app/evaluation/__init__.py`
- Create: `backend/app/evaluation/scarcity.py`
- Create: `backend/tests/test_scarcity_evaluation.py`

**Interfaces:**
- Consumes: Canonical fixture and one pre-generated `ScenarioSet`.
- Produces: `ScarcityEvaluator.ready_at`, `preserves_connection`, `p50_beneficiary_ids`, `incremental_preservation_count`, `constraint_diagnostics`, `evaluate -> StrategyEvaluation`, and `semantic_reproducibility_key -> str`.

- [ ] **Step 1: Write failing arithmetic, safety, and metric tests**

```python
def test_ready_time_uses_all_three_factor_levels(profile, world):
    observed = ScarcityEvaluator().ready_at(profile, world, expedited=False)
    assert observed == profile.base_ready_at - timedelta(minutes=12 + 7 + 2)


def test_expedition_subtracts_the_fixed_saving(profile, world):
    evaluator = ScarcityEvaluator()
    normal = evaluator.ready_at(profile, world, expedited=False)
    expedited = evaluator.ready_at(profile, world, expedited=True)
    assert normal - expedited == timedelta(minutes=30)


def test_evaluation_reports_required_metrics(canonical_fixture, canonical_scenarios):
    plan = AllocationPlan(
        strategy=AllocationStrategy.P50_GREEDY,
        allocated_container_ids=("SYN-CNT-001",),
    )
    result = ScarcityEvaluator().evaluate(
        canonical_fixture, canonical_scenarios, plan, runtime_ms=1.25
    )
    assert result.preserved_connection_total + result.rollover_total == 24 * 50
    assert result.capacity_violations == 0
    assert result.unsafe_allocations == 0
    assert result.runtime_ms == 1.25
```

Add negative tests for nine allocations, each group limit, reefer/DG limits, `SYN-CNT-022` without clearance, and `SYN-CNT-023` without continuity. Assert `p50_beneficiary_ids` returns the exact 13 IDs in the fixture table. Verify nearest-rank p10 and ordered SF1/JV2/EC3 totals.

- [ ] **Step 2: Run RED**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_evaluation.py -q`

Expected: collection fails because the evaluation package does not exist.

- [ ] **Step 3: Implement plain-Python evaluation**

```python
ready_at = profile.base_ready_at - timedelta(
    minutes=(
        world.shared_discharge_factor_minutes
        + factor_for(world.handling_group_factors, profile.handling_group_id)
        + factor_for(world.container_noise_factors, profile.container.id)
    )
)
if expedited:
    ready_at -= timedelta(minutes=profile.expedite_minutes_saved)
```

`incremental_preservation_count` is expedited successes minus normal successes across the supplied worlds. `p50_beneficiary_ids` uses median normal/expedited readiness from those worlds plus structural eligibility. Define rollovers as 24 minus preserved connections in each experimental world without creating `ROLL` decisions.

The CP-SAT objective later uses `constant normal-success total + sum(incremental_count[id] * allocated[id])`. Because the normal-success total is constant across allocations, maximizing the integer incremental term is exactly equivalent to maximizing total preserved connections; it is not a proxy score.

Build the SHA-256 reproducibility key from canonical JSON excluding report/incident UUIDs, timestamps, and runtime; include fixture ID, seed, assumptions, allocation IDs, and semantic totals.

- [ ] **Step 4: Run GREEN and full verification**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_evaluation.py -q`

Expected: PASS.

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/evaluation backend/tests/test_scarcity_evaluation.py
git commit -m "feat: evaluate recovery allocations across shared worlds"
```

### Task 5: Deterministic p50 Greedy Baseline

**Files:**
- Create: `backend/app/policies/baseline.py`
- Create: `backend/tests/test_baseline_allocator.py`

**Interfaces:**
- Consumes: Fixture, `ScenarioSet`, and `ScarcityEvaluator`.
- Produces: `P50GreedyAllocator.allocate(fixture, scenarios) -> AllocationPlan`.

- [ ] **Step 1: Write failing baseline tests**

```python
def test_baseline_uses_eight_of_thirteen_beneficiaries(
    canonical_fixture, canonical_scenarios
):
    plan = P50GreedyAllocator().allocate(canonical_fixture, canonical_scenarios)
    beneficiaries = ScarcityEvaluator().p50_beneficiary_ids(
        canonical_fixture, canonical_scenarios
    )
    assert len(beneficiaries) == 13
    assert len(plan.allocated_container_ids) == 8
    assert set(plan.allocated_container_ids) <= set(beneficiaries)
    assert plan.allocated_container_ids == (
        "SYN-CNT-001", "SYN-CNT-002", "SYN-CNT-003", "SYN-CNT-004",
        "SYN-CNT-005", "SYN-CNT-006", "SYN-CNT-007", "SYN-CNT-010",
    )
    assert ScarcityEvaluator().constraint_diagnostics(canonical_fixture, plan) == (0, 0)


def test_baseline_is_reproducible(canonical_fixture, canonical_scenarios):
    allocator = P50GreedyAllocator()
    assert allocator.allocate(canonical_fixture, canonical_scenarios) == allocator.allocate(
        canonical_fixture, canonical_scenarios
    )
```

Pin naive order to `(service.ready_boundary, container.id)`. Verify the allocator skips a beneficiary if adding it breaks a hard constraint and never reads per-world expected-preservation coefficients.

- [ ] **Step 2: Run RED**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_baseline_allocator.py -q`

Expected: collection fails because `P50GreedyAllocator` does not exist.

- [ ] **Step 3: Implement the minimal baseline**

```python
for profile in sorted(
    beneficiary_profiles,
    key=lambda item: (service_by_id[item.service_id].ready_boundary, item.container.id),
):
    proposed = selected + [profile.container.id]
    if evaluator.constraint_diagnostics_for_ids(fixture, proposed) == (0, 0):
        selected = proposed
return AllocationPlan(
    strategy=AllocationStrategy.P50_GREEDY,
    allocated_container_ids=tuple(selected),
)
```

Do not add probabilities, cargo weights, service weights, or CP-SAT.

- [ ] **Step 4: Run GREEN and full verification**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_baseline_allocator.py -q`

Expected: PASS.

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/policies/baseline.py backend/tests/test_baseline_allocator.py
git commit -m "feat: add p50 greedy recovery baseline"
```

### Task 6: Scenario-Aware CP-SAT Allocation

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `backend/app/optimization/__init__.py`
- Create: `backend/app/optimization/scarcity.py`
- Create: `backend/tests/test_scarcity_optimizer.py`

**Interfaces:**
- Consumes: 13 p50 beneficiary IDs, precomputed integer incremental-preservation counts, and hard-capacity facts.
- Produces: `ScenarioAwareAllocator.solve(fixture, scenarios) -> tuple[AllocationPlan, ...]` and `ScarcityOptimizationError`.

- [ ] **Step 1: Write failing solver tests before adding production behavior**

Use a four-container fixture with capacity two and hand-built worlds giving coefficients 40/30/10/5:

```python
def test_cp_sat_maximises_expected_preserved_connections(hand_checkable_case):
    plans = ScenarioAwareAllocator().solve(
        hand_checkable_case.fixture, hand_checkable_case.scenarios
    )
    assert [plan.allocated_container_ids for plan in plans] == [
        ("SYN-OPT-001", "SYN-OPT-002")
    ]


def test_canonical_plans_are_safe_and_reproducible(
    canonical_fixture, canonical_scenarios
):
    allocator = ScenarioAwareAllocator()
    evaluator = ScarcityEvaluator()
    first = allocator.solve(canonical_fixture, canonical_scenarios)
    second = allocator.solve(canonical_fixture, canonical_scenarios)
    assert first == second
    assert first
    assert all(len(plan.allocated_container_ids) <= 8 for plan in first)
    assert all(
        set(plan.allocated_container_ids)
        <= set(evaluator.p50_beneficiary_ids(canonical_fixture, canonical_scenarios))
        for plan in first
    )
    assert all(
        evaluator.constraint_diagnostics(canonical_fixture, plan) == (0, 0)
        for plan in first
    )
    objective_values = {
        sum(
            evaluator.incremental_preservation_count(
                canonical_fixture, canonical_scenarios, container_id
            )
            for container_id in plan.allocated_container_ids
        )
        for plan in first
    }
    assert len(objective_values) == 1
```

The four-container fixture has a unique optimum, so its exact allocation assertion is meaningful. Add tests for total/group/reefer/DG limits, structural ineligibility, `OPTIMAL` status, and a generator spy that raises if the optimizer tries to sample worlds. Add a separate tied-optima fixture that asserts the optimal objective value, both valid tied allocations, and every constraint invariant; do not introduce a business weight or secondary tie-break merely to choose one.

- [ ] **Step 2: Run RED**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_optimizer.py -q`

Expected: collection fails because the optimization package and dependency are absent.

- [ ] **Step 3: Add and lock OR-Tools**

Add `"ortools>=9.12,<10"` to runtime dependencies.

Run: `uv lock`

Expected: lock resolves a Python 3.12-compatible OR-Tools release.

- [ ] **Step 4: Implement two-pass CP-SAT solving**

```python
variables = {
    container_id: model.new_bool_var(f"expedite_{container_id}")
    for container_id in beneficiary_ids
}
model.add(sum(variables.values()) <= fixture.capacity.total_slots)
for limit in fixture.capacity.handling_group_limits:
    model.add(
        sum(variables[item.container.id] for item in profiles_in_group[limit.handling_group_id])
        <= limit.slots
    )
model.add(sum(variables[item.container.id] for item in reefers) <= fixture.capacity.max_reefer_slots)
model.add(sum(variables[item.container.id] for item in dg_profiles) <= fixture.capacity.max_dg_slots)
model.maximize(sum(coefficients[item_id] * variable for item_id, variable in variables.items()))
```

Set `num_search_workers=1` and `random_seed=0`; require `OPTIMAL`. Read the integer optimum. Build a second satisfaction model with identical constraints plus `objective_expression == optimum`, no active objective, and `enumerate_all_solutions=True`; collect assignments with `CpSolverSolutionCallback`. Sort IDs within plans and plans lexicographically only for reproducible representation, not as a business preference. The canonical full-slot search has at most `C(13, 8)=1287` sets, so do not truncate objective-optimal alternatives. Tests either use the hand-checkable unique-optimum fixture or assert optimal objective value plus hard-constraint invariants; they do not pin a canonical container set unless product semantics make it uniquely optimal without artificial weights.

- [ ] **Step 5: Run GREEN and full verification**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_optimizer.py -q`

Expected: PASS.

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml uv.lock backend/app/optimization backend/tests/test_scarcity_optimizer.py
git commit -m "feat: allocate scarce expedite capacity with CP-SAT"
```

### Task 7: Pareto Alternatives, Dominance, and Comparison

**Files:**
- Create: `backend/app/policies/allocation_dominance.py`
- Modify: `backend/app/evaluation/scarcity.py`
- Create: `backend/tests/test_allocation_dominance.py`
- Modify: `backend/tests/test_scarcity_evaluation.py`

**Interfaces:**
- Consumes: Baseline plan, objective-optimal scenario-aware plans, and their evaluations.
- Produces: `pareto_front(evaluations)`, `AllocationDominancePolicy.select(evaluations) -> AllocationPlan | None`, and `ScarcityComparisonService.compare(...) -> ScarcityEvaluationReport`.

- [ ] **Step 1: Write failing dominance and comparison tests**

```python
def test_policy_selects_only_a_candidate_dominating_every_other_candidate():
    assert AllocationDominancePolicy().select((dominant, dominated)) == dominant.allocation


def test_policy_refuses_a_real_sf1_jv2_tradeoff():
    frontier = pareto_front((sf1_favouring, jv2_favouring))
    assert frontier == (sf1_favouring, jv2_favouring)
    assert AllocationDominancePolicy().select(frontier) is None


def test_comparison_reports_observed_metrics_without_an_expected_winner(
    canonical_fixture, canonical_scenarios
):
    report = ScarcityComparisonService().compare(
        incident_id=INCIDENT_ID,
        fixture=canonical_fixture,
        scenarios=canonical_scenarios,
    )
    assert report.scenario_aware_evaluations
    candidate = report.scenario_aware_evaluations[0]
    assert candidate.expected_preserved_connections == pytest.approx(
        candidate.preserved_connection_total / candidate.world_count
    )
    observed_delta = (
        candidate.expected_preserved_connections
        - report.baseline.expected_preserved_connections
    )
    assert observed_delta == pytest.approx(
        (
            candidate.preserved_connection_total
            - report.baseline.preserved_connection_total
        )
        / candidate.world_count
    )


def test_canonical_comparison_is_reproducible_and_prints_metrics(
    canonical_fixture, canonical_scenarios
):
    service = ScarcityComparisonService()
    first = service.compare(
        incident_id=INCIDENT_ID,
        fixture=canonical_fixture,
        scenarios=canonical_scenarios,
    )
    second = service.compare(
        incident_id=INCIDENT_ID,
        fixture=canonical_fixture,
        scenarios=canonical_scenarios,
    )
    assert first.reproducibility_key == second.reproducibility_key
    assert first.baseline.allocation == second.baseline.allocation
    assert first.selected_allocation == second.selected_allocation
    candidate = first.scenario_aware_evaluations[0]
    assert first.baseline.runtime_ms > 0
    assert candidate.runtime_ms > 0
    print({
        "baseline_expected_preserved": first.baseline.expected_preserved_connections,
        "scenario_expected_preserved": candidate.expected_preserved_connections,
        "observed_development_delta": candidate.expected_preserved_connections - first.baseline.expected_preserved_connections,
        "scenario_expected_rollovers": candidate.expected_rollovers,
        "baseline_runtime_ms": first.baseline.runtime_ms,
        "scenario_runtime_ms": candidate.runtime_ms,
    })
```

Assert baseline and every scenario-aware evaluation have zero violations/unsafe allocations. Run comparison twice and compare semantic fields and reproducibility keys while excluding UUIDs, timestamps, and runtime. These tests validate calculations and reproducibility; they never assert that a scenario-aware result has a positive delta against the baseline.

- [ ] **Step 2: Run RED**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_allocation_dominance.py backend/tests/test_scarcity_evaluation.py -q`

Expected: missing policy/comparison failures.

- [ ] **Step 3: Implement unweighted Pareto dominance**

`left` dominates `right` only when both are hard-safe, left is no worse on total expected preserved, p10 preserved, every ordered service total, and slots used, and at least one comparison is strict. Never combine dimensions into a score. `select` returns one plan only if it strictly dominates every other evaluation; one sole safe alternative may be selected. Equal or cross-service trade-offs return `None`.

`ScarcityComparisonService` times both allocators with `perf_counter_ns`, evaluates every plan on the exact supplied `ScenarioSet`, Pareto-filters scenario-aware evaluations, applies dominance, and creates the report/key.

- [ ] **Step 4: Run GREEN and full verification**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_allocation_dominance.py backend/tests/test_scarcity_evaluation.py -q`

Expected: PASS, with no assertion about the sign of the observed development delta.

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/policies/allocation_dominance.py backend/app/evaluation/scarcity.py backend/tests/test_allocation_dominance.py backend/tests/test_scarcity_evaluation.py
git commit -m "feat: compare Pareto-efficient recovery allocations"
```

### Task 8: Frozen Holdout Benchmark Harness

**Files:**
- Create: `shared/fixtures/scarcity-evaluation-seeds.json`
- Modify: `shared/fixtures/README.md`
- Create: `backend/app/evaluation/benchmark.py`
- Create: `backend/tests/test_scarcity_benchmark.py`

**Interfaces:**
- Consumes: Canonical fixture, `SeededScenarioGenerator`, `ScarcityEvaluator`, and a completed development `ScarcityEvaluationReport` whose allocations were fixed using seed `20260822` before any holdout worlds are loaded.
- Produces: `load_evaluation_seed_manifest() -> EvaluationSeedManifest`, `HoldoutBenchmarkService.evaluate(fixture, development_report, manifest) -> ScarcityBenchmarkReport`, and a module CLI that writes the final observed report as JSON.

- [ ] **Step 1: Write failing holdout-protocol and benchmark tests**

```python
def test_frozen_evaluation_seed_manifest_is_separate_and_well_formed():
    manifest = load_evaluation_seed_manifest()
    assert manifest.manifest_id == "SYN-CANONICAL-24-HOLDOUT-V1"
    assert manifest.fixture_id == "SYN-CANONICAL-24-V1"
    assert manifest.worlds_per_seed == 50
    assert len(manifest.seeds) == 50
    assert len(set(manifest.seeds)) == 50
    assert set(manifest.seeds).isdisjoint({20260822, 20260823, 20260824})


def test_holdout_benchmark_is_reproducible_for_fixed_debug_seeds(
    canonical_fixture, canonical_development_report
):
    debug_manifest = EvaluationSeedManifest(
        manifest_id="SYN-DEBUG-HOLDOUT",
        fixture_id=canonical_fixture.fixture_id,
        worlds_per_seed=10,
        seeds=(314159, 271828, 161803),
    )
    service = HoldoutBenchmarkService()
    first = service.evaluate(
        canonical_fixture, canonical_development_report, debug_manifest
    )
    second = service.evaluate(
        canonical_fixture, canonical_development_report, debug_manifest
    )
    assert first.reproducibility_key == second.reproducibility_key
    assert first.baseline.model_copy(update={"runtime_ms": 0}) == second.baseline.model_copy(
        update={"runtime_ms": 0}
    )
    assert tuple(
        item.evaluation.model_copy(update={"runtime_ms": 0})
        for item in first.scenario_aware
    ) == tuple(
        item.evaluation.model_copy(update={"runtime_ms": 0})
        for item in second.scenario_aware
    )
    assert tuple(item.evaluation.allocation for item in first.scenario_aware) == tuple(
        item.allocation for item in canonical_development_report.pareto_evaluations
    )


def test_holdout_benchmark_reports_valid_calculations_without_sign_assertion(
    holdout_debug_report,
):
    total_worlds = 3 * 10
    assert holdout_debug_report.baseline.world_count == total_worlds
    assert (
        holdout_debug_report.baseline.preserved_connection_total
        + holdout_debug_report.baseline.rollover_total
        == 24 * total_worlds
    )
    assert holdout_debug_report.baseline.capacity_violations == 0
    assert holdout_debug_report.baseline.unsafe_allocations == 0
    for comparison in holdout_debug_report.scenario_aware:
        evaluation = comparison.evaluation
        assert evaluation.capacity_violations == 0
        assert evaluation.unsafe_allocations == 0
        assert comparison.observed_expected_preserved_delta_vs_baseline == pytest.approx(
            evaluation.expected_preserved_connections
            - holdout_debug_report.baseline.expected_preserved_connections
        )
```

Also assert each strategy is evaluated against the exact same per-seed `ScenarioSet` object, the service evaluates only allocations already present in the development report, the benchmark never calls the baseline allocator or CP-SAT, every allocated ID is a valid beneficiary, and observed expected values equal raw totals divided by total world count. Do not assert that any observed delta is positive.

- [ ] **Step 2: Run RED**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_benchmark.py -q`

Expected: collection fails because the manifest loader and holdout benchmark do not exist.

- [ ] **Step 3: Freeze the evaluation seed manifest without using it for tuning**

Create this exact manifest. The values are the first unsigned 32-bit words of `SHA-256("SYN-CANONICAL-24-V1:HOLDOUT-V1:{index}")` for indices 0–49; derivation is deterministic, external to the recovery policy, and unrelated to any observed outcome.

```json
{
  "manifest_id": "SYN-CANONICAL-24-HOLDOUT-V1",
  "fixture_id": "SYN-CANONICAL-24-V1",
  "worlds_per_seed": 50,
  "seeds": [
    3309398482, 3951398951, 1202677221, 163248611, 2925917627,
    662983011, 535220416, 3712295148, 3322287218, 4221776994,
    3583464971, 3829961219, 2909674732, 2930815356, 1290524950,
    221570462, 2889484640, 2523357292, 2651570794, 382770434,
    1949252393, 781115299, 457021634, 2351493851, 490788644,
    1182613177, 2570170220, 2710911550, 2335850418, 1110308685,
    3611131743, 2395838459, 3958056597, 3269696256, 3913539575,
    3217501867, 3664687104, 655908589, 1134109869, 710088785,
    696308748, 3159225489, 247409133, 3144496822, 1737969039,
    2202677500, 3504594914, 3281786063, 488632411, 4223942113
  ]
}
```

Document that these are synthetic holdout seeds, not PSA data. Once this manifest is committed, do not change fixture values, generator distributions, baseline ordering, optimizer objective/constraints, Pareto filtering, or dominance semantics in response to benchmark results. A genuine correctness defect invalidates the benchmark artifact and requires an explicit new manifest version and coordination decision; it is not permission to tune against these seeds.

- [ ] **Step 4: Implement aggregation over fixed allocations**

`HoldoutBenchmarkService` receives the development report rather than allocators. It evaluates the already-fixed baseline allocation and every already-fixed Pareto scenario-aware allocation across each holdout set, using one generated `ScenarioSet` instance per seed for all candidates. Aggregate raw preserved/rollover totals over 2,500 worlds, then derive expected values and observed deltas. Do not select a post-hoc winner. Report every predeclared candidate independently; a positive, neutral, or negative result is valid output.

The CLI must build the development report completely with seed `20260822`, freeze its allocations in memory, then load the holdout manifest and run evaluation. It writes JSON to an explicit `--output` path and prints baseline metrics, each scenario-aware candidate's observed delta, violations, unsafe allocations, and runtime. The benchmark reproducibility key excludes runtime and timestamps but includes the manifest ID and exact seed tuple.

- [ ] **Step 5: Run GREEN and full verification**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_benchmark.py -q`

Expected: PASS. Only development/debug seeds execute in the behavioral benchmark tests; the frozen manifest test validates identity, count, uniqueness, and separation without measuring allocator performance.

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add shared/fixtures/scarcity-evaluation-seeds.json shared/fixtures/README.md backend/app/evaluation/benchmark.py backend/tests/test_scarcity_benchmark.py
git commit -m "feat: add empirical scarcity benchmark harness"
```

### Task 9: Scarcity Report Persistence and Canonical Workflow

**Files:**
- Modify: `backend/app/storage/repositories.py`
- Create: `backend/app/orchestration/scarce_capacity.py`
- Modify: `backend/tests/test_audit.py`
- Create: `backend/tests/test_scarce_capacity_workflow.py`

**Interfaces:**
- Consumes: Existing state machine/repositories/audit, canonical fixture, scenario generator, and comparison service.
- Produces: `ScarcityEvaluationRepository.add/get_for_incident`, `DecisionRepository.add_many`, `CanonicalScarceCapacityWorkflow.run(seed=20260822, world_count=50) -> ScarcityRecoveryResult`, and `build_scarce_capacity_workflow(session)`.

- [ ] **Step 1: Write failing repository and workflow tests**

Expand the exact database table assertion to include `scarcity_evaluations`. Test report JSON round-trip and ordered batch decisions. Verify that the canonical development run persists a coherent outcome without predetermining whether dominance selects a plan:

```python
def test_canonical_workflow_persists_report_and_consistent_outcome(session):
    result = build_scarce_capacity_workflow(session).run(
        seed=20260822, world_count=50
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
        assert {str(decision.container_id) for decision in result.decisions} == set(
            result.report.selected_allocation.allocated_container_ids
        )
        assert all(decision.action is DecisionAction.EXPEDITE for decision in result.decisions)
        assert all(decision.status is DecisionStatus.APPROVED for decision in result.decisions)
```

Inject a hand-built dominant comparison to assert decision materialization and the successful state path `INCIDENT_RECEIVED → COLLECTING_STATE → CONSTRAINT_VALIDATION → RECOVERY_ANALYSIS → RESOLVED`. Inject a non-dominant comparison to assert that no decisions persist, the report/frontier persists, and the last state is `ESCALATED`. Add a spy assertion that baseline and solver receive the exact same `ScenarioSet` object. Do not alter canonical fixture data merely to make its development run resolve.

- [ ] **Step 2: Run RED**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_audit.py backend/tests/test_scarce_capacity_workflow.py -q`

Expected: failures for absent table/repository/workflow.

- [ ] **Step 3: Add one JSON report repository and batch decisions**

```python
class ScarcityEvaluationRecord(SQLModel, table=True):
    __tablename__ = "scarcity_evaluations"
    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True, unique=True)
    report: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at_utc: str
```

Store `report.model_dump(mode="json")` and restore with `ScarcityEvaluationReport.model_validate`. Raise `RecordNotFound` for an unknown incident. `DecisionRepository.add_many` inserts all records, commits once, and refreshes in input order; keep `add` backward-compatible by delegating a one-item tuple.

- [ ] **Step 4: Implement the additive canonical workflow**

Create/persist an `Incident`, load the fixture, generate one `ScenarioSet`, pass that same set through comparison, persist the report, and apply dominance. A selected plan creates one approved `EXPEDITE` decision per allocated container and resolves. No selection creates no decisions and escalates.

Define the workflow result locally without adding another public domain contract:

```python
@dataclass(frozen=True, slots=True)
class ScarcityRecoveryResult:
    incident: Incident
    report: ScarcityEvaluationReport
    decisions: tuple[Decision, ...]
```

Audit fixture loading, 24-container collection, capacity, scenario seed/assumptions, baseline evaluation, CP-SAT evaluation, Pareto/dominance, report persistence, decisions, and transitions. Actors are SYSTEM, SOLVER, and POLICY with explicit actor IDs; AGENT never appears.

- [ ] **Step 5: Run GREEN and full verification**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_audit.py backend/tests/test_scarce_capacity_workflow.py -q`

Expected: PASS.

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: PASS, including the unchanged one-container workflow.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/storage/repositories.py backend/app/orchestration/scarce_capacity.py backend/tests/test_audit.py backend/tests/test_scarce_capacity_workflow.py
git commit -m "feat: persist canonical scarcity recovery results"
```

### Task 10: Minimal Canonical Results API

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_scarcity_api.py`
- Modify: `backend/tests/test_authority_boundaries.py`

**Interfaces:**
- Consumes: `build_scarce_capacity_workflow`, `ScarcityEvaluationRepository`, existing `get_session`.
- Produces: `POST /synthetic/scenarios/canonical-scarcity` and `GET /incidents/{incident_id}/scarcity-evaluation`.

- [ ] **Step 1: Write failing API and authority tests**

```python
def test_trigger_canonical_scarcity_scenario(client):
    response = client.post("/synthetic/scenarios/canonical-scarcity")
    assert response.status_code == 201
    payload = response.json()
    assert isinstance(payload["decision_ids"], list)
    assert len(payload["reproducibility_key"]) == 64


def test_get_scarcity_evaluation_reads_persisted_report(client):
    triggered = client.post("/synthetic/scenarios/canonical-scarcity").json()
    response = client.get(
        f"/incidents/{triggered['incident_id']}/scarcity-evaluation"
    )
    assert response.status_code == 200
    report = response.json()
    assert report["fixture_id"] == "SYN-CANONICAL-24-V1"
    assert report["seed"] == 20260822
    assert report["scenario_count"] == 50
    assert report["baseline"]["capacity_violations"] == 0
    assert report["baseline"]["unsafe_allocations"] == 0
    selected = report["selected_allocation"]
    expected_decision_count = 0 if selected is None else len(
        selected["allocated_container_ids"]
    )
    assert len(triggered["decision_ids"]) == expected_decision_count
```

Add unknown-report 404, repeated-trigger semantic reproducibility, audit inspection with SYSTEM/SOLVER/POLICY and no AGENT, and OpenAPI route assertions. Expand authority discovery to canonical fixture/scenario/baseline/dominance/evaluation/optimization/workflow modules.

- [ ] **Step 2: Run RED**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_api.py backend/tests/test_authority_boundaries.py -q`

Expected: missing-route 404 failures.

- [ ] **Step 3: Add only trigger and inspection routes**

Add an immutable response with `incident_id`, `evaluation_id`, `decision_ids`, and `reproducibility_key`. POST constructs and runs the canonical workflow; it never duplicates orchestration. GET reads `ScarcityEvaluationRepository` and maps `RecordNotFound` to `404 {"detail": "Scarcity evaluation not found"}`.

Use fixed default seed `20260822` and 50 worlds. Do not accept distribution parameters through the API.

- [ ] **Step 4: Run GREEN and full verification**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_api.py backend/tests/test_authority_boundaries.py -q`

Expected: PASS.

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: PASS, including original API tests.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/main.py backend/tests/test_scarcity_api.py backend/tests/test_authority_boundaries.py
git commit -m "feat: expose canonical scarcity evaluation API"
```

### Task 11: Reproducible Phase 2 Verification and Handoff

**Files:**
- Create: `docs/evaluations/2026-08-22-scarcity-benchmark.json`
- Modify only if verification exposes a defect: the smallest affected production file and its focused regression test.
- Update at session end: the executing agent's assigned `docs/coordination/logs/*.md`; update `docs/coordination/WORKSTREAMS.md` only from the lead/integration workflow.

**Interfaces:**
- Consumes: Complete Phase 2 implementation.
- Produces: Test, reproducibility, safety, runtime, empirical 50-seed holdout benchmark, OpenAPI, dependency-lock, diff, and clean-status evidence.

- [ ] **Step 1: Run the focused Phase 2 suite**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_contracts.py backend/tests/test_canonical_incident.py backend/tests/test_scenario_worlds.py backend/tests/test_scarcity_evaluation.py backend/tests/test_baseline_allocator.py backend/tests/test_scarcity_optimizer.py backend/tests/test_allocation_dominance.py backend/tests/test_scarcity_benchmark.py backend/tests/test_scarce_capacity_workflow.py backend/tests/test_scarcity_api.py backend/tests/test_authority_boundaries.py -q
```

Expected: zero failures. The existing dependency-originated TestClient warning may remain.

- [ ] **Step 2: Run the full suite**

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: every Phase 1 and Phase 2 test PASS.

- [ ] **Step 3: Run the canonical reproducibility smoke with visible metrics**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_scarcity_evaluation.py::test_canonical_comparison_is_reproducible_and_prints_metrics -q -s
```

Expected: PASS and printed baseline expected preserved, scenario-aware expected preserved, observed development delta, expected rollovers, and both runtimes. The delta has no expected sign. Semantic keys/allocations match; runtime values are positive but are not asserted equal.

- [ ] **Step 4: Run the final frozen-seed empirical benchmark once**

Run only after the development fixture, distributions, baseline, optimizer, Pareto policy, and dominance policy are committed and frozen:

```powershell
New-Item -ItemType Directory -Force docs/evaluations
uv run --python 3.12 --extra dev python -m backend.app.evaluation.benchmark --output docs/evaluations/2026-08-22-scarcity-benchmark.json
```

Expected: exit 0; the JSON records manifest `SYN-CANONICAL-24-HOLDOUT-V1`, 50 unique evaluation seeds, 50 worlds per seed, 2,500 total worlds, the fixed greedy allocation, every fixed scenario-aware Pareto candidate, preserved connections, rollovers, capacity violations, unsafe allocations, observed delta per candidate, runtime, and a semantic reproducibility key. Capacity violations and unsafe allocations must be zero. Print and retain the observed deltas exactly as measured; positive, neutral, and negative are all acceptable outcomes.

Do not modify the generator, fixture, allocator, or policy after inspecting this artifact. If the command exposes a genuine correctness failure, do not tune on the holdout values: remove/mark the artifact invalid, add a regression using a development seed, fix under RED → GREEN, record the protocol break in `DECISIONS.md`, and require an approved `HOLDOUT-V2` manifest before rerunning a final benchmark.

- [ ] **Step 5: Run lifespan/OpenAPI smoke**

```powershell
uv run --python 3.12 --extra dev python -c "from fastapi.testclient import TestClient; from backend.app.main import app; client=TestClient(app); client.__enter__(); response=client.get('/openapi.json'); assert response.status_code == 200; paths=response.json()['paths']; assert '/synthetic/scenarios/canonical-scarcity' in paths; assert '/incidents/{incident_id}/scarcity-evaluation' in paths; client.__exit__(None, None, None); print(app.title)"
```

Expected: exit 0 and `PSA Transshipment Recovery`.

- [ ] **Step 6: Verify lock, authority, diff, and status**

Run: `uv lock --check`

Expected: lock is current.

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_authority_boundaries.py -q`

Expected: PASS.

Run: `git diff --check`

Expected: no whitespace errors.

Run: `git status --short`

Expected: only intended coordination evidence remains before its final commit.

- [ ] **Step 7: Commit only proven verification corrections**

If a defect appears before the final holdout run, first add its focused regression test with a development seed and observe RED, then correct it, rerun focused/full verification, and commit exact affected files with `fix: complete scarcity recovery verification`. If the final holdout run itself exposes the defect, follow the invalidation/versioning rule in Step 4. If no defect appears, do not create an empty correction commit.

- [ ] **Step 8: Record and commit benchmark evidence and handoff**

Append branch, base SHA, implementation SHA, exact files, RED/GREEN evidence, focused/full/smoke output, the exact observed benchmark metrics without interpreting the sign as a test result, contract additions, deliberate deferrals, blockers, and recommended next step to the authorized environment log. The lead workflow updates `WORKSTREAMS.md`. Commit the benchmark JSON and those exact coordination files with `docs: record Phase 2 scarcity benchmark`.

Stop. Do not begin carrier negotiation, DG semantic analysis, LLM orchestration, or frontend work.

## Architectural Compatibility Notes

- `CargoProfile` has DG but no reefer handling, and `Connection` has no PTA. Additive `ContainerRecoveryProfile` and `ServiceWindow` wrappers avoid frozen-contract mutation.
- `YardForecast` represents one deterministic window. `ExpediteCapacityPlan` and `ScenarioSet` add Phase 2 capacity/uncertainty without changing it.
- `Decision` is per-container while the solver returns a group set. `AllocationPlan` represents the group; only a dominant selected plan becomes one existing `Decision` value per allocated container, up to eight.
- Existing `TransshipmentRecoveryWorkflow` and `TriggerResponse` assume one box/decision. A separate workflow/response preserves them.
- `test_database_helpers_create_tables_and_yield_a_usable_session` currently asserts exactly three tables; report persistence deliberately changes that expectation to four.
- `DecisionRepository.add` commits one decision at a time. Additive `add_many` makes multi-decision materialization atomic without changing `Decision`.
- Existing incident states are sufficient. No new state is introduced.
- Existing `AuditEvent` JSON payload and SYSTEM/SOLVER/POLICY actors already cover Phase 2; no audit contract change is required.

## Self-Review Results

- Spec coverage: explicit tasks cover the 24-box fixture, SF1/JV2/EC3, PTA+35, dry/reefer/DG structure, 13/8 scarcity, hierarchical correlation, shared seeded worlds, p50 baseline, CP-SAT objective, hard constraints, Pareto/dominance, measurements, reproducibility, persistence, audit, and inspection.
- Scope: LLM, agent behavior, carrier/RTA loop, silence, DG semantics, frontend, auth, deployment, reset, and async infrastructure are excluded.
- Contract safety: Phase 2 contracts are additive; frozen models/enums remain untouched.
- Type consistency: `ScenarioSet` is the same type through baseline, solver, evaluator, workflow, and tests; produced interface names match later consumers.
- Solver boundary: scenario sampling and ready arithmetic are plain Python; CP-SAT sees integer coefficients and hard allocation facts only.
- Policy transparency: there is no cargo/service weight or hidden score; raw outcome dimensions remain visible.
- Reproducibility: semantic outputs are deterministic for fixture/seed/assumptions; runtime, IDs, and timestamps remain measured but excluded from equality/key. Development/debug seeds are separate from the frozen 50-seed holdout manifest.
- Empirical comparison: allocations are fixed before holdout worlds are loaded, every fixed allocation sees identical holdout worlds, and the final report preserves the observed positive, neutral, or negative delta without a pass/fail assertion on its sign.
- Solver-test integrity: the hand-checkable fixture has a genuine unique optimum; canonical and tie tests assert objective calculations and hard-constraint invariants without arbitrary weights or a synthetic tie-break.
- Test intent: focused tests cover reproducibility, capacity, safety, valid allocations, objective arithmetic, and hierarchical correlated uncertainty. No test requires the scenario-aware allocator to beat the greedy baseline.
- Placeholder scan: every task names concrete files, interfaces, tests, commands, RED/GREEN expectations, and commit boundaries.
