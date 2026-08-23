# PSA UI Phase 2 + Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for each task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Deliver a live hybrid operations console integrating Phase 2 scarcity evaluation and Phase 3 carrier recovery with canonical ACCEPT/COUNTER/SILENT demo representability.

**Architecture:** Thin `App.tsx`, `OperationsConsole` shell, `useRecoveryConsole` orchestration hook, API modules per domain, `recoverySelectors` for deterministic view models, state-driven carrier panel. All mutations refresh persisted backend state.

**Tech Stack:** React 19, Vite 8, Vitest, Testing Library, Tailwind 4, existing FastAPI backend contracts.

## Global Constraints

- No backend source changes
- No Redux/Zustand/XState/router
- No recovery policy in React — selectors join only
- No hard-coded recovery outcome counts (e.g. 5→18)
- Human approval steps never auto-fired
- SILENT never shown as CarrierResponse
- Demo control visually separated from operator controls
- Work on branch `cursor/psa-ui-phase2-phase3`

---

### Task 1: TypeScript contracts + API clients

**Files:**
- Modify: `web/src/api/types.ts`
- Modify: `web/src/api/client.ts`
- Create: `web/src/api/scarcity.ts`
- Create: `web/src/api/carrierRecovery.ts`
- Create: `web/src/api/scarcity.test.ts`
- Create: `web/src/api/carrierRecovery.test.ts`

**Interfaces:**
- Produces: `DecisionAction.PRESERVE_VIA_RTA`, `ScarcityEvaluationReport`, `CanonicalIncidentFixture`, `CarrierRecoveryCase`, `CarrierRecoveryHistory`, all carrier command body types, `triggerCanonicalScarcity()`, `getCanonicalFixture()`, `getScarcityEvaluation()`, carrier recovery wrappers

- [ ] **Step 1: Write failing API tests** (`scarcity.test.ts`, `carrierRecovery.test.ts`) asserting paths, methods, payloads for all Phase 2/3 endpoints and 404/409 error mapping via `ApiError`

- [ ] **Step 2: Run tests** — `cd web && npm test src/api/scarcity.test.ts src/api/carrierRecovery.test.ts` — expect FAIL

- [ ] **Step 3: Implement types + clients** mirroring `backend/app/domain/enums.py`, `scarcity.py`, `carrier_recovery.py`, `models.py`

- [ ] **Step 4: Run tests** — expect PASS

- [ ] **Step 5: Commit** `feat: sync Phase 2/3 API contracts and clients`

---

### Task 2: Recovery selectors + formatters

**Files:**
- Create: `web/src/lib/recoverySelectors.ts`
- Create: `web/src/lib/recoverySelectors.test.ts`
- Create: `web/src/lib/formatters.ts` (re-export `format.ts` + helpers)

**Interfaces:**
- Consumes: types from Task 1
- Produces: `buildRecoverySummary()`, `buildContainerRows()`, `selectLatestDecisionByContainer()`, `buildDecisionLineage()`, `connectionLabel()`, `carrierCaseForConnection()`, `hasCarrierResponse()`

- [ ] **Step 1: Write failing selector tests** — allocation map from `selected_allocation`, no hard-coded counts, supersession chain, SILENT history has no carrier response display

- [ ] **Step 2: Run** `npm test src/lib/recoverySelectors.test.ts` — FAIL

- [ ] **Step 3: Implement selectors** (join only, no policy)

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** `feat: add recovery view-model selectors`

---

### Task 3: Canonical adapter API fixture

**Files:**
- Modify: `web/src/canonical/adapter.ts`
- Modify: `web/src/canonical/adapter.test.ts`

- [ ] **Step 1: Test** `mapCanonicalFixture(apiFixture)` produces service/container rows

- [ ] **Step 2-4: Refactor adapter** to accept API fixture shape; keep local JSON fallback for tests

- [ ] **Step 5: Commit** `refactor: canonical adapter for API fixture`

---

### Task 4: useRecoveryConsole hook

**Files:**
- Create: `web/src/hooks/useRecoveryConsole.ts`
- Create: `web/src/hooks/useRecoveryConsole.test.ts`

**Interfaces:**
- Produces: state fields + commands: `createCanonicalIncident`, `selectContainer`, `prepareCarrierRecovery`, `approveRequest`, `rejectRequest`, `sendRequest`, `simulateCarrierResponse`, `approveCounter`, `rejectCounter`, `evaluateTimeout`, `refresh`, `loadDemoRun`

- [ ] **Step 1: Test** mutation calls correct API, refresh after success, 409 triggers refresh

- [ ] **Step 2-4: Implement hook**

- [ ] **Step 5: Commit** `feat: add recovery console orchestration hook`

---

### Task 5: UI components

**Files:**
- Create: `web/src/components/incident/RecoverySummary.tsx`
- Create: `web/src/components/recovery/ContainerRecoveryTable.tsx`
- Create: `web/src/components/recovery/RecoveryStatusBadge.tsx`
- Create: `web/src/components/carrier/*.tsx` (focused set)
- Create: `web/src/components/demo/SyntheticDemoControl.tsx`
- Modify: `web/src/components/OperationsConsole.tsx`
- Modify: `web/src/components/IncidentHeader.tsx` (move to incident/ if needed)
- Tests for each component module

- [ ] **Step 1: Component tests** — buttons only in valid states, panel shows connection scope

- [ ] **Step 2-4: Implement components + rewire OperationsConsole**

- [ ] **Step 5: Commit** `feat: build Phase 2/3 operations console UI`

---

### Task 6: Integration test — ACCEPT / COUNTER / SILENT

**Files:**
- Create: `web/src/components/RecoveryConsole.integration.test.tsx`

- [ ] **Step 1: One integration test** mocking full API sequence for three demo flows

- [ ] **Step 2-4: Wire demo control + verify representability**

- [ ] **Step 5: Commit** `test: cover canonical carrier demo suite flows`

---

### Task 7: Final verification

- [ ] Run `cd web && npm test && npm run typecheck && npm run lint && npm run build`
- [ ] Run `git diff --check` and `git status --short`
- [ ] Confirm `git diff origin/main -- backend/` empty
- [ ] Code review per `requesting-code-review` checklist

**Verification commands:**

```bash
cd web
npm test
npm run typecheck
npm run lint
npm run build
cd ..
git diff --check
git status --short
git diff origin/main -- backend/
```
