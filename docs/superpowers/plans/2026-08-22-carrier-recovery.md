# Phase 3 Carrier Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic, connection-scoped carrier recovery with explicit operator authorization, one-round carrier negotiation, timeout handling, and immutable per-container reconsideration.

**Architecture:** Keep the terminal Phase 2 incident and its eight-slot allocation unchanged. Add a `CarrierRecoveryCase` sub-workflow keyed by `(incident_id, connection_id)`, backed by additive contracts, tables, repositories, and a dedicated orchestration service. Carrier outcomes become immutable timing evidence; a deterministic p90 recomputer uses the original fixture, the persisted Phase 2 seed/scenario count, regenerated worlds, fixed allocation, and the case snapshot without rerunning scarcity allocation.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLModel/SQLite, pytest, HTTPX/TestClient, and existing OR-Tools only through the frozen Phase 2 code path.

**Spec:** `docs/superpowers/specs/2026-08-22-carrier-recovery-design.md` (approved at `ca29487d539a8181d119ad43efac162df247ad3b`)

## Global Constraints

- Preserve the existing Phase 1 one-container workflow/API and all Phase 2 fixture, scenario, allocation, optimizer, benchmark, and inspection behavior.
- Keep `IncidentState.RESOLVED` terminal. Never reopen or reinterpret a Phase 2 incident.
- Add exactly one frozen contract value: `DecisionAction.PRESERVE_VIA_RTA`. Record it append-only in `docs/coordination/DECISIONS.md` in Task 1; make no other frozen Phase 1/2 contract mutation.
- `REQUEST_RTA` is connection-level request/authorization vocabulary only; `PRESERVE_VIA_RTA` is container-level and requires valid effective timing plus p90 success.
- A case is unique per `(incident_id, connection_id)` and independent across connections.
- `RTARequest.id` is the immutable request-version identity. Its timing payload is never overwritten.
- All command timestamps (`requested_eta_pta`, `response_deadline`, `effective_at`) must arrive as string input ending in `Z` or `+00:00`, parse to timezone-aware UTC, and persist canonically in UTC. Reject other offsets with 422.
- Sending requires the exact current `Approval + ApprovalBinding`; a stale/mismatched approval command or send command returns 409. Exact completed-command retries return the pre-existing durable result.
- A `COUNTER` needs a fresh connection-level `REQUEST_RTA` proposal, `ApprovalBinding`, and `Approval`; no second carrier negotiation request exists.
- `SILENT` is the absence of a `CarrierResponse`: no `CarrierResponse(SILENT)`, no response row, and no `CARRIER` event.
- Phase 3 must not resample worlds, rerun CP-SAT, alter the fixed Phase 2 allocation, or alter unrelated connections.
- p90 is an explicitly synthetic, non-PSA-calibrated policy: hard-constraint failure escalates; >=90% preserves via RTA; zero remains roll; 1–89% escalates.
- Every Phase 3 state-changing command commits its state, artifacts, decisions/results, audit events, and audit-case links atomically.
- Phase 3 audit uses SYSTEM, OPERATOR, CARRIER, and POLICY only; AGENT and SOLVER are unused.
- Do not add dependencies. Do not implement LLM behavior, DG semantic reasoning, authentication, production integrations, schedulers, WebSockets, deployment, second negotiation rounds, frontend polish, arbitrary scoring, or Phase 2 retuning.

## File map and contracts between units

| File | Responsibility |
|---|---|
| `backend/app/domain/enums.py` | Add the single frozen `PRESERVE_VIA_RTA` action and all additive Phase 3 enums. |
| `backend/app/domain/carrier_recovery.py` | Frozen Phase 3 Pydantic contracts, UTC parser, state machine inputs, and command DTO-shared models. |
| `backend/app/storage/repositories.py` | Add non-committing audit append support while retaining existing repository behavior. |
| `backend/app/storage/carrier_recovery.py` | SQLModel tables, UTC serialization, transactional repository, and query methods for all carrier-recovery artifacts. |
| `backend/app/orchestration/carrier_recovery.py` | Case transitions and command workflow: prepare, approve, send, simulate, counter approval, timeout, and recomputation integration. |
| `backend/app/services/carrier_simulator.py` | Versioned deterministic response-plan loader and response emission contract. |
| `backend/app/evaluation/carrier_recovery.py` | Fixed-evidence recomputer and p90 disposition calculation; it imports no optimizer. |
| `backend/app/main.py` | Phase 3 FastAPI DTOs/routes and 404/409/422 translation while retaining every current route. |
| `shared/fixtures/canonical-carrier-response-plan.json` | Versioned fixed three-run ACCEPT/COUNTER/SILENT carrier-demo suite; no recovery-count assertion. |
| `backend/tests/test_carrier_recovery_contracts.py` | Enums, UTC-only parsing, case state machine, and contract validation. |
| `backend/tests/test_carrier_recovery_repositories.py` | Tables, uniqueness, transaction rollback, and structured audit links. |
| `backend/tests/test_carrier_recovery_workflow.py` | Preparation, lineage, approvals, send, simulator outcomes, timeout, and idempotency. |
| `backend/tests/test_carrier_recovery_recomputation.py` | Exact-world reuse, fixed allocation, p90 outcomes, supersession, and mixed results. |
| `backend/tests/test_carrier_recovery_api.py` | Exact-subject request/counter approval DTOs, status codes, inspection, and OpenAPI. |
| `backend/tests/test_domain_contracts.py`, `backend/tests/test_authority_boundaries.py`, `backend/tests/test_audit.py`, `backend/tests/test_scarcity_api.py` | Freeze-regression updates and preservation of current behavior. |
| `docs/coordination/DECISIONS.md` | Append the approved `PRESERVE_VIA_RTA` enum decision in Task 1 only. |

The planned additive interfaces are:

```python
class CarrierRecoveryCaseState(StrEnum):
    PREPARED = "PREPARED"
    AWAITING_REQUEST_APPROVAL = "AWAITING_REQUEST_APPROVAL"
    AWAITING_CARRIER = "AWAITING_CARRIER"
    AWAITING_COUNTER_APPROVAL = "AWAITING_COUNTER_APPROVAL"
    RECOMPUTING = "RECOMPUTING"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"

class AuthorizationSubjectKind(StrEnum):
    OUTBOUND_REQUEST = "OUTBOUND_REQUEST"
    COUNTER_PROPOSAL = "COUNTER_PROPOSAL"

class CarrierRecoveryDisposition(StrEnum):
    PRESERVED_VIA_RTA = "PRESERVED_VIA_RTA"
    STILL_ROLL = "STILL_ROLL"
    ESCALATE = "ESCALATE"

class CarrierRecoveryCase(FrozenContract):
    id: UUID
    incident_id: UUID
    connection_id: str
    source_evaluation_id: UUID
    affected_container_ids: Sequence[str]
    state: CarrierRecoveryCaseState
    created_at: datetime
    updated_at: datetime

class RTARequestContext(FrozenContract):
    case_id: UUID
    request_id: UUID
    payload_fingerprint: str
    response_deadline: datetime
    sent_at: datetime | None
    closed_at: datetime | None

class ApprovalBinding(FrozenContract):
    case_id: UUID
    proposal_decision_id: UUID
    subject_kind: AuthorizationSubjectKind
    subject_id: UUID
    payload_fingerprint: str
    created_at: datetime

class EffectiveConnectionTiming(FrozenContract):
    id: UUID
    case_id: UUID
    request_id: UUID
    carrier_response_id: UUID
    effective_eta_pta: datetime
    created_at: datetime

class CarrierRecoveryDecisionLink(FrozenContract):
    case_id: UUID
    decision_id: UUID
    role: str
    created_at: datetime

class ContainerReconsiderationResult(FrozenContract):
    id: UUID
    case_id: UUID
    container_id: str
    disposition: CarrierRecoveryDisposition
    prior_decision_id: UUID
    replacement_decision_id: UUID | None
    preserved_world_count: int
    world_count: int
    hard_constraints_satisfied: bool
    created_at: datetime

class CarrierSimulationResult(FrozenContract):
    case_id: UUID
    carrier_response_id: UUID | None
    no_response_emitted: bool

class CarrierRecoveryHistory(FrozenContract):
    case: CarrierRecoveryCase
    request: RTARequest
    request_context: RTARequestContext
    bindings: Sequence[ApprovalBinding]
    approvals: Sequence[Approval]
    carrier_responses: Sequence[CarrierResponse]
    effective_timings: Sequence[EffectiveConnectionTiming]
    decision_links: Sequence[CarrierRecoveryDecisionLink]
    results: Sequence[ContainerReconsiderationResult]
    audit_events: Sequence[AuditEvent]

class PrepareCarrierRecoveryCaseCommand(FrozenContract):
    incident_id: UUID
    connection_id: str
    requested_eta_pta: datetime
    response_deadline: datetime

class RequestApprovalCommand(FrozenContract):
    case_id: UUID
    proposal_decision_id: UUID
    request_id: UUID
    expected_payload_fingerprint: str
    operator_id: str
    status: ApprovalStatus

class CounterApprovalCommand(FrozenContract):
    case_id: UUID
    proposal_decision_id: UUID
    carrier_response_id: UUID
    expected_payload_fingerprint: str
    operator_id: str
    status: ApprovalStatus

class SimulateCarrierResponseCommand(FrozenContract):
    case_id: UUID
    effective_at: datetime

class EvaluateTimeoutCommand(FrozenContract):
    case_id: UUID
    effective_at: datetime
```

`CarrierRecoveryRepository` public methods are `transaction()`, `create_case(case)`, `get_case(case_id)`, `list_cases(incident_id)`, `add_approval_binding(binding)`, `get_binding_for_proposal(proposal_decision_id)`, `add_result(result)`, and `history(case_id)`. Their return types are, respectively, a transaction context manager, `CarrierRecoveryCase`, `CarrierRecoveryCase`, `list[CarrierRecoveryCase]`, `ApprovalBinding`, `ApprovalBinding`, `ContainerReconsiderationResult`, and `CarrierRecoveryHistory`.

`CarrierRecoveryWorkflow` public methods are `prepare(command) -> CarrierRecoveryCase`, `record_request_approval(command) -> Approval`, `send_authorised_request(case_id) -> RTARequestContext`, `simulate_response(command) -> CarrierSimulationResult`, `record_counter_approval(command) -> Approval`, and `evaluate_timeout(command) -> CarrierRecoveryCase`.

---

### Task 1: Freeze the one approved enum extension and define Phase 3 contracts

**Files:**
- Create: `backend/app/domain/carrier_recovery.py`
- Create: `backend/tests/test_carrier_recovery_contracts.py`
- Modify: `backend/app/domain/enums.py`
- Modify: `backend/tests/test_domain_contracts.py`
- Modify: `docs/coordination/DECISIONS.md`

**Interfaces:**
- Produces `CarrierRecoveryCaseState`, `AuthorizationSubjectKind`, `CarrierRecoveryDisposition`, `CarrierRecoveryCase`, `RTARequestContext`, `ApprovalBinding`, `EffectiveConnectionTiming`, `CarrierRecoveryDecisionLink`, `ContainerReconsiderationResult`, `CarrierRecoveryHistory`, all five command contracts, `CarrierSimulationResult`, and `parse_explicit_utc`.
- `parse_explicit_utc(value: str) -> datetime` accepts only textual UTC values ending in `Z` or `+00:00`, returns `datetime` normalized to `UTC`, and raises `ValueError` otherwise.
- Adds only `DecisionAction.PRESERVE_VIA_RTA`; all later tasks import this action from the frozen enum.

- [ ] **Step 1: Write failing contract tests**

```python
def test_decision_actions_add_only_preserve_via_rta() -> None:
    assert {item.value for item in DecisionAction} == {
        "EXPEDITE", "REQUEST_RTA", "ROLL", "ESCALATE", "PRESERVE_VIA_RTA",
    }

@pytest.mark.parametrize("value", ["2026-08-22T06:00:00Z", "2026-08-22T06:00:00+00:00"])
def test_parse_explicit_utc_accepts_only_explicit_utc(value: str) -> None:
    assert parse_explicit_utc(value).tzinfo is UTC

def test_parse_explicit_utc_rejects_non_utc_offset() -> None:
    with pytest.raises(ValueError):
        parse_explicit_utc("2026-08-22T14:00:00+08:00")
```

- [ ] **Step 2: Run RED contract tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_contracts.py backend/tests/test_domain_contracts.py -q`
Expected: FAIL because the Phase 3 module and `PRESERVE_VIA_RTA` do not exist.

- [ ] **Step 3: Implement frozen enum and additive contracts**

Add the enum value, the exact state/disposition/authorization enums, frozen Pydantic models with `extra="forbid"`, and validation that IDs/snapshots are non-empty and timestamps are aware UTC. Define `CarrierRecoveryCaseStateMachine.transition(case, target)` with the approved transition graph; do not import or modify `IncidentStateMachine`. Append an approved `DECISIONS.md` entry naming the sole enum change, its connection/container semantics, and the requirement that `REQUEST_RTA` is never container-level.

- [ ] **Step 4: Run GREEN contract and existing-domain tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_contracts.py backend/tests/test_domain_contracts.py -q`
Expected: PASS, including rejection of non-UTC offsets and exact frozen enum assertions.

- [ ] **Step 5: Commit the contract foundation**

```bash
git add backend/app/domain/enums.py backend/app/domain/carrier_recovery.py backend/tests/test_carrier_recovery_contracts.py backend/tests/test_domain_contracts.py docs/coordination/DECISIONS.md
git commit -m "feat: add carrier recovery contracts"
```

### Task 2: Add transactional carrier-recovery persistence and structured audit scoping

**Files:**
- Create: `backend/app/storage/carrier_recovery.py`
- Create: `backend/tests/test_carrier_recovery_repositories.py`
- Modify: `backend/app/storage/repositories.py`
- Modify: `backend/tests/test_audit.py`

**Interfaces:**
- Consumes all Task 1 contracts and existing `AuditEvent`, `Decision`, `Approval`, `RTARequest`, and `CarrierResponse` models.
- Produces SQLModel records/tables named `carrier_recovery_cases`, `rta_requests`, `rta_request_contexts`, `approvals`, `approval_bindings`, `carrier_responses`, `effective_connection_timings`, `carrier_recovery_decision_links`, `container_reconsideration_results`, and `carrier_recovery_audit_links`.
- `CarrierRecoveryRepository.transaction()` commits once on success and rolls back every newly-added carrier artifact, decision, and audit row on exception.
- Extend `AuditRepository` with `add_uncommitted(event: AuditEvent) -> AuditEventRecord`; keep `append()` as the existing commit-and-refresh API for Phase 1/2 callers.

- [ ] **Step 1: Write failing persistence tests**

```python
def test_case_is_unique_per_incident_and_connection(session: Session) -> None:
    repository.create_case(case)
    with pytest.raises(IntegrityError):
        with repository.transaction():
            repository.create_case(case.model_copy(update={"id": uuid4()}))

def test_transaction_rolls_back_case_and_case_audit_link(session: Session) -> None:
    with pytest.raises(RuntimeError):
        with repository.transaction():
            repository.create_case(case)
            repository.link_audit(case.id, audit_event)
            raise RuntimeError("force rollback")
    assert repository.list_cases(case.incident_id) == []
```

- [ ] **Step 2: Run RED persistence tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_repositories.py backend/tests/test_audit.py -q`
Expected: FAIL during collection because the repository module and transactional audit method do not exist.

- [ ] **Step 3: Implement records, repository methods, and transaction behavior**

Create one focused storage module with conversion helpers using existing `to_utc_text`/`from_utc_text` semantics. Add unique constraints for case `(incident_id, connection_id)`, one request context per case, one binding per proposal decision, one response per request, one timing per applied response, one decision link per decision, one result per `(case_id, container_id)`, and one audit link per event. Make `history(case_id)` query audit links then fetch events ordered by the existing append-only audit sequence. Preserve existing repository commits outside the new transaction path.

- [ ] **Step 4: Run GREEN persistence tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_repositories.py backend/tests/test_audit.py -q`
Expected: PASS, with rollback leaving no case, artifact, result, or linked audit row.

- [ ] **Step 5: Commit persistence foundation**

```bash
git add backend/app/storage/carrier_recovery.py backend/app/storage/repositories.py backend/tests/test_carrier_recovery_repositories.py backend/tests/test_audit.py
git commit -m "feat: persist carrier recovery cases"
```

### Task 3: Prepare connection cases and preserve fallback-roll lineage

**Files:**
- Create: `backend/app/orchestration/carrier_recovery.py`
- Modify: `backend/app/storage/carrier_recovery.py`
- Create: `backend/tests/test_carrier_recovery_workflow.py`

**Interfaces:**
- Consumes `SyntheticCanonicalIncidentService.load()`, `SeededScenarioGenerator.generate(fixture, seed, world_count)`, `ScarcityEvaluationRepository.get_for_incident()`, and the Task 2 repository.
- Produces `CarrierRecoveryWorkflow.prepare(command: PrepareCarrierRecoveryCaseCommand) -> CarrierRecoveryCase`.
- `PrepareCarrierRecoveryCaseCommand` has `incident_id: UUID`, `connection_id: str`, `requested_eta_pta: datetime`, and `response_deadline: datetime`, with Task 1 UTC validation at the API boundary.
- Creates `RTARequest(status=PENDING)`, `RTARequestContext`, a case-level proposed `REQUEST_RTA` decision plus pending `ApprovalBinding`, fallback `ROLL` decisions, decision links, audit events, and case state `AWAITING_REQUEST_APPROVAL` in one transaction.

- [ ] **Step 1: Write failing preparation and lineage tests**

```python
def test_prepare_derives_only_safe_zero_world_containers_and_freezes_snapshot(workflow) -> None:
    case = workflow.prepare(command)
    assert case.affected_container_ids == ("CASE-CNT-001",)
    assert all(item.connection_id == command.connection_id for item in workflow.history(case.id).requests)

def test_prepare_fallback_roll_supersedes_current_phase_two_decision(workflow, phase_two_decision) -> None:
    case = workflow.prepare(command)
    fallback = workflow.history(case.id).fallback_decisions[0]
    assert fallback.supersedes == phase_two_decision.id
    assert "zero preserved worlds" in fallback.supersession_reason
```

- [ ] **Step 2: Run RED preparation tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: FAIL because `CarrierRecoveryWorkflow.prepare` does not exist.

- [ ] **Step 3: Implement exact candidate derivation and decision lineage**

Use the source scarcity report's fixture ID, seed, scenario count, and selected allocation to regenerate worlds once. Evaluate only profiles on the requested connection; include profiles that are structurally safe and preserve zero worlds under original timing with the fixed allocation. For each candidate, resolve exactly one current container-level decision by following `Decision.supersedes`; if none exists, create `ROLL(supersedes=None)`. If one exists, create fallback `ROLL` superseding it with the precise frozen-allocation/original-timing evidence reason. If more than one current decision exists, raise the workflow conflict used by the API for 409. Never create container-level `REQUEST_RTA`.

- [ ] **Step 4: Run GREEN preparation tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: PASS for no-prior-decision and current-Phase-2-decision lineage branches, immutable snapshots, one case per connection, and atomic artifacts.

- [ ] **Step 5: Commit preparation workflow**

```bash
git add backend/app/orchestration/carrier_recovery.py backend/app/storage/carrier_recovery.py backend/tests/test_carrier_recovery_workflow.py
git commit -m "feat: prepare carrier recovery cases"
```

### Task 4: Record exact-subject request approvals

**Files:**
- Modify: `backend/app/orchestration/carrier_recovery.py`
- Modify: `backend/app/storage/carrier_recovery.py`
- Modify: `backend/tests/test_carrier_recovery_workflow.py`

**Interfaces:**
- Produces `RequestApprovalCommand(case_id, proposal_decision_id, request_id, expected_payload_fingerprint, operator_id, status)` and `record_request_approval(command) -> Approval`.
- A binding is found by `proposal_decision_id`; server checks case, `OUTBOUND_REQUEST`, request ID, exact fingerprint, non-empty operator ID, and `AWAITING_REQUEST_APPROVAL`.
- Exact identical retry returns the persisted `Approval`; changed subject/fingerprint/status is a workflow conflict.

- [ ] **Step 1: Write failing exact-subject approval tests**

```python
def test_request_approval_requires_exact_proposal_request_and_fingerprint(workflow) -> None:
    approval = workflow.record_request_approval(exact_command)
    assert approval.decision_id == exact_command.proposal_decision_id

def test_request_approval_rejects_stale_subject_without_creating_approval(workflow) -> None:
    with pytest.raises(CarrierRecoveryConflict):
        workflow.record_request_approval(exact_command.model_copy(update={"request_id": uuid4()}))
```

- [ ] **Step 2: Run RED approval tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: FAIL because request-approval commands and lookup validation do not exist.

- [ ] **Step 3: Implement approval persistence, validation, and operator audit**

Persist the existing immutable `Approval` with its case-level proposal decision ID. On first command, verify the persisted pending binding before creating it; append an OPERATOR audit event with the exact `operator_id`, case ID, proposal ID, subject ID, fingerprint, and approve/reject status. On identical retry, return the existing approval and no new audit event. For a reject, close the pending request and transition to recomputation using original timing; leave the fallback roll current after recomputation.

- [ ] **Step 4: Run GREEN approval tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: PASS for approval/rejection, exact retry, stale conflict, explicit operator identity, and no “approve active case” behavior.

- [ ] **Step 5: Commit request approval handling**

```bash
git add backend/app/orchestration/carrier_recovery.py backend/app/storage/carrier_recovery.py backend/tests/test_carrier_recovery_workflow.py
git commit -m "feat: bind request approvals to exact subjects"
```

### Task 5: Enforce the sole authorized-send boundary

**Files:**
- Modify: `backend/app/orchestration/carrier_recovery.py`
- Modify: `backend/app/storage/carrier_recovery.py`
- Modify: `backend/tests/test_carrier_recovery_workflow.py`

**Interfaces:**
- Produces `send_authorised_request(case_id: UUID) -> RTARequestContext`.
- Requires approved `Approval` joined to the exact `OUTBOUND_REQUEST` binding and matching request fingerprint.
- On success transitions request `PENDING -> SENT` and case `AWAITING_REQUEST_APPROVAL -> AWAITING_CARRIER` atomically.

- [ ] **Step 1: Write failing send-boundary tests**

```python
def test_send_requires_exact_approved_binding(workflow) -> None:
    with pytest.raises(CarrierRecoveryConflict):
        workflow.send_authorised_request(case_id)

def test_send_is_idempotent_after_exact_approval(workflow) -> None:
    first = workflow.send_authorised_request(case_id)
    second = workflow.send_authorised_request(case_id)
    assert second == first
    assert workflow.history(case_id).sent_event_count == 1
```

- [ ] **Step 2: Run RED send tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: FAIL because authorized send is not implemented.

- [ ] **Step 3: Implement durable send transition**

Reject missing/rejected/mismatched approvals, stale case states, changed request payloads, closed requests, and contradictory prior artifacts with `CarrierRecoveryConflict`. For the exact already-sent request, return its persisted context. For the first send, update only lifecycle/send fields; do not alter requested timing. Add one SYSTEM `rta.request_sent` event and its `carrier_recovery_audit_links` row in the same transaction.

- [ ] **Step 4: Run GREEN send tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: PASS for no-send-without-approval, exact-binding validation, one durable dispatch, and idempotent retry.

- [ ] **Step 5: Commit send boundary**

```bash
git add backend/app/orchestration/carrier_recovery.py backend/app/storage/carrier_recovery.py backend/tests/test_carrier_recovery_workflow.py
git commit -m "feat: send authorised carrier requests"
```

### Task 6: Add the deterministic carrier response-plan simulator

**Files:**
- Create: `backend/app/services/carrier_simulator.py`
- Create: `shared/fixtures/canonical-carrier-response-plan.json`
- Modify: `backend/app/orchestration/carrier_recovery.py`
- Modify: `backend/tests/test_carrier_recovery_workflow.py`

**Interfaces:**
- `SyntheticCarrierResponsePlan.load() -> CarrierDemoSuite` loads a versioned fixture containing three named independent runs. `load_run(run_id) -> CarrierResponsePlan` selects the run's `ACCEPT`, `COUNTER` with UTC counter ETA/PTA, or `SILENT` outcome.
- `DeterministicCarrierSimulator.emit(request: RTARequest, effective_at: datetime) -> CarrierSimulationResult` returns `response: CarrierResponse | None`; `None` means command-level no-response-emitted only.
- Simulation is allowed only for a sent request before deadline, is exact-retry idempotent, and rejects a conflicting second outcome.

The fixture shape is fixed as:

```json
{
  "suite_id": "SYN-CANONICAL-CARRIER-DEMO-V1",
  "fixture_id": "SYN-CANONICAL-24-V1",
  "runs": [
    {"run_id": "ACCEPT-RUN", "fixture_id": "SYN-CANONICAL-24-V1", "connection_id": "SYN-CONN-JV2", "outcome": "ACCEPT"},
    {"run_id": "COUNTER-RUN", "fixture_id": "SYN-CANONICAL-24-V1", "connection_id": "SYN-CONN-JV2", "outcome": "COUNTER", "counter_eta_pta": "2026-08-22T06:45:00Z"},
    {"run_id": "SILENT-RUN", "fixture_id": "SYN-CANONICAL-24-V1", "connection_id": "SYN-CONN-EC3", "outcome": "SILENT"}
  ]
}
```

- [ ] **Step 1: Write failing simulator tests**

```python
def test_silent_plan_returns_no_response_and_persists_no_carrier_event(workflow) -> None:
    result = workflow.simulate_response(silent_command)
    assert result.response is None
    assert workflow.history(case_id).carrier_responses == []
    assert "CARRIER" not in workflow.history(case_id).actors

def test_simulator_rejects_effective_at_at_or_after_deadline(workflow) -> None:
    with pytest.raises(CarrierRecoveryConflict):
        workflow.simulate_response(command_at_deadline)
```

- [ ] **Step 2: Run RED simulator tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: FAIL because no response-plan loader or simulator exists.

- [ ] **Step 3: Implement fixture loader and simulator isolation**

Use one fixture with `suite_id`, shared `fixture_id`, and three named independent runs: JV2 ACCEPT, JV2 COUNTER with explicit UTC counter time, and EC3 SILENT. Each run's fixture ID must match the suite fixture ID; do not encode preserved-container counts. The simulator only emits the selected configured response or `None`; it does not mutate `Connection`, `ServiceWindow`, allocation, or request timing. The orchestration layer owns persistence and actor-attributed audit events.

- [ ] **Step 4: Run GREEN simulator tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: PASS for deterministic outcomes, no silent persistence/event, deadline rejection, and conflicting-outcome rejection.

- [ ] **Step 5: Commit deterministic simulator**

```bash
git add backend/app/services/carrier_simulator.py shared/fixtures/canonical-carrier-response-plan.json backend/app/orchestration/carrier_recovery.py backend/tests/test_carrier_recovery_workflow.py
git commit -m "feat: simulate deterministic carrier responses"
```

### Task 7: Apply ACCEPT and COUNTER with exact carrier authority

**Files:**
- Modify: `backend/app/orchestration/carrier_recovery.py`
- Modify: `backend/app/storage/carrier_recovery.py`
- Modify: `backend/tests/test_carrier_recovery_workflow.py`

**Interfaces:**
- `simulate_response(SimulateCarrierResponseCommand)` persists one `CarrierResponse` and returns its result.
- An ACCEPT creates `EffectiveConnectionTiming` from the immutable request and enters recomputation automatically.
- A COUNTER persists its response, creates a fresh case-level proposed `REQUEST_RTA` decision and `COUNTER_PROPOSAL` binding, and enters `AWAITING_COUNTER_APPROVAL`.
- `CounterApprovalCommand(case_id, proposal_decision_id, carrier_response_id, expected_payload_fingerprint, operator_id, status)` creates a new `Approval` or returns its exact retry.

- [ ] **Step 1: Write failing ACCEPT/COUNTER tests**

```python
def test_accept_requires_requested_timing_and_creates_effective_evidence(workflow) -> None:
    result = workflow.simulate_response(accept_command)
    assert result.response.response is CarrierResponseType.ACCEPT
    assert workflow.history(case_id).effective_timing.effective_eta_pta == requested_eta_pta

def test_counter_needs_fresh_exact_approval_before_effective_timing(workflow) -> None:
    workflow.simulate_response(counter_command)
    assert workflow.history(case_id).effective_timing is None
    with pytest.raises(CarrierRecoveryConflict):
        workflow.record_counter_approval(original_request_approval_as_counter)
```

- [ ] **Step 2: Run RED ACCEPT/COUNTER tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: FAIL because responses are not yet persisted or applied.

- [ ] **Step 3: Implement exact outcome handling**

For ACCEPT, require the plan outcome to match the sent request timing exactly, persist one CARRIER event and a timing evidence row, close the request, and advance to `RECOMPUTING` without a second approval. For COUNTER, require `counter_eta_pta`, persist one CARRIER event, close the request response channel, create a new connection-level proposal/binding fingerprinted from that response, and await counter approval. A counter reject adds an OPERATOR audit event and enters fallback recomputation; it does not create effective timing or a second carrier request.

- [ ] **Step 4: Run GREEN ACCEPT/COUNTER tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: PASS for exact accept evidence, fresh counter approval, counter rejection, single response, and CARRIER actor attribution only for persisted responses.

- [ ] **Step 5: Commit carrier outcome handling**

```bash
git add backend/app/orchestration/carrier_recovery.py backend/app/storage/carrier_recovery.py backend/tests/test_carrier_recovery_workflow.py
git commit -m "feat: handle carrier accept and counter outcomes"
```

### Task 8: Add explicit, idempotent timeout observation

**Files:**
- Modify: `backend/app/orchestration/carrier_recovery.py`
- Modify: `backend/app/storage/carrier_recovery.py`
- Modify: `backend/tests/test_carrier_recovery_workflow.py`

**Interfaces:**
- `EvaluateTimeoutCommand(case_id: UUID, effective_at: datetime)`.
- `evaluate_timeout(command) -> CarrierRecoveryCase` requires sent request, non-null deadline, no response, and `effective_at >= deadline`.
- Uses original connection timing as fallback evidence; records one SYSTEM absence event and never writes a carrier response.

- [ ] **Step 1: Write failing timeout tests**

```python
def test_timeout_at_deadline_is_valid_and_observes_absence_once(workflow) -> None:
    first = workflow.evaluate_timeout(command_at_deadline)
    second = workflow.evaluate_timeout(command_at_deadline)
    assert second == first
    assert workflow.history(case_id).carrier_responses == []
    assert workflow.history(case_id).timeout_event_count == 1

def test_timeout_after_response_is_conflict(workflow) -> None:
    workflow.simulate_response(accept_command)
    with pytest.raises(CarrierRecoveryConflict):
        workflow.evaluate_timeout(command_after_deadline)
```

- [ ] **Step 2: Run RED timeout tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: FAIL because timeout evaluation is not implemented.

- [ ] **Step 3: Implement timeout state and audit transition**

Reject unsent requests, missing deadlines, before-deadline timestamps, responses already present, and non-exact retries as workflow conflicts. On first valid timeout, record only SYSTEM `carrier.response_timed_out` evidence containing UTC `effective_at`, close the request, link the event to the case, and invoke fallback recomputation. A repeated identical timeout returns the persisted case/result and does not append anything.

- [ ] **Step 4: Run GREEN timeout tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_workflow.py -q`
Expected: PASS for before-deadline rejection, at-deadline success, after-response rejection, and exact-retry idempotency.

- [ ] **Step 5: Commit timeout handling**

```bash
git add backend/app/orchestration/carrier_recovery.py backend/app/storage/carrier_recovery.py backend/tests/test_carrier_recovery_workflow.py
git commit -m "feat: observe carrier response timeouts"
```

### Task 9: Recompute with frozen Phase 2 evidence and persist p90 dispositions

**Files:**
- Create: `backend/app/evaluation/carrier_recovery.py`
- Modify: `backend/app/orchestration/carrier_recovery.py`
- Modify: `backend/app/storage/carrier_recovery.py`
- Create: `backend/tests/test_carrier_recovery_recomputation.py`

**Interfaces:**
- `CarrierRecoveryRecomputer.recompute(case, source_report, fixture, scenarios, allocation, effective_timing) -> Sequence[ContainerReconsiderationResult]`.
- It calls `SeededScenarioGenerator.generate(fixture, seed=report.seed, world_count=report.scenario_count)` exactly once and uses `report.selected_allocation` unchanged.
- It returns a result for every snapshotted container and must not import `ScenarioAwareAllocator` or `ScarcityComparisonService`.

- [ ] **Step 1: Write failing evidence-boundary and p90 tests**

```python
def test_recomputer_reuses_report_seed_world_count_and_fixed_allocation(monkeypatch, prepared_case) -> None:
    recompute(prepared_case)
    assert observed_generator_args == (report.seed, report.scenario_count)
    assert observed_allocation == report.selected_allocation
    assert solver_calls == 0

def test_p90_results_preserve_roll_and_escalate_with_immutable_lineage(recomputer) -> None:
    assert result_90.disposition is CarrierRecoveryDisposition.PRESERVED_VIA_RTA
    assert result_zero.disposition is CarrierRecoveryDisposition.STILL_ROLL
    assert result_partial.disposition is CarrierRecoveryDisposition.ESCALATE
```

- [ ] **Step 2: Run RED recomputation tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_recomputation.py -q`
Expected: FAIL because no carrier-recovery evaluator exists.

- [ ] **Step 3: Implement the scoped recomputer and decision rules**

Derive only the requested connection's ready boundary as effective PTA plus 35 minutes. For every snapshotted profile, use the existing ready-time arithmetic and structural safety rules with fixed expedite membership. Persist preservation count and source world count. If hard constraints fail, create `ESCALATE` superseding fallback roll. If preservation is >=90%, create approved `PRESERVE_VIA_RTA` superseding fallback roll. If zero, persist `STILL_ROLL` and no replacement decision. If 1–89%, create approved existing `ESCALATE` superseding fallback roll. Link every decision/result/timing-or-timeout evidence to the case, audit recomputation with SYSTEM and disposition/decision creation with POLICY, and derive terminal case state from all results.

- [ ] **Step 4: Run GREEN recomputation tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_recomputation.py backend/tests/test_carrier_recovery_workflow.py -q`
Expected: PASS for no resampling, no optimizer call, fixed allocation, hard-constraint escalation, p90/zero/partial branches, immutable supersession chains, and mixed-case `COMPLETED`/`ESCALATED` summaries.

- [ ] **Step 5: Commit recomputation and dispositions**

```bash
git add backend/app/evaluation/carrier_recovery.py backend/app/orchestration/carrier_recovery.py backend/app/storage/carrier_recovery.py backend/tests/test_carrier_recovery_recomputation.py backend/tests/test_carrier_recovery_workflow.py
git commit -m "feat: recompute carrier recovery dispositions"
```

### Task 10: Expose deterministic case history and complete audit provenance

**Files:**
- Modify: `backend/app/storage/carrier_recovery.py`
- Modify: `backend/app/orchestration/carrier_recovery.py`
- Modify: `backend/tests/test_carrier_recovery_repositories.py`
- Modify: `backend/tests/test_carrier_recovery_workflow.py`

**Interfaces:**
- `CarrierRecoveryHistory` returns case, request/context, proposals/bindings/approvals, responses, effective timing or timeout evidence, linked decisions, per-container results, and audit events ordered by audit sequence.
- `CarrierRecoveryRepository.history(case_id)` selects events through `carrier_recovery_audit_links`, not JSON payload filtering.

- [ ] **Step 1: Write failing history/provenance tests**

```python
def test_history_uses_structured_case_audit_links_and_preserves_actor_identity(workflow) -> None:
    history = workflow.history(case_id)
    assert [event.sequence for event in history.audit_events] == sorted(event.sequence for event in history.audit_events)
    assert {event.actor for event in history.audit_events} <= {AuditActor.SYSTEM, AuditActor.OPERATOR, AuditActor.CARRIER, AuditActor.POLICY}
    assert all(event.payload["recovery_case_id"] == str(case_id) for event in history.audit_events)
```

- [ ] **Step 2: Run RED history tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_repositories.py backend/tests/test_carrier_recovery_workflow.py -q`
Expected: FAIL because history lacks complete ordered typed artifacts or uses unstructured filtering.

- [ ] **Step 3: Implement complete structured history**

Ensure every Phase 3 event is appended with `recovery_case_id` and linked in the same transaction. Build the history aggregate from direct tables and audit links, not re-derived decisions. Ensure it can show the prior/replacement decision IDs and timing/timeout evidence for each result. Do not include AGENT or SOLVER events in this workflow.

- [ ] **Step 4: Run GREEN history tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_repositories.py backend/tests/test_carrier_recovery_workflow.py backend/tests/test_audit.py -q`
Expected: PASS with deterministic history order and correct SYSTEM/OPERATOR/CARRIER/POLICY attribution.

- [ ] **Step 5: Commit history support**

```bash
git add backend/app/storage/carrier_recovery.py backend/app/orchestration/carrier_recovery.py backend/tests/test_carrier_recovery_repositories.py backend/tests/test_carrier_recovery_workflow.py
git commit -m "feat: expose carrier recovery history"
```

### Task 11: Add the fail-closed FastAPI surface

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_carrier_recovery_api.py`
- Modify: `backend/tests/test_scarcity_api.py`

**Interfaces:**
- `PrepareCarrierRecoveryCaseRequest`: `connection_id`, `requested_eta_pta`, `response_deadline`.
- `RequestApprovalRequest`: `proposal_decision_id`, `request_id`, `expected_payload_fingerprint`, `operator_id`, `status: ApprovalStatus`.
- `CounterApprovalRequest`: `proposal_decision_id`, `carrier_response_id`, `expected_payload_fingerprint`, `operator_id`, `status: ApprovalStatus`.
- `SimulateCarrierResponseRequest` and `EvaluateTimeoutRequest`: `effective_at` only.
- Add exactly the nine routes in the approved spec, map `RecordNotFound` to 404 and `CarrierRecoveryConflict` to 409, while Pydantic UTC/payload validation maps to 422.

- [ ] **Step 1: Write failing route and status-code tests**

```python
def test_request_approval_requires_exact_subject_fields(client: TestClient) -> None:
    response = client.post(f"/carrier-recovery-cases/{case_id}/request-approval", json={"operator_id": "OP-1"})
    assert response.status_code == 422

def test_stale_approval_subject_returns_409_and_exact_retry_is_idempotent(client: TestClient) -> None:
    assert client.post(approval_url, json=exact_body).status_code == 201
    assert client.post(approval_url, json=exact_body).status_code == 200
    assert client.post(approval_url, json={**exact_body, "request_id": str(uuid4())}).status_code == 409
```

- [ ] **Step 2: Run RED API tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_api.py -q`
Expected: FAIL because no Phase 3 routes or DTOs exist.

- [ ] **Step 3: Implement DTOs, routes, and exact retry responses**

Construct workflow dependencies from the request session. Keep each endpoint a thin command adapter; it must not create artifacts itself. Return 201 for a first create/approval/action and 200 for a detected exact retry. Require UTF UTC request strings through Task 1 parser in all DTOs. Map all stale, wrong-state, late-response, closed-request, mismatched binding, and ambiguous-lineage failures to 409. Keep existing routes verbatim and extend the existing OpenAPI test rather than replacing it.

- [ ] **Step 4: Run GREEN API and existing route tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_api.py backend/tests/test_scarcity_api.py backend/tests/test_api.py -q`
Expected: PASS for all Phase 3 commands, deterministic history, 404/409/422 behavior, exact retries, and unchanged Phase 1/2 routes.

- [ ] **Step 5: Commit FastAPI surface**

```bash
git add backend/app/main.py backend/tests/test_carrier_recovery_api.py backend/tests/test_scarcity_api.py
git commit -m "feat: expose carrier recovery API"
```

### Task 12: Verify the canonical deterministic demo and all authority boundaries

**Files:**
- Modify: `backend/tests/test_carrier_recovery_api.py`
- Modify: `backend/tests/test_authority_boundaries.py`
- Modify: `backend/tests/test_scarcity_api.py`
- Modify: `shared/fixtures/README.md`

**Interfaces:**
- The response-plan fixture is exercised only through `simulate-carrier-response`; it demonstrates one ACCEPT path, one COUNTER path, and one SILENT-plus-timeout path.
- The plan reports observed results from persisted recomputation; no test asserts five RTA recoveries or 18/5/1.

- [ ] **Step 1: Write failing end-to-end and authority tests**

```python
def test_canonical_phase_three_demo_exercises_accept_counter_and_silence(client: TestClient) -> None:
    histories = run_canonical_carrier_demo(client)
    assert {history.response_kind for history in histories} == {"ACCEPT", "COUNTER", None}
    assert all(history.results for history in histories)

def test_new_public_modules_and_routes_expose_no_local_carrier_control() -> None:
    assert forbidden_public_names == set()
```

- [ ] **Step 2: Run RED end-to-end and authority tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_api.py backend/tests/test_authority_boundaries.py -q`
Expected: FAIL until the demo orchestration, fixture documentation, and carrier-module authority scan are complete.

- [ ] **Step 3: Complete deterministic demo coverage and documentation**

Drive three independent canonical scarcity incidents, one for each named carrier-demo run: JV2 `ACCEPT`, JV2 `COUNTER`, and EC3 `SILENT`. Prepare only eligible connection cases, approve/send each exact subject, simulate each fixed outcome, approve or reject the counter, and timeout the silent request with its explicit UTC timestamp. Assert only observed evidence and immutable histories. Extend authority scanning to include `carrier_recovery`, `carrier_simulator`, and `carrier_recovery` evaluation/orchestration modules plus new routes. Document the demo-suite format and representative DCSA framing in `shared/fixtures/README.md` without claiming PSA operational integration.

- [ ] **Step 4: Run GREEN focused demo and authority tests**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_carrier_recovery_api.py backend/tests/test_authority_boundaries.py backend/tests/test_scarcity_api.py -q`
Expected: PASS with no forbidden authority names, no silent response row/event, and no target-count hard-coding.

- [ ] **Step 5: Run full verification**

Run: `uv run --python 3.12 --extra dev pytest -q`
Expected: PASS for all Phase 1, Phase 2, and Phase 3 tests.

Run: `uv lock --check`
Expected: PASS with no dependency change.

Run: `git diff --check`
Expected: PASS with no whitespace errors.

Run: `uv run --python 3.12 --extra dev python -c "from backend.app.main import create_app; app=create_app(); print(app.title); print(len(app.routes))"`
Expected: prints `PSA Transshipment Recovery` and a positive route count without startup failure.

- [ ] **Step 6: Commit final demo verification artifacts**

```bash
git add backend/tests/test_carrier_recovery_api.py backend/tests/test_authority_boundaries.py backend/tests/test_scarcity_api.py shared/fixtures/README.md
git commit -m "test: verify canonical carrier recovery demo"
```

## Final execution checklist

- Run every focused RED/GREEN command above at its task boundary.
- Do not use holdout seeds, alter benchmark artifacts, or re-run/retune Phase 2 behavior.
- Confirm the only frozen enum addition is `PRESERVE_VIA_RTA` and that `DECISIONS.md` has one append-only Task 1 entry for it.
- Confirm all Phase 3 command timestamps reject `+08:00` and accept only `Z`/`+00:00` input.
- Confirm all approval routes require explicit immutable proposal, subject, fingerprint, and operator identity.
- Confirm `REQUEST_RTA` appears only in case-level authorization decisions and `PRESERVE_VIA_RTA` only in p90-success container replacements.
- Confirm silent simulator outcomes never persist a `CarrierResponse` or CARRIER audit event.
- Confirm every case history uses `carrier_recovery_audit_links` for event scoping.
- Confirm `IncidentState` remains unchanged and every existing one-container/Phase 2 API, test, and benchmark artifact still passes.
