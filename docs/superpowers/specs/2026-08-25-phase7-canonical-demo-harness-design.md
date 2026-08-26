# Phase 7: Canonical End-to-End Demo Harness Design

**Status:** Approved architectural design, ready for implementation planning

**Date:** 2026-08-25

**Base:** main `4e2e93c66391c31c65b92b387b8f4ef45a09cf13` (Phase 6 merged and frozen)

**Scope:** A replayable, credential-free canonical hero demo with two modes — Guided Demo (primary judging path) and Synthetic Auto Replay (rehearsal/recording path) — driven by a read-only replay projector over existing persisted state, a deterministic canonical demo `AgentModel`, and the real production-shaped APIs. No second recovery workflow, no background production agent, no new authority.

## 1. Goal / non-goals

### Goal

The canonical hero must be replayable from clean synthetic state to safe escalation:

1. create canonical incident
2. bootstrap PRE_DISCHARGE
3. start AgentRun (canonical demo run)
4. explicit agent advance → pause at `NEW_OPERATIONAL_EVIDENCE`
5. wait for active evidence
6. publish DISCHARGE_ACTIVE
7. explicit agent advance → deterministic reconsideration
8. R0 → R1 (SYN-CNT-005 OUT/CANCELLED, SYN-CNT-001 IN/PLANNED, SYN-CNT-002/004 stay COMMITTED)
9. preserved totals 601 → 602 across 50 worlds; expected 12.02 → 12.04
10. agent prepares JV2 recovery; affected set exactly SYN-CNT-017
11. REQUEST_APPROVAL; operator approves exact fingerprint-bound request
12. agent sends authorised RTA; carrier returns COUNTER
13. COUNTER_APPROVAL; operator approves exact fingerprint-bound counter
14. agent advances/recomputes resume
15. persist canonical SYN-CNT-010 contradiction evidence
16. agent evaluates persisted safety evidence → semantic result CONTRADICTION_FOUND
17. deterministic policy blocks automation
18. final AgentRun: ESCALATED / SAFETY_REVIEW_REQUIRED

The correct terminal state is **safe escalation**. Success is never reinterpreted as automatically completing recovery.

Both modes work with zero OpenAI credentials and zero network calls to model providers.

### Non-goals

- Live-model production hardening, deployment, OpenAI credential configuration (Phase 9).
- Evaluation framework expansion, portfolio/deck/video work (Phase 10).
- Final UI polish unrelated to demo comprehension.
- New solver behavior, new Phase 3 negotiation semantics, new Phase 4 safety authority.
- Background/autonomous production agent execution of any kind.
- Enterprise infrastructure (auth, multi-tenancy, persistence hardening).
- Generic destructive database reset.

## 2. Current-state context (repository facts this design builds on)

Verified against the repository at the base SHA:

- `AgentRuntimeCoordinator.advance()` executes **exactly one** model decision per call: `_execute_turn` always returns an `AgentRun`, so the per-advance loop in `backend/app/orchestration/agent_runtime.py:100-107` performs one `_decide_once` and returns. One explicit advance == exactly one durable tool invocation. This makes canonical stages map 1:1 onto explicit advances.
- The model seam exists: `create_app(*, ..., agent_model: AgentModel | None = None)` defaults to `OpenAIAgentModel()` (`backend/app/main.py:133,200-202`). Without credentials, advance escalates `MODEL_UNAVAILABLE` after one retry — proven in the Phase 6 dev-proxy smoke log ("direct HTTP advance escalated with MODEL_UNAVAILABLE because the local app has no model credentials"). Today the guided console therefore cannot complete the hero credential-free. Phase 7 fixes exactly this.
- `AgentRuntimeCoordinator(..., cargo_safety_checker=None)` is an existing injection seam used by tests via `FakeSemanticSafetyChecker`; `CargoSafetyWorkflow.for_session` defaults to `OpenAISemanticSafetyChecker()`. A checker failure produces `CHECK_FAILED`, not `CONTRADICTION_FOUND` — so the safety peak also needs a credential-free deterministic path for demo runs only.
- `AgentRun.model_name` is persisted durably at creation from the bound model (`orchestration/agent_runtime.py:81`) — a clean hook for per-run model resolution without changing any coordinator logic.
- Carrier case state machine (`backend/app/domain/carrier_recovery.py:233-237`): `PREPARED → AWAITING_REQUEST_APPROVAL → {AWAITING_CARRIER, RECOMPUTING}`; `AWAITING_CARRIER → {AWAITING_COUNTER_APPROVAL, RECOMPUTING}`; `AWAITING_COUNTER_APPROVAL → RECOMPUTING`; `RECOMPUTING → {COMPLETED, ESCALATED}`. Request/counter rejections flow through `RECOMPUTING` with typed `ReconsiderationEvidenceKind.REQUEST_REJECTED` / `COUNTER_REJECTED`.
- Advancing while `AWAITING_COUNTER_APPROVAL` raises one expected `409` that upgrades the persisted wait kind to `COUNTER_APPROVAL` (`orchestration/agent_runtime.py:265-269`; documented Phase 6 behavior mirrored by frontend `canAdvanceAgent`).
- Trusted canonical RTA configuration lives in `shared/fixtures/canonical-agent-runtime-config.json`: JV2 prepared_at `2026-08-23T00:00:00Z`, requested_eta_pta `04:00:00Z`, response_deadline `06:00Z`; trusted clocks `before_deadline = 2026-08-23T05:00:00Z`. The existing canonical hero test simulates the carrier COUNTER at `2026-08-23T05:00:00Z` (before deadline). These differ from the legacy direct-API `CARRIER_DEMO_TIMESTAMPS` in `web/src/lib/canonicalDemo.ts` (Phase 3 compatibility path); the Phase 7 hero uses only the trusted configuration through the agent's prepare tool.
- Assessment metrics field names are exact: `preserved_connection_total_before/after` (integers 601/602) and `expected_preserved_connections_before/after` (12.02/12.04) on `ExpediteReconsiderationAssessment` (`backend/app/domain/dynamic_yard.py:132-135`).
- Frontend already loads the full incident bundle (incident, fixture, scarcity, decisions, audit, carrier cases + histories, yard forecasts/revisions/commitments/assessments/tradeoff reviews/options, safety reviews + histories, agent runs + history) through `useRecoveryConsole`, refreshes after every mutation, and refreshes again on any `409`. `SyntheticDemoControl` exposes guided actions only and explicitly promises "No autoplay, run-all, replay, reset."
- Existing canonical carrier demo definitions ACCEPT-RUN / COUNTER-RUN / SILENT-RUN live in `web/src/lib/canonicalDemo.ts` with direct Phase 3 API controls in `useRecoveryConsole` (prepare/approve/send/simulate/counter/timeout with operator id `operator-console`). They remain functional compatibility support.

## 3. Architecture

Hybrid derived replay harness — approved shape, made concrete:

```text
Real persisted recovery state (incidents, agent runs/history,
forecasts, revisions, commitments, assessments, tradeoff reviews,
carrier cases/history/bindings/approvals/responses, safety
reviews/histories, audit events)
        |
        v
CanonicalReplayProjector  (backend, read-only, pure function of
durable state; no new mutable tables)
        |
        v
GET /synthetic/scenarios/{incident_id}/canonical-replay/stage
        |
        v
SyntheticDemoControl (Guided) / AutoReplayController (frontend loop)
        |
        v
existing production-shaped APIs (create/bootstrap/publish/advance/
simulate/approve/create-review), including the new synthetic-scoped
demo-run creation endpoint
```

Decisions and rationale:

- **The projector is backend, read-only, and single.** Both modes consume one projection endpoint rather than duplicating stage-mapping logic in TypeScript. Stage truth is derived fresh from durable state on every read; there is no stored step counter anywhere. Refresh/reload reconstructs the identical stage because it derives from the same immutable records. Backend tests can assert stage mapping directly against seeded domain state.
- **The Auto Replay controller lives in the frontend** over existing APIs (approved recommendation; nothing in the repo contradicts it). It is a bounded explicit-action loop, not a background process; it dies with the page and leaves no server-side residue beyond the same durable records Guided mode produces.
- **Deterministic model support lives in the backend behind the existing injection seams**: run-level `model_name` resolution for the agent decisions, and the coordinator's `cargo_safety_checker` parameter for the deterministic semantic check. `AgentRuntimeCoordinator` logic is not forked; the registry, state checks, waits, guards, escalation paths, and validation are all unchanged.
- **No parallel recovery implementation.** Every mutation in both modes hits the same endpoints Guided operations use today. The only new mutating endpoint creates a demo-bound AgentRun; everything else already exists or is read-only.

### New backend modules

| Module | Content |
|---|---|
| `backend/app/domain/canonical_replay.py` | Frozen pydantic contracts: `CanonicalReplayStageView` (stage, ordinal, status, explanation, deviation_reason, next_action, flags), `CanonicalReplayActionType`, stage/status enums. |
| `backend/app/services/canonical_replay.py` | Constants (`CANONICAL_REPLAY_MODEL_NAME`, `SYNTHETIC_DEMO_OPERATOR_ID`, canonical connection/container/note/effective-at constants below), `CanonicalReplayAgentModel`, `CanonicalReplaySemanticChecker`. |
| `backend/app/orchestration/canonical_replay.py` | `project_canonical_replay_stage(session, incident_id) -> CanonicalReplayStageView` plus the small evidence-gathering helpers it needs (all reads via existing repositories/workflow history methods). |

### Additive context change

`build_agent_turn_context` gains one additive summary entry so the deterministic model never guesses identities:

```json
"dynamic_yard": {"snapshot_count": n, "forecast_stages": ["PRE_DISCHARGE"], ...},
"cargo_safety_pending_reviews": [{"review_id": "...", "container_id": "SYN-CNT-010"}]
```

`forecast_stages` lists distinct persisted snapshot stages in order; `cargo_safety_pending_reviews` lists reviews in `PENDING_CHECK`. Both are read-only derivations of durable state, consistent with the existing trust labeling. No other context changes.

### New/changed endpoints

| Endpoint | Change | Contract |
|---|---|---|
| `POST /synthetic/scenarios/{incident_id}/canonical-replay/agent-runs` | new, synthetic-scoped | Creates the incident's AgentRun bound to `CanonicalReplayAgentModel` (`model_name = "canonical-replay-agent-v1"` persisted). No body. 201 with `AgentRun`; 404 unknown incident; 409 duplicate active run (same partial-unique constraint as production creation); 422 any body. |
| `POST /agent-runs/{run_id}/advance` | behavior-preserving resolution | Handler resolves the model by the run's **persisted** `model_name` before constructing the coordinator: `"canonical-replay-agent-v1"` → `CanonicalReplayAgentModel` + `CanonicalReplaySemanticChecker` as `cargo_safety_checker`; anything else → current default (`OpenAIAgentModel()`, checker `None`). 404 unknown run unchanged. Coordinator internals untouched. |
| `GET /synthetic/scenarios/{incident_id}/canonical-replay/stage` | new, read-only | 200 `CanonicalReplayStageView`; 404 unknown incident. No mutation of any table; no side effects. |

Normal `POST /incidents/{incident_id}/agent-runs` continues to create OpenAI-bound runs and keeps refusing bodies/budgets/model selectors. Production-shaped runs can never silently become demo runs: the demo binding is visible on `GET /agent-runs/{id}` as `model_name` and is only settable through the synthetic endpoint above.

## 4. Guided Demo

Primary/default mode; the judging path. `SyntheticDemoControl` evolves into a mode-switched control with GUIDED DEMO as the default tab.

At every point the console shows, derived from the projected stage view:

- current canonical stage name and human explanation;
- progress ("Stage k of N" from the stage's fixed ordinal);
- why execution is waiting (wait kind, unresolved condition, external party);
- the single next legal action (button enabled only when the stage permits it);
- relevant persisted evidence (latest revision delta and commitment states, assessment metrics, carrier case state + bindings + responses, pending/completed safety review, latest agent step summaries from `AgentRun` history).

Operator-triggered actions remain exactly the existing ones, each calling one endpoint then refreshing:

- create canonical incident (`POST /synthetic/scenarios/canonical-scarcity`);
- bootstrap PRE_DISCHARGE / publish DISCHARGE_ACTIVE (existing dynamic-yard endpoints);
- start canonical demo AgentRun (new synthetic endpoint above — Guided also uses the demo binding so the whole hero is credential-free);
- explicit agent advance (`POST /agent-runs/{id}/advance`, one action per click);
- simulate carrier response (`effective_at` fixed constant, no payload construction);
- approve/reject request and counter (real endpoints, fingerprint taken from the persisted binding via case history, `operator_id="operator-console"`);
- persist canonical SYN-CNT-010 review (real Phase 4 create endpoint with the pinned note text/source); evaluation itself is **not** a Guided control on the hero path — the agent evaluates via its tool, keeping "the agent evaluates persisted safety evidence" visible in run history.

Human authority moments are real and prominent: `REQUEST_APPROVAL_REQUIRED` and `COUNTER_APPROVAL_REQUIRED` stages render a "HUMAN APPROVAL REQUIRED" badge showing subject kind, decision/request/response identifiers, and the exact expected payload fingerprint copied from the persisted `ApprovalBinding`. Approve and Reject are both offered.

**Rejection is real.** If the operator rejects the outbound request or the counter proposal, Phase 3 persists the rejection, recomputes, and drives the case to `ESCALATED`; the projector maps the resulting state to `OFF_CANONICAL_PATH` (deviation reasons `REQUEST_REJECTED` / `COUNTER_REJECTED`). The harness never forces the scenario back onto the hero: no hidden approvals, no retry-until-approved, no alternate bindings. The UI explains that the run has left the canonical hero path and offers "Start new canonical replay".

## 5. Synthetic Auto Replay

Convenience/rehearsal/recording mode driving the **same** replay sequence through the **same** APIs and projector. It is a bounded frontend controller (`web/src/lib/autoReplayController.ts`), started only by an explicit user action, with a visible running state, current-action display, an append-only on-screen action log (stage → action → result), and Stop support via an abort flag checked between steps (React effect cleanup cancels; no timers, no intervals, no background workers — matching the repo-wide "no fetch-on-interval" guarantee).

Loop per iteration:

1. `GET .../canonical-replay/stage` — refresh persisted truth by re-projecting;
2. if the view marks the stage executable-by-auto, execute **exactly one** allowed action through the normal typed API client;
3. await completion (mutation + bundle refresh, reusing `useRecoveryConsole.runMutation` semantics so `loading`/error surfaces stay consistent);
4. repeat.

Halt conditions (each stops the loop and renders a terminal explanation):

- terminal stage reached (`SAFETY_BLOCKED`, `COMPLETE`, `FAILED`);
- `OFF_CANONICAL_PATH` or `TRADEOFF_DECISION_REQUIRED` (see below);
- any error response (404/422/network) — halt immediately;
- `409` handling below;
- action budget exhausted (`MAX_AUTO_ACTIONS = 40`, comfortably above the ~13 mutating actions of the hero; guards against loops);
- user Stop.

Auto-executable actions only: create incident, bootstrap, start demo run, advance, publish discharge-active, simulate carrier COUNTER, approve request, approve counter, persist safety review.

**Synthetic operator discipline.** When Auto Replay reaches `REQUEST_APPROVAL_REQUIRED` or `COUNTER_APPROVAL_REQUIRED` it performs the approval automatically **only** as the explicitly synthetic operator:

```text
operator_id = "synthetic-demo-operator"
```

Those approvals still use the real approval endpoints, read the real persisted `ApprovalBinding`, submit the exact persisted `payload_fingerprint`, and satisfy identical backend validation. The agent never approves anything — the approval is recorded as a human-authority `Approval` record whose operator id discloses its synthetic nature. Auto Replay never selects tradeoff options (that is a genuine business judgment reserved to a human; if a tradeoff review ever opens, Auto halts at `TRADEOFF_DECISION_REQUIRED`). Auto Replay never calls the cargo-safety evaluate endpoint directly; the agent's own tool does the evaluation so run history shows it.

The Auto Replay panel permanently displays disclosure copy equivalent to:

> "Demo harness automatically performs operator actions using a synthetic operator identity (`synthetic-demo-operator`). Production authority boundaries remain unchanged."

Reload mid-run: the running flag is ephemeral frontend state; the durable stage survives, the console resumes showing the correct projected stage, and Auto Replay is idle until explicitly restarted — whereupon it continues from the projected stage, not from memory.

## 6. Canonical replay projector / state vocabulary

`project_canonical_replay_stage` reads (via existing repositories and workflow history accessors only): incident; scarcity-evaluation existence; yard snapshots; allocation revisions; expedite commitments; reconsideration assessments (+handled); tradeoff reviews/options/selections; JV2 carrier case + full history (state, bindings, approvals, responses, request context); cargo-safety reviews + histories (semantic result, `automation_blocked`); latest AgentRun (`list_runs` ascending, last) + its escalation reason/wait kind; latest safety-relevant agent invocation results if needed. It writes nothing.

Vocabulary (20 stages; names adjusted only where repository semantics demanded precision — `OFF_CANONICAL_PATH` replaces ad-hoc rejected states, `TRADEOFF_DECISION_REQUIRED` covers the legal non-hero-but-legitimate tradeoff branch):

```text
READY_TO_CREATE                  (frontend-local when no incident is loaded)
READY_FOR_PRE_DISCHARGE
READY_TO_START_AGENT
READY_TO_ADVANCE_TO_EVIDENCE_WAIT
WAITING_FOR_ACTIVE_EVIDENCE
READY_TO_RECONSIDER
READY_TO_PREPARE_RTA
REQUEST_APPROVAL_REQUIRED
REQUEST_APPROVED_READY_TO_SEND
WAITING_FOR_CARRIER
CARRIER_COUNTER_RECEIVED
COUNTER_APPROVAL_REQUIRED
COUNTER_APPROVED_READY_TO_RESUME
READY_FOR_SAFETY_EVIDENCE
SAFETY_REVIEW_PENDING
SAFETY_BLOCKED                   (terminal success)
COMPLETE                         (terminal)
FAILED                           (terminal)
TRADEOFF_DECISION_REQUIRED       (human-only halt)
OFF_CANONICAL_PATH               (terminal-for-demo, typed reason)
```

Each stage view carries:

- `stage`, `ordinal` (fixed positions 1..15 over the linear hero prefix `READY_TO_CREATE` … `SAFETY_REVIEW_PENDING`; the three terminal stages share ordinal 16; `TRADEOFF_DECISION_REQUIRED`/`OFF_CANONICAL_PATH` report the ordinal of the state where deviation occurred plus the typed deviation), `progress_label` ("Stage k of N");
- `status`: `PENDING_ACTION` | `WAITING_HUMAN` | `WAITING_EXTERNAL` | `TERMINAL_SUCCESS` | `TERMINAL_HALTED`;
- `explanation` (concise, operator-facing);
- `next_allowed_action`: one of `CREATE_CANONICAL_INCIDENT`, `BOOTSTRAP_PRE_DISCHARGE`, `START_DEMO_AGENT_RUN`, `ADVANCE_AGENT`, `PUBLISH_DISCHARGE_ACTIVE`, `SIMULATE_CARRIER_RESPONSE`, `APPROVE_REQUEST`, `APPROVE_COUNTER`, `PERSIST_SAFETY_REVIEW`, `SELECT_TRADEOFF_OPTION`, `NONE`;
- `guided_can_execute`, `auto_replay_may_execute`, `requires_human_authority` booleans.

Human-authority stages: `REQUEST_APPROVAL_REQUIRED`, `COUNTER_APPROVAL_REQUIRED`, `TRADEOFF_DECISION_REQUIRED`.

### Exact mapping rules (evaluated top-down; first match wins)

Let `R` = latest AgentRun for the incident, `C` = the JV2 carrier case (`connection_id == "SYN-CONN-JV2"`), `S` = safety history for SYN-CNT-010 if a review exists.

1. `R` absent:
   - any `DISCHARGE_ACTIVE` snapshot exists → `OFF_CANONICAL_PATH(EVIDENCE_PUBLISHED_BEFORE_AGENT_START)`
   - else any snapshot exists (bootstrap done) → `READY_TO_START_AGENT`
   - else incident + scarcity evaluation exist → `READY_FOR_PRE_DISCHARGE`
2. `R.state == ESCALATED`:
   - reason `SAFETY_REVIEW_REQUIRED` **and** `S.policy_result.automation_blocked is true` **and** `S.assessment.result == CONTRADICTION_FOUND` → `SAFETY_BLOCKED`
   - otherwise → `OFF_CANONICAL_PATH(AGENT_ESCALATION_<reason>)`
3. `R.state == FAILED` → `FAILED`
4. `R.state == COMPLETED` → `COMPLETE`
5. `R.wait_kind == HUMAN_TRADEOFF_DECISION` → `TRADEOFF_DECISION_REQUIRED`
6. `R.wait_kind == NEW_OPERATIONAL_EVIDENCE` → `WAITING_FOR_ACTIVE_EVIDENCE`; next action is `PUBLISH_DISCHARGE_ACTIVE` (status `WAITING_EXTERNAL`) while no unhandled assessment exists, and flips to `ADVANCE_AGENT` (status `PENDING_ACTION`) once the DISCHARGE_ACTIVE ingestion has created it
7. `R.wait_kind == REQUEST_APPROVAL`:
   - any approval on `C` with status `REJECTED` → `OFF_CANONICAL_PATH(REQUEST_REJECTED)`
   - any approval `APPROVED` → `REQUEST_APPROVED_READY_TO_SEND` (next `ADVANCE_AGENT`)
   - else → `REQUEST_APPROVAL_REQUIRED` (next `APPROVE_REQUEST`; guided may also reject)
8. `R.wait_kind == CARRIER_RESPONSE_OR_TIMEOUT`:
   - `C.state == AWAITING_COUNTER_APPROVAL` and a `COUNTER` response exists → `CARRIER_COUNTER_RECEIVED` (next `ADVANCE_AGENT`; this is the documented one-shot upgrade advance that answers 409 and flips the wait kind)
   - `C` still `AWAITING_CARRIER` with no response → `WAITING_FOR_CARRIER` (next `SIMULATE_CARRIER_RESPONSE`)
   - anything else (ACCEPT recompute, silence past deadline, completed case) → `OFF_CANONICAL_PATH(NON_HERO_CARRIER_OUTCOME)` — accept/silent outcomes remain supported by the legacy panels, not by the replay harness
9. `R.wait_kind == COUNTER_APPROVAL`:
   - counter approval `REJECTED` → `OFF_CANONICAL_PATH(COUNTER_REJECTED)`
   - counter approval `APPROVED` (case in `RECOMPUTING`/`COMPLETED`/`ESCALATED`) → `COUNTER_APPROVED_READY_TO_RESUME`; next action is `PERSIST_SAFETY_REVIEW` while no SYN-CNT-010 review exists yet, and flips to `ADVANCE_AGENT` once the review is persisted in `PENDING_CHECK`
   - else → `COUNTER_APPROVAL_REQUIRED` (next `APPROVE_COUNTER`; guided may reject)
10. `R` CREATED/RUNNING/WAITING(other):
    - unhandled reconsideration assessment exists → `READY_TO_RECONSIDER` (next `ADVANCE_AGENT`)
    - open tradeoff review exists → `TRADEOFF_DECISION_REQUIRED`
    - `R.step_count == 0` → `READY_TO_ADVANCE_TO_EVIDENCE_WAIT` (next `ADVANCE_AGENT`)
    - no JV2 case exists yet and bootstrap done → `READY_TO_PREPARE_RTA` (next `ADVANCE_AGENT`)
    - JV2 case terminal (`COMPLETED`/`ESCALATED`) and no SYN-CNT-010 review exists → `READY_FOR_SAFETY_EVIDENCE` (next `PERSIST_SAFETY_REVIEW`; defensive mapping for a run resumed before evidence was persisted)
    - `S` exists with review `PENDING_CHECK` → `SAFETY_REVIEW_PENDING` (next `ADVANCE_AGENT`)
    - otherwise → `OFF_CANONICAL_PATH(UNEXPECTED_PERSISTED_STATE)` with actual state quoted in the explanation

Ordering notes (deliberate): rule 10 orders reconsideration → first-advance → prepare ahead of safety-pending, mirroring the deterministic model's tool priority, so an early-persisted safety review cannot reorder the hero; rule 2 requires all three safety facts so a partially evaluated review can never masquerade as the terminal success.

**Sequencing note (counter-resume).** The coordinator resolves a wait and executes the next model turn inside the **same** advance; there is no advance that "only resumes". The proven hero therefore persists the SYN-CNT-010 review *before* the resuming advance, so that single advance resolves the counter wait and evaluates the safety evidence together. The harness pins this order: after counter approval, the projected stage demands evidence persistence first (`COUNTER_APPROVED_READY_TO_RESUME` → next `PERSIST_SAFETY_REVIEW`) and only then the resuming `ADVANCE_AGENT`. This realizes approved goal steps 23–25 with identical visible outcomes and avoids an intermediate RUNNING state whose only legal model actions would be completion or fallback escalation.

Because every rule reads only immutable/durable records, projecting twice — across refreshes, reloads, processes, or repeated replays of the same incident — yields the identical stage. That property is directly tested.

## 7. Deterministic demo AgentModel

`CanonicalReplayAgentModel` (in `backend/app/services/canonical_replay.py`):

```python
class CanonicalReplayAgentModel:
    model_name = "canonical-replay-agent-v1"
```

It implements the existing `AgentModel` protocol and chooses strictly from `available_tools` using persisted context, in this priority order:

1. `request_expedite_feasibility` available → call it (zero arguments).
2. elif `prepare_rta_request` available **and** the context shows dynamic-yard bootstrap evidence (`forecast_stages` non-empty) → `connection_id` = the **single** value of the tool's `connection_id` enum (registry exposes exactly the compatible set; canonical replay yields exactly `SYN-CONN-JV2`). If the enum is missing or has ≠1 entries → return `InvalidAgentModelTurn(CANONICAL_AMBIGUOUS_CONNECTION)`. If bootstrap evidence is absent, the registry is exposing the legacy pre-5B prepare path; the demo model returns `InvalidAgentModelTurn(CANONICAL_SEQUENCE_VIOLATION)` so a run started before bootstrap fails safely into escalation instead of silently reordering the hero.
3. elif `send_authorised_rta_request` available → `case_id` = the unique context `carrier_cases` entry with state `AWAITING_REQUEST_APPROVAL`; zero or multiple matches → invalid turn.
4. elif `request_cargo_safety_review` available → `container_id` = the unique container in the additive `cargo_safety_pending_reviews` context entry; canonical replay asserts exactly one, `SYN-CNT-010`.
5. elif `context.step_count == 0` and context `forecast_stages == ["PRE_DISCHARGE"]` and `pause_agent_run` available → `pause_agent_run` (zero arguments).
6. else → `escalate_agent_run` (fail-safe; unreachable on the hero).

Guarantees, unchanged from production semantics:

- The tool registry still derives availability from durable state; the model can only pick exposed tools, and every tool revalidates independently (stale decisions still fail closed).
- All policy/authority validation stays active: Phase 3 fingerprints, the Phase 5B stale-plan/compatibility guard, wait precedence, loop guard, step budget, idempotent invocation recovery.
- Durable `AgentRun`/`AgentStep`/`AgentToolInvocation` history is written by the same code path as production; `model_name` on the run and steps reads `canonical-replay-agent-v1`, making demo provenance auditable.
- Normal runs never switch models silently: resolution keys off the persisted `model_name`, which only the synthetic creation endpoint sets.
- No OpenAI credentials, environment variables, or network access are involved.

Activation is exclusively: `POST /synthetic/scenarios/{incident_id}/canonical-replay/agent-runs` (creation) and the `model_name`-keyed resolution inside the advance handler. There is no config flag, query parameter, or fallback that can bind it elsewhere. Live OpenAI execution remains exactly as today for non-demo runs (Phase 9 scope).

### Deterministic semantic checker for demo runs

`CanonicalReplaySemanticChecker` implements the existing `SemanticSafetyChecker` protocol deterministically (`checker_kind = "canonical-replay-deterministic"`, `model_name = None`) and is bound **only** as the coordinator's `cargo_safety_checker` for canonical-replay-run advances (the same narrow seam tests already use). Rule set:

- Input is the existing `SemanticSafetyCheckInput` (trusted structured `dangerous_goods`/`un_number`/`commodity` from the frozen `CargoProfile`; untrusted note text).
- Contradiction iff structured profile declares **no** dangerous goods AND the note text asserts hazardous content, matched by a fixed token list (`UN \d{4}`, `dangerous goods`, `DG`, `hazardous`, `corrosive`, `flammable`, `explosive`, `radioactive`, `toxic`, `lithium-ion batteries`) — case-insensitive word-boundary match. → `CONTRADICTION_FOUND` with an explanation citing the structured commodity and an `evidence_excerpt` quoted verbatim (a substring of the note; the workflow already validates this invariant).
- Benign notes (no hazardous tokens) → `NO_CONTRADICTION_FOUND`.
- The checker never classifies cargo, never infers/corrects a UN number, never assigns DG class, and never decides an operational action — it only reports that untrusted text conflicts with trusted structure, which is exactly the Phase 4 semantic role. The deterministic policy boundary (PASS_THROUGH vs ESCALATE, `automation_blocked`) remains owned entirely by frozen `CargoSafetyWorkflow` code.

Direct `POST /cargo-safety-reviews/{id}/evaluate` keeps the production OpenAI checker. Neither mode calls it on the hero path; the agent's tool performs the evaluation.

## 8. Canonical constants (pinned)

| Constant | Value |
|---|---|
| `CANONICAL_REPLAY_MODEL_NAME` | `"canonical-replay-agent-v1"` |
| `SYNTHETIC_DEMO_OPERATOR_ID` | `"synthetic-demo-operator"` |
| `CANONICAL_JV2_CONNECTION_ID` | `"SYN-CONN-JV2"` |
| `CANONICAL_SAFETY_CONTAINER_ID` | `"SYN-CNT-010"` |
| `CANONICAL_SAFETY_NOTE_TEXT` | `"Manifest declares general cargo; free-text handling note identifies corrosive material and requires safety review."` (matches the existing frontend string) |
| `CANONICAL_SAFETY_NOTE_SOURCE` | `"synthetic-canonical-cargo-note"` (matches the existing frontend string) |
| `CANONICAL_COUNTER_EFFECTIVE_AT` | `"2026-08-23T05:00:00Z"` (inside the trusted config window prepared 00:00Z / deadline 06:00Z; equals the trusted `before_deadline` clock; identical to the existing hero test) |

RTA preparation timing comes solely from `shared/fixtures/canonical-agent-runtime-config.json` via `CanonicalAgentRuntimeConfiguration` — never from the browser, prompt text, or model arguments (unchanged Phase 5A rule).

## 9. Reset / replay isolation

- **Reset = fresh canonical incident.** "Start new canonical replay" invokes the existing `POST /synthetic/scenarios/canonical-scarcity`, which mints a brand-new incident UUID with pristine Phase 1/2 state, and clears local demo selection state. Prior incidents, runs, audits, and evidence are never mutated or deleted — they remain fully inspectable.
- **No destructive endpoints are added.** No delete/wipe route exists in Phase 7; the reset surface is exactly the pre-existing synthetic scenario trigger.
- **Repeat isolation** follows from fresh incident UUIDs: two replays cannot touch each other's revisions, cases, reviews, or runs. Concurrent browser tabs operate on different incidents unless pointed at the same one; the backend's existing conflict codes arbitrate any race.
- **Resume** is free: every stage read re-derives from durable state, so refreshing an active replay mid-hero lands on the exact current stage with the exact remaining legal actions.

## 10. Human authority semantics

- Approvals are always recorded through the real Phase 3 endpoints against the real persisted bindings with the exact persisted fingerprint. Guided uses `operator-console`; Auto Replay uses `synthetic-demo-operator` and says so on screen. No third identity exists.
- The browser never constructs allocations, alters solver results, classifies dangerous goods, infers/corrects UN numbers, approves under the agent identity, sends RTA without an approved binding, bypasses carrier approval, bypasses deterministic safety policy, or displays model chain-of-thought. Agent reasoning appears only as concise persisted action/tool summaries (`action_summary`, invocation result summaries) from `AgentRun` history.
- Tradeoff selection remains human-only in both modes (Auto halts).
- The thesis statements hold verbatim: the agent cannot hallucinate authority it does not have (tool absence = authority absence; unchanged registry), and safety is a policy boundary, not a prompt instruction (contradiction detection feeds a frozen deterministic policy that alone blocks automation).

## 11. Carrier COUNTER canonical path

After `prepare_rta_request(SYN-CONN-JV2)` (trusted config timing; Phase 5B compatibility guard passes because R1 preserves JV2 membership and forecast equivalence), the run waits `REQUEST_APPROVAL`. Approval → advance → `send_authorised_rta_request(case_id)` (binding validates; invocation crash-recovery semantics unchanged) → wait `CARRIER_RESPONSE_OR_TIMEOUT`. The synthetic harness publishes the carrier's decision via the existing `POST /carrier-recovery-cases/{case_id}/simulate-carrier-response` with `effective_at = CANONICAL_COUNTER_EFFECTIVE_AT`; the simulator returns the canonical COUNTER (counter ETA `2026-08-22T06:45:00Z` per the existing carrier simulator definition). The runtime upgrades the wait to `COUNTER_APPROVAL`; approval (human or disclosed synthetic operator, fingerprint-bound) lets the next advance resolve the wait after Phase 3's deterministic reconsideration completes (`RECOMPUTING → COMPLETED` for the accepted counter). Affected set stays exactly `SYN-CNT-017` throughout.

## 12. Dynamic-yard R0/R1 canonical evidence

Unchanged from frozen Phase 5B: bootstrap creates PRE_DISCHARGE (±30 min bands), R0 = {002, 004, 005, 010, 011, 012, 014, 015}, PLANNED commitments for each, 002/004 promoted COMMITTED. Discharge-active ingestion (±17.987433384504683 min bands, SF1 container 005 p50 moved three minutes earlier) creates the assessment with exact metrics `preserved_connection_total_before/after = 601/602` and `expected_preserved_connections_before/after = 12.02/12.04` across the same 50 reconstructed worlds. The agent's zero-argument `request_expedite_feasibility()` applies `AUTO_SUPERSEDE` (dominance selects the unique hard-safe optimum): R1 = {001, 002, 004, 010, 011, 012, 014, 015}, SYN-CNT-005 CANCELLED (while PLANNED), SYN-CNT-001 PLANNED, 002/004 locked. The harness publishes evidence but never computes projections, solves, or selects allocations in the browser.

## 13. Cargo-safety canonical contradiction

The operator (or Auto Replay) persists the review through the existing Phase 4 create endpoint for `SYN-CNT-010` with the pinned note text/source; the trusted profile declares general cargo. The agent's `request_cargo_safety_review("SYN-CNT-010")` evaluates the pending review through `CargoSafetyWorkflow` with the demo checker producing `CONTRADICTION_FOUND`; frozen policy sets disposition `ESCALATE`, `automation_blocked = true`, creates the escalation decision with supersession lineage, and the runtime ends the run `ESCALATED / SAFETY_REVIEW_REQUIRED`. Pipeline displayed: trusted structured CargoProfile + untrusted CargoNote → semantic inconsistency detection → deterministic policy → PASS_THROUGH or ESCALATE.

## 14. Error / conflict handling

| Condition | Guided behavior | Auto Replay behavior |
|---|---|---|
| Stale persisted state (UI behind DB) | Next action disabled or backend rejects; Refresh re-projects; UI follows new stage | Detected at each iteration start because stage is fetched fresh before acting |
| `404` (incident/run/case/review gone) | Error surfaced; refresh offered | Halt immediately with the error in the log |
| `409` conflict | Existing semantics: surface message **and** refresh; re-projected stage governs what is legal next; the known `AWAITING_COUNTER_APPROVAL → COUNTER_APPROVAL` upgrade advance intentionally 409s once and is labeled as such in the stage explanation | Refresh + re-project once; continue **only if** the new stage permits a legal action (including the deliberate upgrade case); if the re-projected stage indicates the same attempted action again → halt. Never blindly retry a mutating operation |
| `422` invalid request | Error surfaced (harness bug, not user error) | Halt immediately |
| Deterministic model mismatch (unavailable tool, ambiguous enum, ambiguous ids) | Runtime's existing invalid-output contract escalates `INVALID_MODEL_OUTPUT`; projector maps to `OFF_CANONICAL_PATH(AGENT_ESCALATION_INVALID_MODEL_OUTPUT)` | Same, via stage; loop halts at terminal |
| Unexpected projected state (`UNEXPECTED_PERSISTED_STATE`) | Explanation quotes actual durable state; offer new replay | Halt at `OFF_CANONICAL_PATH` |
| Step/action budget exhausted | Not applicable (explicit clicks) | Halt at 40 actions with budget message |
| Cancellation | Not applicable | Abort flag between iterations; in-flight request completes or errors normally; no orphan server state beyond the last completed action |
| Backend unavailable / network failure | Existing ApiError surfacing | Halt immediately |
| Refresh/reload mid-run | Stage re-derived; controls follow projected stage | Controller state resets to idle; restart resumes from projected stage |
| Rejection branches | `OFF_CANONICAL_PATH(REQUEST_REJECTED|COUNTER_REJECTED)`; explain departure; offer new replay | Halts (Auto itself only ever approves, so these arise only from out-of-band interference) |

General rule: `409` means *refresh persisted truth, re-project, continue only if the new stage permits*; mutating operations are never retried blind.

## 15. UI behavior

`SyntheticDemoControl` becomes a mode-switched section with two clearly separated modes; **GUIDED DEMO is default and primary**. Shared stage header renders: stage name, progress label, status chip, explanation, and the actor attribution for the next action (`AGENT ACTION` / `OPERATOR ACTION` / `SYNTHETIC EVIDENCE ACTION`), plus a `HUMAN APPROVAL REQUIRED` badge on authority stages showing the binding fingerprint. Terminal success renders the safe-escalation outcome prominently (ESCALATED / SAFETY_REVIEW_REQUIRED with contradiction evidence); errors/conflicts render in the existing error region with the projected-stage explanation.

AUTO REPLAY adds: Start / Stop controls (Start enabled only when the projected stage is auto-executable), running indicator, current action line, scrollable action log, budget display, and the permanent synthetic-operator disclosure quoted in §5. Auto Replay is visually secondary (collapsed by default is acceptable) and never auto-starts.

Existing panels (`AgentRunPanel`, `DynamicYardPanel`, `TradeoffReviewPanel`, `CargoSafetyPanel`, `CarrierRecoveryPanel`, recovery table, audit timeline) remain the evidence surfaces; stage-aware enablement gates duplicate actions so the demo control and specialist panels cannot issue conflicting mutations simultaneously (buttons disable while a mutation is in flight — existing `loading` behavior).

## 16. Existing demo compatibility

- ACCEPT-RUN and SILENT-RUN keep working through the existing direct Phase 3 controls (`prepareCarrierRecovery` with legacy `CARRIER_DEMO_TIMESTAMPS`, send/simulate/timeout, `loadDemoRun` selection). Tests covering them keep passing.
- The legacy COUNTER-RUN direct path remains functional but is superseded as a demo narrative by the Phase 7 canonical hero, which produces the same COUNTER outcome through the agent path with stronger authority guarantees.
- The Phase 6 guided buttons (bootstrap/start/advance/publish/safety-create) remain, now stage-gated and augmented with the demo-run start. The old "no autoplay/run-all/replay/reset" promise text is updated to describe the two sanctioned modes; the underlying guarantee (no hidden automation; every action explicit and logged) is unchanged.

## 17. Testing strategy

Ordinary tests make zero network calls and require no credentials. Verification commands inherit Phase 6's (`uv run --python 3.12 --extra dev pytest backend/tests -q`, `uv lock --check`, web `npm test -- --run` / `typecheck` / `build` / `lint`, `git diff --check`, `git status --short`).

Backend (new files under `backend/tests/`):

1. **Projector mapping** (`test_canonical_replay_projector.py`): seed each persisted-state permutation via production workflows and assert the exact stage/ordinal/status/next-action/flags; precedence rules (escalation-vs-safety facts, rejection-before-approved, prepare-before-safety-pending); `OFF_CANONICAL_PATH` reasons.
2. **Refresh/resume determinism**: project repeatedly and after simulated reload boundaries; assert identical views; assert projection mutates nothing (repository snapshots equal).
3+4. **Full canonical hero, Guided-shaped and API-driven** (`test_canonical_replay_hero_api.py`): drive the entire §1 sequence through `TestClient` using the demo run endpoint and real approval/simulation/review endpoints; assert every exact canonical assertion listed in §18.
5+6. **Rejection leaves the hero** (`test_canonical_replay_rejections.py`): request rejection and counter rejection each end `OFF_CANONICAL_PATH(REQUEST_REJECTED|COUNTER_REJECTED)` with the case escalated and no forced recovery.
7. **Synthetic operator identity**: Auto-shaped flow asserts recorded `Approval.operator_id == "synthetic-demo-operator"` while Guided assertions keep `"operator-console"`.
8. **Fingerprint binding exactness**: wrong fingerprint → 409 and no state change; exact persisted fingerprint succeeds; identical for both subjects.
9+10. **Authority negatives**: browser-facing routes accept no allocation/optimizer/fingerprint-inference inputs (contract tests on request bodies); agent-side approval impossible (no such tool; send without approval rejected/persisted).
11+12. **Demo model constraints** (`test_canonical_replay_agent_model.py`): policy picks only available tools in priority order; ambiguous enum/ids yield invalid turns; integration proof that demo-model decisions flow through `AgentRuntimeCoordinator` (durable steps/invocations identical in shape to the existing hero test, including REJECTED-invocation handling and loop-guard coverage with a deliberately corrupted model instance).
13. **Safety block**: contradiction → `automation_blocked=true`, ESCALATE disposition, supersession lineage, run `ESCALATED / SAFETY_REVIEW_REQUIRED`.
14. **Credential-free**: run the hero suite with `OPENAI_API_KEY` unset and monkeypatched env isolation; assert no provider construction occurs on demo paths.
15. **Auto halt-on-failure**: simulated 409-loop and 404 force halts at the controller boundary (mirrored in frontend tests) and at stage level.
16. **Repeat isolation**: two consecutive full replays (fresh incidents) in one database produce independent complete histories; cross-assert no shared rows.
17. **ACCEPT/SILENT compatibility**: existing tests green; add one assertion that legacy paths still function alongside a demo run on another incident.

Frontend:

- `web/src/api/canonicalReplay.test.ts`: stage-view client + demo-run creation client contracts.
- `web/src/lib/autoReplayController.test.ts`: full mocked-hero sequence; budget exhaustion; 409-upgrade continuation; repeated-conflict halt; tradeoff halt; stop mid-sequence; disclosure constant presence.
- `web/src/components/demo/SyntheticDemoControl.test.tsx`: modes, stage rendering, badges, gating, terminal success copy.
- `web/src/components/OperationsConsole.test.tsx`: extend the guided journey with the demo-run start and projected-stage wiring; add a mocked Auto Replay journey ending in safe escalation.

Regression: full backend suite, full frontend suite, typecheck/build/lint, lock check, and a final local HTTP smoke (uvicorn + dev proxy, mirroring the Phase 6 Run C smoke checklist, extended with `/synthetic/scenarios/{id}/canonical-replay/*`).

## 18. Exact acceptance criteria

Phase 7 is accepted only when all of the following hold in ordinary deterministic tests (no credentials, no network):

1. Full hero replayable end-to-end through the real APIs in both Guided-shaped and controller-shaped tests, terminating `ESCALATED / SAFETY_REVIEW_REQUIRED`.
2. Assessment metrics exactly `(601, 602)` and `(12.02, 12.04)`; R1 membership exactly `{001, 002, 004, 010, 011, 012, 014, 015}`; SYN-CNT-005 OUT/CANCELLED; SYN-CNT-001 IN/PLANNED; SYN-CNT-002 and SYN-CNT-004 COMMITTED.
3. JV2 case affected set exactly `("SYN-CNT-017",)`.
4. Safety review SYN-CNT-010: semantic result `CONTRADICTION_FOUND`, `automation_blocked = true`.
5. Recorded approvals carry exact persisted fingerprints; Auto Replay approvals record `synthetic-demo-operator`; no approval ever originates from the agent identity.
6. Demo model emits only the five canonical tool calls on the hero (`pause_agent_run`, `request_expedite_feasibility`, `prepare_rta_request{SYN-CONN-JV2}`, `send_authorised_rta_request{case}`, `request_cargo_safety_review{SYN-CNT-010}`), each durably invoked through `AgentRuntimeCoordinator` with registry filtering and independent revalidation intact; the resuming advance after counter approval resolves the wait and performs the safety evaluation in the same advance (evidence persisted first).
6b. A run advanced before bootstrap, or any out-of-sequence demo decision, fails safely (`CANONICAL_SEQUENCE_VIOLATION` → escalation) rather than reordering the hero.
7. Zero credentials required on every Phase 7 path; production run creation/advance behavior byte-for-byte compatible (non-demo runs still resolve the default model/checker).
8. Projector is pure: repeated/reloaded projections identical; no new mutable tables; stage reconstructable from durable state alone.
9. Both rejection branches land `OFF_CANONICAL_PATH` with typed reasons and clean explanations; no path forces the hero back on.
10. Auto Replay exhibits every §5 halt condition correctly and never issues an undocumented action.
11. Repeat replays are isolated (fresh incidents; no cross-contamination).
12. ACCEPT/SILENT legacy paths unaffected; full backend and frontend suites pass; lint/typecheck/build/lock checks pass; final smoke passes.

## 19. Explicit Phase 8–11 exclusions

Phase 7 excludes and must be implemented without: Phase 9 live-model production hardening, deployment, or credential configuration; Phase 8 evaluation-framework expansion; Phase 11 portfolio/deck/video work; Phase 10 unrelated UI polish; solver changes; new negotiation semantics; new safety authority; background production agent execution; enterprise infrastructure; generic reset/destruction; chat UIs; state-management frameworks; polling loops; any automatic agent invocation outside explicit user actions.
