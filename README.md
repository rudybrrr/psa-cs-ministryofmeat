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

## Table of contents

- [The one architectural decision](#the-one-architectural-decision)
- [What is hard about this](#what-is-hard-about-this)
- [Who decides what](#who-decides-what)
- [System architecture](#system-architecture)
- [Repository layout](#repository-layout)
- [The canonical incident](#the-canonical-incident)
- [Capability walkthrough (phase by phase)](#capability-walkthrough-phase-by-phase)
- [The agent runtime](#the-agent-runtime)
- [Domain contracts and state machines](#domain-contracts-and-state-machines)
- [Persistence](#persistence)
- [HTTP API](#http-api)
- [Frontend](#frontend)
- [Running locally](#running-locally)
- [Tests](#tests)
- [Evaluation and measured results](#evaluation-and-measured-results)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Safety and security posture](#safety-and-security-posture)
- [Honest limitations](#honest-limitations)
- [Documentation map](#documentation-map)

---

## The one architectural decision

**The agent's tool list encodes organisational authority. Actions PSA cannot take do not exist as
tools.**

A model cannot hallucinate an authority it has no tool for. This is the load-bearing design
decision of the whole system, and it is enforced structurally — the tool registry
(`backend/app/orchestration/agent_context.py`) computes the exposed tool set from durable typed
state on every single turn, and the runtime rejects any tool name that is not in that set.

| Exists as a tool | Does **not** exist, at any layer |
|---|---|
| `get_incident_context`, `get_scarcity_evaluation`, `get_carrier_recovery_cases`, `get_carrier_recovery_history`, `get_cargo_safety_reviews` | `hold_feeder()` — PSA cannot order another company's feeder to wait |
| `request_expedite_feasibility` — apply the deterministic expedite reconsideration | `change_carrier_schedule()` — carrier schedules are never mutated locally |
| `prepare_rta_request` — prepare a DCSA-shaped timing request (never sends) | `override_dg_rule()` — DG constraints are not negotiable by a model |
| `send_authorised_rta_request` — send an **already operator-approved** request | `set_yard_capacity()` — capacity is evidence, not an agent lever |
| `evaluate_carrier_timeout` — record a due timeout using the trusted clock | *(also absent)* any tool that approves, selects a trade-off, or classifies cargo |
| `request_cargo_safety_review` — run the semantic check on a **persisted** review | |
| `pause_agent_run`, `complete_agent_run`, `escalate_agent_run` | |

The four forbidden names above are asserted as a verified evidence claim
(`agent_no_unavailable_tool_execution`) rather than merely documented.

Three further boundaries hold structurally:

1. **The agent never supplies time.** RTA timestamps come from a trusted checked-in configuration
   (`shared/fixtures/canonical-agent-runtime-config.json`); the clock is injected. The agent passes
   only a connection or case *identity*.
2. **The agent never approves.** `send_authorised_rta_request` fails with a conflict unless a
   durable `Approval` exists, bound to the exact payload fingerprint.
3. **The agent never resolves a genuine trade-off.** When the Pareto frontier retains a real
   business trade-off, the run enters `WAITING / HUMAN_TRADEOFF_DECISION` and no tool that could
   resolve it is exposed.

---

## What is hard about this

Four things, and all four are built. Drop any one and this becomes an if-statement with a language
model attached.

**1 · Scarce capacity, allocated under uncertainty.**
Thirteen containers would benefit from expedited yard handling. Equipment supports eight during the
critical SF1/JV2 overlap. The allocation does not run on median ready times — it maximises the
*expected* number of preserved connections across 50 antithetic-paired scenario worlds, subject to
total-slot, per-handling-group, reefer and DG constraints. A CP-SAT model proves the optimum, then
re-solves with the objective pinned to enumerate **every** optimal allocation, so the Pareto
frontier is complete rather than sampled.

**2 · Uncertainty that moves.**
Ready times are forecasts. Before discharge the yard returns a band (p10 / p50 / p90), not a number.
Once discharge begins the bands tighten, the agent must revisit earlier recommendations, and
containers that were marginal under a wide band may no longer be. Allocation revisions are an
append-only lineage (R0 → R1 → …), and already-committed expedite slots are immutable.

**3 · External authority.**
PSA cannot order another company's feeder to wait. It issues a request under DCSA's
Estimated / Requested / Planned / Actual pattern, and the carrier decides: ACCEPT, COUNTER, or
silence. Silence is modelled as the *absence* of a response, which becomes evidence only when a
timeout is explicitly recorded by `SYSTEM` — never as a synthetic "no" event.

**4 · Safety that cannot be argued with.**
A DG container passes structured validation, but the free-text commodity description contradicts the
declaration. The semantic checker's entire output vocabulary is `{result, explanation,
evidence_excerpt}` — it has no field in which to express a DG classification, a UN number, or an
operational recommendation. A frozen deterministic policy, not the model, converts that evidence
into `PASS_THROUGH` or `ESCALATE`. Any checker failure fails **closed**.

---

## Who decides what

| The agent handles | Deterministic systems decide | The human operator decides |
|---|---|---|
| Which information to gather next | Whether a move is physically feasible | Which Pareto-efficient alternative to take when a genuine trade-off remains |
| The evolving exception as forecasts, tool results and counterparty responses change | Earliest safe ready time and connection feasibility arithmetic | How cargo priority and downstream consequence resolve that trade-off |
| Authorised tool calls and counterparty communication | DG segregation, reefer continuity, handling-group and slot limits | Whether to approve externally directed actions (RTA send, counter acceptance) |
| Detecting missing evidence, failure and silence, then recomputing or escalating | Whether one alternative *clearly dominates* under established policy | Anything escalated beyond deterministic authority |

The optimisation objective is expected preserved connections. Every remaining dimension is a hard
constraint, established deterministic policy, or explicit human judgment. There is deliberately **no
hand-weighted scoring formula** over priority and cargo type — that hides policy inside arbitrary
numbers, and an LLM must not replace arbitrary numbers with equally arbitrary prose.

---

## System architecture

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
│  orchestration/   workflows — the only writers of durable state               │
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
- Only `orchestration/` writes. Repositories persist; policies and optimisers are pure functions over
  contracts; services are read-only synthetic adapters.
- The LLM sits behind the `AgentModel` protocol (one method: `decide(context, tools)`) and the
  `SemanticSafetyChecker` protocol (one method: `check(evidence)`). Both have deterministic,
  credential-free implementations, which is why the entire test suite and the whole evidence package
  run offline.
- `orchestration/canonical_replay.py` is a **read-only projector**: it derives a demo stage purely
  from persisted state and writes nothing — no tables, no audit events.

---

## Repository layout

```
backend/
  app/
    main.py                    FastAPI app factory: 38 routes, CORS validation, health
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
  tests/                       543 tests (2 skipped: opt-in live smoke)
web/
  src/
    api/                       typed clients, one module per bounded context
    components/
      command-center/          dashboard shell, sidebar, chapters, workspaces
      carrier/ dynamic/ safety/ recovery/ agent/   domain panels
    hooks/                     useRecoveryConsole (state+commands), useAutoReplay
    lib/                       selectors, chapter mapping, formatters, persistence
    styles/tokens.css          PSA dark terminal design tokens
  scripts/                     Playwright checkpoint screenshot capture
shared/fixtures/               canonical synthetic data (see below)
docs/
  specs/                       the canonical nine-day plan
  superpowers/plans|specs/     per-phase design + implementation plans
  coordination/                WORKSTREAMS.md, append-only DECISIONS.md, agent logs
  evaluations/                 benchmark JSON, Phase-8 evidence, Phase-9 live runs
  deployment.md                Railway + Vercel operator runbook
Dockerfile                     uv + Python 3.12 backend image for Railway
```

---

## The canonical incident

One scenario is the acceptance test, the synthetic data target, the demo script and the deck spine.
It lives in `shared/fixtures/canonical-24-container.json`, validated directly as
`CanonicalIncidentFixture`.

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
| Capacity | **8 total slots**; group limits `SYN-A-EQ1=4`, `SYN-B-EQ2=3`, `SYN-C-EQ3=3`; ≤3 reefer; ≤1 DG |

The fixture stores **no beneficiary or outcome labels**. The 13-candidate / 8-slot squeeze is
*derived* from ready times, boundaries, the expedite saving, reefer continuity and structural DG
clearance — it is not written down anywhere as an answer.

Companion fixtures:

| File | Purpose |
|---|---|
| `canonical-carrier-response-plan.json` | Three named carrier runs: JV2→ACCEPT, JV2→COUNTER, EC3→SILENT |
| `canonical-agent-runtime-config.json` | Trusted RTA timestamps and injectable clock values |
| `canonical-dg-contradiction.json` | The DG semantic-catch cargo note |
| `scarcity-evaluation-seeds.json` | 50 frozen holdout seeds (`SYN-CANONICAL-24-HOLDOUT-V1`) |

**All data is synthetic.** Vessel names, container numbers, yard positions and timings are invented
to resemble realistic terminal operations, and the UI says so on screen via a persistent
`SyntheticBanner`. The integration boundary is modelled on public DCSA OVS and Port Call 2.0
patterns; nothing here is a PSA, carrier, manifest, schedule or yard integration.

---

## Capability walkthrough (phase by phase)

### Phase 1 — Deterministic vertical slice

`orchestration/state_machine.py`. One delay event → one container → feasibility → decision, with
every step audited. The incident FSM is explicit and total:

```
INCIDENT_RECEIVED → COLLECTING_STATE → CONSTRAINT_VALIDATION → RECOVERY_ANALYSIS → RESOLVED
                          ↓                    ↓                       ↓
                      ESCALATED            ESCALATED               ESCALATED
```

`RESOLVED` and `ESCALATED` are terminal; an illegal transition raises `InvalidIncidentTransition`
rather than silently coercing state. `DominancePolicy` selects `EXPEDITE` **only** when normal
transfer misses the cutoff, expedited transfer meets it, and a slot exists. Otherwise it returns
`None` and the incident escalates — the policy has no "best guess" branch.

### Phase 2 — Scarce capacity under uncertainty

`orchestration/scarce_capacity.py` · `optimization/scarcity.py` · `evaluation/scarcity.py`

1. **Scenario generation** (`services/scenarios.py`) builds 50 worlds from a seeded RNG with three
   variance components — a shared discharge factor (σ=12 min), per-handling-group factors (σ=7 min)
   and per-container noise (σ=2 min) — using **antithetic pairs**: for each of 25 draws, a mirrored
   world with every factor negated. That halves Monte-Carlo variance and makes the estimate
   symmetric by construction.
2. **Objective coefficients** are each container's *incremental* preserved-world count — how many of
   the 50 worlds flip from missed to preserved if this container is expedited.
3. **CP-SAT solve** maximises `Σ coefficient·x` subject to total slots, handling-group limits,
   reefer cap and DG cap. Solver parameters are pinned (`num_search_workers=1`, `random_seed=0`) so
   results are bit-reproducible.
4. **Complete enumeration**: a second model with the objective *fixed at the proven optimum* and
   `enumerate_all_solutions=True` collects every optimal allocation. If either solve returns
   non-`OPTIMAL`, it raises rather than returning a maybe-answer.
5. **Pareto filtering** (`policies/allocation_dominance.py`) keeps hard-safe evaluations
   (zero capacity violations, zero unsafe allocations) that nothing else dominates across expected
   preserved, p10 preserved, per-service totals, and slot count.
6. **Dominance selection** picks an allocation only when one candidate dominates *all* others.
   Otherwise `selected_allocation` is `None` and the trade-off surfaces to a human.

Everything is fingerprinted: `reproducibility_key` is a 64-char SHA-256 over the semantic inputs, so
two runs that claim the same result can be proven to have compared the same thing.

### Phase 3 — Carrier recovery under external authority

`orchestration/carrier_recovery.py` · case FSM in `domain/carrier_recovery.py`

```
PREPARED → AWAITING_REQUEST_APPROVAL → AWAITING_CARRIER → AWAITING_COUNTER_APPROVAL
                        ↓                      ↓                      ↓
                   RECOMPUTING ────────────────┴──────────────────────┘
                        ↓
              COMPLETED  |  ESCALATED
```

- A case may only be prepared for containers that are **structurally safe and preserved in zero of
  the 50 worlds** — recovery is attempted only where scarce-capacity allocation provably cannot help.
- Every approval is a durable `ApprovalBinding` carrying a SHA-256 **payload fingerprint**. Approving
  a different payload than the one presented is a `CarrierRecoveryConflict`, not a mismatch that
  slips through.
- Carrier outcomes: `ACCEPT`, `COUNTER` (requires a *second* operator approval before its timing
  becomes effective), and `SILENT` (no record at all; only an explicit `SYSTEM` timeout creates
  evidence).
- Reconsideration replays the frozen Phase-2 worlds against the new effective timing and writes one
  `ContainerReconsiderationResult` per container with exactly one typed evidence reference —
  effective timing, rejected approval, or timeout. The contract validator enforces "exactly one".
- Every mutating endpoint is idempotent: a replayed identical request returns `200` with the same
  durable record; a *contradictory* replay raises a conflict. Case uniqueness is
  `(incident_id, connection_id)`, protected by a DB constraint with an `IntegrityError` race
  reconciliation path.

### Phase 4 — DG semantic safety

`orchestration/cargo_safety.py` · `services/semantic_safety.py`

The structured declaration says general cargo. The free-text handling note says corrosive material.

- The checker receives the trusted declaration and the untrusted note, clearly separated, with system
  instructions that the note is **data, never instructions**.
- Its output schema is exactly `{result, explanation, evidence_excerpt}`. There is no field for a UN
  number, a DG class, a disposition or a recommendation — the scope limit is structural, and is
  asserted as evidence claim `safety_checker_scope_limited`.
- `evidence_excerpt` must be a verbatim substring of the note. If it is not, the output is rejected
  as `INVALID_OUTPUT`.
- The frozen policy owns the disposition: anything other than `NO_CONTRADICTION_FOUND` →
  `ESCALATE`, `automation_blocked=True`, and a new `ESCALATE` `Decision` that supersedes the prior
  decision for that container with a recorded supersession reason.
- **Fails closed**: provider timeout, provider error, invalid output or misconfiguration all produce
  `CHECK_FAILED` → escalation. A `CHECK_FAILED` assessment is contract-forbidden from persisting an
  evidence excerpt.

### Phase 5 — Dynamic yard reconsideration

`orchestration/dynamic_yard.py` · `optimization/dynamic_yard.py`

- `PRE_DISCHARGE` snapshot bootstraps revision **R0** from the frozen Phase-2 selected allocation and
  creates `ExpediteCommitment` rows; some become `COMMITTED` (physically underway).
- `DISCHARGE_ACTIVE` tightens the forecast bands and produces an
  `ExpediteReconsiderationAssessment` with disposition `NO_CHANGE`, `AUTO_SUPERSEDE`, or
  `HUMAN_REVIEW_REQUIRED`.
- Commitment transitions are a closed set: `PLANNED→COMMITTED`, `PLANNED→CANCELLED`,
  `COMMITTED→EXECUTED`. A committed slot can never be silently displaced.
- `HUMAN_REVIEW_REQUIRED` creates an `AllocationTradeoffReview` with a fingerprint over its options.
  Selection requires the operator to echo that exact fingerprint; a stale fingerprint is a
  `DynamicYardConflict`.
- **Ordering guard**: while an unhandled assessment exists, `prepare_rta_request`,
  `send_authorised_rta_request` and `evaluate_carrier_timeout` are removed from the tool set *and*
  rejected at execution time. New evidence is handled before any external commitment is made.

### Phase 6 — Full agent + frontend integration

The console drives the real backend end to end: create incident → bootstrap → agent run → advance →
publish discharge-active → reconsider → prepare RTA → approve → send → carrier counter → approve
counter → safety review → escalation. All visible state is re-read from persisted APIs after every
mutation; no recovery policy lives in React.

### Phase 7 — Canonical replay harness

`orchestration/canonical_replay.py` + `services/canonical_replay.py`

A credential-free `CanonicalReplayAgentModel` and `CanonicalReplaySemanticChecker` implement the same
protocols as the live ones, so the full demo runs with **no API key and no network**. The read-only
projector maps durable state onto a 16-stage view:

```
READY_TO_CREATE → READY_FOR_PRE_DISCHARGE → READY_TO_START_AGENT
→ READY_TO_ADVANCE_TO_EVIDENCE_WAIT → WAITING_FOR_ACTIVE_EVIDENCE → READY_TO_RECONSIDER
→ READY_TO_PREPARE_RTA → REQUEST_APPROVAL_REQUIRED → REQUEST_APPROVED_READY_TO_SEND
→ WAITING_FOR_CARRIER → CARRIER_COUNTER_RECEIVED → COUNTER_APPROVAL_REQUIRED
→ COUNTER_APPROVED_READY_TO_RESUME → READY_FOR_SAFETY_EVIDENCE → SAFETY_REVIEW_PENDING
→ SAFETY_BLOCKED / COMPLETE       (+ TRADEOFF_DECISION_REQUIRED, OFF_CANONICAL_PATH, FAILED)
```

Each stage view carries `guided_can_execute`, `auto_replay_may_execute` and
`requires_human_authority`. **Auto mode is structurally unable to click through a human decision** —
at `TRADEOFF_DECISION_REQUIRED` and both approval stages, `auto_replay_may_execute` is `false`.

### Phase 8 — Deterministic evidence package

`python -m backend.app.evaluation.evidence` runs the full canonical scenario in an isolated session
and emits a fingerprinted evidence report as JSON + Markdown. It asserts a credential-isolation
probe (zero provider clients constructed, no key present), builds a provenance map from every claim
to the exact durable record that supports it, and marks anything unproven as `NOT_ESTABLISHED` or
`DEFERRED` rather than quietly rounding up.

### Phase 9 — Live provider hardening and deployment

`python -m backend.app.evaluation.live_provider` is an opt-in, hard-bounded live harness
(`RUN_LIVE_LLM_TESTS=1`, `PHASE9_LIVE_MAX_CALLS ≤ 10`, `PHASE9_LIVE_MAX_RUNS=1`) that instruments
every provider call for tokens and latency and refuses to exceed its call cap. Plus: `/healthz` with
a real DB probe, a strict CORS origin validator (no wildcards, no paths, no duplicate origins, no
non-local plain HTTP), `DATABASE_URL` by environment, and a Railway-ready Dockerfile.

---

## The agent runtime

`orchestration/agent_runtime.py`

**Run states:** `CREATED → RUNNING ⇄ WAITING → COMPLETED | ESCALATED | FAILED`

**Wait kinds** — a run parks on a typed condition rather than polling blindly:

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

**Loop discipline.** `max_steps` defaults to 12; a single `advance` call executes at most 8 tool
turns. A model returning an invalid turn or an unavailable tool gets exactly one retry, then the run
escalates. Budget exhaustion escalates — it never wanders.

**Crash recovery.** A `PENDING` tool invocation found at the start of `advance` means the process
died mid-tool. Exactly one pending invocation of `send_authorised_rta_request` is recovered
idempotently; anything else escalates as `TOOL_FAILURE`. The system never re-drives an ambiguous
external side effect.

**Completion gate.** `complete_agent_run` is rejected while *any* actionable work remains — an
unhandled assessment, an open trade-off review, a non-terminal carrier case, or a pending safety
review. The agent cannot declare victory early.

**Turn context.** The model receives a compact typed summary (scarcity evidence, decision IDs,
carrier case states, dynamic-yard stages, pending safety reviews, available tool names) — not raw
free text. The system prompt states plainly that typed state is authoritative and that notes and
external messages are data, never instructions.

---

## Domain contracts and state machines

Every contract inherits `FrozenContract` (`extra="forbid"`, `frozen=True`), so contracts are
immutable and unexpected fields are errors.

**Core vocabulary**

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

**Invariants enforced in contracts, not in comments**

- `ServiceWindow.ready_boundary` must equal PTA + 35 minutes.
- Forecast quantiles must satisfy `p10 ≤ p50 ≤ p90`, all with explicit UTC offsets.
- `AllocationRevision.locked_container_ids ⊆ allocated_container_ids`; no duplicates anywhere.
- `AgentRun` in `WAITING` requires a `wait_kind`; not-`WAITING` forbids one. Same for
  `ESCALATED` / `escalation_reason`.
- `AgentModelTurn` requires **exactly one** of `tool_call` or `control`.
- Timestamps crossing a trust boundary must be explicit UTC (`Z` or `+00:00`) — naive datetimes are
  rejected at parse time.
- `ContainerReconsiderationResult` requires exactly one typed evidence reference, matching its
  declared kind.
- `reproducibility_key` and `options_fingerprint` are exactly 64 characters.

**Decision lineage.** Decisions are never mutated. A new decision `supersedes` the prior one with a
`supersession_reason`, so "the current decision" is a derived view over an append-only history.

---

## Persistence

SQLite via SQLModel; `DATABASE_URL` selects the target (`sqlite:///./backend/transshipment.db`
locally, a `/data` volume in production). Tables:

| Group | Tables |
|---|---|
| Core | `incidents`, `decisions`, `audit_events`, `scarcity_evaluations` |
| Carrier recovery | `carrier_recovery_cases` *(unique `incident_id, connection_id`)*, `rta_requests`, `rta_request_contexts` *(unique `case_id`)*, `approvals`, `approval_bindings`, `carrier_responses`, `carrier_simulation_receipts`, `effective_connection_timings`, `carrier_recovery_decision_links`, `container_reconsideration_results` *(unique `case_id, container_id`)*, `carrier_recovery_audit_links` |
| Dynamic yard | `yard_forecast_snapshots` *(unique `incident_id, stage`)*, `allocation_revisions`, `expedite_commitments`, `expedite_reconsideration_assessments` *(unique `source_snapshot_id`)*, `allocation_tradeoff_reviews`, `allocation_tradeoff_options`, `allocation_tradeoff_selections` |
| Cargo safety | `cargo_notes`, `cargo_safety_reviews` *(unique `cargo_note_id`)*, `semantic_safety_assessments`, `semantic_safety_policy_results`, `cargo_safety_audit_links` |
| Agent runtime | `agent_runs`, `agent_steps`, `agent_tool_invocations`, `agent_audit_links` |

Idempotency and concurrency safety are database-level, not advisory: unique constraints back every
"exactly once" claim, and workflows reconcile `IntegrityError` races by re-reading and comparing the
durable record. `audit_events` is append-only — nothing updates or deletes a row.

---

## HTTP API

FastAPI serves interactive docs at `/docs`. Mutating endpoints are idempotent: an identical replay
returns `200` with the same record, a contradictory replay returns `409`.

**Health and scenarios**

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Liveness + DB probe (`200 ok` / `503 unavailable`) |
| POST | `/synthetic/scenarios/schedule-delay` | Phase-1 single-container slice |
| POST | `/synthetic/scenarios/canonical-scarcity` | Create the canonical 24-container incident |
| GET | `/synthetic/scenarios/canonical-scarcity/fixture` | The canonical fixture |

**Incident**

| Method | Path |
|---|---|
| GET | `/incidents/{id}` |
| GET | `/incidents/{id}/decisions` |
| GET | `/incidents/{id}/audit-events` |
| GET | `/incidents/{id}/scarcity-evaluation` |

**Dynamic yard**

| Method | Path |
|---|---|
| POST | `/synthetic/scenarios/{id}/dynamic-yard/bootstrap` |
| POST | `/synthetic/scenarios/{id}/dynamic-yard/discharge-active` |
| GET | `/incidents/{id}/yard-forecast-snapshots` |
| GET | `/incidents/{id}/allocation-revisions` |
| GET | `/incidents/{id}/expedite-commitments` |
| GET | `/incidents/{id}/expedite-reconsiderations` |
| GET | `/incidents/{id}/allocation-tradeoff-reviews` |
| GET | `/incidents/{id}/allocation-tradeoff-options` |
| POST | `/allocation-tradeoff-reviews/{review_id}/selection` |

**Carrier recovery**

| Method | Path |
|---|---|
| POST | `/incidents/{id}/carrier-recovery-cases` |
| POST | `/carrier-recovery-cases/{case_id}/request-approval` |
| POST | `/carrier-recovery-cases/{case_id}/send` |
| POST | `/carrier-recovery-cases/{case_id}/simulate-carrier-response` |
| POST | `/carrier-recovery-cases/{case_id}/counter-approval` |
| POST | `/carrier-recovery-cases/{case_id}/evaluate-timeout` |
| GET | `/incidents/{id}/carrier-recovery-cases` · `/carrier-recovery-cases/{case_id}` · `/carrier-recovery-cases/{case_id}/history` |

**Cargo safety**

| Method | Path |
|---|---|
| POST | `/incidents/{id}/cargo-safety-reviews` |
| POST | `/cargo-safety-reviews/{review_id}/evaluate` |
| GET | `/incidents/{id}/cargo-safety-reviews` · `/cargo-safety-reviews/{review_id}` · `/cargo-safety-reviews/{review_id}/history` |

**Agent runtime and replay**

| Method | Path |
|---|---|
| POST | `/incidents/{id}/agent-runs` |
| POST | `/agent-runs/{run_id}/advance` |
| GET | `/incidents/{id}/agent-runs` · `/agent-runs/{run_id}` · `/agent-runs/{run_id}/history` |
| POST | `/synthetic/scenarios/{id}/canonical-replay/agent-runs` |
| GET | `/synthetic/scenarios/{id}/canonical-replay/stage` |

Endpoints that take no body **reject** a body with `422` rather than ignoring it.

---

## Frontend

React 19 + Vite 8 + Tailwind v4, plain React state — no Redux, Zustand, XState or WebSockets.
`App.tsx` is three lines; `OperationsConsole` is the shell.

**State model.** `useRecoveryConsole()` owns every loaded resource and every mutation command. The
cycle is always: POST mutation → durable response → refetch persisted resources → re-render.
No recovery policy exists in React; the UI joins backend facts and never recomputes them.

**Three modes**

| Mode | Behaviour |
|---|---|
| **Guided** | Stage-by-stage narrative. One `StageActionCard` shows the single next legal action, taken from `canonical-replay/stage`. |
| **Auto** | `autoReplayController` walks stages automatically — and **halts** wherever `auto_replay_may_execute` is false (both approvals, the trade-off decision). |
| **Explore** | Free navigation across the full dashboard workspaces. |

**Seven narrative chapters** map the 16 backend stages onto a story:
Incident → Optimize → Observe → Adapt → Coordinate → Respond → Protect.

**Five workspaces:** Overview · Recovery · Containers · Carrier · Evidence/Audit.

**Design language.** Dark terminal, PSA design tokens in `src/styles/tokens.css` (void/graphite/
charcoal greys, signal blue, amber, fern, coral), Inter + monospace for identifiers. GSAP handles
chapter motion, gated behind `useReducedMotion`. A persistent `SyntheticBanner` and `ActorBadge`
legend keep the synthetic-data disclaimer and actor attribution visible at all times.

Approved layout spec: `docs/superpowers/specs/2026-08-23-psa-ui-phase2-phase3-design.md`.

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

Vite proxies `/synthetic`, `/incidents`, `/agent-runs`, `/carrier-recovery-cases`,
`/allocation-tradeoff-reviews` and `/cargo-safety-reviews` to the backend, so no CORS setup is
needed in development.

Stop: `lsof -ti:8000 | xargs kill` and `lsof -ti:5173 | xargs kill`.
Reinstall: `uv sync --python 3.12 --extra dev` and `npm install`.
More detail in `LOCAL-DEV.txt`.

---

## Tests

```bash
# Backend — 543 tests, credential-free and network-free
uv run --python 3.12 --extra dev pytest backend/tests -q

# Frontend — 104 tests across 22 files
cd web && npm test

# Types and lint
cd web && npm run typecheck && npm run lint

# Lockfile integrity
uv lock --check
```

Current status: **541 passed, 2 skipped** (the two skips are the opt-in live-provider smoke tests,
which require `RUN_LIVE_LLM_TESTS=1`), and **104 frontend tests passing**.

The suites assert the authority boundaries directly, not just the happy path — among them: DG
constraints are never bypassed; no carrier schedule is ever modified locally; never more than 8
expedite jobs are allocated; no RTA is sent without operator approval; a timeout triggers
recomputation; low-confidence containers are reconsidered; every material action produces an audit
event; and the agent cannot execute a tool that was not exposed to it.

---

## Evaluation and measured results

### Headline: stochastic allocator vs. median-threshold baseline

Run on **50 frozen holdout seeds × 50 worlds = 2,500 scenario worlds**
(`SYN-CANONICAL-24-HOLDOUT-V1`). The holdout seeds were frozen before evaluation and were never used
to tune the fixture, distributions, allocator, Pareto filter or dominance policy.

| Metric | P50-greedy baseline | Scenario-aware CP-SAT | Delta |
|---|---:|---:|---:|
| Expected preserved connections | 12.0136 | **12.5088** | **+0.4952 (+4.12%)** |
| Preserved connections (2,500 worlds) | 30,034 | **31,272** | +1,238 |
| Expected rollovers | 11.9864 | 11.4912 | −0.4952 |
| p10 preserved | 8 | 8 | — |
| Expedite slots used | 8 / 8 | 8 / 8 | — |
| Capacity violations | 0 | 0 | — |
| Unsafe allocations | 0 | 0 | — |

Reproducibility key `d0dc76fb…5fe21`. Regenerate:

```bash
uv run --python 3.12 --extra dev python -m backend.app.evaluation.benchmark \
  --output docs/evaluations/2026-08-22-scarcity-benchmark.json
```

The two allocators share only **four of eight** slots. The baseline loads SF1 (16,535 preserved
worlds on SF1, 6,594 on JV2); the scenario-aware allocator rebalances toward JV2 (10,830 / 13,537),
because containers whose p50 clears the boundary but whose p90 does not are worth less than
containers with a tighter band. That is exactly the effect a median threshold cannot see.

### Deterministic evidence package (Phase 8)

```bash
uv run --python 3.12 --extra dev python -m backend.app.evaluation.evidence \
  --output-json docs/evaluations/phase8-evidence-report.json \
  --output-markdown docs/evaluations/phase8-evidence-summary.md \
  --runtime-repetitions 20
```

Fingerprint `d707b991…e543`. Verified claims include:

- `agent_zero_model_credentials` — 0 provider clients constructed, no API key present
- `agent_no_unavailable_tool_execution` — `hold_feeder`, `change_carrier_schedule`,
  `override_dg_rule`, `set_yard_capacity` neither exposed nor invoked
- `agent_successful_tool_order` — `pause_agent_run → request_expedite_feasibility →
  prepare_rta_request → send_authorised_rta_request → request_cargo_safety_review` in 6 steps
- `authority_request_approval_required` / `authority_counter_approval_required` /
  `authority_*_fingerprint_bound` — unapproved or wrong-fingerprint sends raise and change nothing
- `authority_carrier_silence_is_absence` — silence persists zero `CarrierResponse` rows
- `safety_policy_owns_disposition`, `safety_checker_failure_fails_closed`,
  `safety_checker_scope_limited`, `safety_terminal_escalation`
- `human_tradeoff_boundary`, `human_tradeoff_auto_replay_halts`,
  `human_tradeoff_committed_slots_immutable`
- `audit_material_action_coverage` — 8 / 8 required categories covered, with a provenance map from
  every claim to the exact durable record backing it
- `deterministic_local_runtime` — p50 610 ms, p95 672 ms over 20 repetitions, explicitly labelled
  `LOCAL_MACHINE_DEPENDENT` and **not** a production SLA

The report deliberately publishes what it could *not* prove. `full_18_preserved_5_rolled_1_escalated`
is recorded as **NOT_ESTABLISHED**: no complete disjoint durable ledger classifies all 24 containers,
so the plan's 18/5/1 target is reported as unproven rather than asserted.

### Live provider evidence (Phase 9, opt-in)

Latest bounded run — 10/10 calls succeeded, 1/1 complete workflow, p50 **1,728 ms**, p95 **2,378 ms**
(client-observed request latency). Token usage per call is recorded per stage: ~306–1,244 input,
25–129 output. Cost is reported as `NOT_ESTABLISHED / NO_PRICING_SNAPSHOT` rather than estimated from
memory. Artifacts in `docs/evaluations/live/`.

The live agent selected the same tool sequence as the deterministic replay
(`pause_agent_run → request_expedite_feasibility → prepare_rta_request →
send_authorised_rta_request → request_cargo_safety_review`) — the authority boundary holds with a
real model behind it, not only a scripted one.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./backend/transshipment.db` | Persistence target |
| `ALLOWED_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | Exact CORS origins, comma-separated |
| `OPENAI_API_KEY` | — | Only for live agent/safety calls; never required for the demo |
| `OPENAI_AGENT_MODEL` | `gpt-5.6-luna` (deployment sets `gpt-5.6-terra`) | Agent tool-selection model |
| `OPENAI_MODEL` | `gpt-5.6-luna` | DG semantic-safety model |
| `RUN_LIVE_LLM_TESTS` | unset | Enables opt-in live smoke tests |
| `PHASE9_LIVE_MAX_CALLS` / `PHASE9_LIVE_MAX_RUNS` | — | Hard caps for the live harness (≤10 / =1) |
| `PORT` | — | Required by the container entrypoint |
| `VITE_API_BASE_URL` | `""` (dev proxy) | Public API origin baked into the browser bundle |

`ALLOWED_ORIGINS` is validated strictly, and the validator is tested: no `*`, no paths, query
strings or fragments, no credentials in the URL, no trailing-slash variants, no duplicate origins
after default-port normalisation, and no plain `http` except for localhost.

---

## Deployment

Backend on Railway from the root `Dockerfile` (uv + Python 3.12, `--frozen --no-dev`, `web/` and
`docs/` excluded from the image); frontend on Vercel with project root `web/`.

- Attach a persistent volume at `/data` and set `DATABASE_URL=sqlite:////data/transshipment.db`.
- Health check `GET /healthz` → `{"status":"ok","database":"ready"}`.
- `OPENAI_API_KEY` is a server-only secret. It must never appear in a `VITE_` variable, the bundle,
  logs, responses, artifacts or the image — verified by a sentinel scan of `web/dist` using
  disposable values.
- Rollback is configuration-first: restore the previous release while **retaining** the `/data`
  volume. Deleting or reinitialising the volume is never a rollback step.

Full runbook, including the CORS verification curls and the human-authorization gate for any live
provider spend: `docs/deployment.md`.

---

## Safety and security posture

- **Prompt injection.** Cargo notes and carrier messages are untrusted data. Both system prompts say
  so explicitly, and — more importantly — neither model has a tool or output field capable of acting
  on an injected instruction. Injection can at most produce a semantic-evidence string; the frozen
  policy still decides.
- **Fail closed.** Provider timeout, provider error, invalid output, missing configuration and
  malformed tool arguments all route to escalation, never to a permissive default.
- **No local mutation of external authority.** Carrier schedules, DG rules and yard capacity have no
  write path anywhere in the codebase.
- **Approval binding.** Every operator approval is bound to a payload fingerprint, so an approval
  cannot be replayed against a different payload.
- **Append-only audit.** Every material action writes an `AuditEvent` with a typed actor
  (`AGENT` / `SOLVER` / `POLICY` / `OPERATOR` / `CARRIER` / `SYSTEM`). Decisions supersede rather than
  mutate.
- **Credential isolation.** The deterministic suite and the entire Phase-8 evidence package assert
  that zero provider clients were constructed and no key was present.
- **Secret hygiene.** `.env` is gitignored, `.env.example` carries placeholders only, the Docker
  image excludes `.env` and databases, and no secret is ever exposed through a `VITE_` variable.

---

## Honest limitations

Known before a judge finds them:

- **The berth-time lever is an inference.** Real terminals may negotiate the cargo cut-off rather
  than the carrier's berth arrival, and DCSA's Port Call standard puts cargo operations out of scope.
  The berth request is used because it is the only publicly standardised terminal-to-carrier timing
  mechanism. If the lever differs, nothing about the agent's role changes.
- **The problem size is not publicly measured.** Nobody publishes how often transshipment
  connections fail or what it costs, so no such number is invented here. This is true of
  terminal-internal data generally.
- **All data is synthetic.** The +4.12% improvement is a real, reproducible result *on this
  synthetic fixture and these frozen seeds*. It is a claim about the allocator's behaviour under a
  stated distribution, not a business-impact figure.
- **The 18/5/1 canonical target is NOT_ESTABLISHED.** The evidence package says so explicitly rather
  than reporting the target as an outcome.
- **Runtime numbers are local-machine measurements**, labelled as such, and are not a production SLA.
- **Live cost is NOT_ESTABLISHED** pending a committed pricing snapshot; it is not estimated from
  memory.
- **Transshipment is a crowded theme.** ~90% of Singapore's throughput is transshipment, so many
  teams land nearby. This scope — container-level decisions *after* the connection is already broken
  — is deliberately much narrower than the likely field.

---

## Documentation map

| Path | What it is |
|---|---|
| `docs/specs/psa-code-sprint-final-plan.md` | The canonical plan. Scope disputes resolve here. |
| `docs/superpowers/specs/` | Per-phase design documents (carrier recovery, DG safety, agent runtime, dynamic yard, UI, replay harness, evidence, deployment) |
| `docs/superpowers/plans/` | Per-phase implementation plans |
| `docs/coordination/DECISIONS.md` | **Append-only** record of changes to frozen interfaces, architecture or scope |
| `docs/coordination/WORKSTREAMS.md` | Task ownership, base/result SHAs, status |
| `docs/evaluations/` | Benchmark JSON, Phase-8 evidence report + summary, Phase-9 live runs |
| `docs/deployment.md` | Railway + Vercel operator runbook |
| `shared/fixtures/README.md` | Full provenance of every synthetic fixture |
| `LOCAL-DEV.txt` | Local dev cheat sheet |
| `AGENTS.md` | UI/design skill protocols for contributors |
| `UI_REVIEW.md` | Frontend design review notes |

---

**Stack:** Python 3.12 · FastAPI · Pydantic v2 · SQLModel / SQLite · OR-Tools CP-SAT · OpenAI
Responses API (optional) · React 19 · Vite 8 · Tailwind v4 · GSAP · Vitest · pytest · uv

**All data in this repository is synthetic.** It does not contain, represent, or integrate with any
PSA, carrier, manifest, schedule or yard system.
