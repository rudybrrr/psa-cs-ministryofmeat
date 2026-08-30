# PSA Transshipment Recovery

**Container-level recovery orchestration for broken transshipment connections.**
PSA Code Sprint 2.0 · All data synthetic · Python + FastAPI + OR-Tools CP-SAT + React 19

---

> 24 transhipment containers are at risk. Thirteen could benefit from expedited handling.
> The terminal has capacity for eight. The onward carrier has not agreed to adjust its timing.

When a mainline vessel arrives late, containers booked onto onward services can no longer make
their connections. This system manages that exception **container by container**: it allocates
scarce yard capacity under forecast uncertainty, negotiates a later berth time with the onward
carrier under DCSA-shaped authority, rolls what cannot be saved, escalates what cannot be decided
safely, and leaves a complete audit trace behind every action.

It does not predict the delay, replace the TOS, or optimise the berth plan. Those systems exist.
It handles what happens to the box *after* the plan has already broken.

---

## Contents

| Section | |
|---|---|
| **[1 · Architecture](#1--architecture)** | Layers, module map, contracts, persistence, API surface |
| **[2 · Execution flow](#2--execution-flow)** | End-to-end trace of the canonical incident, the agent turn loop, request lifecycle |
| **[3 · Key decisions](#3--key-decisions)** | Decision register: what was chosen, why, and what was rejected |
| **[4 · Impact](#4--impact)** | Measured allocator improvement, evidence package, what the numbers do and do not claim |
| **[5 · Security, safety & scalability](#5--security-safety--scalability)** | Threat handling, safety invariants, measured scaling limits |
| [Canonical incident](#the-canonical-incident) · [Running locally](#running-locally) · [Tests](#tests) · [Configuration](#configuration) · [Deployment](#deployment) · [Limitations](#honest-limitations) · [Docs](#documentation-map) | |

---

# 1 · Architecture

## The organising principle

**The agent's tool list encodes organisational authority. Actions PSA cannot take do not exist as
tools.**

A model cannot hallucinate an authority it has no tool for. This is the load-bearing design
decision of the whole system, and it is enforced structurally, not by prompting: the tool registry
(`backend/app/orchestration/agent_context.py`) recomputes the exposed tool set from durable typed
state on **every turn**, and the runtime rejects any tool name outside that set.

| Exists as a tool | Does **not** exist, at any layer |
|---|---|
| `get_incident_context`, `get_scarcity_evaluation`, `get_carrier_recovery_cases`, `get_carrier_recovery_history`, `get_cargo_safety_reviews` | `hold_feeder()` — PSA cannot order another company's feeder to wait |
| `request_expedite_feasibility` — apply the deterministic expedite reconsideration | `change_carrier_schedule()` — carrier schedules are never mutated locally |
| `prepare_rta_request` — prepare a DCSA-shaped timing request (never sends) | `override_dg_rule()` — DG constraints are not negotiable by a model |
| `send_authorised_rta_request` — send an **already operator-approved** request | `set_yard_capacity()` — capacity is evidence, not an agent lever |
| `evaluate_carrier_timeout` — record a due timeout using the trusted clock | *(also absent)* any tool that approves, selects a trade-off, or classifies cargo |
| `request_cargo_safety_review` — run the semantic check on a **persisted** review | |
| `pause_agent_run`, `complete_agent_run`, `escalate_agent_run` | |

The four forbidden names are asserted as a verified evidence claim
(`agent_no_unavailable_tool_execution`), not merely documented.

## Layers

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  web/  React 19 + Vite + Tailwind v4                                         │
│  OperationsConsole → useRecoveryConsole() → typed API clients                 │
│  Guided · Auto · Explore modes over one canonical replay stage projector      │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │  HTTP (JSON), Vite dev proxy → :8000
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  backend/app/main.py   FastAPI app factory, CORS allowlist, /healthz          │
├──────────────────────────────────────────────────────────────────────────────┤
│  orchestration/   workflows — the ONLY writers of durable state               │
│    state_machine · scarce_capacity · dynamic_yard · carrier_recovery ·        │
│    cargo_safety · agent_runtime · agent_context · canonical_replay (read-only)│
├──────────────────────────────────────────────────────────────────────────────┤
│  policies/            deterministic decision authority                        │
│    dominance · allocation_dominance (Pareto front) · baseline (P50 greedy)    │
│  optimization/        OR-Tools CP-SAT — scarcity · dynamic_yard               │
│  evaluation/          scarcity evaluator · holdout benchmark · Phase-8        │
│                       evidence suite · Phase-9 live provider harness          │
├──────────────────────────────────────────────────────────────────────────────┤
│  domain/     frozen Pydantic contracts (extra="forbid", frozen=True)          │
│  services/   synthetic adapters: schedule · manifest · yard · carrier ·       │
│              scenarios · canonical fixture · agent model · semantic checker   │
│  storage/    SQLModel repositories over SQLite  ·  audit/  append-only log    │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Layering rules that actually hold in the code:**

- `domain/` imports nothing from the layers above it. Every contract is a frozen Pydantic model with
  `extra="forbid"`, so an unexpected field is a validation error, not silent data.
- Only `orchestration/` writes. Repositories persist; policies and optimisers are pure functions
  over contracts; services are read-only synthetic adapters.
- The LLM sits behind two narrow protocols — `AgentModel.decide(context, tools)` and
  `SemanticSafetyChecker.check(evidence)`. Both have deterministic, credential-free implementations,
  which is why the entire test suite and the whole evidence package run offline.
- `orchestration/canonical_replay.py` is a **read-only projector**: it derives the demo stage purely
  from persisted state and writes nothing — no tables, no audit events.

## Module map

```
backend/app/
  main.py                    FastAPI app factory: 38 routes, CORS validation, health probe
  domain/                    frozen contracts + enums
    models.py                Incident, Container, Decision, Approval, AuditEvent, …
    scarcity.py              fixture, scenarios, allocation plans, evaluations
    carrier_recovery.py      case/request/approval/timing contracts + case FSM
    dynamic_yard.py          forecast snapshots, allocation revisions, commitments
    cargo_safety.py          notes, semantic assessments, policy results
    agent_runtime.py         runs, steps, tool invocations, wait/escalation kinds
    canonical_replay.py      16-stage demo projection vocabulary
    evidence.py              Phase-8 evidence claim contracts
    live_evidence.py         Phase-9 live provider evidence contracts
  orchestration/             workflows (the only writers)
  policies/                  dominance, Pareto front, P50-greedy baseline
  optimization/              CP-SAT models
  evaluation/                evaluators, benchmark CLI, evidence CLIs
  services/                  synthetic adapters + provider clients
  storage/                   SQLModel records and repositories
  audit/                     append-only audit service
web/src/
  api/                       typed clients, one module per bounded context
  components/command-center/ dashboard shell, sidebar, chapters, workspaces
  hooks/                     useRecoveryConsole (state+commands), useAutoReplay
  lib/                       selectors, chapter mapping, formatters, persistence
  styles/tokens.css          PSA dark terminal design tokens
shared/fixtures/             canonical synthetic data
docs/                        specs, per-phase plans, coordination, evaluations, deployment
```

## Contracts and invariants

Every contract inherits `FrozenContract` (`extra="forbid"`, `frozen=True`) — immutable, and
unexpected fields are errors.

| Enum | Values |
|---|---|
| `IncidentState` | INCIDENT_RECEIVED · COLLECTING_STATE · CONSTRAINT_VALIDATION · RECOVERY_ANALYSIS · RESOLVED · ESCALATED |
| `DecisionAction` | EXPEDITE · REQUEST_RTA · ROLL · ESCALATE · PRESERVE_VIA_RTA |
| `DecisionStatus` | PROPOSED · APPROVED · REJECTED · SUPERSEDED |
| `AuditActor` | AGENT · SOLVER · POLICY · OPERATOR · CARRIER · SYSTEM |
| `CarrierResponseType` | ACCEPT · COUNTER *(silence is absence, not a value)* |
| `ForecastStage` | PRE_DISCHARGE · DISCHARGE_ACTIVE |
| `ReconsiderationDisposition` | NO_CHANGE · AUTO_SUPERSEDE · HUMAN_REVIEW_REQUIRED |
| `SemanticCheckResult` | NO_CONTRADICTION_FOUND · CONTRADICTION_FOUND · INDETERMINATE · CHECK_FAILED |

**Invariants enforced in contracts, not comments:**

- `ServiceWindow.ready_boundary` must equal PTA + 35 minutes.
- Forecast quantiles must satisfy `p10 ≤ p50 ≤ p90`, all with explicit UTC offsets.
- `AllocationRevision.locked_container_ids ⊆ allocated_container_ids`; no duplicates anywhere.
- `AgentRun` in `WAITING` requires a `wait_kind`; not-`WAITING` forbids one. Same for
  `ESCALATED` / `escalation_reason`.
- `AgentModelTurn` requires **exactly one** of `tool_call` or `control`.
- Timestamps crossing a trust boundary must be explicit UTC (`Z` or `+00:00`); naive datetimes are
  rejected at parse time.
- `ContainerReconsiderationResult` requires exactly one typed evidence reference matching its kind.
- `reproducibility_key` and `options_fingerprint` are exactly 64 characters.

**Decision lineage.** Decisions are never mutated. A new decision `supersedes` the prior one with a
recorded `supersession_reason`, so "the current decision" is a derived view over an append-only
history.

## Persistence

SQLite via SQLModel; `DATABASE_URL` selects the target (local file, or a `/data` volume in
production). 33 tables:

| Group | Tables |
|---|---|
| Core | `incidents`, `decisions`, `audit_events`, `scarcity_evaluations` |
| Carrier recovery | `carrier_recovery_cases` *(unique `incident_id, connection_id`)*, `rta_requests`, `rta_request_contexts` *(unique `case_id`)*, `approvals`, `approval_bindings`, `carrier_responses`, `carrier_simulation_receipts`, `effective_connection_timings`, `carrier_recovery_decision_links`, `container_reconsideration_results` *(unique `case_id, container_id`)*, `carrier_recovery_audit_links` |
| Dynamic yard | `yard_forecast_snapshots` *(unique `incident_id, stage`)*, `allocation_revisions`, `expedite_commitments`, `expedite_reconsideration_assessments` *(unique `source_snapshot_id`)*, `allocation_tradeoff_reviews`, `allocation_tradeoff_options`, `allocation_tradeoff_selections` |
| Cargo safety | `cargo_notes`, `cargo_safety_reviews` *(unique `cargo_note_id`)*, `semantic_safety_assessments`, `semantic_safety_policy_results`, `cargo_safety_audit_links` |
| Agent runtime | `agent_runs`, `agent_steps`, `agent_tool_invocations`, `agent_audit_links` |

Idempotency is database-level, not advisory: unique constraints back every "exactly once" claim, and
workflows reconcile `IntegrityError` races by re-reading and comparing the durable record.
`audit_events` is append-only — nothing updates or deletes a row.

## API surface

38 routes; FastAPI serves interactive docs at `/docs`. Mutating endpoints are idempotent — an
identical replay returns `200` with the same record, a contradictory replay returns `409`.
Endpoints that take no body **reject** a body with `422` rather than ignoring it.

| Group | Routes |
|---|---|
| Health & scenarios | `GET /healthz` · `POST /synthetic/scenarios/schedule-delay` · `POST /synthetic/scenarios/canonical-scarcity` · `GET …/canonical-scarcity/fixture` |
| Incident | `GET /incidents/{id}` · `/decisions` · `/audit-events` · `/scarcity-evaluation` |
| Dynamic yard | `POST …/dynamic-yard/bootstrap` · `POST …/dynamic-yard/discharge-active` · `GET /incidents/{id}/{yard-forecast-snapshots,allocation-revisions,expedite-commitments,expedite-reconsiderations,allocation-tradeoff-reviews,allocation-tradeoff-options}` · `POST /allocation-tradeoff-reviews/{id}/selection` |
| Carrier recovery | `POST /incidents/{id}/carrier-recovery-cases` · `POST /carrier-recovery-cases/{id}/{request-approval,send,simulate-carrier-response,counter-approval,evaluate-timeout}` · `GET …/{id}` · `GET …/{id}/history` |
| Cargo safety | `POST /incidents/{id}/cargo-safety-reviews` · `POST /cargo-safety-reviews/{id}/evaluate` · `GET …/{id}` · `GET …/{id}/history` |
| Agent & replay | `POST /incidents/{id}/agent-runs` · `POST /agent-runs/{id}/advance` · `GET /agent-runs/{id}/history` · `POST …/canonical-replay/agent-runs` · `GET …/canonical-replay/stage` |

---

# 2 · Execution flow

## The canonical incident, end to end

This is the actual observed run — the tool order and terminal state below are asserted as verified
evidence claims (`agent_successful_tool_order`, `agent_step_count` = 6,
`agent_terminal_state` = `ESCALATED / SAFETY_REVIEW_REQUIRED`), not an idealised diagram.

| # | Stage | Who acts | What happens | Persisted |
|---:|---|---|---|---|
| 1 | `READY_TO_CREATE` | Operator | ASX-17 slips 195 min. Fixture loads 24 containers across SF1/JV2/EC3. **Scenario generation** builds 50 antithetic worlds. **CP-SAT** proves the optimal 8-slot allocation and enumerates *all* optima. Dominance policy selects. | `Incident`, `ScarcityEvaluationReport`, per-container `Decision`s, audit chain |
| 2 | `READY_FOR_PRE_DISCHARGE` | Operator | `PRE_DISCHARGE` yard forecast (p10/p50/p90 bands) ingested; revision **R0** derived from the frozen selected allocation. Two containers are already physically committed. | `YardForecastSnapshot`, `AllocationRevision` R0, 8 × `ExpediteCommitment` |
| 3 | `READY_TO_START_AGENT` | Operator | Agent run created against the incident. | `AgentRun` (`CREATED`) |
| 4 | `READY_TO_ADVANCE_TO_EVIDENCE_WAIT` | **Agent** | Registry exposes `pause_agent_run` because `PRE_DISCHARGE` exists without `DISCHARGE_ACTIVE`. Agent pauses rather than acting on stale forecasts. → `WAITING / NEW_OPERATIONAL_EVIDENCE` | `AgentStep` 1, `AgentToolInvocation` |
| 5 | `WAITING_FOR_ACTIVE_EVIDENCE` | Yard | `DISCHARGE_ACTIVE` snapshot arrives; bands tighten. Reconsideration assessment computed against the frozen Phase-2 worlds. | `YardForecastSnapshot`, `ExpediteReconsiderationAssessment` |
| 6 | `READY_TO_RECONSIDER` | **Agent** | Wait resolves. `request_expedite_feasibility` applies the deterministic reconsideration: R0 → **R1**. `SYN-CNT-005` (planned) is displaced by `SYN-CNT-001`; the two committed slots are untouchable. | `AllocationRevision` R1, commitment transitions, audit |
| 7 | `READY_TO_PREPARE_RTA` | **Agent** | Carrier tools unlock only now that no unhandled evidence remains. `prepare_rta_request` on JV2 — a connection whose containers are preserved in **zero of 50 worlds**. Backend supplies all timestamps. → `WAITING / REQUEST_APPROVAL` | `CarrierRecoveryCase`, `RTARequest`, `RTARequestContext` + payload fingerprint |
| 8 | `REQUEST_APPROVAL_REQUIRED` | **Human** | Operator approves the exact payload. Approval is bound to the fingerprint; a mismatch is a `409`. **The agent has no approval tool.** | `Approval`, `ApprovalBinding` |
| 9 | `REQUEST_APPROVED_READY_TO_SEND` | **Agent** | `send_authorised_rta_request` — permitted *only* because a durable matching approval exists. → `WAITING / CARRIER_RESPONSE_OR_TIMEOUT` | `RTARequestContext.sent_at` |
| 10 | `WAITING_FOR_CARRIER` | Carrier | Carrier may ACCEPT, COUNTER, or stay silent. Silence writes **nothing**; only an explicit `SYSTEM` timeout would create evidence. | — (or `CarrierResponse`) |
| 11 | `CARRIER_COUNTER_RECEIVED` | Carrier | COUNTER arrives with an alternative PTA. Its timing is **not yet effective**. | `CarrierResponse` |
| 12 | `COUNTER_APPROVAL_REQUIRED` | **Human** | Second approval gate: the counter-proposal needs its own fingerprint-bound operator approval. | `Approval`, `ApprovalBinding` |
| 13 | `COUNTER_APPROVED_READY_TO_RESUME` | System | Timing becomes effective. Frozen worlds replay against the new boundary; each container gets one typed reconsideration result and a superseding decision. | `EffectiveConnectionTiming`, `ContainerReconsiderationResult`, replacement `Decision`s |
| 14 | `READY_FOR_SAFETY_EVIDENCE` | Operator | A free-text cargo note on `SYN-CNT-010` is persisted — declared general cargo, note says corrosive. | `CargoNote`, `CargoSafetyReview` (`PENDING_CHECK`) |
| 15 | `SAFETY_REVIEW_PENDING` | **Agent** | `request_cargo_safety_review` runs the semantic checker. It reports a **contradiction as evidence** — it cannot classify, infer a UN number, or recommend. | `SemanticSafetyAssessment` |
| 16 | `SAFETY_BLOCKED` | **Policy** | Frozen policy converts evidence → `ESCALATE`, `automation_blocked = true`, superseding the container's prior decision. Run terminates `ESCALATED / SAFETY_REVIEW_REQUIRED`. | `SemanticSafetyPolicyResult`, `ESCALATE` `Decision`, audit |

**Three moments where the design shows itself:** the agent *pauses* at step 4 rather than acting on
stale evidence; it *stops* at steps 8 and 12 because approval is not a tool it has; and it *refuses
to resolve* at step 16, escalating instead of deciding.

## The agent turn loop

`advance()` runs at most 8 tool turns per call (`max_steps` = 12 for the run):

```
advance(run_id)
  ├─ recover any PENDING invocation      → idempotent replay, or escalate TOOL_FAILURE
  ├─ if WAITING: resolve the typed wait  → unresolved ⇒ 409, never a busy loop
  └─ loop (≤8):
       build_agent_turn_context()   compact typed evidence — no raw prose
       available_tools()            recomputed from durable state THIS turn
       model.decide(ctx, tools)     one retry on provider failure or invalid turn
       ├─ tool not in exposed set → escalate INVALID_MODEL_OUTPUT
       └─ execute → guards → persist step + invocation → update run
     budget exhausted → escalate STEP_BUDGET_EXCEEDED
```

**Guards inside execution**, applied before any side effect:

- An unhandled dynamic-yard assessment blocks all three carrier-mutating tools — removed from the
  tool set *and* rejected at execution time (defence in depth).
- `prepare_rta_request` revalidates Phase-3 compatibility against current forecast evidence.
- `evaluate_carrier_timeout` requires the trusted clock to be past the deadline **and** no carrier
  response to exist.
- `complete_agent_run` is rejected while any actionable work remains — unhandled assessment, open
  trade-off review, non-terminal carrier case, or pending safety review.

**Wait kinds** — a run parks on a typed condition instead of polling blindly:

| Wait kind | Resolved by |
|---|---|
| `NEW_OPERATIONAL_EVIDENCE` | a `DISCHARGE_ACTIVE` snapshot producing an unhandled assessment |
| `REQUEST_APPROVAL` | a durable operator `Approval` on the outbound request |
| `CARRIER_RESPONSE_OR_TIMEOUT` | a carrier response, or the trusted clock passing the deadline |
| `COUNTER_APPROVAL` | operator approval of the carrier's counter-proposal |
| `HUMAN_TRADEOFF_DECISION` | an operator selection matching the exact options fingerprint |

**Escalation reasons:** `SAFETY_REVIEW_REQUIRED`, `MISSING_EVIDENCE`, `TOOL_FAILURE`,
`MODEL_UNAVAILABLE`, `INVALID_MODEL_OUTPUT`, `AGENT_LOOP_GUARD`, `STEP_BUDGET_EXCEEDED`,
`UNRESOLVED_TRADEOFF`.

**Crash recovery.** A `PENDING` invocation at the start of `advance` means the process died
mid-tool. Exactly one pending `send_authorised_rta_request` is recovered idempotently; anything else
escalates as `TOOL_FAILURE`. The system never re-drives an ambiguous external side effect.

## Request lifecycle

Every mutation follows the same path, and the frontend never holds authoritative state:

```
UI command → POST → workflow validates against durable state
                  → conflict? 409 (contradictory) / 200 (identical replay)
                  → write inside a transaction + append AuditEvent(s)
                  → return the durable record
           → UI refetches persisted resources → re-render
```

The console recomputes nothing. All visible state is read back from the API after every mutation,
so the screen can never disagree with the database.

## The optimisation pipeline

1. **Scenario generation** — 50 worlds from a seeded RNG with three variance components: shared
   discharge factor (σ=12 min), per-handling-group factors (σ=7 min), per-container noise (σ=2 min).
   **Antithetic pairs**: each of 25 draws is mirrored with every factor negated, halving Monte-Carlo
   variance and making the estimate symmetric by construction.
2. **Coefficients** — each container's *incremental* preserved-world count: how many of the 50
   worlds flip from missed to preserved if this container is expedited.
3. **CP-SAT solve** — maximise `Σ coefficient·x` subject to total slots, handling-group limits,
   reefer cap and DG cap. Parameters pinned (`num_search_workers=1`, `random_seed=0`) for
   bit-reproducibility.
4. **Complete enumeration** — a second model with the objective *fixed at the proven optimum* and
   `enumerate_all_solutions=True` collects every optimal allocation. A non-`OPTIMAL` status raises
   rather than returning a maybe-answer.
5. **Pareto filtering** — keep hard-safe evaluations (zero capacity violations, zero unsafe
   allocations) that nothing else dominates across expected preserved, p10 preserved, per-service
   totals and slot count.
6. **Dominance selection** — select only when one candidate dominates *all* others. Otherwise
   `selected_allocation` is `None` and the trade-off surfaces to a human.

---

# 3 · Key decisions

| # | Decision | Why | Rejected alternative |
|---|---|---|---|
| 1 | **Authority is encoded in the tool list.** Actions PSA cannot take have no tool, at any layer. | A model cannot hallucinate an authority it has no tool for. Prompt-level guardrails are advisory; a missing tool is structural. | An omnipotent agent constrained by prompt instructions — the common approach, and the one that fails under adversarial input. |
| 2 | **No hand-weighted scoring formula** over cargo priority and downstream consequence. The objective is expected preserved connections; everything else is a hard constraint, deterministic policy, or human judgment. | A weighted score hides policy inside arbitrary numbers. Letting an LLM assign them replaces arbitrary numbers with equally arbitrary prose. | A single "recovery score" ranking all alternatives — demos well, but is indefensible under questioning. |
| 3 | **Silence is absence, not an event.** A non-responding carrier persists no record; only an explicit `SYSTEM` timeout creates evidence. | Modelling silence as a synthetic "no" invents information the terminal does not have. | A `NO_RESPONSE` enum value on `CarrierResponse`. |
| 4 | **Enumerate all optima, then filter Pareto, then require strict dominance.** | Returning one arbitrary optimum hides that a genuine trade-off exists. If the frontier is not a singleton, that is a fact the operator needs. | Take the first optimal solution the solver returns. |
| 5 | **The safety checker's output schema has no field for a conclusion** — only `{result, explanation, evidence_excerpt}`. | Scope limitation is structural, not instructional. It *cannot* express a DG class or a recommendation. | A checker that returns a DG classification and a suggested action. |
| 6 | **Fail closed everywhere.** Provider timeout, error, invalid output, misconfiguration → escalation. | Near safety-critical work, the permissive default is the dangerous one. | Fall back to "no contradiction found" when the checker is unavailable. |
| 7 | **A credential-free deterministic replay implements the same protocols as the live model.** | The demo, the entire test suite and the whole evidence package run offline with no key and no network — and the same code path is exercised. | A mocked/stubbed demo mode that diverges from the real execution path. |
| 8 | **Append-only audit; decisions supersede rather than mutate.** | "What was decided, when, by which actor, on what evidence" must be reconstructible after the fact. | Updating a decision row in place. |
| 9 | **Approvals are bound to a payload fingerprint.** | Prevents an approval being replayed against a different payload. | Approval by case ID alone. |
| 10 | **Frozen holdout seeds, declared before evaluation.** 50 seeds, never used to tune anything. | Otherwise the headline number is tuned-on-test and worthless. | Report results on the development seed. |
| 11 | **Plain Python state machines, no agent framework.** | Nine days. Explicit transition tables are auditable and debuggable; a framework is a week of learning and an opaque control flow. | LangGraph or similar. |
| 12 | **Publish what could not be proven.** The 18/5/1 target ships as `NOT_ESTABLISHED`; live cost as `NOT_ESTABLISHED`. | A judge who finds an unproven claim discounts every other claim. | Report the target as the outcome. |

Approved changes to frozen interfaces, architecture or scope are recorded append-only in
`docs/coordination/DECISIONS.md`.

---

# 4 · Impact

## Headline: stochastic allocator vs. median-threshold baseline

**50 frozen holdout seeds × 50 worlds = 2,500 scenario worlds** (`SYN-CANONICAL-24-HOLDOUT-V1`).
Seeds were frozen before evaluation and never used to tune the fixture, distributions, allocator,
Pareto filter or dominance policy.

| Metric | P50-greedy baseline | Scenario-aware CP-SAT | Delta |
|---|---:|---:|---:|
| **Expected preserved connections** | 12.0136 | **12.5088** | **+0.4952 (+4.12%)** |
| Preserved connections (2,500 worlds) | 30,034 | **31,272** | +1,238 |
| Expected rollovers | 11.9864 | 11.4912 | −0.4952 |
| p10 preserved | 8 | 8 | — |
| Expedite slots used | 8 / 8 | 8 / 8 | — |
| Capacity violations | 0 | 0 | — |
| Unsafe allocations | 0 | 0 | — |

Reproducibility key `d0dc76fb…5fe21`.

```bash
uv run --python 3.12 --extra dev python -m backend.app.evaluation.benchmark \
  --output docs/evaluations/2026-08-22-scarcity-benchmark.json
```

**Why it wins, mechanically.** The two allocators share only **four of eight** slots. The baseline
loads SF1 (16,535 preserved worlds on SF1 vs 6,594 on JV2); the scenario-aware allocator rebalances
toward JV2 (10,830 / 13,537). A container whose p50 clears the boundary but whose p90 does not is
worth less than one with a tighter band — exactly the effect a median threshold cannot see. **Same
eight slots, same hard constraints, 1,238 more preserved connections.**

## What the number does and does not claim

- ✅ Reproducible, seeded, and honestly ours to make — bit-identical on re-run.
- ✅ Achieved with **zero** capacity violations and **zero** unsafe allocations. The improvement is
  not bought by relaxing a constraint.
- ❌ Not a business-impact figure. It is a claim about allocator behaviour on a synthetic fixture
  under a stated distribution.
- ❌ Not a claim about real transshipment failure rates. Nobody publishes those, so none is invented.

## Deterministic evidence package

```bash
uv run --python 3.12 --extra dev python -m backend.app.evaluation.evidence \
  --output-json docs/evaluations/phase8-evidence-report.json \
  --output-markdown docs/evaluations/phase8-evidence-summary.md \
  --runtime-repetitions 20
```

Fingerprint `d707b991…e543`. Verified claims include:

| Claim | Result |
|---|---|
| `agent_zero_model_credentials` | 0 provider clients constructed, no API key present |
| `agent_no_unavailable_tool_execution` | 4 forbidden tools neither exposed nor invoked |
| `agent_successful_tool_order` | `pause → reconsider → prepare → send → safety-review`, 6 steps |
| `authority_request_approval_required` / `authority_counter_approval_required` | unapproved send raises; state unchanged |
| `authority_*_fingerprint_bound` | wrong-fingerprint approval raises; nothing persisted |
| `authority_carrier_silence_is_absence` | zero `CarrierResponse` rows on silence |
| `safety_policy_owns_disposition` | checker says CONTRADICTION_FOUND; **policy** says ESCALATE |
| `safety_checker_failure_fails_closed` | CHECK_FAILED ⇒ automation blocked |
| `safety_checker_scope_limited` | no DG / UN-number / disposition field exists in the output |
| `human_tradeoff_boundary` / `_auto_replay_halts` / `_committed_slots_immutable` | model calls while waiting: **0** |
| `audit_material_action_coverage` | 8 / 8 categories, with a provenance map claim → durable record |
| `dynamic_committed_allocations_immutable` | committed slots survive reconsideration |

**Published non-results.** `full_18_preserved_5_rolled_1_escalated` is recorded **NOT_ESTABLISHED**:
no complete disjoint durable ledger classifies all 24 containers, so the plan's 18/5/1 target is
reported as unproven rather than asserted. Live cost is `NOT_ESTABLISHED / NO_PRICING_SNAPSHOT`
rather than estimated from memory. Runtime is labelled `LOCAL_MACHINE_DEPENDENT` (p50 610 ms,
p95 672 ms over 20 repetitions) and explicitly **not** a production SLA.

## Live provider evidence

Latest bounded run: **10/10 calls succeeded**, 1/1 complete workflow, p50 **1,728 ms**, p95
**2,378 ms** client-observed latency; 306–1,244 input tokens and 25–129 output tokens per call.

The live model selected the **same tool sequence** as the deterministic replay — the authority
boundary holds with a real model behind it, not only a scripted one. Artifacts in
`docs/evaluations/live/`.

---

# 5 · Security, safety & scalability

## Security

| Threat | Handling |
|---|---|
| **Prompt injection** via cargo notes or carrier messages | Untrusted text is labelled as data in both system prompts — but the real defence is structural: neither model has a tool or output field capable of acting on an injected instruction. Injection can at most produce a semantic-evidence string; the frozen policy still decides. |
| **Excerpt fabrication** | `evidence_excerpt` must be a verbatim substring of the note; otherwise the output is rejected as `INVALID_OUTPUT`. |
| **Approval replay against a different payload** | Every approval is bound to a SHA-256 payload fingerprint; a mismatch is a `409`. |
| **Stale-state trade-off selection** | Selection must echo the exact `options_fingerprint`; a stale one is a `DynamicYardConflict`. |
| **Cross-origin abuse** | Strict `ALLOWED_ORIGINS` validator: no `*`, no paths/queries/fragments, no credentials in URL, no duplicate origins after default-port normalisation, no plain `http` except localhost. `allow_credentials=False`, methods limited to GET/POST/OPTIONS. |
| **Secret leakage** | `OPENAI_API_KEY` is server-only. Never in a `VITE_` variable, bundle, log, response, artifact or image. `.env` gitignored; the Docker image excludes `.env`, `web/`, `docs/` and databases; `web/dist` is scanned with disposable sentinels. |
| **Unbounded provider spend** | The live harness is opt-in and hard-capped (`PHASE9_LIVE_MAX_CALLS ≤ 10`, `PHASE9_LIVE_MAX_RUNS = 1`) and refuses to exceed its budget. |
| **Injection into the datastore** | All persistence goes through SQLModel/SQLAlchemy parameterised queries; no string-built SQL. |

**Not built, and deliberately so:** authentication, authorisation, rate limiting and multi-tenancy.
This is a single-operator demonstration console. Production would need all four — see below.

## Safety

- **Fail closed.** Provider timeout, provider error, invalid output, missing configuration and
  malformed tool arguments all route to escalation, never to a permissive default.
- **The model never determines safety.** The checker produces evidence; a frozen deterministic
  policy owns `PASS_THROUGH` vs `ESCALATE`. Verified: checker says `CONTRADICTION_FOUND`, policy
  says `ESCALATE`, and the two are separately recorded.
- **No local mutation of external authority.** Carrier schedules, DG rules and yard capacity have no
  write path anywhere in the codebase.
- **Committed work is immutable.** A physically committed expedite slot can never be silently
  displaced; commitment transitions are a closed set.
- **Evidence precedes commitment.** While unhandled operational evidence exists, all
  carrier-mutating tools are withdrawn *and* rejected at execution.
- **Two independent human gates**, both fingerprint-bound, both without any agent-side tool.
- **Append-only audit** with typed actors (`AGENT` / `SOLVER` / `POLICY` / `OPERATOR` / `CARRIER` /
  `SYSTEM`) across 8 material action categories, each mapped to the durable record supporting it.
- **Auto mode cannot bypass a human.** `auto_replay_may_execute` is `false` at both approvals and at
  any trade-off decision — enforced by the backend projector, not by frontend politeness.

## Scalability

Measured on the canonical fixture, this machine. **The optimiser is not the bottleneck.**

**CP-SAT scaling** (solve + *complete* enumeration of all optima, 50 worlds):

| Containers | Binary vars | Slots | Solve + enumerate | Optima found |
|---:|---:|---:|---:|---:|
| 24 | 21 | 8 | **9.4 ms** | 1 |
| 48 | 42 | 16 | 15.7 ms | 3 |
| 96 | 75 | 32 | 33.4 ms | 18 |
| 192 | 166 | 64 | 89.8 ms | 18 |
| 384 | 322 | 128 | **258 ms** | 1 |

**Scenario-count scaling** (24 containers) — linear, and dominated by coefficient computation, not
by the solver:

| Worlds | Coefficient computation | Total solve |
|---:|---:|---:|
| 50 | 6 ms | 10.6 ms |
| 200 | 25 ms | 26 ms |
| 1,000 | 138 ms | 139.7 ms |
| 4,000 | 699 ms | 719.4 ms |

A realistic terminal exception (a few hundred containers, a few thousand worlds) stays comfortably
inside a second. **Wall-clock time is dominated by LLM latency — ~1,728 ms p50 per turn versus ~10 ms
for the entire optimisation.** Reducing agent turns matters roughly 170× more than optimising the
solver.

**Known ceilings, honestly named:**

| Ceiling | Impact | Upgrade path |
|---|---|---|
| **SQLite single-writer** | One concurrent writer per database file. Fine for one terminal's exception queue; not for multi-terminal concurrency. | PostgreSQL — repositories are SQLModel, so the change is the engine URL plus a migration story. |
| **Complete optimum enumeration is unbounded in principle** | Worst case is combinatorial (`C(24,8)` ≈ 735k). Observed 1–21 across every probe, because per-container noise breaks ties. No solution cap is currently set. | Add a solution limit and report "≥N optima" when hit. |
| **Coefficient computation is O(candidates × worlds)** and single-threaded | 699 ms at 4,000 worlds; grows linearly. | Vectorise with NumPy, or parallelise across worlds — trivially data-parallel. |
| **Fixture re-parsed per call** (~0.14 ms × 10 call sites) | Negligible now; O(fixture size) per request. | `functools.lru_cache` on the loader. |
| **History endpoints are unpaginated** | Full audit history per request; grows with incident age. | Cursor pagination on `audit_events.sequence`. |
| **No authentication, rate limiting or multi-tenancy** | Single-operator demo scope. | Required before any real deployment. |
| **In-process synchronous workflows** | A long agent advance holds a request. | Background worker + job status endpoint. |
| **Single-incident agent runs** | No cross-incident scheduling or prioritisation. | Out of scope by design — the system handles one broken plan at a time. |

**What scales well by construction:** stateless request handling (any instance can serve any
request; all state is durable), idempotent mutations (safe to retry behind a load balancer),
append-only audit (no update contention), and deterministic seeded evaluation (reproducible on any
machine).

---

## The canonical incident

One scenario is the acceptance test, the synthetic data target, the demo script and the deck spine.
`shared/fixtures/canonical-24-container.json`, validated as `CanonicalIncidentFixture`.

| Property | Value |
|---|---|
| Fixture | `SYN-CANONICAL-24-V1` |
| Terminal | `SYN-TUAS-TERMINAL` |
| Inbound | `ASX-17` / `M/V Synthetic Meridian`, call `SYN-ASX17-TUAS-001` |
| Delay | scheduled `2026-08-22T01:00Z` → estimated `04:15Z` = **195 minutes** |
| Onward services | SF1 (9 containers), JV2 (8), EC3 (7) |
| Ready boundary | PTA + 35 minutes for every service (contract-enforced) |
| Cargo mix | 14 dry · 6 reefer · 4 structurally-represented DG |
| Expedite saving | 30 minutes per container |
| Critical overlap | SF1 / JV2, window `05:00Z–05:55Z` |
| Capacity | **8 total slots**; groups `SYN-A-EQ1=4`, `SYN-B-EQ2=3`, `SYN-C-EQ3=3`; ≤3 reefer; ≤1 DG |

The fixture stores **no beneficiary or outcome labels**. The 13-candidate / 8-slot squeeze is
*derived* from ready times, boundaries, the expedite saving, reefer continuity and structural DG
clearance — it is not written down anywhere as an answer.

| Companion fixture | Purpose |
|---|---|
| `canonical-carrier-response-plan.json` | Three named runs: JV2→ACCEPT, JV2→COUNTER, EC3→SILENT |
| `canonical-agent-runtime-config.json` | Trusted RTA timestamps and injectable clock values |
| `canonical-dg-contradiction.json` | The DG semantic-catch cargo note |
| `scarcity-evaluation-seeds.json` | 50 frozen holdout seeds |

**All data is synthetic.** Vessel names, container numbers, yard positions and timings are invented
to resemble realistic terminal operations, and the UI says so on screen via a persistent
`SyntheticBanner`. The integration boundary is modelled on public DCSA OVS and Port Call 2.0
patterns; nothing here is a PSA, carrier, manifest, schedule or yard integration.

---

## Frontend

React 19 + Vite 8 + Tailwind v4, plain React state — no Redux, Zustand, XState or WebSockets.
`App.tsx` is three lines; `OperationsConsole` is the shell.

**State model.** `useRecoveryConsole()` owns every loaded resource and every mutation command. No
recovery policy exists in React; the UI joins backend facts and never recomputes them.

| Mode | Behaviour |
|---|---|
| **Guided** | Stage-by-stage narrative. One `StageActionCard` shows the single next legal action, taken from `canonical-replay/stage`. |
| **Auto** | Walks stages automatically — and **halts** wherever `auto_replay_may_execute` is false. |
| **Explore** | Free navigation across the full dashboard. |

**Seven narrative chapters** map the 16 backend stages onto a story: Incident → Optimize → Observe →
Adapt → Coordinate → Respond → Protect. **Five workspaces:** Overview · Recovery · Containers ·
Carrier · Evidence/Audit.

Dark terminal design language with PSA tokens (`src/styles/tokens.css`), Inter + monospace for
identifiers, GSAP chapter motion gated behind reduced-motion preference, and a persistent synthetic
banner with actor-badge legend. Approved layout spec:
`docs/superpowers/specs/2026-08-23-psa-ui-phase2-phase3-design.md`.

---

## Running locally

**Prerequisites:** Python 3.12 (via `uv`), Node 20+.
**No OpenAI key is needed** — the canonical demo replay is fully deterministic and offline.

```bash
# Optional: only for live LLM calls
cp .env.example .env && $EDITOR .env
set -a && source .env && set +a
```

```bash
# Terminal 1 — backend on :8000
uv run --python 3.12 --extra dev uvicorn backend.app.main:app --reload --port 8000

# Terminal 2 — frontend on :5173
cd web && npm install && npm run dev
```

| URL | |
|---|---|
| http://localhost:5173 | Operations console |
| http://127.0.0.1:8000/docs | Interactive API docs |
| http://127.0.0.1:8000/healthz | Health probe |

Vite proxies the API paths in development, so no CORS setup is needed. Stop with
`lsof -ti:8000 | xargs kill` / `lsof -ti:5173 | xargs kill`. More detail in `LOCAL-DEV.txt`.

---

## Tests

```bash
uv run --python 3.12 --extra dev pytest backend/tests -q   # 543 tests, offline
cd web && npm test                                          # 104 tests, 22 files
cd web && npm run typecheck && npm run lint
uv lock --check
```

Current status: **541 passed, 2 skipped** (the skips are opt-in live-provider smoke tests requiring
`RUN_LIVE_LLM_TESTS=1`) and **104 frontend tests passing**.

The suites assert the authority boundaries directly, not just the happy path: DG constraints are
never bypassed; no carrier schedule is ever modified locally; never more than 8 expedite jobs are
allocated; no RTA is sent without operator approval; a timeout triggers recomputation;
low-confidence containers are reconsidered; every material action produces an audit event; and the
agent cannot execute a tool that was not exposed to it.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./backend/transshipment.db` | Persistence target |
| `ALLOWED_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | Exact CORS origins, comma-separated |
| `OPENAI_API_KEY` | — | Only for live calls; never required for the demo |
| `OPENAI_AGENT_MODEL` | `gpt-5.6-luna` (deployment sets `gpt-5.6-terra`) | Agent tool-selection model |
| `OPENAI_MODEL` | `gpt-5.6-luna` | DG semantic-safety model |
| `RUN_LIVE_LLM_TESTS` | unset | Enables opt-in live smoke tests |
| `PHASE9_LIVE_MAX_CALLS` / `PHASE9_LIVE_MAX_RUNS` | — | Hard caps for the live harness (≤10 / =1) |
| `PORT` | — | Required by the container entrypoint |
| `VITE_API_BASE_URL` | `""` (dev proxy) | Public API origin baked into the browser bundle |

---

## Deployment

Backend on Railway from the root `Dockerfile` (uv + Python 3.12, `--frozen --no-dev`); frontend on
Vercel with project root `web/`.

- Persistent volume at `/data`; `DATABASE_URL=sqlite:////data/transshipment.db`.
- Health check `GET /healthz` → `{"status":"ok","database":"ready"}`.
- Rollback is configuration-first: restore the previous release while **retaining** the `/data`
  volume. Deleting or reinitialising the volume is never a rollback step.

Full runbook, including CORS verification and the human-authorization gate for any live provider
spend: `docs/deployment.md`.

---

## Honest limitations

- **The berth-time lever is an inference.** Real terminals may negotiate the cargo cut-off rather
  than the carrier's berth arrival, and DCSA's Port Call standard puts cargo operations out of
  scope. The berth request is used because it is the only publicly standardised terminal-to-carrier
  timing mechanism. If the lever differs, nothing about the agent's role changes.
- **The problem size is not publicly measured.** Nobody publishes how often transshipment
  connections fail or what it costs, so no such number is invented here.
- **All data is synthetic.** The +4.12% is a real, reproducible result *on this fixture and these
  frozen seeds* — a claim about allocator behaviour, not a business-impact figure.
- **The 18/5/1 canonical target is NOT_ESTABLISHED**, and the evidence package says so.
- **Runtime numbers are local-machine measurements**, labelled as such, not a production SLA.
- **Live cost is NOT_ESTABLISHED** pending a committed pricing snapshot.
- **No auth, rate limiting or multi-tenancy.** Single-operator demonstration scope.
- **Transshipment is a crowded theme.** ~90% of Singapore's throughput is transshipment. This
  scope — container-level decisions *after* the connection is already broken — is deliberately much
  narrower than the likely field.

---

## Documentation map

| Path | What it is |
|---|---|
| `docs/specs/psa-code-sprint-final-plan.md` | The canonical plan. Scope disputes resolve here. |
| `docs/superpowers/specs/` | Per-phase design documents |
| `docs/superpowers/plans/` | Per-phase implementation plans |
| `docs/coordination/DECISIONS.md` | **Append-only** record of frozen-interface/scope changes |
| `docs/coordination/WORKSTREAMS.md` | Task ownership, base/result SHAs, status |
| `docs/evaluations/` | Benchmark JSON, Phase-8 evidence, Phase-9 live runs |
| `docs/deployment.md` | Railway + Vercel operator runbook |
| `shared/fixtures/README.md` | Full provenance of every synthetic fixture |
| `LOCAL-DEV.txt` · `AGENTS.md` · `UI_REVIEW.md` | Dev cheat sheet · UI skill protocols · design review |

---

**Stack:** Python 3.12 · FastAPI · Pydantic v2 · SQLModel / SQLite · OR-Tools CP-SAT · OpenAI
Responses API (optional) · React 19 · Vite 8 · Tailwind v4 · GSAP · Vitest · pytest · uv

**All data in this repository is synthetic.** It does not contain, represent, or integrate with any
PSA, carrier, manifest, schedule or yard system.
