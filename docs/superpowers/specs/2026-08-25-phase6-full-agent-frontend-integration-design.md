# Phase 6: Full Agent + Frontend Integration

## Goal

Extend the existing operations-console architecture so persisted Phase 2–5B recovery state is visible and driven through explicit, authority-safe operator actions. The console must show the progression from scarcity through dynamic-yard reconsideration, durable agent waits, carrier approvals, safety review, escalation, and audit provenance. It remains a dense operations console, not a chat product.

## Approved approach

`OperationsConsole` will continue to compose `useRecoveryConsole`, typed API clients, and focused presentation components. The hook remains the single state owner: it loads an incident bundle, performs explicit mutations, refreshes persisted data after mutations, and retains the existing 409 refresh behavior. No browser logic computes feasibility, revises allocations, resolves waits, or constructs tradeoff candidates.

Three focused clients will mirror the existing backend routes without backend behavior changes:

* `agentRuntime.ts` for create, advance, list, get, and history of AgentRuns.
* `dynamicYard.ts` for bootstrap, discharge-active publication, read histories, and exact tradeoff selection.
* `cargoSafety.ts` for create, evaluate, list, and history of reviews.

The API contract uses backend JSON field names exactly. Existing backend endpoints provide every required read and approved command, so no backend route or workflow change is required.

## Data flow and authority

The hook reads incident, fixture, scarcity evaluation, decisions, audit events, carrier cases, dynamic-yard histories, safety reviews, agent runs, and selected AgentRun history. It selects the latest AgentRun and latest allocation revision deterministically for presentation. Mutations call exactly one backend endpoint, then refresh. Advancing an agent invokes `POST /agent-runs/{id}/advance` exactly once; publishing dynamic evidence does not advance the agent.

The browser renders solver/policy evidence and authority state. The agent chooses only exposed backend tools; solver/policy retains feasibility and safety authority; the operator submits existing fingerprint-bound approvals or persisted tradeoff-option IDs; carrier responses remain external/simulated carrier state; backend state and audit records remain authoritative.

## UI components

`AgentRunPanel` renders durable AgentRun state, abbreviated identifier, step budget, wait subject, safe action summary, latest invocation and status, escalation reason, and compact history. WAITING has prominent copy for each exact backend wait kind. It exposes Start, one-shot Advance, and Refresh only when the persisted state permits them. It never shows model reasoning.

`DynamicYardPanel` renders PRE_DISCHARGE and DISCHARGE_ACTIVE snapshots with p10/p50/p90 bands, clearly labels forecasts as uncertain, identifies the active revision as R0/R1 by history sequence, and derives allocation/commitment states from responses. Revision delta shows totals as synthetic scenario-world counts, not physical containers. It shows allocation provenance, locked members, and state-driven bootstrap/publication controls.

`TradeoffReviewPanel` appears for reviews and renders only persisted options. Selection posts `selected_option_id`, `expected_options_fingerprint`, and `operator_id`; it contains no allocation editor.

`CargoSafetyPanel` renders trusted structured fields, untrusted note, review/semantic/policy results, automation-blocked status, and the explicit boundary: semantic AI detects inconsistency while deterministic policy decides whether automation may proceed. It never claims to classify DG, infer UN numbers, or correct declarations.

The recovery table gains concise derived operational columns for forecast band, active allocation membership, expedite commitment, carrier state, safety warning, and outcome. Existing CarrierRecoveryPanel keeps its approved controls; console context makes AgentRun waits visible so carrier approval and counter approval remain external before the next explicit advance.

The page order is banner, incident and summary, orchestration panels, operational table/carrier panel, conditional tradeoff and safety panels, audit/history, then guided synthetic controls. The synthetic banner stays visible and the controls expose only eligible actions; they do not add Phase 7 reset/replay or a run-all shortcut.

## Errors and tests

Errors continue through `ApiError`, with user copy distinguishing unavailable/network failure, 404, 409 conflict (followed by refresh), 422 malformed request, terminal agent state, and safety escalation. Controls are conservatively disabled but backend remains final authority.

TDD coverage will add client tests, selector tests for revision/forecast/commitment/wait/safety derivations, panel tests across required states, and a mocked OperationsConsole guided-flow test. Existing component and hook patterns will be reused. Verification includes backend pytest/lock check and the repository's frontend test, typecheck, build, lint, diff-check, status, plus a rendered smoke check if the environment supports it.

## Scope boundaries

This work does not add autoplay/reset/replay, evaluation infrastructure, production deployment hardening, deep visual polish, a chat UI, state-management framework, polling loop, backend decision logic, or any new authority bypass.
