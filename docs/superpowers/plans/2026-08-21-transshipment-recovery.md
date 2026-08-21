# One-Container Transshipment Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the Python backend foundation and move one synthetic transshipment container from an inbound schedule-delay event to a persisted deterministic `EXPEDITE` decision with an immutable audit trail and a minimal inspection API.

**Architecture:** A synchronous FastAPI application coordinates deterministic synthetic schedule, manifest, and yard adapters through an explicit incident state machine. Frozen Pydantic v2 models define the domain boundary, while small SQLModel repositories persist incidents, decisions, and append-only audit events in SQLite; the synthetic adapters are intentionally not represented as production integrations.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLModel, SQLite, pytest, HTTPX/TestClient, `pyproject.toml`.

**Spec:** `docs/specs/psa-code-sprint-final-plan.md` — reserved for the project owner to copy in the approved “PSA Code Sprint 2.0: Final Plan.” Product direction and the four hard requirements in that document are frozen.

## Global Constraints

- Target Python 3.12 and use only Python 3.12-compatible language features. The workstation currently has Python 3.11 and 3.14; create a 3.12 environment with the already-installed `uv` tool before verification.
- Use FastAPI, Pydantic v2, SQLModel, SQLite, pytest, and `pyproject.toml`; do not use LangGraph.
- Persist timestamps as timezone-aware UTC values. SQLite records store canonical ISO-8601 UTC strings, and repositories reconstruct Pydantic `AwareDatetime` values.
- Implement exactly one synthetic container, one onward connection, and one synthetic yard forecast.
- Do not implement React, the 24-container scenario, OR-Tools, stochastic sampling, RTA negotiation behavior, a carrier simulator, DG semantic analysis, LLM integration, or deployment.
- The services in this slice are deterministic synthetic adapters, not production integrations.
- Attribute deterministic workflow and state-machine activity to `SYSTEM`; reserve `AGENT` for later actions actually performed by an LLM agent.
- External authority remains external: no operation or route may be named `hold_feeder`, `change_carrier_schedule`, `override_dg_rule`, or `set_yard_capacity`; future externally owned changes are represented only as requests.
- The future carrier timing action is `REQUEST_RTA`. `CarrierResponse` represents only `ACCEPT` or `COUNTER`; silence is the absence of a response after a future timeout/deadline.
- Frozen contracts, architecture, and scope may change only through a proposed append-only entry in `docs/coordination/DECISIONS.md`; no agent may change them silently.
- Use TDD for every behavior: add a focused failing test, observe the expected failure, add the minimum implementation, and rerun the focused test before proceeding.
- Keep repositories concrete and small; do not introduce generic repository interfaces, a unit-of-work layer, an event bus, or asynchronous workers.

## File Map

- `.gitignore`: Ignore the local virtual environment, Python caches, pytest caches, coverage output, and the runtime SQLite database.
- `pyproject.toml`: Declare Python 3.12 and the runtime/test dependencies plus pytest configuration.
- `backend/app/domain/enums.py`: Hold only domain enums, including incident state, decision action/status, and audit actor.
- `backend/app/domain/models.py`: Hold frozen Pydantic contracts and UTC helpers; no persistence or service behavior.
- `backend/app/storage/database.py`: Build the SQLite engine, create tables, and yield SQLModel sessions.
- `backend/app/storage/repositories.py`: Hold the three concrete SQLModel tables and small incident, decision, and audit repositories.
- `backend/app/audit/service.py`: Construct and append immutable `AuditEvent` values.
- `backend/app/orchestration/state_machine.py`: Define allowed transitions and coordinate the one-container recovery workflow.
- `backend/app/services/schedule.py`: Create the synthetic delay event/incident and evaluate normal versus expedited connection feasibility.
- `backend/app/services/manifest.py`: Return the one clearly synthetic affected container.
- `backend/app/services/yard.py`: Return the one clearly synthetic capacity forecast.
- `backend/app/policies/dominance.py`: Apply the deterministic rule that selects `EXPEDITE` only when normal transfer is infeasible, expedited transfer is feasible, and yard capacity is sufficient.
- `backend/app/main.py`: Build the FastAPI app and expose only the trigger and three inspection endpoints.
- `backend/tests/conftest.py`: Provide isolated in-memory SQLite and TestClient fixtures.
- `backend/tests/test_domain_contracts.py`: Freeze and validate the required contracts and UTC timestamps.
- `backend/tests/test_state_machine.py`: Verify legal transitions and rejection of illegal transitions.
- `backend/tests/test_audit.py`: Verify append-only events and actor identity.
- `backend/tests/test_vertical_slice.py`: Verify the complete one-container backend flow, including service retrievals and persistence.
- `backend/tests/test_api.py`: Verify trigger/retrieval endpoints and 404 behavior.
- `backend/tests/test_authority_boundaries.py`: Verify that neither callable domain operations nor API routes expose prohibited direct-control capabilities.
- `shared/fixtures/README.md`: Document the synthetic fixture identities and explicitly state they are non-production data.
- `docs/specs/psa-code-sprint-final-plan.md`: Canonical location for the owner-supplied approved source plan.
- `docs/coordination/WORKSTREAMS.md`: Lead/integration-owned work allocation and ownership ledger.
- `docs/coordination/DECISIONS.md`: Append-only decisions affecting frozen interfaces, architecture, or scope.
- `docs/coordination/logs/*.md`: Per-environment work logs; each agent edits only its own file.

---

### Task 1: Project Foundation and Frozen Domain Contracts

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/domain/__init__.py`
- Create: `backend/app/domain/enums.py`
- Create: `backend/app/domain/models.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_domain_contracts.py`
- Create: `shared/fixtures/README.md`
- Create: `docs/specs/psa-code-sprint-final-plan.md`
- Create: `docs/coordination/WORKSTREAMS.md`
- Create: `docs/coordination/DECISIONS.md`
- Create: `docs/coordination/logs/win-codex.md`
- Create: `docs/coordination/logs/win-cursor.md`
- Create: `docs/coordination/logs/mac-codex.md`
- Create: `docs/coordination/logs/mac-cursor.md`

**Interfaces:**
- Consumes: No application code.
- Produces: `utc_now() -> datetime`; `ScheduleEvent`, `Incident`, `Container`, `CargoProfile`, `YardForecast`, `Connection`, `RecoveryAlternative`, `ExpediteAllocation`, `RTARequest`, `CarrierResponse`, `Decision`, `Approval`, and `AuditEvent`; `IncidentState`, `DecisionAction`, `DecisionStatus`, `AuditActor`, and `CarrierResponseType`.

- [x] **Step 1: Add project metadata and the failing domain contract tests**

Create `pyproject.toml` with a PEP 621 project requiring Python 3.12, runtime dependencies `fastapi`, `pydantic>=2`, `sqlmodel`, and `uvicorn`, and a `dev` extra containing `pytest` and `httpx`. Configure pytest with `testpaths = ["backend/tests"]` and `pythonpath = ["."]`.

Create `backend/tests/test_domain_contracts.py` with direct constructions of every required model. Use synthetic IDs and UTC datetimes, then assert:

```python
def test_required_contracts_are_constructible(synthetic_contracts):
    assert set(synthetic_contracts) == {
        "schedule_event", "incident", "container", "cargo_profile",
        "yard_forecast", "connection", "recovery_alternative",
        "expedite_allocation", "rta_request", "carrier_response",
        "decision", "approval", "audit_event",
    }


def test_decision_identity_is_immutable(decision):
    with pytest.raises(ValidationError, match="Instance is frozen"):
        decision.id = uuid4()


@pytest.mark.parametrize("field", ["created_at", "timestamp"])
def test_contract_timestamps_reject_naive_datetimes(field):
    model = Decision if field == "created_at" else AuditEvent
    data = decision_data() if model is Decision else audit_data()
    data[field] = datetime(2026, 8, 21, 8, 0)
    with pytest.raises(ValidationError):
        model(**data)


def test_audit_actor_contract_contains_all_authority_sources():
    assert {actor.value for actor in AuditActor} >= {
        "AGENT", "SOLVER", "POLICY", "OPERATOR", "CARRIER", "SYSTEM"
    }


def test_carrier_response_uses_accept_or_counter_not_silence(rta_request):
    accepted = CarrierResponse(
        request_id=rta_request.id,
        carrier_id="SYN-CARRIER-01",
        response=CarrierResponseType.ACCEPT,
        message="Synthetic acceptance",
    )
    countered = CarrierResponse(
        request_id=rta_request.id,
        carrier_id="SYN-CARRIER-01",
        response=CarrierResponseType.COUNTER,
        counter_eta_pta=datetime(2026, 8, 21, 8, 15, tzinfo=UTC),
        message="Synthetic counter",
    )
    assert accepted.response is CarrierResponseType.ACCEPT
    assert countered.response is CarrierResponseType.COUNTER
    with pytest.raises(ValidationError):
        CarrierResponse(
            request_id=rta_request.id,
            carrier_id="SYN-CARRIER-01",
            response="SILENCE",
            message="No response is not a carrier response",
        )
```

- [x] **Step 2: Run the domain tests and confirm the expected import failure**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_domain_contracts.py -q`

Expected: FAIL during collection because `backend.app.domain.enums` and `backend.app.domain.models` do not exist.

- [x] **Step 3: Implement only the enums and frozen contracts needed by the tests**

Define string enums with explicit values:

```python
class IncidentState(StrEnum):
    INCIDENT_RECEIVED = "INCIDENT_RECEIVED"
    COLLECTING_STATE = "COLLECTING_STATE"
    CONSTRAINT_VALIDATION = "CONSTRAINT_VALIDATION"
    RECOVERY_ANALYSIS = "RECOVERY_ANALYSIS"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class DecisionAction(StrEnum):
    EXPEDITE = "EXPEDITE"
    REQUEST_RTA = "REQUEST_RTA"
    ROLL = "ROLL"
    ESCALATE = "ESCALATE"


class CarrierResponseType(StrEnum):
    ACCEPT = "ACCEPT"
    COUNTER = "COUNTER"


class AuditActor(StrEnum):
    AGENT = "AGENT"
    SOLVER = "SOLVER"
    POLICY = "POLICY"
    OPERATOR = "OPERATOR"
    CARRIER = "CARRIER"
    SYSTEM = "SYSTEM"
```

Use a common base model with `ConfigDict(frozen=True, extra="forbid")`. Use `AwareDatetime` for every timestamp, UUID values for identities, `Field(default_factory=uuid4)` for generated identity, and `Field(default_factory=utc_now)` for created timestamps. The required decision and audit shapes are:

```python
class Decision(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    container_id: str | None = None
    action: DecisionAction
    status: DecisionStatus
    rationale: str
    supersedes: UUID | None = None
    supersession_reason: str | None = None
    created_at: AwareDatetime = Field(default_factory=utc_now)


class AuditEvent(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    actor: AuditActor
    actor_id: str | None = None
    incident_id: UUID
    event_type: str
    payload: dict[str, JsonValue]
    timestamp: AwareDatetime = Field(default_factory=utc_now)
```

Define the other named contracts with minimal, typed fields needed for the slice or their future boundary:

- `ScheduleEvent`: `id`, vessel call/name, terminal, scheduled/estimated arrival, delay minutes, occurred-at.
- `Incident`: `id`, source event ID, current `IncidentState`, created-at.
- `CargoProfile`: commodity, gross kilograms, DG flag, optional UN number.
- `Connection`: ID, outbound vessel/voyage, port, cutoff/departure, normal and expedited transfer minutes.
- `Container`: container ID, origin/destination, cargo, inbound vessel call ID, onward connection.
- `YardForecast`: ID, terminal, window start/end, available expedite slots, generated-at.
- `RecoveryAlternative`: ID, incident/container IDs, action, feasible flag, projected delay, rationale.
- `ExpediteAllocation`: ID, incident/container/forecast IDs, requested slots, status, created-at.
- `RTARequest`: ID, incident/connection IDs, requested ETA/PTA, status, created-at.
- `CarrierResponse`: ID, request ID, carrier ID, explicit `CarrierResponseType`, optional counter ETA/PTA, message, received-at. It never represents silence.
- `Approval`: ID, decision ID, operator ID, approval status, optional reason, created-at.

Do not add behavior to the future-facing contracts.

- [x] **Step 4: Run the domain tests and confirm they pass**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_domain_contracts.py -q`

Expected: all domain contract tests PASS.

- [x] **Step 5: Commit the foundation**

```powershell
git add .gitignore pyproject.toml docs/superpowers/plans/2026-08-21-transshipment-recovery.md docs/specs docs/coordination backend/app/__init__.py backend/app/domain backend/tests/__init__.py backend/tests/test_domain_contracts.py shared/fixtures/README.md
git commit -m "chore: establish recovery domain foundation"
```

---

### Task 2: Explicit Incident State Machine and SQLite Persistence

**Files:**
- Create: `backend/app/orchestration/__init__.py`
- Create: `backend/app/orchestration/state_machine.py`
- Create: `backend/app/storage/__init__.py`
- Create: `backend/app/storage/database.py`
- Create: `backend/app/storage/repositories.py`
- Create: `backend/app/audit/__init__.py`
- Create: `backend/app/audit/service.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_state_machine.py`
- Create: `backend/tests/test_audit.py`

**Interfaces:**
- Consumes: `Incident`, `Decision`, `AuditEvent`, `IncidentState`, and `AuditActor` from Task 1.
- Produces: `IncidentStateMachine.transition(incident, target) -> Incident`; `IncidentRepository.create/get/update_state`; `DecisionRepository.add/list_for_incident`; `AuditRepository.append/list_for_incident`; `AuditService.record(...) -> AuditEvent`; `get_session() -> Iterator[Session]`.

- [ ] **Step 1: Add failing state transition tests**

Create an incident in `INCIDENT_RECEIVED`, transition it through the slice, and assert the exact sequence:

```python
EXPECTED_STATES = [
    IncidentState.INCIDENT_RECEIVED,
    IncidentState.COLLECTING_STATE,
    IncidentState.CONSTRAINT_VALIDATION,
    IncidentState.RECOVERY_ANALYSIS,
    IncidentState.RESOLVED,
]


def test_state_machine_accepts_the_vertical_slice_path(incident):
    machine = IncidentStateMachine()
    observed = [incident.state]
    for target in EXPECTED_STATES[1:]:
        incident = machine.transition(incident, target)
        observed.append(incident.state)
    assert observed == EXPECTED_STATES


def test_state_machine_rejects_skipping_recovery_analysis(incident):
    with pytest.raises(InvalidIncidentTransition):
        IncidentStateMachine().transition(incident, IncidentState.RESOLVED)
```

- [ ] **Step 2: Run the state-machine tests and confirm the import failure**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_state_machine.py -q`

Expected: FAIL because the orchestration module does not exist.

- [ ] **Step 3: Implement the explicit allowed-transition map**

Use exactly this behavior:

```python
ALLOWED_TRANSITIONS = {
    IncidentState.INCIDENT_RECEIVED: {IncidentState.COLLECTING_STATE},
    IncidentState.COLLECTING_STATE: {
        IncidentState.CONSTRAINT_VALIDATION,
        IncidentState.ESCALATED,
    },
    IncidentState.CONSTRAINT_VALIDATION: {
        IncidentState.RECOVERY_ANALYSIS,
        IncidentState.ESCALATED,
    },
    IncidentState.RECOVERY_ANALYSIS: {
        IncidentState.RESOLVED,
        IncidentState.ESCALATED,
    },
    IncidentState.RESOLVED: set(),
    IncidentState.ESCALATED: set(),
}


class IncidentStateMachine:
    def transition(self, incident: Incident, target: IncidentState) -> Incident:
        if target not in ALLOWED_TRANSITIONS[incident.state]:
            raise InvalidIncidentTransition(incident.state, target)
        return incident.model_copy(update={"state": target})
```

- [ ] **Step 4: Run the state-machine tests and confirm they pass**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_state_machine.py -q`

Expected: all state-machine tests PASS.

- [ ] **Step 5: Add failing persistence and append-only audit tests**

Configure `backend/tests/conftest.py` to create a new `sqlite://` engine with `check_same_thread=False` and `StaticPool`, call `SQLModel.metadata.create_all(engine)`, and yield a fresh `Session` per test.

In `test_audit.py`, append two events, then assert insertion order, actor values, stable first-event content, and absence of mutation methods:

```python
def test_audit_events_are_append_only_and_ordered(session, incident):
    repository = AuditRepository(session)
    service = AuditService(repository)
    first = service.record(
        actor=AuditActor.SYSTEM,
        incident_id=incident.id,
        event_type="incident.created",
        payload={"state": "INCIDENT_RECEIVED"},
    )
    second = service.record(
        actor=AuditActor.POLICY,
        incident_id=incident.id,
        event_type="decision.selected",
        payload={"action": "EXPEDITE"},
    )

    observed = repository.list_for_incident(incident.id)
    assert [event.id for event in observed] == [first.id, second.id]
    assert observed[0] == first
    assert [event.actor for event in observed] == [
        AuditActor.SYSTEM,
        AuditActor.POLICY,
    ]
    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")
```

Add repository tests that round-trip an incident, update only its current state through `update_state`, persist a decision, and list decisions by incident.

- [ ] **Step 6: Run the persistence tests and confirm the expected import failure**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_audit.py -q`

Expected: FAIL because storage and audit modules do not exist.

- [ ] **Step 7: Implement the concrete SQLModel tables and repositories**

Create only three table classes: `IncidentRecord`, `DecisionRecord`, and `AuditEventRecord`. Store UUIDs as strings and UTC datetimes through helpers:

```python
def to_utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def from_utc_text(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)
```

`AuditEventRecord` has an auto-increment integer `sequence` primary key plus a unique event UUID string. Store evidence with SQLAlchemy's JSON column. `AuditRepository` exposes only `append` and `list_for_incident`; listing orders by `sequence`. Do not expose update/delete operations for audit records.

`IncidentRepository` exposes `create`, `get`, and `update_state`. `DecisionRepository` exposes `add` and `list_for_incident`. Raise a small `RecordNotFound` exception when an incident does not exist.

`database.py` provides a file-backed default engine with `check_same_thread=False`, `create_db_and_tables()`, and a yielded `get_session()` dependency. It does not create tables at import time.

`AuditService.record` constructs a frozen `AuditEvent` and immediately appends it through `AuditRepository`.

- [ ] **Step 8: Run state, repository, and audit tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_state_machine.py backend/tests/test_audit.py -q`

Expected: all selected tests PASS.

- [ ] **Step 9: Commit state and persistence**

```powershell
git add backend/app/orchestration backend/app/storage backend/app/audit backend/tests/conftest.py backend/tests/test_state_machine.py backend/tests/test_audit.py
git commit -m "feat: persist incident state and audit history"
```

---

### Task 3: Synthetic Services and Deterministic One-Container Recovery

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/schedule.py`
- Create: `backend/app/services/manifest.py`
- Create: `backend/app/services/yard.py`
- Create: `backend/app/policies/__init__.py`
- Create: `backend/app/policies/dominance.py`
- Modify: `backend/app/orchestration/state_machine.py`
- Create: `backend/tests/test_vertical_slice.py`

**Interfaces:**
- Consumes: all Task 1 contracts, Task 2 repositories/audit service, and `Session`.
- Produces: `SyntheticScheduleService.delay_event()`, `create_incident(event)`, `normal_connection_feasible(event, connection)`, and `expedited_connection_feasible(event, connection)`; `SyntheticManifestService.affected_container(event)`; `SyntheticYardService.forecast(container)`; `DominancePolicy.decide(...) -> tuple[RecoveryAlternative, Decision] | None`; `TransshipmentRecoveryWorkflow.run(event) -> RecoveryResult`.

- [ ] **Step 1: Add the failing complete vertical-slice acceptance test**

The test must execute production services against the isolated SQLModel session and assert all acceptance evidence:

```python
def test_one_container_completes_the_recovery_vertical_slice(session):
    workflow = build_workflow(session)
    event = workflow.schedule.delay_event()

    result = workflow.run(event)

    assert result.incident.source_event_id == event.id
    assert result.incident.state is IncidentState.RESOLVED
    assert result.container.id == "PSAU1234567"
    assert result.yard_forecast.available_expedite_slots == 4
    assert result.original_connection_feasible is False
    assert result.expedited_connection_feasible is True
    assert result.decision.action is DecisionAction.EXPEDITE
    assert result.decision.status is DecisionStatus.APPROVED

    persisted = DecisionRepository(session).list_for_incident(result.incident.id)
    assert persisted == [result.decision]

    audit = AuditRepository(session).list_for_incident(result.incident.id)
    transitions = [
        event.payload["to"]
        for event in audit
        if event.event_type == "incident.state_transitioned"
    ]
    assert transitions == [
        "COLLECTING_STATE",
        "CONSTRAINT_VALIDATION",
        "RECOVERY_ANALYSIS",
        "RESOLVED",
    ]
    assert {event.actor for event in audit} >= {
        AuditActor.SYSTEM,
        AuditActor.POLICY,
    }
    assert AuditActor.AGENT not in {event.actor for event in audit}
    assert any(event.event_type == "manifest.container_loaded" for event in audit)
    assert any(event.event_type == "yard.forecast_retrieved" for event in audit)
```

Add two focused deterministic-policy tests: the synthetic facts select `EXPEDITE`; insufficient yard capacity returns no decision and does not fabricate another recovery behavior.

- [ ] **Step 2: Run the vertical-slice tests and confirm the expected import failure**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_vertical_slice.py -q`

Expected: FAIL because the services and policy modules do not exist.

- [ ] **Step 3: Implement the deterministic synthetic adapters**

Use clearly synthetic values, documented in `shared/fixtures/README.md`:

- Schedule event `SYN-EVT-20260821-001`, vessel call `SYN-VC-SOUTHERN-STAR-01`, vessel `M/V Synthetic Southern Star`, terminal `SYN-TUAS-TERMINAL`, scheduled arrival `2026-08-21T05:00:00Z`, estimated arrival `2026-08-21T06:30:00Z`, delay 90 minutes.
- Container `PSAU1234567`, Rotterdam to Jakarta, non-DG machinery, 18,500 kg.
- Connection `SYN-CONN-STRAITS-01`, `M/V Synthetic Straits Pioneer`, cutoff `2026-08-21T07:30:00Z`, departure `2026-08-21T09:00:00Z`, normal transfer 120 minutes, expedited transfer 45 minutes.
- Yard forecast `SYN-YARD-20260821-AM`, terminal `SYN-TUAS-TERMINAL`, window `06:00Z`–`10:00Z`, four available expedite slots.

Normal feasibility is `estimated_arrival + normal_transfer_minutes <= cutoff`; expedited feasibility uses the expedited transfer minutes. No service makes network calls or accepts a schedule mutation.

- [ ] **Step 4: Implement the minimal dominance policy**

The policy is pure and deterministic:

```python
def decide(
    self,
    *,
    incident: Incident,
    container: Container,
    yard_forecast: YardForecast,
    original_connection_feasible: bool,
    expedited_connection_feasible: bool,
) -> tuple[RecoveryAlternative, Decision] | None:
    expedite_is_dominant = (
        not original_connection_feasible
        and expedited_connection_feasible
        and yard_forecast.available_expedite_slots >= 1
    )
    if not expedite_is_dominant:
        return None
    rationale = (
        "Normal transfer misses the synthetic cutoff; expedited transfer "
        "meets it and the synthetic yard forecast has capacity."
    )
    alternative = RecoveryAlternative(
        incident_id=incident.id,
        container_id=container.id,
        action=DecisionAction.EXPEDITE,
        feasible=True,
        projected_delay_minutes=0,
        rationale=rationale,
    )
    decision = Decision(
        incident_id=incident.id,
        container_id=container.id,
        action=DecisionAction.EXPEDITE,
        status=DecisionStatus.APPROVED,
        rationale=rationale,
    )
    return alternative, decision
```

- [ ] **Step 5: Implement the workflow one transition at a time**

`TransshipmentRecoveryWorkflow.run` must:

1. Create and persist the incident at `INCIDENT_RECEIVED`; record `schedule.delay_ingested` and `incident.created` as `SYSTEM`.
2. Transition/persist to `COLLECTING_STATE`; record the deterministic transition as `SYSTEM`.
3. Load the container; record `manifest.container_loaded` as `SYSTEM` with the container ID.
4. Load the yard forecast; record `yard.forecast_retrieved` as `SYSTEM` with the forecast ID and available slots.
5. Transition/persist to `CONSTRAINT_VALIDATION`; record the deterministic transition as `SYSTEM`.
6. Calculate both normal and expedited feasibility; record `connection.feasibility_evaluated` as `POLICY` with both booleans.
7. Transition/persist to `RECOVERY_ANALYSIS`; record the deterministic transition as `SYSTEM`.
8. Invoke `DominancePolicy`. If it returns no decision, transition to `ESCALATED`; otherwise persist the decision and record `decision.created` as `POLICY`.
9. Transition/persist the successful incident to `RESOLVED`; record the deterministic transition as `SYSTEM`.
10. Return a frozen `RecoveryResult` containing the incident, container, yard forecast, alternative, decision, and both feasibility booleans.

Use a helper for every transition so persistence and the corresponding audit event cannot drift apart. Do not introduce retries, events queues, optimizers, or alternative recovery execution.

- [ ] **Step 6: Run the vertical-slice tests and confirm they pass**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_vertical_slice.py -q`

Expected: all vertical-slice and dominance-policy tests PASS.

- [ ] **Step 7: Commit the complete backend workflow**

```powershell
git add backend/app/services backend/app/policies backend/app/orchestration/state_machine.py backend/tests/test_vertical_slice.py shared/fixtures/README.md
git commit -m "feat: recover one synthetic transshipment container"
```

---

### Task 4: Minimal FastAPI Trigger and Inspection Surface

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/tests/test_api.py`
- Create: `backend/tests/test_authority_boundaries.py`

**Interfaces:**
- Consumes: `get_session`, repositories, synthetic services, policy, and workflow.
- Produces: `create_app() -> FastAPI`, module-level `app`, `POST /synthetic/scenarios/schedule-delay`, `GET /incidents/{incident_id}`, `GET /incidents/{incident_id}/decisions`, and `GET /incidents/{incident_id}/audit-events`.

- [ ] **Step 1: Add failing API tests**

Use the SQLModel-documented `StaticPool` pattern and FastAPI dependency overrides in `conftest.py`. Run `TestClient` as a context manager so lifespan is exercised.

```python
def test_trigger_and_inspect_synthetic_scenario(client):
    triggered = client.post("/synthetic/scenarios/schedule-delay")
    assert triggered.status_code == 201
    ids = triggered.json()

    incident = client.get(f"/incidents/{ids['incident_id']}")
    assert incident.status_code == 200
    assert incident.json()["state"] == "RESOLVED"

    decisions = client.get(f"/incidents/{ids['incident_id']}/decisions")
    assert decisions.status_code == 200
    assert [item["action"] for item in decisions.json()] == ["EXPEDITE"]

    audit = client.get(f"/incidents/{ids['incident_id']}/audit-events")
    assert audit.status_code == 200
    assert audit.json()[0]["event_type"] == "schedule.delay_ingested"
    assert audit.json()[-1]["payload"]["to"] == "RESOLVED"


def test_unknown_incident_returns_404(client):
    response = client.get(f"/incidents/{uuid4()}")
    assert response.status_code == 404
```

- [ ] **Step 2: Add the failing authority-boundary test**

Inspect the actual FastAPI routes plus public callables in service/policy/orchestration modules:

```python
PROHIBITED_OPERATIONS = {
    "hold_feeder",
    "change_carrier_schedule",
    "override_dg_rule",
    "set_yard_capacity",
}


def test_api_and_domain_do_not_expose_external_control_operations():
    route_names = {route.name for route in app.routes}
    route_paths = {route.path for route in app.routes}
    public_callables = discover_public_callable_names(
        schedule, manifest, yard, dominance, state_machine
    )
    exposed = route_names | route_paths | public_callables
    assert PROHIBITED_OPERATIONS.isdisjoint(exposed)
```

- [ ] **Step 3: Run API tests and confirm the missing-app failure**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_api.py backend/tests/test_authority_boundaries.py -q`

Expected: FAIL because `backend.app.main` does not exist.

- [ ] **Step 4: Implement only the four required endpoints**

Create tables in an `asynccontextmanager` lifespan. Construct repositories and the workflow per request from the injected session. Return status 201 from the trigger:

```python
@app.post(
    "/synthetic/scenarios/schedule-delay",
    status_code=status.HTTP_201_CREATED,
)
def trigger_synthetic_delay(session: Session = Depends(get_session)) -> TriggerResponse:
    workflow = build_workflow(session)
    result = workflow.run(workflow.schedule.delay_event())
    return TriggerResponse(
        incident_id=result.incident.id,
        decision_id=result.decision.id,
    )
```

The three GET routes return the frozen domain models from the repositories. Convert `RecordNotFound` into HTTP 404. Do not add reset because test isolation uses a fresh in-memory database and the requirement makes reset optional.

- [ ] **Step 5: Run API and authority tests and confirm they pass**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_api.py backend/tests/test_authority_boundaries.py -q`

Expected: all API and authority-boundary tests PASS.

- [ ] **Step 6: Commit the API surface**

```powershell
git add backend/app/main.py backend/tests/conftest.py backend/tests/test_api.py backend/tests/test_authority_boundaries.py
git commit -m "feat: expose synthetic recovery inspection API"
```

---

### Task 5: Full Verification and Focused Handoff

**Files:**
- Modify only if verification exposes a defect: the smallest affected file and its corresponding test.

**Interfaces:**
- Consumes: the complete repository.
- Produces: passing formatting/lint checks if configured, passing full pytest output, a FastAPI lifespan smoke result, and the final commit SHA.

- [ ] **Step 1: Run the complete pytest suite**

Run: `uv run --python 3.12 --extra dev pytest -q`

Expected: all tests PASS with zero failures or errors.

- [ ] **Step 2: Run the FastAPI import/lifespan smoke test**

Run:

```powershell
uv run --python 3.12 --extra dev python -c "from fastapi.testclient import TestClient; from backend.app.main import app; client = TestClient(app); client.__enter__(); response = client.get('/openapi.json'); assert response.status_code == 200; client.__exit__(None, None, None); print(app.title)"
```

Expected: exit code 0 and output `PSA Transshipment Recovery`.

- [ ] **Step 3: Confirm the repository contains no prohibited production operations**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_authority_boundaries.py -q`

Expected: PASS. The literal names appear only in the negative test and plan, never as application callables or routes.

- [ ] **Step 4: Inspect the final diff and working tree**

Run: `git status --short` and `git diff --check`.

Expected: no whitespace errors; only intended project files are present. If `uv.lock` is created by `uv run`, include it because it makes dependency resolution reproducible.

- [ ] **Step 5: Commit any verification-only corrections**

If Step 1–4 required a code correction, first add a regression test, observe it fail, implement the smallest fix, rerun the focused and full suites, then commit:

```powershell
git add <affected-test> <affected-code>
git commit -m "fix: complete synthetic recovery verification"
```

If no correction was needed, do not create an empty commit.

- [ ] **Step 6: Capture the handoff evidence**

Run: `git rev-parse HEAD` and `git status --short`.

Return the exact created-file list, exact test names, command/output summary, four API endpoints, frozen domain contract list, intentional deferrals, final commit SHA, and whether the working tree is clean. Stop; do not begin the next feature.

## Self-Review Results

- Spec coverage: every named contract, required state, vertical-slice step, acceptance test category, persistence constraint, authority boundary, endpoint, verification command, and handoff item maps to a task above.
- Placeholder scan: no implementation step uses `TBD`, `TODO`, “implement later,” or an unspecified error-handling instruction.
- Type consistency: workflow, repository, policy, service, and endpoint names are consistent across the task interfaces and code examples; UUID identity and timezone-aware UTC serialization use the same types throughout.
- Deliberate exclusions: no frontend, optimizer, sampling, negotiation execution, carrier simulation, DG semantic engine, LLM, deployment, generic repository abstraction, event bus, or reset endpoint is introduced.
