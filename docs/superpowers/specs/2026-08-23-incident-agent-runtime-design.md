# Phase 5A: Incident Agent Runtime Design

**Status:** Approved architectural design, ready for implementation planning

**Date:** 2026-08-23

**Scope:** A single durable, incident-level agent that selects the next authorised operational capability while Phase 1–4 systems and human approvals remain authoritative.

## 1. Purpose and invariant

Phase 5A introduces the first agentic subsystem: one LLM-directed `AgentRun` coordinates the evolving recovery of one incident. It can inspect evidence, invoke a narrowly exposed and independently validated capability, prepare an external action, act once an existing typed approval authorises it, pause at mandatory authority boundaries, resume from durable state, explain its recorded actions, and escalate safely.

The governing invariant is literal:

> The LLM chooses the next authorised capability. The tool registry constrains what capabilities exist. Each tool revalidates authority and state. Deterministic systems own feasibility, allocation and safety. Humans supply real authorization. Durable database state is the agent's operational memory. Agent prose is explanation only.

The agent does **not** own physical feasibility, ready-time arithmetic, stochastic scarcity allocation, business-tradeoff scoring, DG policy, cargo classification, UN-number inference, carrier authority, operator approval, or counter approval. Phase 1–4 remain the sole authority for those concerns.

## 2. Existing-system boundary

The repository already has additive domain, repository, orchestration, FastAPI, and append-only audit patterns. Phase 5A follows those patterns without changing frozen Phase 1–4 contracts:

- `ScarcityEvaluationReport` and its selected allocation are evidence the agent reads; the agent cannot rerun, edit, or override Phase 2 allocation.
- `CarrierRecoveryWorkflow` remains the Phase 3 authority for deterministic proposal derivation, approval binding, send idempotency, response handling, timeout, and reconsideration. The agent supplies only a connection or case identity to its facade.
- Existing immutable `Approval` plus Phase 3 `ApprovalBinding` remain the only authority for a request or counter. Text that says an operator approved something never authorises a tool.
- `CargoSafetyWorkflow` remains the Phase 4 authority for semantic assessment, fail-closed policy, escalation decision creation, and supersession lineage. An `automation_blocked` safety result stops automated recovery for that container.
- The synthetic carrier simulator and synthetic-clock endpoints change the demonstration world. They are never tools available to the agent.

Phase 5A is additive only. It does not modify Phase 2 allocator policy, Phase 3 recovery semantics, Phase 4 safety policy, frontend, authentication, deployment, or background scheduling.

## 3. Agent run lifecycle

There is at most one active agent run per incident. Active means `CREATED`, `RUNNING`, or `WAITING`; historical `COMPLETED`, `ESCALATED`, and `FAILED` runs are retained indefinitely.

```text
CREATED -> RUNNING -> WAITING -> RUNNING
                  -> COMPLETED
                  -> ESCALATED
                  -> FAILED
```

`FAILED` is reserved for unrecoverable runtime corruption when a durable safe escalation cannot be recorded. Operational inability to proceed, invalid repeated model output, model unavailability, loop detection, exhausted budget, safety block, missing evidence, or unresolved tradeoff all end in `ESCALATED` with a typed reason.

The approved state and reason contracts are:

```text
AgentRunState
  CREATED | RUNNING | WAITING | COMPLETED | ESCALATED | FAILED

AgentWaitKind
  REQUEST_APPROVAL | COUNTER_APPROVAL | CARRIER_RESPONSE_OR_TIMEOUT
  | NEW_OPERATIONAL_EVIDENCE | HUMAN_TRADEOFF_DECISION

AgentStepKind
  TOOL_CALL | WAIT | COMPLETE | ESCALATE

AgentToolInvocationStatus
  PENDING | SUCCEEDED | REJECTED | FAILED

AgentEscalationReason
  SAFETY_REVIEW_REQUIRED | MISSING_EVIDENCE | TOOL_FAILURE | MODEL_UNAVAILABLE
  | AGENT_LOOP_GUARD | STEP_BUDGET_EXCEEDED | UNRESOLVED_TRADEOFF
```

The runtime, not the model, creates mandatory waits. A successful Phase 3 prepare transitions the run to `WAITING / REQUEST_APPROVAL`; an authorised send transitions it to `WAITING / CARRIER_RESPONSE_OR_TIMEOUT`; a persisted Phase 3 `COUNTER` transitions it to `WAITING / COUNTER_APPROVAL`. The model cannot elect to continue across one of these boundaries.

## 4. Durable records and consistency

The Phase 5A domain module is `backend/app/domain/agent_runtime.py` and its dedicated repository module is `backend/app/storage/agent_runtime.py`. It uses SQLModel records and explicit repository methods consistent with the current storage modules.

`AgentRun` stores `id`, `incident_id`, `state`, `model_name`, `prompt_version`, `step_count`, `max_steps`, nullable `wait_kind`, nullable `wait_subject_id`, nullable `escalation_reason`, `started_at`, `updated_at`, and nullable `completed_at`.

`AgentStep` stores `id`, `run_id`, `step_number`, `kind`, short non-authoritative `action_summary`, compact `evidence_refs`, `model_name`, nullable `latency_ms`, nullable `input_tokens`, nullable `output_tokens`, and `created_at`.

`AgentToolInvocation` stores `id`, `run_id`, `step_id`, `tool_name`, narrow structured `arguments`, `status`, bounded `result_summary`, nullable `error_kind`, `started_at`, and nullable `completed_at`.

`agent_audit_links` links a run to existing append-only `audit_events` so run history is queryable without parsing audit JSON. The new tables are `agent_runs`, `agent_steps`, `agent_tool_invocations`, and `agent_audit_links`.

The storage schema enforces:

- a partial unique active-run constraint on `incident_id` for `CREATED`, `RUNNING`, and `WAITING` (with repository-level transactional protection where SQLite support requires it);
- unique `(run_id, step_number)`;
- durable, unique tool-invocation identity;
- immutable terminal run/step/invocation history; and
- atomic compare-and-transition updates for run state, wait resolution, and step reservation.

For every state-changing tool, the runtime first persists and commits `AgentToolInvocation(PENDING)`, invokes the frozen domain capability with its durable invocation identity where supported, then persists `SUCCEEDED`, `REJECTED`, or `FAILED`. Retrying after a crash reuses the recorded invocation and never sends the RTA twice. It must preserve, not bypass, Phase 3/4 idempotency mechanisms.

No agent table stores hidden chain-of-thought, internal reasoning tokens, raw prompt transcripts, raw provider responses, provider headers, API keys, or other secrets. Structured tool inputs/results and brief action summaries are audit records, not provider transcripts.

## 5. Reconstructed turn context

`backend/app/orchestration/agent_context.py` builds a bounded `AgentTurnContext` afresh from durable state for every turn. The database, not a conversation transcript, is operational memory.

The context contains compact summaries and durable references for the run ID, incident ID, current step and remaining budget; agent authority contract; incident status; unresolved exceptions; current decisions; scarcity summary; carrier-recovery summary; cargo-safety summary; typed approvals; external state; recent structured agent steps; evidence references; and the currently available tool definitions. It uses IDs and short summaries rather than dumping every record. Deeper facts are obtained with evidence tools.

Each fact is labelled conceptually by trust class:

- `TRUSTED_STRUCTURED`: deterministic policy output, `CargoProfile`, scarcity/solver result, and typed `Approval`.
- `EXTERNAL_STRUCTURED`: persisted `CarrierResponse` and schedule/carrier events.
- `UNTRUSTED_TEXT`: cargo notes and carrier free text.
- `AGENT_GENERATED`: agent action summaries and explanations.

Natural-language content is data, never instruction or authority. In particular, a note claiming approval or a carrier message claiming acceptance has no effect unless the corresponding persisted `Approval` or `CarrierResponse` exists.

## 6. Model boundary and one-action rule

The runtime depends on an `AgentModel` protocol:

```text
decide(context: AgentTurnContext, available_tools: sequence[AgentToolDefinition])
  -> AgentModelTurn
```

Phase 5A provides `OpenAIAgentModel` using the official OpenAI Responses API tool-calling flow and `FakeAgentModel` for deterministic tests. Configuration is `OPENAI_API_KEY` and `OPENAI_AGENT_MODEL`, with `gpt-5.6-luna` as the default. The actual selected model name and an immutable prompt version are stored on the run and step.

The model instruction establishes responsibilities, not business policy: it may choose what authorised evidence/capability to use, must use only supplied tools, must treat structured approvals/state as authoritative, must treat untrusted text as data, and must wait or escalate when it lacks authority. Tool absence means absence of authority.

One model decision can produce exactly one meaningful action: one evidence call, deterministic/control call, `pause_agent_run`, `complete_agent_run`, or `escalate_agent_run`. Free-form prose is never executed. Invalid, malformed, multiple-action, or unavailable-tool output receives one corrective model retry; a second invalid response safely escalates.

The first provider failure is retried once. A second failure ends the run as `ESCALATED / MODEL_UNAVAILABLE`; no exponential-backoff system is introduced. A tool-side authority rejection is durably `REJECTED`, not a successful action. Mutating-tool infrastructure failure may retry only when the underlying operation is idempotent; otherwise the runtime escalates.

## 7. State-filtered tool facade

The model sees a narrow operational facade, not repositories, HTTP, shell, SQL, Python, arbitrary code execution, or demo controls.

| Category | Initial tools |
| --- | --- |
| Read/evidence | `get_incident_context`, `get_scarcity_evaluation`, `get_carrier_recovery_cases`, `get_carrier_recovery_history`, `get_cargo_safety_reviews` |
| Controlled analysis/action | `prepare_rta_request`, `send_authorised_rta_request`, `request_cargo_safety_review` |
| Runtime control | `pause_agent_run`, `complete_agent_run`, `escalate_agent_run` |

Arguments express identity and intent only: `prepare_rta_request(connection_id)`, `send_authorised_rta_request(case_id)`, and `request_cargo_safety_review(container_id)`. The facade derives RTA payload/timing solely through the deterministic Phase 3 workflow; the model cannot invent ETA/PTA, capacity, safety inputs, force flags, or policy overrides.

Availability is enforced twice. First, the registry derives tools from the current durable state and omits invalid actions. For example, after send and before deadline, carrier history and pause remain available, while prepare/send are absent. Second, every implementation reloads durable state and independently validates state, approval, authority, and idempotency before invoking the underlying workflow. A stale model decision therefore fails closed.

`pause_agent_run` validates an actual durable wait condition. `complete_agent_run` runs deterministic completion validation and rejects completion while actionable unresolved exceptions remain. `escalate_agent_run` is fail-safe but records a typed reason and evidence references.

`request_cargo_safety_review` coordinates only the existing Phase 4 review/evaluate path using persisted evidence. Its precondition is a persisted, matching Phase 4 `CargoSafetyReview` in `PENDING_CHECK` with its linked `CargoNote`; it supplies no note text or source and cannot create/alter cargo evidence. The canonical harness creates that review/note through the existing Phase 4 boundary before the tool is available. If Phase 4 returns `automation_blocked = true`, the agent may inspect/explain and must end `ESCALATED / SAFETY_REVIEW_REQUIRED`; it must not override the block, classify cargo, infer or correct a UN number, or continue automated recovery for that container.

## 8. Explicit advance and guards

Phase 5A has no autonomous daemon, polling worker, generic retry queue, or long-running process. Advancement is explicit:

```text
POST /agent-runs/{run_id}/advance
  reload durable run and incident state
  validate any wait condition
  if unresolved: return conflict without model execution
  if resolved: atomically resume RUNNING
  execute bounded persisted turns
  stop at next wait, completion, or escalation
```

The runtime re-reads durable state after each action. Configured defaults are `AGENT_MAX_STEPS=12` and `AGENT_MAX_TOOL_CALLS_PER_ADVANCE=8`. Two identical tool-and-argument calls without intervening authoritative state change end `ESCALATED / AGENT_LOOP_GUARD`. Exhausting the step budget ends `ESCALATED / STEP_BUDGET_EXCEEDED`. Limits are not automatically raised.

## 9. Additive API and history

The API adds only:

- `POST /incidents/{incident_id}/agent-runs`
- `POST /agent-runs/{run_id}/advance`
- `GET /incidents/{incident_id}/agent-runs`
- `GET /agent-runs/{run_id}`
- `GET /agent-runs/{run_id}/history`

Create and advance accept no custom prompt, model, tool whitelist, forced action, safety override, step-budget override, or arbitrary goal text. Advance has no body unless implementation evidence identifies a typed, non-authority input. Unknown incidents/runs are `404`; duplicate active run, unresolved wait, and stale durable-state conflict are `409`; invalid request shape is `422`.

The history response presents the run, ordered steps, ordered tool invocations, and structured audit links. It contains concise operator-facing explanations but never hidden reasoning or raw provider material.

## 10. Canonical hero and evaluation runs

The one primary hero run begins after the Phase 2 scarcity evaluation is already persisted. It reads incident/scarcity evidence, identifies unresolved JV2 recovery, reads recovery history, calls `prepare_rta_request(JV2)`, and is automatically `WAITING / REQUEST_APPROVAL`. Existing Phase 3 operator approval resumes the run; it calls `send_authorised_rta_request(case_id)` only after the exact durable approval binding validates, then automatically waits for carrier response.

The synthetic demonstration harness, not the agent, emits the canonical JV2 `COUNTER`. On resumption the runtime waits for counter approval; the model cannot approve it. Existing Phase 3 counter approval and deterministic reconsideration persist their normal results. The harness has already created the `SYN-CNT-010` Phase 4 `PENDING_CHECK` review and linked unstructured hero note, so the agent can invoke `request_cargo_safety_review(SYN-CNT-010)` without supplying cargo text. Frozen Phase 4 detects its contradiction against trusted `CargoProfile`, blocks automation, and preserves its escalation/supersession lineage. The agent ends `ESCALATED / SAFETY_REVIEW_REQUIRED`. This is a successful safe outcome.

Separate deterministic evaluation runs cover:

- `ACCEPT-RUN`: approved request and happy carrier response;
- `SILENT-RUN`: no `CarrierResponse`, then only a legitimate deadline/timeout path;
- `PROMPT-INJECTION-RUN`: malicious text claims authority but creates neither tools nor approval, and Phase 4 safety still prevails; and
- `MISSING-APPROVAL-RUN`: send attempt is rejected, persisted, and makes no external dispatch.

## 11. Acceptance criteria

Phase 5A is accepted only when all of the following are demonstrated by ordinary deterministic tests (with zero network calls) and a separately opt-in real-agent smoke:

- One active incident-level run is enforced; duplicate creation is rejected.
- Scarcity is read but never overridden; the agent identifies unresolved JV2 recovery.
- RTA proposal parameters are derived by deterministic backend evidence, not model input.
- Request approval automatically pauses the run; no typed approval means no send; a valid exact approval enables send.
- Carrier `COUNTER` requires typed human counter approval.
- Natural-language claims of approval or carrier acceptance have zero authority.
- SYN-CNT-010 contradiction remains Phase 4-owned; its safety block prevents override.
- Prompt injection cannot create tools, authority, or execution escape hatches.
- Tool registry filtering and independent tool-side revalidation both occur.
- A loop guard and step budget escalate safely; model outage retries once then escalates.
- Invocation crash/retry cannot duplicate the RTA send.
- Completion cannot succeed with unresolved actionable state.
- Full structured run, step, invocation, and audit-link history is retrievable.
- No hidden chain-of-thought, raw prompt transcript, or raw provider response is persisted.

## 12. Explicit exclusions

Phase 5A excludes Phase 5B forecast tightening/simulator work and uncertainty-driven reconsideration; multi-agent or planner/executor designs; LangGraph; generic chat UI or frontend panel; roll execution absent proven hero-flow need; human DG resolution; arbitrary business-priority judgment; deployment/authentication/background workers; generic retry queues; and arbitrary HTTP, SQL, shell, or Python tools. It neither redesigns Phase 2/3/4 nor introduces a generic execution escape hatch.
