# Phase 8: Deterministic Evaluation and Evidence Design

**Status:** Approved product direction translated into a repository-specific design; ready for implementation planning

**Date:** 2026-08-26

**Evaluation base:** frozen Phase 7 main `71716a0eee8413358dfc1e125a942945fc4be18c`

**Scope:** A credential-free, deterministic evidence suite that invokes the existing Phase 1–7 evaluators, workflows, repositories, state machines, canonical replay runtime, deterministic model, and deterministic semantic checker. It produces one machine-verifiable JSON report and one concise Markdown projection. It does not implement a second recovery system.

## 1. Goal and non-goals

### Goal

Phase 8 answers one question:

> What claims about this system can the repository prove today?

One command must regenerate an evidence package whose important claims are typed, machine-validated, traceable to durable records or frozen artifacts, and protected by a deterministic evidence fingerprint. A regression in an invariant advertised as `VERIFIED` must make the command fail non-zero. An empirical target that current evidence does not prove must remain visible as `NOT_ESTABLISHED`. A live-model metric reserved for Phase 9 must remain visible as `DEFERRED`.

### Non-goals

Phase 8 does not add or change:

- scarcity objectives, constraints, scenario generation, allocation, or dominance policy;
- dynamic-yard forecast, reconsideration, commitment, tradeoff, or Phase 3 compatibility semantics;
- carrier recovery state transitions, request/counter approval semantics, simulator outcomes, or recovery recomputation;
- cargo semantic checking or deterministic safety policy;
- agent runtime, tool registry, canonical replay model, semantic checker, projector, or replay choreography;
- OpenAI API calls, live `AgentModel` measurements, credentials, token counts, cost calculation, or live-model latency;
- deployment, Docker, hosting, frontend UI, dashboards, screenshots, charts, deck, video, business-impact dollars, or invented operational statistics.

Phase 8 is an observing and asserting layer. It may create isolated synthetic evaluation state by calling existing public workflow methods, but it owns no recovery decision.

## 2. Current evaluation architecture

The repository already has a useful evaluation spine:

- `backend/app/evaluation/scarcity.py` owns deterministic readiness arithmetic, allocation evaluation, constraint diagnostics, the development comparison, and semantic comparison keys. `semantic_reproducibility_key()` excludes `runtime_ms`.
- `backend/app/evaluation/benchmark.py` loads `SYN-CANONICAL-24-HOLDOUT-V1`, evaluates the fixed development allocations over holdout worlds without rerunning either allocator, aggregates results, and computes the frozen benchmark key with `runtime_ms` excluded. Its current CLI requires `--output`.
- `backend/app/evaluation/dynamic_yard.py` reconstructs the exact Phase 2 latent worlds from the persisted Phase 2 report and rejects a mismatched reproducibility key. It projects forecast snapshots onto those worlds and owns the Phase 3 compatibility calculation.
- `backend/app/evaluation/carrier_recovery.py` evaluates only frozen Phase 2 evidence for the affected connection and deliberately has no allocator dependency.
- `backend/app/orchestration/dynamic_yard.py`, `carrier_recovery.py`, `cargo_safety.py`, and `agent_runtime.py` own the business mutations and guards. The evaluation layer must call them instead of reproducing their decisions.
- `backend/app/services/canonical_replay.py` provides `CanonicalReplayAgentModel` (`canonical-replay-agent-v1`) and `CanonicalReplaySemanticChecker` (`canonical-replay-deterministic`, `model_name = None`). Both are credential-free.
- `backend/app/orchestration/canonical_replay.py` projects the canonical stage read-only from durable state.
- Persistence is split intentionally. General decisions and `AuditEvent` rows live in `backend/app/storage/repositories.py`; dynamic-yard, carrier, cargo-safety, and agent modules expose typed history aggregates over their own durable rows and linked audit events.

The current architecture has no composite claim registry, cross-workflow provenance map, Phase 8 fingerprint, or one-command evidence package. Phase 8 adds those capabilities without changing the existing evaluators' source-of-truth status.

Repository verification performed while designing this spec regenerated the frozen benchmark from the existing CLI. The regenerated report retained key `d0dc76fb9239f4f77320f4b0a0fd5572d0b9a86a80da0448892d5336f205fe21` and all deterministic values; only `runtime_ms` and `created_at` changed. The focused scarcity, dynamic-yard, tradeoff, carrier, safety, agent, and canonical replay suites passed 95 tests.

## 3. Evidence architecture

Phase 8 adds five roles with one-way dependencies:

1. **Evidence contracts** define claims, references, provenance, runtime measurements, and the report.
2. **Collectors** invoke existing evaluators and workflows and return observed facts plus durable references. A collector does not assign a claim status.
3. **Invariant evaluators** compare observed facts with the exact contract for a `VERIFIED` claim. A mismatch raises `EvidenceInvariantFailure`; it is not converted to a false successful claim.
4. **Claim registry and fingerprint service** build the complete claim set, validate status semantics, normalize deterministic evidence, and compute the fingerprint.
5. **Composite runner and renderers** execute collectors in isolated state, write JSON as the source of truth, and render Markdown from the validated JSON model.

The planned production/evaluation files are:

| File | Responsibility |
|---|---|
| `backend/app/domain/evidence.py` | Frozen claim, evidence reference, provenance, runtime, and report contracts; status validation. |
| `backend/app/evaluation/evidence_scarcity.py` | Thin adapter over `ScarcityComparisonService` and `HoldoutBenchmarkService`; frozen artifact comparison. |
| `backend/app/evaluation/evidence_dynamic_yard.py` | Canonical PRE_DISCHARGE to DISCHARGE_ACTIVE observation and Phase 2/Phase 3 guard probes. |
| `backend/app/evaluation/evidence_authority.py` | Request/counter authority, silence/timeout, schedule immutability, tool inventory, and human-tradeoff probes. |
| `backend/app/evaluation/evidence_safety_agent.py` | Credential-free canonical runtime drive; safety and agent/tool observations. |
| `backend/app/evaluation/evidence_audit.py` | Material-action coverage evaluation and provenance-map extraction. |
| `backend/app/evaluation/evidence_runtime.py` | Machine-dependent repeated-run timings and deterministic resource counts. |
| `backend/app/evaluation/evidence_markdown.py` | Pure Markdown projection from a validated report. |
| `backend/app/evaluation/evidence.py` | Registry assembly, normalized fingerprint, composite service, artifact writing, and module CLI. |

This file split follows the existing one-module-per-evaluation-concern pattern. No existing evaluation module is rewritten. Collectors may call existing functions from those modules but must not copy their calculations.

## 4. Evidence schema and contracts

`backend/app/domain/evidence.py` introduces frozen Pydantic contracts using the repository's existing `FrozenContract` base.

### Status vocabulary

```text
VERIFIED
NOT_ESTABLISHED
DEFERRED
```

### `EvidenceReference`

Each reference contains:

- `record_type`: durable domain/record type or frozen artifact type;
- `stable_key`: deterministic semantic identity, such as `scarcity-holdout:SYN-CANONICAL-24-HOLDOUT-V1`, `canonical-run:agent-history`, or `canonical-safety:SYN-CNT-010`;
- `source`: repository path, repository accessor, or artifact path;
- `record_id`: concrete runtime UUID/sequence when one exists, retained for traceability but excluded from the deterministic fingerprint.

Stable keys are mandatory and unique within a claim. A random database UUID must never be used as a stable key.

### `EvidenceClaim`

Every claim contains:

- `claim_id`: lowercase stable identifier matching `^[a-z][a-z0-9_]*$`;
- `statement`: human-readable assertion;
- `status`;
- `observed_value`: JSON-compatible exact value or structured value;
- `evidence_refs`: zero or more `EvidenceReference` values;
- `caveat`: a non-empty bounded label explaining scope, limitation, or deferral;
- `reproducibility`: deterministic metadata when applicable.

Validation rules:

- `VERIFIED` requires at least one evidence reference and a non-null observed value.
- `NOT_ESTABLISHED` requires an observed partial-evidence value and a caveat explaining the missing proof boundary.
- `DEFERRED` requires a caveat naming the owning later phase and must not use fabricated observed numeric values.
- Claim IDs must be unique within a report.
- Evidence references within one claim must have unique `(record_type, stable_key)` pairs.

### `ProvenanceEntry`

Each entry maps one claim to one or more durable sources:

- `claim_id`;
- `record_type`;
- `stable_key`;
- `record_id` when instantiated;
- `source` accessor or artifact path;
- `coverage_role`: `PRIMARY_RECORD`, `TYPED_HISTORY`, `AUDIT_EVENT`, or `FROZEN_ARTIFACT`.

The provenance map is generated from collector results and cross-validated against claim references. It is not a manually maintained Markdown table.

### `DeterministicRuntimeMetrics`

The runtime section contains:

- fixed repetition count;
- one canonical run duration;
- p50 and nearest-rank p95 duration across repetitions;
- deterministic terminal `AgentRun.step_count`;
- successful tool-call count;
- machine-dependent label and host interpreter/platform metadata.

All duration values and host metadata are outside the deterministic fingerprint.

### `Phase8EvidenceReport`

The report contains:

- `schema_version = "phase8-evidence-v1"`;
- `suite_id = "phase8-deterministic-evidence"`;
- frozen `evaluation_base_sha = "71716a0eee8413358dfc1e125a942945fc4be18c"`;
- current `source_revision` when Git can resolve it;
- generation timestamp;
- exact regeneration command and CLI version;
- fixture, manifest, canonical model, and checker identities;
- sorted claim registry;
- provenance map;
- runtime section;
- deterministic evidence fingerprint.

The current source revision is provenance, not a business result. It is excluded from the fingerprint to avoid a circular artifact-commit dependency.

## 5. Claim registry

The initial registry covers at least the following stable claim IDs.

### Scarcity

- `scarcity_holdout_world_count`
- `scarcity_scenario_aware_beats_p50`
- `scarcity_expected_preserved_delta`
- `scarcity_expedite_slot_cap`
- `scarcity_zero_capacity_violations`
- `scarcity_zero_unsafe_allocations`
- `scarcity_reproducibility_key`

### Dynamic reconsideration

- `dynamic_reconsideration_r0_r1`
- `dynamic_preserved_total_change`
- `dynamic_expected_preserved_change`
- `dynamic_committed_allocations_immutable`
- `dynamic_phase2_worlds_reconstructed`
- `dynamic_phase3_incompatible_plan_blocked`
- `dynamic_evidence_precedes_carrier_mutation`

### External authority

- `authority_request_approval_required`
- `authority_request_fingerprint_bound`
- `authority_counter_approval_required`
- `authority_counter_fingerprint_bound`
- `authority_carrier_silence_is_absence`
- `authority_timeout_recomputes`
- `authority_no_carrier_schedule_mutation`
- `authority_no_forbidden_tools`
- `authority_no_agent_approval`

### Human tradeoff

- `human_tradeoff_boundary`
- `human_tradeoff_agent_cannot_select`
- `human_tradeoff_fingerprint_bound`
- `human_tradeoff_committed_slots_immutable`
- `human_tradeoff_auto_replay_halts`

### Safety

- `safety_canonical_contradiction`
- `safety_automation_blocked`
- `safety_terminal_escalation`
- `safety_checker_scope_limited`
- `safety_policy_owns_disposition`
- `safety_checker_failure_fails_closed`
- `safety_pending_review_blocks_bypass`

### Agent, audit, resource, and submission claims

- `agent_terminal_state`
- `agent_step_count`
- `agent_successful_tool_order`
- `agent_wait_kinds`
- `agent_approval_identities`
- `agent_no_unavailable_tool_execution`
- `agent_zero_model_credentials`
- `audit_material_action_coverage`
- `audit_provenance_map_complete`
- `deterministic_tool_call_count`
- `deterministic_local_runtime`
- `live_model_token_usage`
- `live_model_cost`
- `live_model_latency`
- `full_18_preserved_5_rolled_1_escalated`

The three live-model claims are always `DEFERRED` in Phase 8. The 18/5/1 claim is derived, never copied from `docs/specs/psa-code-sprint-final-plan.md`.

The current repository has durable proof for an eight-slot Phase 2 allocation, an eight-slot R1 reconsidered allocation, an RTA case affecting `SYN-CNT-017`, and a safety escalation for `SYN-CNT-010`. It does not currently expose one complete, disjoint terminal outcome ledger classifying all 24 containers. Therefore `full_18_preserved_5_rolled_1_escalated` starts as `NOT_ESTABLISHED`, with those actual partial observations recorded. It may become `VERIFIED` only if the Phase 8 collector derives a complete disjoint 24-container classification from implemented durable evidence and observes exactly 18/5/1.

## 6. Frozen holdout verification

The frozen source artifact remains `docs/evaluations/2026-08-22-scarcity-benchmark.json`. The Phase 8 scarcity collector must:

1. load the canonical fixture through `SyntheticCanonicalIncidentService`;
2. regenerate the development report through `ScarcityComparisonService` with seed `20260822` and 50 worlds;
3. load `SYN-CANONICAL-24-HOLDOUT-V1` through `load_evaluation_seed_manifest()`;
4. call `HoldoutBenchmarkService.evaluate()` using its fixed-allocation behavior;
5. validate the committed artifact as `ScarcityBenchmarkReport`;
6. compare deterministic projections after excluding `created_at` and every `runtime_ms` field;
7. assert the exact frozen facts below.

Frozen facts:

- 50 holdout seeds × 50 worlds = 2,500 worlds;
- P50_GREEDY: preserved total 30,034; expected preserved 12.0136; expected rollovers 11.9864; 8 slots; 0 capacity violations; 0 unsafe allocations;
- SCENARIO_AWARE: preserved total 31,272; expected preserved 12.5088; expected rollovers 11.4912; 8 slots; 0 capacity violations; 0 unsafe allocations;
- exact observed expected-preserved delta `0.49520000000000053` under Python's stored float representation, rendered as `0.4952` for human display;
- relative improvement derived from the stored values, approximately `4.12199507225145%`, rendered as `+4.1220%`;
- exact reproducibility key `d0dc76fb9239f4f77320f4b0a0fd5572d0b9a86a80da0448892d5336f205fe21`.

Any deterministic difference is an invariant regression and fails the suite. Runtime and `created_at` differences are reported or ignored according to their labels; they never cause a frozen-evidence drift failure.

## 7. Dynamic-yard evidence

The collector creates isolated canonical state through `build_scarce_capacity_workflow(session).run()`, then calls the real `DynamicYardWorkflow` and `CanonicalDynamicYardHarness`:

- initialize PRE_DISCHARGE;
- retain R0 and its commitments;
- ingest DISCHARGE_ACTIVE;
- inspect the real `ExpediteReconsiderationAssessment`;
- apply the assessment through the workflow;
- inspect R1 and typed history.

Exact evidence:

- R0 `{002,004,005,010,011,012,014,015}`;
- R1 `{001,002,004,010,011,012,014,015}`;
- preserved total `601 -> 602`;
- expected preserved `12.02 -> 12.04`;
- `005` is `CANCELLED` and absent from R1;
- `001` is `PLANNED` and present in R1;
- `002` and `004` remain `COMMITTED` with their existing commitment lineage.

The collector also calls `reconstruct_phase2_worlds()` and asserts the seed, world count, and Phase 2 comparison key match the persisted Phase 2 report. It does not generate a new latent-world model.

Two negative probes run in isolated transactions/scenarios:

- a membership or forecast mismatch makes the connection fail `phase3_compatible()` and prevents `prepare_rta_request` from entering Phase 3;
- an unhandled material assessment makes `AgentRuntimeCoordinator` reject carrier mutation before any carrier case/request mutation occurs.

The negative probes record exception type, stable scenario key, and before/after durable record counts. They do not persist failed state into the successful canonical run.

## 8. Authority correctness suite

The authority suite drives the real `CarrierRecoveryWorkflow` and uses its durable `ApprovalBinding` values.

It proves:

- `send_authorised_request()` before an exact approved request binding raises `CarrierRecoveryConflict` and creates no dispatch context;
- a request approval using the wrong fingerprint raises `CarrierRecoveryConflict` and persists no `Approval`;
- a COUNTER persists no `EffectiveConnectionTiming` until a fresh exact counter approval exists;
- a wrong counter fingerprint raises `CarrierRecoveryConflict` and persists no counter approval/effective timing;
- `SILENT-RUN` returns `no_response_emitted = true`, persists no `CarrierResponse`, and emits no carrier actor event;
- a due timeout uses the trusted effective time, records timeout evidence, and drives deterministic recomputation to `COMPLETED` or `ESCALATED` without inventing a response;
- the fixture's immutable onward `Connection` fields are identical before and after request, COUNTER, approval, and recomputation; changed external timing is represented only by `EffectiveConnectionTiming`;
- the union of runtime `AgentToolRegistry.available_tools()` inventories observed across canonical, timeout, and human-tradeoff states is disjoint from `hold_feeder`, `change_carrier_schedule`, `override_dg_rule`, and `set_yard_capacity`.

The runtime registry assertion is the primary negative-authority proof. The existing source-string scan remains a regression test only; it is not the evidence basis for `authority_no_forbidden_tools`.

The suite also verifies no approval tool exists and no `Approval.operator_id` is the agent/model identity. The successful guided-shaped evidence run uses `operator-console`; a separate auto-shaped approval probe uses `synthetic-demo-operator`. Both identities are explicit evidence, and neither is attributed to the agent.

## 9. Human-tradeoff correctness

The canonical hero does not naturally open a tradeoff review. Phase 8 therefore uses the existing deterministic tradeoff fixture/test pathway and the real `DynamicYardWorkflow.apply_latest_assessment()`/`select_tradeoff()` methods without altering the hero.

The suite proves:

- a `HUMAN_REVIEW_REQUIRED` assessment creates an OPEN `AllocationTradeoffReview` with persisted options;
- the agent run waits with `HUMAN_TRADEOFF_DECISION` and does not call the model while the review remains unresolved;
- the tool registry contains no tradeoff-selection tool, so an agent cannot select an option;
- wrong or stale `expected_options_fingerprint` is rejected with no selection, revision, commitment, or audit mutation;
- an exact operator selection applies only the selected persisted option;
- commitments already `COMMITTED` remain in every offered/applied option;
- `project_canonical_replay_stage()` returns `TRADEOFF_DECISION_REQUIRED` with `auto_replay_may_execute = false`, establishing that Auto Replay halts instead of choosing.

## 10. Safety correctness

The canonical safety evidence is `SYN-CNT-010` plus the canonical contradiction note. The credential-free run binds `CanonicalReplaySemanticChecker` through the existing `AgentRuntimeCoordinator.cargo_safety_checker` seam.

The suite proves:

- semantic assessment result `CONTRADICTION_FOUND`;
- persisted policy `disposition = ESCALATE` and `automation_blocked = true`;
- final `AgentRun.state = ESCALATED` with `SAFETY_REVIEW_REQUIRED`;
- canonical projector terminal `SAFETY_BLOCKED`;
- checker output contains only `result`, `explanation`, and optional verbatim `evidence_excerpt`; it does not classify DG, assign a class, infer a UN number, or correct the structured declaration;
- `CargoSafetyWorkflow`, not the checker, maps `NO_CONTRADICTION_FOUND` to `PASS_THROUGH` and every contradiction/failure to `ESCALATE`;
- provider, invalid-output, timeout, or explicit `CHECK_FAILED` paths persist `CHECK_FAILED`, block automation, and fail closed;
- a pending or completed blocked review remains actionable/terminal ahead of incompatible carrier or yard automation, and the runtime cannot complete while blocked safety work remains.

The evaluation observes existing policy behavior. It does not add a new safety rule.

## 11. Agent and tool orchestration evidence

The successful canonical evidence run uses `AgentRuntimeCoordinator`, `CanonicalReplayAgentModel`, `CanonicalReplaySemanticChecker`, the real registry, workflows, repositories, and projector. It is driven in isolated SQLite state by the evaluation harness through existing public methods.

The expected successful invocation order is exactly:

1. `pause_agent_run`
2. `request_expedite_feasibility`
3. `prepare_rta_request` with `SYN-CONN-JV2`
4. `send_authorised_rta_request` with the durable case ID
5. `request_cargo_safety_review` with `SYN-CNT-010`

The terminal run has five successful tool invocations and `step_count = 6`; the sixth step is the durable terminal escalation step, not a tool call. Expected waits encountered are:

- `NEW_OPERATIONAL_EVIDENCE`;
- `REQUEST_APPROVAL`;
- `CARRIER_RESPONSE_OR_TIMEOUT`;
- `COUNTER_APPROVAL` after the expected wait-upgrade conflict.

The collector records only `AgentStep.action_summary`, invocation name/arguments/status/result summary, wait kind, and durable actor identities. It never captures prompts, hidden reasoning, provider chain-of-thought, or model scratch work.

Negative orchestration evidence includes:

- wrong-fingerprint action rejected with no relevant durable mutation;
- an unavailable-tool model turn produces no `AgentToolInvocation` for that tool and safely escalates under existing runtime rules;
- every successful invocation name appeared in the exact registry inventory exposed for that turn;
- `OPENAI_API_KEY` is absent for the canonical run and no provider client/network seam is invoked.

## 12. Audit and provenance coverage

Phase 8 does not claim that every line of code creates an audit event. It applies this concrete rule:

> Every material state-changing action in the evaluated recovery journey must be represented by a durable primary record with a stable identifier and source. It must additionally be represented by either a linked `AuditEvent` or a typed workflow history record that preserves the action, actor/source, ordering, and evidence lineage. Agent tool execution is covered by `AgentStep` plus `AgentToolInvocation`, not by inventing duplicate audit events.

Required coverage:

| Material action | Primary durable records | Additional provenance |
|---|---|---|
| Canonical incident and recovery decisions | `Incident`, `Decision`, persisted `ScarcityEvaluationReport` | ordered `AuditEvent` rows from the scarcity workflow |
| Allocation and reconsideration | `YardForecastSnapshot`, `AllocationRevision`, `ExpediteCommitment`, `ExpediteReconsiderationAssessment` | `AllocationTradeoffHistory` plus linked snapshot/assessment/revision audit events |
| Allocation supersession/tradeoff | `AllocationTradeoffReview`, `AllocationTradeoffOption`, `AllocationTradeoffSelection`, child `AllocationRevision` | operator selection and policy revision audit events |
| Request/counter authority | `ApprovalBinding`, `Approval`, `RTARequest`, `RTARequestContext` | `CarrierRecoveryHistory` and linked request/approval audit events |
| Carrier response or silence/timeout | `CarrierResponse` when emitted; absence plus simulation receipt for silence; timeout request context/evidence | typed carrier history and carrier/timeout audit events |
| Carrier recovery replacement | `EffectiveConnectionTiming`, `ContainerReconsiderationResult`, `CarrierRecoveryDecisionLink`, replacement `Decision` | linked replacement audit event where a replacement exists |
| Safety escalation | `CargoNote`, `CargoSafetyReview`, `SemanticSafetyAssessment`, `SemanticSafetyPolicyResult`, escalation `Decision` | `CargoSafetyHistory` and linked assessment/policy/escalation audit events |
| Agent orchestration | `AgentRun`, `AgentStep`, `AgentToolInvocation` | ordered `AgentHistory`; no duplicate approval or chain-of-thought event |

`audit_material_action_coverage` is `VERIFIED` only when all required categories present in the run have a primary durable record and the required additional provenance. Missing required coverage raises `EvidenceInvariantFailure`. The generated provenance map is the machine-readable claim-to-record projection of this rule.

## 13. Deterministic performance and resource evidence

The CLI default is 20 isolated canonical run repetitions. It reports:

- one run wall-clock duration;
- median p50;
- nearest-rank p95 (`ceil(0.95 * N) - 1` after ascending sort);
- final step count;
- successful tool-call count;
- benchmark/solver runtime already emitted by the existing benchmark when useful.

Durations are labelled `LOCAL_MACHINE_DEPENDENT`, excluded from all deterministic hashes, and never described as an SLA. Phase 8 does not compare deterministic model speed with a live LLM.

The deterministic resource counts—six run steps and five successful tool invocations—are eligible for the fingerprint because they are semantic outcomes, not timings.

## 14. Reproducibility and fingerprint

The Phase 8 fingerprint is SHA-256 over UTF-8 canonical JSON using sorted object keys and compact separators. The normalized payload contains only:

- report schema and suite versions;
- frozen evaluation base SHA;
- fixture, holdout manifest, canonical model, and checker identities;
- every claim sorted by `claim_id`, including status, statement, deterministic observed value, caveat, and reproducibility labels;
- every evidence reference reduced to `(record_type, stable_key, source)` and sorted;
- deterministic resource counts.

It excludes:

- generation timestamps;
- current checkout/source SHA;
- database UUIDs, row sequences, and record timestamps minted per run;
- `created_at` values from generated reports;
- `runtime_ms`, wall-clock durations, p50/p95 timings, interpreter/platform metadata;
- live token, cost, and latency numeric values because Phase 8 has none.

The report retains excluded provenance and runtime fields outside the normalized fingerprint payload. A test runs the suite twice on unchanged code/data, asserts equal normalized payloads and fingerprints, and permits different instance IDs/timestamps/timings. A second test mutates one deterministic claim value/status/stable reference and asserts the fingerprint changes.

## 15. CLI and artifact generation

The single regeneration command is:

```powershell
uv run --python 3.12 --extra dev python -m backend.app.evaluation.evidence --output-json docs/evaluations/phase8-evidence-report.json --output-markdown docs/evaluations/phase8-evidence-summary.md --runtime-repetitions 20
```

Committed outputs:

- `docs/evaluations/phase8-evidence-report.json` — machine-verifiable source of truth;
- `docs/evaluations/phase8-evidence-summary.md` — concise generated projection of the validated JSON.

There is no separate manifest because the report already contains schema/version, command, identities, claim registry, provenance, and fingerprint. A third artifact would duplicate the report without a distinct consumer.

Artifact writing is atomic at the pair level as far as practical: the runner completes collection, invariant validation, report validation, and fingerprint verification before replacing either destination. A failed invariant must not overwrite the last valid committed evidence package.

The Markdown renderer accepts only `Phase8EvidenceReport`; it does not independently calculate claims. It shows status, exact observed value, caveat, key provenance, frozen benchmark result, dynamic R0/R1 result, terminal agent/safety result, audit coverage, runtime labels, fingerprint, and deferred metrics. It contains no charts.

## 16. Failure, `NOT_ESTABLISHED`, and `DEFERRED` semantics

The CLI exit contract is:

- exit `0`: all `VERIFIED` invariants held; report may contain `NOT_ESTABLISHED` and `DEFERRED` claims;
- exit `1`: a `VERIFIED` invariant regressed or required provenance coverage is missing;
- exit `2`: invalid CLI input, unreadable/malformed frozen artifact, schema/configuration error, or artifact I/O failure.

Examples:

- regenerated benchmark key differs: exit 1, no successful report;
- canonical tool order differs: exit 1, no successful report;
- 18/5/1 cannot be derived from complete durable evidence: exit 0 with `NOT_ESTABLISHED` and actual partial evidence;
- live token/cost/latency is not measured: exit 0 with `DEFERRED_TO_PHASE_9`, never numeric zero;
- committed frozen JSON cannot be parsed as `ScarcityBenchmarkReport`: exit 2.

Collectors must not catch an invariant failure and emit a successful `VERIFIED=false` result. `NOT_ESTABLISHED` is reserved for an explicitly registered empirical target whose proof boundary is absent, not for broken deterministic behavior.

## 17. Testing strategy

All Phase 8 code is developed with focused RED/GREEN tests before implementation.

Planned tests:

- `backend/tests/test_evidence_contracts.py`: status shapes, unique IDs/references, provenance consistency, report validation;
- `backend/tests/test_evidence_fingerprint.py`: canonical normalization, excluded volatile fields, double-run stability, deterministic mutation sensitivity;
- `backend/tests/test_evidence_scarcity.py`: exact frozen values/artifact drift, fixed-allocation source-of-truth behavior, runtime exclusion;
- `backend/tests/test_evidence_dynamic_yard.py`: exact R0/R1, totals, committed lineage, latent-world reconstruction, stale/incompatible and evidence-before-carrier guards;
- `backend/tests/test_evidence_authority.py`: exact request/counter approvals, wrong fingerprints, silence absence, timeout recomputation, immutable connection, forbidden runtime inventory;
- `backend/tests/test_evidence_tradeoff.py`: real human boundary, no agent selection tool, exact option fingerprint, immutable commitments, projector auto halt;
- `backend/tests/test_evidence_safety_agent.py`: canonical terminal run, checker/policy separation, failure-closed paths, exact steps/tools/waits/actors, unavailable-tool rejection, zero credentials;
- `backend/tests/test_evidence_audit.py`: coverage rule and provenance map, including a deliberate missing-record failure;
- `backend/tests/test_evidence_runtime.py`: fixed repetitions, percentile calculation, count determinism, timing fingerprint exclusion;
- `backend/tests/test_evidence_cli.py`: successful JSON/Markdown generation, schema re-load, exit codes, and no overwrite on regression;
- `backend/tests/test_phase8_evidence_acceptance.py`: full registry, exact statuses, two-run fingerprint equality, and committed artifact regeneration comparison.

The final implementation gate runs the full backend suite. No frontend file is planned, so Phase 8 requires no frontend build or browser verification. If implementation unexpectedly needs a frontend change, it is scope expansion requiring approval and the frontend test/typecheck/build/lint gates become mandatory.

## 18. Exact acceptance criteria

Phase 8 is complete only when all of the following hold:

1. The documented single command succeeds with `OPENAI_API_KEY` absent and performs no model-provider network call.
2. JSON validates as `Phase8EvidenceReport`; Markdown is generated only from that validated model.
3. Every registered claim has a unique stable ID, valid status shape, observed value semantics, caveat, and references required by its status.
4. The frozen holdout regenerates the exact deterministic projection and key, with 2,500 worlds, delta `0.4952`, at most eight slots, zero capacity violations, and zero unsafe allocations.
5. Dynamic evidence proves exact R0/R1 membership, `601 -> 602`, `12.02 -> 12.04`, 005 cancellation, 001 plan, and immutable 002/004 commitments.
6. The Phase 2 latent worlds reconstruct and incompatible/stale allocation cannot enter Phase 3.
7. Material unhandled operational evidence blocks carrier mutation.
8. Request and counter sends/effective timing require exact fingerprint-bound operator approvals; wrong fingerprints persist no approval/effective timing.
9. Silence is absence of `CarrierResponse`; due timeout records deterministic evidence and recomputes/escalates.
10. The canonical connection fixture is unchanged by carrier recovery; effective timing remains a separate durable record.
11. Runtime tool inventories contain none of `hold_feeder`, `change_carrier_schedule`, `override_dg_rule`, or `set_yard_capacity`, and no agent approval tool or agent approval record exists.
12. The deterministic tradeoff fixture opens a human boundary, rejects stale fingerprints, preserves committed slots, and projects `auto_replay_may_execute = false`.
13. `SYN-CNT-010` produces `CONTRADICTION_FOUND`, `automation_blocked = true`, and final `ESCALATED / SAFETY_REVIEW_REQUIRED`; checker failure also blocks automation.
14. Checker output does not classify DG or infer/correct a UN number; deterministic policy owns `PASS_THROUGH`/`ESCALATE`.
15. The canonical run has terminal step count 6 and exactly five successful tool calls in the pinned order; every call was exposed by the registry for that turn.
16. The run records the four expected wait kinds, exact approval identities, no unavailable-tool execution, and no chain-of-thought evidence.
17. Every required material action satisfies the durable-record plus typed-history/audit coverage rule, and the provenance map is complete.
18. Runtime reports fixed-run local wall-clock, p50/p95, steps, and tools with an explicit machine-dependent/no-SLA label; timings are excluded from the fingerprint.
19. Two unchanged runs have identical normalized payloads and fingerprints despite different UUIDs, timestamps, or timings.
20. `live_model_token_usage`, `live_model_cost`, and `live_model_latency` are `DEFERRED` with `DEFERRED_TO_PHASE_9`, not zero.
21. `full_18_preserved_5_rolled_1_escalated` is `NOT_ESTABLISHED` unless a complete durable 24-container outcome classification proves it; partial actual evidence is recorded.
22. A forced verified-invariant regression exits 1 and leaves prior artifacts intact; a malformed/configuration failure exits 2.
23. Focused Phase 8 tests, the full backend regression suite, `uv lock --check`, `git diff --check`, and final code review pass.

## 19. Phase 9, 10, and 11 exclusions

Phase 9 owns live model and deployment hardening, including real input/output/total tokens, API cost, provider/model latency, credentials, network behavior, and deployment configuration.

Phase 10 owns product/UI polish. Phase 8 adds no judge-facing dashboard, frontend evaluation surface, charts, or visual polish.

Phase 11 owns the submission package, deck, screenshots, charts, and video. Phase 8 provides machine-verifiable JSON and a concise Markdown evidence summary only.

No Phase 9, 10, or 11 item is pulled forward by the Phase 8 CLI or artifacts.
