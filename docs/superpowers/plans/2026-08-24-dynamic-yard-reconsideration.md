# Phase 5B Dynamic Yard Reconsideration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add deterministic dynamic-yard forecast evidence, locked-capacity reconsideration, and safe agent coordination without mutating Phase 2 or rewriting Phase 3.

**Architecture:** Use dedicated dynamic-yard domain, storage, evaluation, optimisation, orchestration, and synthetic-service modules. Extend the existing agent registry/runtime and FastAPI routes only at their established boundaries.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLModel/SQLite, OR-Tools CP-SAT, pytest.

**Spec:** docs/superpowers/specs/2026-08-24-dynamic-yard-reconsideration-design.md

## Global Constraints

- Phase 2 reports, worlds, fixture, allocation, and decisions are immutable; reconstruct worlds only with SeededScenarioGenerator and consume no RNG.
- PRE_DISCHARGE is base-ready p50 plus/minus 30 minutes. DISCHARGE_ACTIVE is plus/minus 17.987433384504683 minutes; only 005 p50 changes 05:59Z to 05:56Z.
- Before/after totals use the same DISCHARGE_ACTIVE snapshot/worlds/constraints. Only PLANNED capacity moves; COMMITTED and EXECUTED never move.
- Reuse pareto_front and AllocationDominancePolicy without new weights or tie-breakers.
- request_expedite_feasibility() has zero arguments. The agent receives no forecast, allocation, capacity, commitment, threshold, or tradeoff input.
- Do not modify CarrierRecoveryWorkflow.prepare/recompute. No frontend, worker, second agent, deployment/authentication, or generic execution system. Ordinary tests make zero network calls.

## File Structure

| File | Responsibility |
| --- | --- |
| backend/app/domain/dynamic_yard.py | Frozen contracts and validation |
| backend/app/storage/dynamic_yard.py | SQLModel records, idempotency, histories, transactions |
| backend/app/evaluation/dynamic_yard.py | World reconstruction, quantile projection, Phase 3 proof |
| backend/app/optimization/dynamic_yard.py | Locked solver and disposition |
| backend/app/orchestration/dynamic_yard.py | Bootstrap, ingest, assessment, revision, selection |
| backend/app/services/dynamic_yard.py | Canonical snapshots |
| backend/app/orchestration/agent_context.py, agent_runtime.py | Tool/wait/context integration |
| backend/app/main.py | Synthetic, selection, history routes |
| backend/tests/test_dynamic_yard_*.py | New deterministic tests |

### Task 1: Dynamic-yard frozen contracts

**Files:**
- Create: backend/app/domain/dynamic_yard.py
- Create: backend/tests/test_dynamic_yard_contracts.py

**Interfaces:**
- Produces ForecastStage, ExpediteCommitmentStatus, ReconsiderationDisposition, TradeoffReviewState, ContainerReadyForecast, YardForecastSnapshot, AllocationRevision, ExpediteCommitment, ExpediteReconsiderationAssessment, AllocationTradeoffReview, AllocationTradeoffOption, AllocationTradeoffSelection, AllocationTradeoffHistory.
- Consumed by Tasks 2-9.

- [ ] **Step 1: Write the failing test**

~~~python
def test_forecast_requires_utc_ordered_quantiles() -> None:
    with pytest.raises(ValidationError):
        ContainerReadyForecast(
            container_id="SYN-CNT-001",
            p10_ready_at="2026-08-22T05:40:00Z",
            p50_ready_at="2026-08-22T05:39:00Z",
            p90_ready_at="2026-08-22T05:41:00Z",
        )
~~~

- [ ] **Step 2: Run the RED test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_contracts.py -q

Expected: FAIL because backend.app.domain.dynamic_yard is missing.

- [ ] **Step 3: Define frozen contract validators and transition predicate**

~~~python
class ForecastStage(StrEnum):
    PRE_DISCHARGE = "PRE_DISCHARGE"
    DISCHARGE_ACTIVE = "DISCHARGE_ACTIVE"

class ContainerReadyForecast(FrozenContract):
    container_id: str
    p10_ready_at: AwareDatetime
    p50_ready_at: AwareDatetime
    p90_ready_at: AwareDatetime
~~~

Validate zero UTC offset and p10 <= p50 <= p90. Define allowed_commitment_transition(current, target) for exactly PLANNED->COMMITTED/CANCELLED and COMMITTED->EXECUTED. Contracts use UUIDs and frozen tuples. Commitment uses origin_revision_id; current membership is AllocationRevision.allocated_container_ids.

- [ ] **Step 4: Run the GREEN test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_contracts.py -q

Expected: PASS for UTC/order, enums, immutable review options, and no reverse lifecycle.

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/domain/dynamic_yard.py backend/tests/test_dynamic_yard_contracts.py
git commit -m "feat: add dynamic yard contracts"
~~~

### Task 2: Dynamic-yard storage

**Files:**
- Create: backend/app/storage/dynamic_yard.py
- Create: backend/tests/test_dynamic_yard_repositories.py
- Modify: backend/tests/conftest.py

**Interfaces:**
- Produces DynamicYardRepository, DynamicYardConflict, DynamicYardHistory.
- Repository API: transaction, add_snapshot, get_snapshot_for_stage, active_revision, add_revision, list_commitments, transition_commitment, add_assessment, latest_unhandled_assessment, mark_assessment_handled, create_tradeoff_review, select_tradeoff_option, and incident histories.

- [ ] **Step 1: Write the failing test**

~~~python
def test_snapshot_retry_is_idempotent_and_conflicting_stage_is_rejected(session) -> None:
    assert repository.add_snapshot(snapshot) == repository.add_snapshot(snapshot)
    with pytest.raises(DynamicYardConflict, match="contradictory"):
        repository.add_snapshot(snapshot.model_copy(update={"source": "other"}))
~~~

- [ ] **Step 2: Run the RED test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_repositories.py -q

Expected: FAIL because DynamicYardRepository is missing.

- [ ] **Step 3: Define records, constraints, converters, and transactional repository methods**

Define `YardForecastSnapshotRecord(id, incident_id, stage, source, fingerprint, snapshot_json, generated_at_utc)`, with `UniqueConstraint("incident_id", "stage")`; `AllocationRevisionRecord(id, incident_id, source_phase2_evaluation_id, source_forecast_snapshot_id, parent_revision_id, allocated_container_ids_json, locked_container_ids_json, preserved_connection_total, expected_preserved_connections, reason, created_at_utc)`; and `ExpediteCommitmentRecord(id, incident_id, origin_revision_id, container_id, status, created_at_utc, updated_at_utc)`. Define `ExpediteReconsiderationAssessmentRecord` with unique `source_snapshot_id`, prior revision ID, candidate JSON, before/after totals, disposition, handled fields; review/option/selection records use unique `(review_id, option_id)` and one selection per review. `add_snapshot(snapshot) -> YardForecastSnapshot` returns an exact fingerprint retry and raises `DynamicYardConflict` for a different stage payload. `transaction()` follows the nested-safe `CarrierRecoveryRepository` counter pattern. `transition_commitment(id, target) -> ExpediteCommitment` calls Task 1's predicate; `select_tradeoff_option(review_id, command) -> AllocationTradeoffSelection` verifies exact open-review option/fingerprint before persist.

- [ ] **Step 4: Run the GREEN test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_repositories.py -q

Expected: PASS for rollback, lifecycle, retry, stale fingerprint, immutable revisions/options, and history order.

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/storage/dynamic_yard.py backend/tests/test_dynamic_yard_repositories.py backend/tests/conftest.py
git commit -m "feat: persist dynamic yard evidence"
~~~

### Task 3: Frozen-world projection

**Files:**
- Create: backend/app/evaluation/dynamic_yard.py
- Create: backend/tests/test_dynamic_yard_projection.py

**Interfaces:**
- Produces `reconstruct_phase2_worlds(report: ScarcityEvaluationReport, fixture: CanonicalIncidentFixture) -> ScenarioSet`, `projected_ready_at(profile: ContainerRecoveryProfile, world: ScenarioWorld, forecast: ContainerReadyForecast) -> datetime`, `DynamicYardEvaluator.evaluate_allocation(fixture: CanonicalIncidentFixture, scenarios: ScenarioSet, snapshot: YardForecastSnapshot, allocation: AllocationPlan) -> StrategyEvaluation`, and `connection_is_phase3_compatible(fixture: CanonicalIncidentFixture, scenarios: ScenarioSet, snapshot: YardForecastSnapshot, active_allocation: AllocationPlan, frozen_allocation: AllocationPlan, connection_id: str) -> bool`.

- [ ] **Step 1: Write the failing test**

~~~python
def test_unchanged_jv2_discharge_active_rows_reconstruct_phase_two(canonical_fixture, canonical_scenarios) -> None:
    assert max_ready_delta_seconds == 0.0

def test_projection_uses_positive_and_negative_quantile_branches(canonical_fixture, canonical_scenarios) -> None:
    assert projected_ready_at(profile, positive_world, forecast) == expected_early
    assert projected_ready_at(profile, negative_world, forecast) == expected_late
~~~

- [ ] **Step 2: Run the RED test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_projection.py -q

Expected: FAIL because the dynamic evaluator is missing.

- [ ] **Step 3: Implement exact world reconstruction and split-quantile functions**

~~~python
LATENT_STD_MINUTES = sqrt(12**2 + 7**2 + 2**2)
Z90 = 1.2815515655
z = combined_factor_minutes(profile, world) / LATENT_STD_MINUTES
~~~

Use the approved split formula and full timedelta precision. Regenerate exact seed/count worlds and compare index/factors. Reuse structural eligibility and capacity diagnostics, but derive readiness from forecast bands. Compatibility proves per-connection allocation membership and normal ready timestamps world by world.

- [ ] **Step 4: Run the GREEN test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_projection.py -q

Expected: PASS for no new RNG, factors, anchors, both branches, and positive/negative compatibility.

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/evaluation/dynamic_yard.py backend/tests/test_dynamic_yard_projection.py
git commit -m "feat: project dynamic yard forecasts"
~~~

### Task 4: Locked solver and disposition

**Files:**
- Create: backend/app/optimization/dynamic_yard.py
- Modify: backend/app/optimization/scarcity.py
- Create: backend/tests/test_dynamic_yard_optimizer.py

**Interfaces:**
- Produces `LockedAllocationSolver.solve(fixture: CanonicalIncidentFixture, scenarios: ScenarioSet, current_allocation: AllocationPlan, locked_container_ids: tuple[str, ...], evaluator: DynamicYardEvaluator) -> tuple[AllocationPlan, ...]` and `assess_reconsideration(incident_id: UUID, source_snapshot: YardForecastSnapshot, prior_revision: AllocationRevision, fixture: CanonicalIncidentFixture, scenarios: ScenarioSet, locked_container_ids: tuple[str, ...]) -> ExpediteReconsiderationAssessment`.

- [ ] **Step 1: Write the failing test**

~~~python
def test_canonical_assessment_is_same_snapshot_auto_supersede(canonical_fixture, canonical_scenarios) -> None:
    assert (assessment.preserved_total_before, assessment.preserved_total_after) == (601, 602)
    assert assessment.disposition is ReconsiderationDisposition.AUTO_SUPERSEDE
    assert {"SYN-CNT-002", "SYN-CNT-004"} <= set(assessment.candidate_options[0].allocated_container_ids)
~~~

- [ ] **Step 2: Run the RED test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_optimizer.py -q

Expected: FAIL because LockedAllocationSolver is missing.

- [ ] **Step 3: Implement locked CP-SAT solve and existing-policy disposition**

Extract only the current CP-SAT hard-constraint model builder into a reusable internal helper while leaving ScenarioAwareAllocator.solve unchanged. Force locks true, enumerate equal integer optima with existing solver settings, evaluate current/candidates under one snapshot, then pass safe evaluations through unchanged pareto_front and AllocationDominancePolicy.select. Return NO_CHANGE, AUTO_SUPERSEDE, or HUMAN_REVIEW_REQUIRED exactly as specified.

- [ ] **Step 4: Run the GREEN test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_optimizer.py backend/tests/test_scarcity_optimizer.py -q

Expected: PASS for no-change, auto, human tradeoff, locks, capacity/group/reefer/DG, and unchanged Phase 2 allocation.

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/optimization/dynamic_yard.py backend/app/optimization/scarcity.py backend/tests/test_dynamic_yard_optimizer.py
git commit -m "feat: solve locked yard allocations"
~~~

### Task 5: Workflow and atomic revision path

**Files:**
- Create: backend/app/orchestration/dynamic_yard.py
- Create: backend/tests/test_dynamic_yard_workflow.py

**Interfaces:**
- Produces `DynamicYardWorkflow.for_session(session) -> DynamicYardWorkflow`, `initialize(incident_id: UUID, snapshot: YardForecastSnapshot) -> DynamicYardHistory`, `ingest(snapshot: YardForecastSnapshot) -> ExpediteReconsiderationAssessment`, `apply_latest_assessment(incident_id: UUID, run_id: UUID) -> AllocationRevision | AllocationTradeoffReview | None`, `select_tradeoff(review_id: UUID, command: AllocationTradeoffSelectionCommand) -> AllocationRevision`, `phase3_compatible(incident_id: UUID, connection_id: str) -> bool`, `compatible_connection_ids(incident_id: UUID) -> tuple[str, ...]`, and `history(incident_id: UUID) -> DynamicYardHistory`.

- [ ] **Step 1: Write the failing test**

~~~python
def test_auto_supersede_keeps_r0_cancels_005_and_creates_001(session) -> None:
    result = workflow.apply_latest_assessment(incident.id, run.id)
    assert result.revision.parent_revision_id == r0.id
    assert commitment("SYN-CNT-005").status is ExpediteCommitmentStatus.CANCELLED
    assert commitment("SYN-CNT-001").status is ExpediteCommitmentStatus.PLANNED
~~~

- [ ] **Step 2: Run the RED test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_workflow.py -q

Expected: FAIL because DynamicYardWorkflow is missing.

- [ ] **Step 3: Implement reusable workflow methods and exact atomic operations**

`initialize` accepts only a PRE_DISCHARGE typed snapshot for a resolved incident with a persisted selected Phase 2 report. In one repository transaction it persists the snapshot, writes R0 referencing its report/snapshot, creates eight PLANNED commitments from selected allocation, transitions only 002/004 to COMMITTED, and appends audit links. It contains no canonical times. `ingest` persists an idempotent typed snapshot; for DISCHARGE_ACTIVE it reconstructs worlds, calls `assess_reconsideration`, and persists exactly one unhandled assessment. `apply_latest_assessment` handles NO_CHANGE; for AUTO_SUPERSEDE stages `add_revision`, cancels every displaced active PLANNED commitment, creates only replacement PLANNED commitments, marks assessment handled, and commits once; for HUMAN_REVIEW_REQUIRED writes/reuses immutable review/options then marks assessment handled by review. `select_tradeoff` validates the repository selection command and runs that same child-revision transaction. `compatible_connection_ids` iterates fixture connections and returns only `phase3_compatible == True`; it contains no carrier invocation. All durable operations emit SYSTEM/SOLVER/POLICY audit links through existing `AuditService`.

- [ ] **Step 4: Run the GREEN test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_workflow.py backend/tests/test_dynamic_yard_repositories.py -q

Expected: PASS for crash rollback/retry, R0/R1 immutability, origin semantics, selection, no-change, and terminal audit-only ingestion.

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/orchestration/dynamic_yard.py backend/tests/test_dynamic_yard_workflow.py
git commit -m "feat: orchestrate dynamic yard revisions"
~~~

### Task 6: Canonical harness and APIs

**Files:**
- Create: backend/app/services/dynamic_yard.py
- Modify: backend/app/main.py
- Create: backend/tests/test_dynamic_yard_api.py

**Interfaces:**
- Produces `CanonicalDynamicYardHarness.bootstrap_snapshot(incident_id: UUID) -> YardForecastSnapshot` and `discharge_active_snapshot(incident_id: UUID) -> YardForecastSnapshot`; harness methods construct fixed values only and do not persist or optimise. `main.py` routes call the Task 5 workflow with those typed snapshots.

- [ ] **Step 1: Write the failing test**

~~~python
def test_harness_exposes_no_request_body_and_tightens_forecast_bands(client) -> None:
    assert "requestBody" not in openapi_post("/synthetic/scenarios/{incident_id}/dynamic-yard/bootstrap")
    assert pre_width_minutes == 30
    assert active_width_minutes == 17.987433384504683
~~~

- [ ] **Step 2: Run the RED test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_api.py -q

Expected: FAIL because the harness and routes are absent.

- [ ] **Step 3: Implement fixed snapshot builders and exact FastAPI route contracts**

`CanonicalDynamicYardHarness` uses `SyntheticCanonicalIncidentService.load()` and returns `YardForecastSnapshot` only: PRE has every base-ready p50 ±30 minutes; ACTIVE has every base-ready p50 ±17.987433384504683 minutes except 005 p50 05:56Z. It imports neither repository nor optimiser nor agent runtime. Route contract: `POST /synthetic/scenarios/{incident_id}/dynamic-yard/bootstrap` calls `workflow.initialize(incident_id, harness.bootstrap_snapshot(incident_id))`; `POST /synthetic/scenarios/{incident_id}/dynamic-yard/discharge-active` calls `workflow.ingest(harness.discharge_active_snapshot(incident_id))`; `GET /incidents/{incident_id}/yard-forecast-snapshots`; `GET /incidents/{incident_id}/allocation-revisions`; `GET /incidents/{incident_id}/expedite-commitments`; `GET /incidents/{incident_id}/expedite-reconsiderations`; `GET /incidents/{incident_id}/allocation-tradeoff-reviews`; and `POST /allocation-tradeoff-reviews/{review_id}/selection` accepting frozen `AllocationTradeoffSelectionBody(selected_option_id: UUID, expected_options_fingerprint: str, operator_id: str)`. Synthetic POST handlers reject non-empty request bodies and expose no OpenAPI requestBody. Map missing/conflict/validation to 404/409/422.

- [ ] **Step 4: Run the GREEN test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_api.py -q

Expected: PASS for OpenAPI, retry, widths, 005->001, 601->602, and error mapping.

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/services/dynamic_yard.py backend/app/main.py backend/tests/test_dynamic_yard_api.py
git commit -m "feat: add dynamic yard harness api"
~~~

### Task 7: Phase 3 compatibility facade

**Files:**
- Modify: backend/app/orchestration/agent_context.py
- Modify: backend/app/orchestration/agent_runtime.py
- Create: backend/tests/test_dynamic_yard_phase3_compatibility.py

**Interfaces:**
- Consumes DynamicYardWorkflow.phase3_compatible.
- Produces connection-specific registry filtering and execution revalidation of prepare_rta_request(connection_id).

- [ ] **Step 1: Write the failing test**

~~~python
@pytest.mark.parametrize("change", ["membership", "projected_evidence"])
def test_incompatible_prepare_is_hidden_and_direct_attempt_is_rejected(session, change) -> None:
    assert "prepare_rta_request" not in tool_names
    assert latest_invocation.status is AgentToolInvocationStatus.REJECTED

def test_jv2_remains_compatible_with_existing_affected_set(session) -> None:
    assert prepare_jv2().affected_container_ids == ("SYN-CNT-017",)
~~~

- [ ] **Step 2: Run the RED test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_phase3_compatibility.py -q

Expected: FAIL because the compatibility facade is absent.

- [ ] **Step 3: Implement compatible-connection schema filtering and direct-call revalidation**

Extend `_tool(name, description, required=(), string_enums: dict[str, tuple[str, ...]] | None = None) -> AgentToolDefinition`; an enum-valued required string serializes as `{"type": "string", "enum": list(values)}`. When no Phase 5B state exists, retain current Phase 5A `prepare_rta_request` schema. When state exists and `latest_unhandled_assessment` is absent, call `compatible_connection_ids`: omit prepare for an empty tuple; otherwise expose `prepare_rta_request` with `connection_id` enum exactly equal to that tuple. Include `compatible_connection_ids` in `AgentTurnContext.summary["dynamic_yard"]`. In `_execute_turn`, call `phase3_compatible(run.incident_id, arguments["connection_id"])` immediately before the unchanged trusted `prepare_command`/Phase 3 call; false raises the existing durable rejection path. Canonical ACTIVE state yields JV2 only, with `SYN-CONN-JV2` permitted and SF1 excluded. Do not edit any Phase 3 module.

- [ ] **Step 4: Run the GREEN test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_phase3_compatibility.py backend/tests/test_carrier_recovery_workflow.py backend/tests/test_carrier_recovery_recomputation.py -q

Expected: PASS for canonical JV2 and changed membership/evidence negatives.

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/orchestration/agent_context.py backend/app/orchestration/agent_runtime.py backend/tests/test_dynamic_yard_phase3_compatibility.py
git commit -m "feat: guard carrier preparation against yard evidence"
~~~

### Task 8: Agent feasibility, waits, and stale-plan gate

**Files:**
- Modify: backend/app/orchestration/agent_context.py
- Modify: backend/app/orchestration/agent_runtime.py
- Modify: backend/app/domain/agent_runtime.py only for required bounded context/history fields
- Create: backend/tests/test_dynamic_yard_agent_runtime.py
- Modify: backend/tests/test_agent_runtime_workflow.py
- Modify: backend/tests/test_agent_context.py

**Interfaces:**
- Produces request_expedite_feasibility(), dynamic context evidence, NEW_OPERATIONAL_EVIDENCE resolution, stale-plan filtering, and completion guard.

- [ ] **Step 1: Write the failing test**

~~~python
def test_feasibility_tool_has_zero_arguments_and_applies_once(session) -> None:
    assert tool.parameters == {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    assert active_revision.allocated_container_ids[0] == "SYN-CNT-001"

def test_stronger_wait_is_not_preempted_and_no_change_blocks_completion(session) -> None:
    assert run.wait_kind is AgentWaitKind.REQUEST_APPROVAL
    with pytest.raises(AgentRuntimeConflict, match="actionable"):
        coordinator._execute_turn(run, "complete_agent_run", {})

def test_human_tradeoff_wait_resumes_only_after_valid_selection(session) -> None:
    assert coordinator.advance(run.id).wait_kind is AgentWaitKind.HUMAN_TRADEOFF_DECISION
    with pytest.raises(AgentRuntimeConflict, match="unresolved"):
        coordinator.advance(run.id)
    selection_api(review.id, exact_selection)
    assert coordinator.advance(run.id).state is AgentRunState.RUNNING

def test_invalid_selection_and_ingestion_do_not_run_model(session) -> None:
    with pytest.raises(DynamicYardConflict):
        selection_api(review.id, stale_selection)
    assert fake_model.calls == calls_before_ingest
~~~

- [ ] **Step 2: Run the RED test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_agent_runtime.py backend/tests/test_agent_context.py -q

Expected: FAIL because dynamic agent integration is absent.

- [ ] **Step 3: Implement exact evidence and human-review wait transitions**

Expose `request_expedite_feasibility` using `_tool("request_expedite_feasibility", "Apply the latest deterministic expedite reconsideration.", ())` only for an unhandled assessment with no stronger wait. `pause_agent_run` may set `WAITING/NEW_OPERATIONAL_EVIDENCE` only when `history` proves initialized PRE and no ACTIVE snapshot. Ingestion never calls the model or updates a stronger wait. On the next explicit `advance`, `_resolve_wait` for NEW_OPERATIONAL_EVIDENCE loads `latest_unhandled_assessment`; if present it clears state to RUNNING with null wait fields, otherwise returns unresolved conflict. A feasibility HUMAN result sets `WAITING/HUMAN_TRADEOFF_DECISION` and exact review UUID in `wait_subject_id`. `_resolve_wait` for that kind loads the review UUID, requires `state == RESOLVED`, one valid persisted selection, and completed assessment/revision transition; only then clears wait fields and returns RUNNING. An open/stale/invalid review remains WAITING and advance returns existing unresolved conflict. Retried advance after resolution observes the durable resolved review and is safe. With an unhandled assessment, hide unrelated mutations, keep reads/feasibility/safe controls, revalidate execution, and extend `_actionable_work_remains`; terminal runs receive audit evidence only.

- [ ] **Step 4: Run the GREEN test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_agent_runtime.py backend/tests/test_agent_runtime_workflow.py backend/tests/test_agent_context.py -q

Expected: PASS for no-change/auto/human paths; unresolved human review; valid selection resume; stale selection non-resume; selection and ingestion making zero model calls; safe retry; stronger-wait priority; terminal non-resurrection; and completion block.

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/domain/agent_runtime.py backend/app/orchestration/agent_context.py backend/app/orchestration/agent_runtime.py backend/tests/test_dynamic_yard_agent_runtime.py backend/tests/test_agent_runtime_workflow.py backend/tests/test_agent_context.py
git commit -m "feat: handle dynamic yard agent evidence"
~~~

### Task 9: Canonical cross-phase hero

**Files:**
- Create: backend/tests/test_dynamic_yard_canonical_hero.py

**Interfaces:**
- Consumes Tasks 1-8 plus unchanged Phase 3/4 fake helpers.
- Produces one deterministic same-run acceptance test.

- [ ] **Step 1: Write the failing test**

~~~python
def test_dynamic_yard_then_jv2_counter_then_safety_escalation(session) -> None:
    yard.initialize(incident.id, harness.bootstrap_snapshot(incident.id))
    assert runtime.advance(run.id).wait_kind is AgentWaitKind.NEW_OPERATIONAL_EVIDENCE
    yard.ingest(harness.discharge_active_snapshot(incident.id))
    runtime.advance(run.id)
    assert active_ids == ("SYN-CNT-001", "SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-010", "SYN-CNT-011", "SYN-CNT-012", "SYN-CNT-014", "SYN-CNT-015")
    assert prepare_jv2().affected_container_ids == ("SYN-CNT-017",)
    assert finish_counter_and_safety().escalation_reason is AgentEscalationReason.SAFETY_REVIEW_REQUIRED
~~~

- [ ] **Step 2: Run the RED test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_canonical_hero.py -q

Expected: FAIL until all Phase 5B capability is integrated.

- [ ] **Step 3: Wire only the already-defined Task 5/6/7/8 interfaces into the acceptance fixture**

Create the fixture with `DynamicYardWorkflow.for_session`, `CanonicalDynamicYardHarness`, the existing fake agent model, and existing Phase 3 approval/counter plus Phase 4 fake checker. Call only `initialize`, `ingest`, `advance`, and existing carrier/safety methods already defined in Tasks 5-8. If the test cannot call one of those signatures, add the missing import/wiring at the defined integration boundary only; do not introduce a new production method or special hero branch. Assert 601->602, 002/004 committed, 005 cancelled, 001 planned, JV2 enum availability, and SYN-CNT-017.

- [ ] **Step 4: Run the GREEN test**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_canonical_hero.py backend/tests/test_agent_runtime_workflow.py backend/tests/test_carrier_recovery_workflow.py -q

Expected: PASS with no network call or Phase 3 rewrite.

- [ ] **Step 5: Commit**

~~~bash
git add backend/tests/test_dynamic_yard_canonical_hero.py
git commit -m "test: cover dynamic yard canonical hero"
~~~

### Task 10: Verification and scope freeze

**Files:**
- Modify: docs/coordination/logs/win-codex.md only after all checks pass

**Interfaces:**
- Produces verification evidence only.

- [ ] **Step 1: Run focused Phase 5B tests**

Run: uv run --python 3.12 --extra dev pytest backend/tests/test_dynamic_yard_contracts.py backend/tests/test_dynamic_yard_repositories.py backend/tests/test_dynamic_yard_projection.py backend/tests/test_dynamic_yard_optimizer.py backend/tests/test_dynamic_yard_workflow.py backend/tests/test_dynamic_yard_api.py backend/tests/test_dynamic_yard_phase3_compatibility.py backend/tests/test_dynamic_yard_agent_runtime.py backend/tests/test_dynamic_yard_canonical_hero.py -q

Expected: PASS with zero network calls.

- [ ] **Step 2: Run full backend regression**

Run: uv run --python 3.12 --extra dev pytest backend/tests -q

Expected: PASS, retaining Phase 2 allocation, Phase 3 SYN-CNT-017, Phase 4 safety, and Phase 5A waits.

- [ ] **Step 3: Verify lockfile and scope**

~~~bash
uv lock --check
git diff --check
git diff --name-only bedf0d013af3be2198c52ec3ced9cf54cc0627f9..HEAD
~~~

Expected: all succeed and no changed path starts with web/.

- [ ] **Step 4: Record verification outcome**

Append exact commands, test counts/warnings, no-network evidence, 601->602 result, and scope result to docs/coordination/logs/win-codex.md.

- [ ] **Step 5: Commit**

~~~bash
git add docs/coordination/logs/win-codex.md
git commit -m "docs: record Phase 5B verification"
~~~

## Plan self-review

- Tasks 1-9 map to all approved specification sections; Task 10 covers freeze.
- Dedicated tests cover NO_CHANGE, AUTO_SUPERSEDE, HUMAN_REVIEW_REQUIRED, crash/retry, wait priority, Phase 3 positive/negative compatibility, and canonical metrics.
- Dependency order is contracts, persistence, projection, solver, workflow, API, compatibility, agent, hero, verification.
- No frontend task or Phase 3 internal redesign appears.
- The decomposition is hackathon-grade: one additive domain/repository/workflow boundary, fixed fixtures, no new dependency, worker, or event-sourcing framework.
