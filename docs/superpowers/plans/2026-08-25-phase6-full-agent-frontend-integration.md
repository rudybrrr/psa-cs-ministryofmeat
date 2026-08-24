# Phase 6 Implementation Plan

**Goal:** integrate persisted Phase 2–5B state into the existing React operations console without changing backend authority or adding an automatic agent loop.

**Architecture:** preserve `OperationsConsole -> useRecoveryConsole -> typed API modules -> focused components`. The hook owns one incident bundle and refreshes it after every explicit mutation. Backend JSON contracts are represented in `web/src/api/types.ts`; selectors transform that persisted data into compact presentation data.

## Task 1: Write typed Phase 5 API clients (TDD)

**Files:**
* Modify `web/src/api/types.ts`
* Create `web/src/api/agentRuntime.ts` and `web/src/api/agentRuntime.test.ts`
* Create `web/src/api/dynamicYard.ts` and `web/src/api/dynamicYard.test.ts`
* Create `web/src/api/cargoSafety.ts` and `web/src/api/cargoSafety.test.ts`

1. Add failing fetch-mock tests for every route and exact tradeoff selection body.
2. Add backend-shaped const/type contracts for AgentRun/history, forecasts/revisions/commitments/reviews, and cargo-safety history/evaluation.
3. Implement focused `request` wrappers using existing API client conventions.
4. Re-run the focused tests and commit the client slice.

## Task 2: Derive dynamic and safety table state (TDD)

**Files:**
* Modify `web/src/lib/recoverySelectors.ts` and `web/src/lib/recoverySelectors.test.ts`
* Modify `web/src/components/recovery/ContainerRecoveryTable.tsx`

1. Add failing selector tests for latest revision, R0/R1 delta, commitment map, forecast lookup, wait presentation, safety state, and enriched recovery rows.
2. Implement pure selectors based only on typed API values.
3. Render the judging-relevant compact table fields, retaining the existing selection behavior.
4. Run selector/component tests and commit the presentation-data slice.

## Task 3: Add orchestration, dynamic-yard, tradeoff, and safety panels (TDD)

**Files:**
* Create `web/src/components/agent/AgentRunPanel.tsx` and test
* Create `web/src/components/dynamic/DynamicYardPanel.tsx` and test
* Create `web/src/components/dynamic/TradeoffReviewPanel.tsx` and test
* Create `web/src/components/safety/CargoSafetyPanel.tsx` and test

1. Write component tests for AgentRun RUNNING, all required wait states, and SAFETY_REVIEW_REQUIRED escalation.
2. Write dynamic tests for PRE/ACTIVE bands, revision delta, and planned/committed/cancelled commitments.
3. Write tradeoff test asserting only persisted options and the exact fingerprint payload; no candidate-allocation input exists.
4. Write safety tests for contradiction/block language and absence of misleading DG claims.
5. Implement focused dense operations panels and run their tests.

## Task 4: Extend the single recovery-console hook (TDD)

**Files:**
* Modify `web/src/hooks/useRecoveryConsole.ts` and `web/src/hooks/useRecoveryConsole.test.ts`
* Modify `web/src/components/demo/SyntheticDemoControl.tsx` and test if needed

1. Add failing hook tests that the incident bundle includes all persisted Phase 5 state and that mutations refresh it.
2. Add state-owned dynamic-yard, agent, tradeoff, and safety values plus explicit mutation callbacks.
3. Preserve 409 refresh behavior and permit agent advance only through the explicit one-call action.
4. Extend guided controls with eligible create/bootstrap/start/advance/publish/safety actions; do not add reset/replay/run-all.
5. Run focused hook tests and commit the integration slice.

## Task 5: Compose and validate the full console (TDD)

**Files:**
* Modify `web/src/components/OperationsConsole.tsx` and `web/src/components/OperationsConsole.test.tsx`
* Modify `docs/coordination/logs/win-codex.md`

1. Add a mocked HTTP representative-flow integration test: incident, PRE, AgentRun, evidence wait, ACTIVE/reconsideration, request approval, counter approval, and safety escalation.
2. Compose panels in approved responsive order and connect only hook callbacks.
3. Run frontend suite, typecheck, build, lint; run backend pytest and lock check; inspect UI if available.
4. Record commits, verification evidence, deviations, and acceptance results in coordination log.
5. Request code review, resolve material findings, then push the feature branch.

## Verification commands

* `uv run --python 3.12 --extra dev pytest backend/tests -q`
* `uv lock --check`
* `cd web; npm test -- --run`
* `cd web; npm run typecheck`
* `cd web; npm run build`
* `cd web; npm run lint`
* `git diff --check`
* `git status --short`
