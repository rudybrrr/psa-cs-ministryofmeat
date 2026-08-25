# Phase 7 Implementation Plan — Canonical End-to-End Demo Harness

**Spec (source of truth):** `docs/superpowers/specs/2026-08-25-phase7-canonical-demo-harness-design.md` (commit `7f77d4ce1c3ff402a25ff188e0c9427bfea3979e`)
**Base:** main `4e2e93c66391c31c65b92b387b8f4ef45a09cf13`
**Branch:** `feat/phase7-canonical-demo-harness`

## Architecture summary

Real persisted recovery state → read-only `CanonicalReplayProjector` (`backend/app/orchestration/canonical_replay.py`) → `GET /synthetic/scenarios/{incident_id}/canonical-replay/stage` → Guided Demo (`SyntheticDemoControl`, default/primary) and Synthetic Auto Replay (`web/src/lib/autoReplayController.ts`) → existing production-shaped APIs. One deterministic demo `AgentModel` (`canonical-replay-agent-v1`) bound per-run via persisted `AgentRun.model_name`; one deterministic semantic checker bound only through the coordinator's existing `cargo_safety_checker` seam for demo-run advances. No second recovery workflow, no mutable replay-step table, no browser optimizer, no browser authority, no background loop, no chain-of-thought.

**Design harmonization note (documented clarification, not a deviation):** spec §7 lists the model's pause rule at priority 5 while §1 goal step 4, §6 projector rule 10 (`step_count == 0 → READY_TO_ADVANCE_TO_EVIDENCE_WAIT`), and §18 acceptance 6 (pause is the first of the five canonical calls) unanimously require the first hero advance to pause even when bootstrap precedes run creation. The plan implements the step-0 gate ahead of the prepare gate so that every explicit requirement holds simultaneously: step 0 with `forecast_stages == ["PRE_DISCHARGE"]` + available `pause_agent_run` pauses; step 0 without bootstrap evidence returns `InvalidAgentModelTurn("CANONICAL_SEQUENCE_VIOLATION")` (acceptance 6b, including the legacy pre-5B prepare path the registry exposes pre-bootstrap). All other priorities keep the spec's order.

## Frozen constants (spec §8)

```
CANONICAL_REPLAY_MODEL_NAME   = "canonical-replay-agent-v1"
SYNTHETIC_DEMO_OPERATOR_ID    = "synthetic-demo-operator"
GUIDED_OPERATOR_ID            = "operator-console"          (existing value)
CANONICAL_JV2_CONNECTION_ID   = "SYN-CONN-JV2"
CANONICAL_SAFETY_CONTAINER_ID = "SYN-CNT-010"
CANONICAL_SAFETY_NOTE_TEXT    = "Manifest declares general cargo; free-text handling note identifies corrosive material and requires safety review."
CANONICAL_SAFETY_NOTE_SOURCE  = "synthetic-canonical-cargo-note"
CANONICAL_COUNTER_EFFECTIVE_AT = "2026-08-23T05:00:00Z"
MAX_AUTO_ACTIONS              = 40
```

RTA preparation timing comes only from `shared/fixtures/canonical-agent-runtime-config.json` via `CanonicalAgentRuntimeConfiguration` (existing Phase 5A rule).

---

## Task 0: Spec taxonomy correction (documentation-only, pre-approved)

**Files:** modify `docs/superpowers/specs/2026-08-25-phase7-canonical-demo-harness-design.md`

- [ ] 0.1 Rename §19 heading to "Explicit Phase 8–11 exclusions"; attribute "portfolio/deck/video work" to Phase 11 and "live-model production hardening/deployment/credential configuration" to Phase 9, "evaluation framework expansion" to Phase 8, "unrelated UI polish" to Phase 10. Preserve every exclusion verbatim otherwise.
- [ ] 0.2 Commit: `docs: align phase 7 spec exclusions with project roadmap taxonomy`.

---

## Task 1: Backend canonical replay domain contracts (TDD)

**Files:**
* create `backend/tests/test_canonical_replay_contracts.py`
* create `backend/app/domain/canonical_replay.py`

Interfaces (exact):

```python
class CanonicalReplayStage(StrEnum):
    READY_TO_CREATE = "READY_TO_CREATE"                       # frontend-local only
    READY_FOR_PRE_DISCHARGE = "READY_FOR_PRE_DISCHARGE"
    READY_TO_START_AGENT = "READY_TO_START_AGENT"
    READY_TO_ADVANCE_TO_EVIDENCE_WAIT = "READY_TO_ADVANCE_TO_EVIDENCE_WAIT"
    WAITING_FOR_ACTIVE_EVIDENCE = "WAITING_FOR_ACTIVE_EVIDENCE"
    READY_TO_RECONSIDER = "READY_TO_RECONSIDER"
    READY_TO_PREPARE_RTA = "READY_TO_PREPARE_RTA"
    REQUEST_APPROVAL_REQUIRED = "REQUEST_APPROVAL_REQUIRED"
    REQUEST_APPROVED_READY_TO_SEND = "REQUEST_APPROVED_READY_TO_SEND"
    WAITING_FOR_CARRIER = "WAITING_FOR_CARRIER"
    CARRIER_COUNTER_RECEIVED = "CARRIER_COUNTER_RECEIVED"
    COUNTER_APPROVAL_REQUIRED = "COUNTER_APPROVAL_REQUIRED"
    COUNTER_APPROVED_READY_TO_RESUME = "COUNTER_APPROVED_READY_TO_RESUME"
    READY_FOR_SAFETY_EVIDENCE = "READY_FOR_SAFETY_EVIDENCE"
    SAFETY_REVIEW_PENDING = "SAFETY_REVIEW_PENDING"
    SAFETY_BLOCKED = "SAFETY_BLOCKED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    TRADEOFF_DECISION_REQUIRED = "TRADEOFF_DECISION_REQUIRED"
    OFF_CANONICAL_PATH = "OFF_CANONICAL_PATH"

class CanonicalReplayStatus(StrEnum):
    PENDING_ACTION | WAITING_HUMAN | WAITING_EXTERNAL | TERMINAL_SUCCESS | TERMINAL_HALTED

class CanonicalReplayActionType(StrEnum):
    CREATE_CANONICAL_INCIDENT | BOOTSTRAP_PRE_DISCHARGE | START_DEMO_AGENT_RUN |
    ADVANCE_AGENT | PUBLISH_DISCHARGE_ACTIVE | SIMULATE_CARRIER_RESPONSE |
    APPROVE_REQUEST | APPROVE_COUNTER | PERSIST_SAFETY_REVIEW |
    SELECT_TRADEOFF_OPTION | NONE

class CanonicalReplayStageView(FrozenContract):
    stage: CanonicalReplayStage
    ordinal: int = Field(ge=1, le=16)
    progress_label: str            # "Stage k of 16"
    status: CanonicalReplayStatus
    explanation: str               # concise operator-facing
    next_allowed_action: CanonicalReplayActionType
    guided_can_execute: bool
    auto_replay_may_execute: bool
    requires_human_authority: bool
    deviation_reason: str | None = None   # EVIDENCE_PUBLISHED_BEFORE_AGENT_START |
                                          # REQUEST_REJECTED | COUNTER_REJECTED |
                                          # NON_HERO_CARRIER_OUTCOME | UNEXPECTED_PERSISTED_STATE |
                                          # AGENT_ESCALATION_<reason>
```

Fixed ordinals: `READY_TO_CREATE`=1 … `SAFETY_REVIEW_PENDING`=15 in the order listed above; `SAFETY_BLOCKED`/`COMPLETE`/`FAILED` share 16.

- [ ] 1.1 RED: contract tests assert enum vocabularies match spec exactly; frozen view rejects mutation; ordinal bounds; progress label format; human-authority stages are exactly {`REQUEST_APPROVAL_REQUIRED`, `COUNTER_APPROVAL_REQUIRED`, `TRADEOFF_DECISION_REQUIRED`}.
- [ ] 1.2 GREEN: implement contracts extending `FrozenContract`.
- [ ] 1.3 Run focused tests green; commit `feat: add canonical replay domain contracts`.

---

## Task 2: Read-only canonical replay projector (TDD)

**Files:**
* create `backend/tests/test_canonical_replay_projector.py`
* create `backend/app/orchestration/canonical_replay.py`

Primary interface:

```python
def project_canonical_replay_stage(session: Session, incident_id: UUID) -> CanonicalReplayStageView
```

Reads only (via existing accessors): `IncidentRepository.get`, `ScarcityEvaluationRepository.get_for_incident` (LookupError tolerated), `DynamicYardWorkflow.for_session(session).history(incident_id)`, `AgentRuntimeRepository.list_runs(incident_id)` (ascending; latest last), `CarrierRecoveryRepository.list_cases(incident_id)` + `.history(case.id)` for the JV2 case (`connection_id == CANONICAL_JV2_CONNECTION_ID`), `CargoSafetyRepository.list_reviews(incident_id)` + `.history(review.id)` for the SYN-CNT-010 review. Writes nothing; no audit events; repeated projection of unchanged state returns an identical view (asserted by snapshotting repository rows before/after).

Exact mapping rules (top-down, first match wins) per spec §6, with pinned deviation ordinals:

1. No run: DISCHARGE_ACTIVE snapshot exists → `OFF_CANONICAL_PATH(EVIDENCE_PUBLISHED_BEFORE_AGENT_START, ordinal 3, TERMINAL_HALTED)`; else any snapshot → `READY_TO_START_AGENT`(3); else scarcity evaluation exists → `READY_FOR_PRE_DISCHARGE`(2); else → `OFF_CANONICAL_PATH(UNEXPECTED_PERSISTED_STATE, 16)`.
2. Run ESCALATED: reason SAFETY_REVIEW_REQUIRED AND SYN-CNT-010 policy_result.automation_blocked AND assessment.result == CONTRADICTION_FOUND → `SAFETY_BLOCKED`(16, TERMINAL_SUCCESS); else `OFF_CANONICAL_PATH(f"AGENT_ESCALATION_{reason.value}")` with deviation ordinal derived from the last completed tool invocation: pause_agent_run→4, request_expedite_feasibility→6, prepare_rta_request→7, send_authorised_rta_request→9, request_cargo_safety_review→14, none→3, other→16.
3. FAILED → `FAILED`(16, TERMINAL_HALTED). 4. COMPLETED → `COMPLETE`(16, TERMINAL_SUCCESS).
5. wait HUMAN_TRADEOFF_DECISION → `TRADEOFF_DECISION_REQUIRED`(6, WAITING_HUMAN, SELECT_TRADEOFF_OPTION, auto=False, requires_human_authority=True).
6. wait NEW_OPERATIONAL_EVIDENCE → `WAITING_FOR_ACTIVE_EVIDENCE`(5): unhandled assessment absent → status WAITING_EXTERNAL / next PUBLISH_DISCHARGE_ACTIVE; present → PENDING_ACTION / next ADVANCE_AGENT.
7. wait REQUEST_APPROVAL: any JV2 approval REJECTED → `OFF_CANONICAL_PATH(REQUEST_REJECTED, 8)`; any APPROVED → `REQUEST_APPROVED_READY_TO_SEND`(9, ADVANCE_AGENT); missing JV2 case → UNEXPECTED_PERSISTED_STATE; else `REQUEST_APPROVAL_REQUIRED`(8, WAITING_HUMAN, APPROVE_REQUEST, requires_human_authority=True).
8. wait CARRIER_RESPONSE_OR_TIMEOUT: AWAITING_COUNTER_APPROVAL + COUNTER response → `CARRIER_COUNTER_RECEIVED`(11, ADVANCE_AGENT; explanation names the expected one-shot 409 upgrade); AWAITING_CARRIER + no response → `WAITING_FOR_CARRIER`(10, WAITING_EXTERNAL, SIMULATE_CARRIER_RESPONSE); else → `OFF_CANONICAL_PATH(NON_HERO_CARRIER_OUTCOME, 10)`.
9. wait COUNTER_APPROVAL: REJECTED → `OFF_CANONICAL_PATH(COUNTER_REJECTED, 12)`; APPROVED and case in {RECOMPUTING, COMPLETED, ESCALATED} → `COUNTER_APPROVED_READY_TO_RESUME`(13) whose next action is PERSIST_SAFETY_REVIEW until the SYN-CNT-010 review exists in PENDING_CHECK, then ADVANCE_AGENT; else `COUNTER_APPROVAL_REQUIRED`(12, WAITING_HUMAN, APPROVE_COUNTER, requires_human_authority=True).
10. CREATED/RUNNING/WAITING(other), ordered: unhandled assessment → `READY_TO_RECONSIDER`(6); open tradeoff review → `TRADEOFF_DECISION_REQUIRED`; `step_count == 0` → `READY_TO_ADVANCE_TO_EVIDENCE_WAIT`(4); no JV2 case yet → `READY_TO_PREPARE_RTA`(7); JV2 terminal + no SYN-CNT-010 review → `READY_FOR_SAFETY_EVIDENCE`(14, PERSIST_SAFETY_REVIEW); SYN-CNT-010 review PENDING_CHECK → `SAFETY_REVIEW_PENDING`(15, ADVANCE_AGENT); else → `OFF_CANONICAL_PATH(UNEXPECTED_PERSISTED_STATE, 16)` quoting actual durable state in the explanation.

Flags: guided/auto may execute every next action except `SELECT_TRADEOFF_OPTION` (auto=False) and `NONE` (both False).

- [ ] 2.1 RED: seed each permutation through production workflows (scarcity run, yard initialize/ingest, real carrier workflows, real safety workflow with FakeSemanticSafetyChecker) and assert exact stage/ordinal/status/explanation-substance/next-action/flags for: empty incident; bootstrapped; run started; paused; evidence published; reconsidered; prepared; request approval pending/approved/rejected; sent/waiting; counter received; counter approval pending/approved/rejected; evidence persisted; safety pending; blocked-terminal; completed; failed; tradeoff; escalation deviations; unexpected state.
- [ ] 2.2 RED: purity/determinism tests — project twice plus after fresh Session reopen; identical views; row counts of every persisted table unchanged by projection.
- [ ] 2.3 GREEN: implement `project_canonical_replay_stage` exactly as specified above.
- [ ] 2.4 Focused suite green; commit `feat: add read-only canonical replay projector`.

---

## Task 3: Deterministic demo model + semantic checker + additive context (TDD)

**Files:**
* create `backend/tests/test_canonical_replay_agent_model.py`
* create `backend/tests/test_canonical_replay_semantic_checker.py`
* modify `backend/tests/test_agent_context.py` (additive assertions)
* create `backend/app/services/canonical_replay.py`
* modify `backend/app/orchestration/agent_context.py`

### 3a. `CanonicalReplayAgentModel` (in `backend/app/services/canonical_replay.py`)

```python
class CanonicalReplayAgentModel:
    model_name = "canonical-replay-agent-v1"
    def decide(self, context: AgentTurnContext, available_tools: Sequence[AgentToolDefinition]) -> AgentModelTurn | InvalidAgentModelTurn
```

Decision gates, evaluated in this exact order (see harmonization note):

1. `request_expedite_feasibility` exposed → zero-argument call.
2. `context.step_count == 0`: if `summary["dynamic_yard"]["forecast_stages"] == ["PRE_DISCHARGE"]` and `pause_agent_run` exposed → zero-argument pause; otherwise → `InvalidAgentModelTurn(error_kind="CANONICAL_SEQUENCE_VIOLATION", ...)` (covers both pre-bootstrap starts and the legacy pre-5B prepare path).
3. `prepare_rta_request` exposed → require non-empty bootstrap evidence; `connection_id` = the single value of its `parameters["properties"]["connection_id"]["enum"]`; missing or ≠1 entry → `InvalidAgentModelTurn("CANONICAL_AMBIGUOUS_CONNECTION")`.
4. `send_authorised_rta_request` exposed → `case_id` = the unique `summary["carrier_cases"]` entry with `state == "AWAITING_REQUEST_APPROVAL"`; zero or multiple → invalid turn `"CANONICAL_AMBIGUOUS_CASE"`.
5. `request_cargo_safety_review` exposed → `container_id` = the unique entry of `summary["cargo_safety_pending_reviews"]`; must be exactly one and equal `SYN-CNT-010`, else invalid turn `"CANONICAL_AMBIGUOUS_CONTAINER"`.
6. else → `escalate_agent_run` (fail-safe; unreachable on the hero).

Returns `AgentModelTurn(tool_call=AgentToolCall(...), action_summary=...)`. Never raises provider failures; never invents IDs; picks only from `available_tools`.

### 3b. `CanonicalReplaySemanticChecker`

```python
class CanonicalReplaySemanticChecker:
    checker_kind = "canonical-replay-deterministic"
    model_name = None
    def check(self, evidence: SemanticSafetyCheckInput) -> SemanticSafetyCheckOutput
```

Fixed token list (`UN \d{4}`, `dangerous goods`, `DG`, `hazardous`, `corrosive`, `flammable`, `explosive`, `radioactive`, `toxic`, `lithium-ion batteries`) matched case-insensitively with word boundaries against `note_text`. Contradiction iff `structured_dangerous_goods` is False AND any token matches → `CONTRADICTION_FOUND`, explanation cites the structured commodity, `evidence_excerpt` is a verbatim substring of the original note text (the CargoSafetyWorkflow invariant must hold). Otherwise `NO_CONTRADICTION_FOUND`. Never classifies cargo, infers/corrects UN numbers, assigns DG class, or chooses actions.

### 3c. Additive agent context (modify `build_agent_turn_context` summary only)

```python
"dynamic_yard": {"snapshot_count": ..., "compatible_connection_ids": [...], "forecast_stages": [...]},   # additive key: distinct persisted snapshot stage values in order
"cargo_safety_pending_reviews": [{"review_id": str(r.id), "container_id": r.container_id} for r in reviews if r.state is PENDING_CHECK],  # new key
```

No other context changes; trust labeling preserved.

- [ ] 3.1 RED model unit tests: priority selection over synthetic registries/contexts (feasibility first; step-0 pause post-bootstrap; step-0 violation pre-bootstrap incl. legacy-prepare-exposed case; single-enum connection selection; ambiguous enum/case/container invalid turns; escalate fallback); asserts it never emits a tool absent from `available_tools`.
- [ ] 3.2 RED checker tests: canonical contradiction (exact excerpt verbatim substring); benign note; DG-declaring profile; token edge cases ("dg" word boundary, "UN 3480"); no classification fields touched.
- [ ] 3.3 RED context tests: `forecast_stages` reflects persisted snapshots; `cargo_safety_pending_reviews` lists only PENDING_CHECK reviews with id+container.
- [ ] 3.4 GREEN: implement module + additive context keys.
- [ ] 3.5 Focused suites green (existing `test_agent_context.py` stays green); commit `feat: add deterministic canonical replay demo model and semantic checker`.

---

## Task 4: Endpoints — demo-run creation, per-run model resolution, stage projection (TDD)

**Files:**
* create `backend/tests/test_canonical_replay_api.py`
* modify `backend/app/main.py`

Changes:

1. New endpoint:

```python
@application.post("/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs",
                  response_model=AgentRun, status_code=status.HTTP_201_CREATED)
async def create_canonical_demo_agent_run(incident_id: UUID, session: SessionDependency, request: Request) -> AgentRun:
    # body present -> 422 "Canonical demo agent run creation accepts no request body"
    # builds AgentRuntimeCoordinator(model=CanonicalReplayAgentModel(),
    #      clock=CanonicalAgentRuntimeConfiguration.load().clock("before_deadline"),
    #      configuration=..., cargo_safety_checker=CanonicalReplaySemanticChecker())
    # RecordNotFound -> 404; AgentRuntimeConflict -> 409
```

Persisted `model_name == "canonical-replay-agent-v1"`.

2. Per-run resolution on advance: split the existing `agent_runtime()` helper into `default_agent_runtime(session)` (unchanged construction: `agent_model or OpenAIAgentModel()`, checker `None`) and:

```python
def agent_runtime_for_run(session: Session, run: AgentRun) -> AgentRuntimeCoordinator:
    configuration = CanonicalAgentRuntimeConfiguration.load()
    if run.model_name == CANONICAL_REPLAY_MODEL_NAME:
        return AgentRuntimeCoordinator(..., model=CanonicalReplayAgentModel(), cargo_safety_checker=CanonicalReplaySemanticChecker())
    return default_agent_runtime(session)
```

`advance_agent_run` fetches the run via `AgentRuntimeRepository.get_run(run_id)` (LookupError → existing 404), resolves with `agent_runtime_for_run`, advances. Coordinator internals untouched; non-demo runs resolve exactly as today.

3. Read-only stage endpoint:

```python
@application.get("/synthetic/scenarios/{incident_id}/canonical-replay/stage",
                 response_model=CanonicalReplayStageView)
def get_canonical_replay_stage(incident_id: UUID, session: SessionDependency) -> CanonicalReplayStageView:
    # RecordNotFound -> 404 "Incident not found"
```

4. Normal `POST /incidents/{incident_id}/agent-runs` unchanged (still refuses bodies, still OpenAI-bound).

- [ ] 4.1 RED API tests: demo-run 201 with persisted canonical `model_name`; 404 unknown incident; 409 second active run; 422 body supplied; stage endpoint 200 shape + 404 unknown; advance of demo run uses canonical model (observable: credential-free advance succeeds end-to-end later in Task 6); normal run creation still persists default model name and refuses bodies.
- [ ] 4.2 GREEN: implement endpoints + resolution helper.
- [ ] 4.3 Full backend suite green (regression: production behavior unchanged); commit `feat: expose canonical replay demo-run, advance resolution, and stage endpoints`.

---

## Task 5: Frontend typed API + hook integration (TDD)

**Files:**
* modify `web/src/api/types.ts`
* create `web/src/api/canonicalReplay.ts` and `web/src/api/canonicalReplay.test.ts`
* modify `web/src/hooks/useRecoveryConsole.ts` and `web/src/hooks/useRecoveryConsole.test.ts`
* modify `web/src/lib/recoverySelectors.ts` and `web/src/lib/recoverySelectors.test.ts` (stage helpers only)

API module (mirrors backend JSON exactly; no business logic):

```ts
export const fetchCanonicalReplayStage = (incidentId: string) => request<CanonicalReplayStageView>(`/synthetic/scenarios/${incidentId}/canonical-replay/stage`);
export const createCanonicalDemoAgentRun = (incidentId: string) => request<AgentRun>(`/synthetic/scenarios/${incidentId}/canonical-replay/agent-runs`, { method: "POST" });
export const AUTO_REPLAY_DISCLOSURE = "Demo harness automatically performs operator actions using a synthetic operator identity (synthetic-demo-operator). Production authority boundaries remain unchanged.";
export const initialCanonicalStageView = () => CanonicalReplayStageView;  // frontend-local READY_TO_CREATE(1)
```

Types in `types.ts`: const objects `CanonicalReplayStage`, `CanonicalReplayStatus`, `CanonicalReplayActionType` + `CanonicalReplayStageView` interface (fields exactly as backend).

Hook additions (extend, do not replace):

* bundle loads `canonicalStage` via `fetchCanonicalReplayStage` inside `loadIncidentBundle`; when `incident === null` the hook exposes `initialCanonicalStageView()`;
* `startDemoAgentRun` → `createCanonicalDemoAgentRun(incident.id)` through `runMutation`;
* `runMutation` now returns `{ ok: boolean; conflict: boolean; error: ApiError | null }` (callers that ignore it are unaffected; 409 refresh semantics preserved);
* approval callbacks accept optional operator identity defaulting to `"operator-console"`: `approveRequest(operatorId?)`, `approveCounter(operatorId?)`, `rejectRequest()`, `rejectCounter()` unchanged;
* `simulateCarrierResponse(effectiveAt = CARRIER_DEMO_TIMESTAMPS.simulateAt)` — canonical callers pass `CANONICAL_COUNTER_EFFECTIVE_AT`; legacy demos unchanged;
* selector `stageActionBinding(stage, agentWaitHistory)` surfaces the exact persisted binding fingerprint for authority stages (never inferred).

Vite proxy: `/synthetic` already proxied to `127.0.0.1:8000` — no change required.

- [ ] 5.1 RED API tests: stage GET path + demo-run POST path via mocked fetch; disclosure constant exactness; initial view shape.
- [ ] 5.2 RED hook tests: bundle includes projected stage; startDemoAgentRun posts once to the synthetic route and refreshes; parameterized operator ids reach approval bodies; simulate override sends canonical effective_at; legacy defaults preserved; 409 refresh behavior intact.
- [ ] 5.3 GREEN: implement.
- [ ] 5.4 Focused frontend suites green; commit `feat: add canonical replay typed api and console hook integration`.

---

## Task 6: Synthetic Auto Replay controller (TDD)

**Files:**
* create `web/src/lib/autoReplayController.ts` and `web/src/lib/autoReplayController.test.ts`
* create `web/src/hooks/useAutoReplay.ts` and `web/src/hooks/useAutoReplay.test.ts`

Pure bounded async loop (no timers/intervals/workers; abort flag checked between steps):

```ts
export const MAX_AUTO_ACTIONS = 40;
export type AutoReplayHaltReason = "terminal-success" | "off-canonical-path" | "tradeoff" | "budget-exhausted" | "conflict" | "error" | "stopped";
export interface AutoReplayLogEntry { ordinal: number; stage: string; action: string; outcome: "ok" | "conflict-upgraded" | "halted"; }
export interface AutoReplayCallbacks {
  fetchStage(): Promise<CanonicalReplayStageView>;
  execute(action: CanonicalReplayActionType): Promise<{ ok: boolean; conflict: boolean }>;
}
export interface AutoReplayProgress { running: boolean; actionsUsed: number; currentAction: string | null; log: AutoReplayLogEntry[]; halt: AutoReplayHaltReason | null; }
export async function runAutoReplay(callbacks, opts: { maxActions?: number }, signal: { aborted: boolean }, onProgress: (p: AutoReplayProgress) => void): Promise<AutoReplayProgress>
```

Per iteration: check abort → fetch stage (fresh projection each time) → halt when `status` is TERMINAL_* (success on SAFETY_BLOCKED/COMPLETE), stage is OFF_CANONICAL_PATH, or next is SELECT_TRADEOFF_OPTION/NONE-nonterminal (tradeoff/unexpected halts) → budget check (attempts counted; exceeding MAX_AUTO_ACTIONS halts `budget-exhausted`) → set currentAction → `execute(next_allowed_action)` → on failure: conflict → refresh+re-project happens via the caller's next iteration ONLY IF the re-fetched stage's next action differs from the attempted one (the documented 409 wait-upgrade continues; a same-action re-projection halts `conflict`); non-conflict error → halt `error` → append log entry → continue. `useAutoReplay(console)` wires callbacks to hook actions (approvals as `SYNTHETIC_DEMO_OPERATOR_ID`; simulate with `CANONICAL_COUNTER_EFFECTIVE_AT`; safety persist for SYN-CNT-010) and React state with Start/Stop; effect cleanup flips the abort flag. Reload mid-run resets to idle; restart resumes from the projected stage.

- [ ] 6.1 RED controller tests (mocked callbacks): full canonical hero sequence ending at SAFETY_BLOCKED; budget exhaustion at 40 attempts; 409-upgrade continuation then completion; repeated-conflict halt (same action re-projected); 404 halt; 422 halt; tradeoff halt; stop between steps; log append-only; disclosure constant exported unchanged.
- [ ] 6.2 RED useAutoReplay tests: idle-until-started; running/current/log surfaced; Stop halts between actions; reload resets to idle.
- [ ] 6.3 GREEN: implement.
- [ ] 6.4 Focused suites green; commit `feat: add bounded synthetic auto replay controller`.

---

## Task 7: Guided Demo UI evolution + OperationsConsole wiring (TDD)

**Files:**
* modify `web/src/components/demo/SyntheticDemoControl.tsx` and test
* modify `web/src/components/OperationsConsole.tsx` and test

SyntheticDemoControl becomes mode-switched with **GUIDED DEMO as the default tab** and AUTO REPLAY secondary (never auto-started):

Shared stage header: stage name, `progress_label`, status chip, explanation, actor attribution for the next action (`AGENT ACTION` for ADVANCE_AGENT, `OPERATOR ACTION` for operator endpoints, `SYNTHETIC EVIDENCE ACTION` for PUBLISH_DISCHARGE_ACTIVE/PERSIST_SAFETY_REVIEW/SIMULATE_CARRIER_RESPONSE), `HUMAN APPROVAL REQUIRED` badge on authority stages showing subject kind + decision/request/response identifiers + exact persisted binding fingerprint, terminal success rendering (ESCALATED / SAFETY_REVIEW_REQUIRED with contradiction evidence), errors/conflicts in the existing alert region, deviation rendering with "Start new canonical replay".

Guided buttons enabled strictly when `guided_can_execute && next_allowed_action` matches; Approve AND Reject offered on both authority stages; every click = one endpoint call then refresh; no hidden progression. Auto tab: Start/Stop, running indicator, current action, scrollable log, budget display, permanent `AUTO_REPLAY_DISCLOSURE` paragraph. Existing panels untouched as evidence surfaces.

- [ ] 7.1 RED component tests: modes render; stage header content; gating (button disabled when stage disallows); fingerprint shown verbatim on authority stages; reject paths present; terminal copy; deviation copy + new-replay offer; auto disclosure permanently rendered; no polling/timers introduced (grep assertion in test file comments unnecessary — verified by code review instead).
- [ ] 7.2 RED OperationsConsole integration tests: extend the guided journey to use the demo-run start + stage-driven gating through to safe escalation (mocked HTTP); add a mocked Auto Replay journey ending in safe escalation asserting approvals posted with `synthetic-demo-operator` and exact fingerprints.
- [ ] 7.3 GREEN: implement components/wiring.
- [ ] 7.4 Focused suites green; commit `feat: evolve guided demo control and wire canonical replay into the operations console`.

---

## Task 8: Full canonical heroes + rejections + isolation (TDD)

**Files:**
* create `backend/tests/test_canonical_replay_hero_api.py`
* create `backend/tests/test_canonical_replay_rejections.py`
* create `backend/tests/test_canonical_replay_isolation.py`

Guided-shaped TestClient hero (all real endpoints, credentials unset via monkeypatch): create canonical incident → bootstrap PRE_DISCHARGE → demo-run 201 → stage checks at every transition → advance(pause) → publish ACTIVE → metrics `(601, 602)` / `(12.02, 12.04)` asserted on the persisted assessment → advance(reconsider R1 = {001,002,004,010,011,012,014,015}; 005 OUT/CANCELLED; 001 IN/PLANNED; 002/004 COMMITTED) → stage READY_TO_PREPARE_RTA → advance(prepare) → JV2 affected set exactly `("SYN-CNT-017",)` → REQUEST_APPROVAL stage shows human authority → approve with `operator-console` + exact persisted fingerprint from `/carrier-recovery-cases/{id}/history` → wrong-fingerprint negative (409, no state change) → advance(send) → WAITING_FOR_CARRIER → simulate `CANONICAL_COUNTER_EFFECTIVE_AT` → COUNTER response → advance hits expected 409 upgrade → stage COUNTER_APPROVAL_REQUIRED → counter approval `operator-console` + exact fingerprint → stage demands PERSIST_SAFETY_REVIEW before ADVANCE_AGENT (sequencing pin) → create SYN-CNT-010 review (pinned text/source) → advance resolves wait + evaluates together → terminal `ESCALATED / SAFETY_REVIEW_REQUIRED`, semantic `CONTRADICTION_FOUND`, `automation_blocked = True`; invocation inventory equals exactly the five canonical calls; `model_name == "canonical-replay-agent-v1"` on run/steps.

Auto-shaped hero: same journey driven with `synthetic-demo-operator` approvals; recorded Approval.operator_id assertions for both identities across the two heroes; agent never appears as approval actor (audit scan).

Rejections: request-rejected and counter-rejected journeys each end `OFF_CANONICAL_PATH` with typed reason, case ESCALATED, run untouched-on-hero impossible; no hidden recovery.

Isolation: two consecutive full replays in one database; independent histories; cross-assert no shared revision/case/review/run rows. ACCEPT-RUN and SILENT-RUN legacy flows exercised directly alongside an active demo incident (legacy compatibility proof).

Out-of-sequence safety: run advanced before bootstrap escalates INVALID_MODEL_OUTPUT via CANONICAL_SEQUENCE_VIOLATION (acceptance 6b).

- [ ] 8.1 RED hero tests (both shapes) with every §18 assertion. 8.2 RED rejection tests. 8.3 RED isolation + legacy-compatibility tests.
- [ ] 8.4 GREEN: fix whatever the heroes expose (expected: minor projector/model calibration only; no coordinator changes permitted).
- [ ] 8.5 Commit `test: prove guided and auto canonical heroes, rejection paths, and repeat isolation`.

---

## Task 9: Full verification

- [ ] 9.1 `uv run --python 3.12 --extra dev pytest backend/tests -q` — full suite green.
- [ ] 9.2 Hero file separately; repeat-isolation file separately; ACCEPT/SILENT compatibility file separately.
- [ ] 9.3 `uv lock --check`.
- [ ] 9.4 `cd web; npm test -- --run`; `npm run typecheck`; `npm run build`; `npm run lint` (AuditTimeline Fast Refresh warning acceptable iff lint exits 0).
- [ ] 9.5 `git diff --check`; `git status --short` clean.

## Task 10: Local integration smoke

Start `uv run --python 3.12 --extra dev uvicorn backend.app.main:app --port 8000` and `npm run dev`; drive through the dev proxy (HTTP-level; browser automation unavailable in this environment — stated accurately): frontend serves; stage endpoint reachable; demo-run creation works; full GUIDED representative path PRE→ACTIVE→R0→R1→prepare→approve→send→COUNTER→counter approve→evidence→safe escalation; AUTO representative path via repeated stage reads + legal actions; no OpenAI credentials required; audit/history accessible; fresh second replay mints a new incident; no fatal logs. Stop both processes afterward. Record results honestly.

## Task 11: Final code review over `4e2e93c..HEAD`

Classify Critical/Important/Minor. Specifically check: second workflow; authority bypass; agent-side approvals; browser allocations; guessed fingerprints; production model regression; projector mutation; mutable step truth; stale-state races; blind 409 retries; infinite loops; hidden timers; counter sequencing; checker scope creep; DG/UN inference; missing escalation; credential dependency; cross-contamination; ACCEPT/SILENT regression; CoT exposure; removed Phase 6 coverage. Fix ALL Critical/Important; document Minor for Phase 10 polish. Re-run Task 9 verification after fixes.

## Task 12: Coordination log + push

- [ ] 12.1 Append Phase 7 entry to `docs/coordination/logs/win-codex.md` (branch, SHAs, commits, architecture implemented, tests/counts, hero results, negatives, verification, smoke, findings/dispositions, deviations).
- [ ] 12.2 Commit `docs: record phase 7 canonical demo harness completion`; push `feat/phase7-canonical-demo-harness`; confirm origin equals local HEAD. DO NOT MERGE. DO NOT START PHASE 8.

## Verification commands

```
uv run --python 3.12 --extra dev pytest backend/tests -q
uv lock --check
cd web; npm test -- --run; npm run typecheck; npm run build; npm run lint
git diff --check; git status --short
```
