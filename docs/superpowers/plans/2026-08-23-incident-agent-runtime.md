# Incident Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the durable, incident-level Phase 5A agent runtime that chooses one authorised next capability while Phase 2 scarcity, Phase 3 carrier recovery, Phase 4 cargo safety, and typed human approval remain authoritative.

**Architecture:** Add frozen runtime contracts and isolated SQLModel persistence, then expose a reconstructed context and state-filtered tool facade through an injected coordinator. The coordinator reconstructs durable truth on every turn, delegates controlled calls to the existing workflows, records invocation/step/audit history, and terminates at wait, completion, or safe escalation. `FakeAgentModel` drives ordinary tests; the OpenAI Responses adapter is opt-in only.

**Tech Stack:** Python 3.12, Pydantic v2, SQLModel/SQLite, FastAPI, official OpenAI Python SDK Responses API, pytest/httpx.

**Spec:** `docs/superpowers/specs/2026-08-23-incident-agent-runtime-design.md`

## Global Constraints

- Do not modify frontend files or redesign Phase 1–4 domain contracts, allocator policy, carrier workflow, or cargo-safety policy.
- The model receives only a bounded reconstructed context and state-filtered narrow tool definitions; it never receives RTA timing, timeout time, arbitrary goal, prompt, model selection, tool whitelist, force flag, shell, SQL, HTTP, or Python execution capability.
- Natural-language text is data only. Only persisted `Approval`/`ApprovalBinding` and `CarrierResponse` records create authority.
- Phase 5A’s deterministic carrier facade resolves `prepared_at`, `requested_eta_pta`, and `response_deadline` from trusted backend/shared synthetic configuration; it delegates the unchanged `PrepareCarrierRecoveryCaseCommand` to Phase 3.
- The trusted injectable runtime/synthetic clock supplies `effective_at` for timeout evaluation; only the synthetic harness moves that clock.
- Persist no hidden reasoning, raw prompt transcript, raw Responses API body, provider headers, API key, or secret.
- Ordinary tests use `FakeAgentModel` and fake safety checker inputs, make zero network calls, and must pass with `OPENAI_API_KEY` unset.
- Real OpenAI smoke is opt-in only with `RUN_LIVE_LLM_TESTS=1`, `OPENAI_API_KEY`, and optional `OPENAI_AGENT_MODEL` (default `gpt-5.6-luna`).

---

## File map

| File | Responsibility |
| --- | --- |
| `backend/app/domain/agent_runtime.py` | Frozen run, step, tool-turn, context, enum, history, and command contracts. |
| `backend/app/storage/agent_runtime.py` | Agent SQLModel rows, active-run uniqueness, atomic state transitions, invocation identity, and history/audit persistence. |
| `backend/app/services/agent_model.py` | `AgentModel` protocol, strict turn schema, fake model, OpenAI Responses tool-call adapter, and provider errors. |
| `backend/app/orchestration/agent_context.py` | Durable-state-to-bounded-context projection and trust-class summaries. |
| `backend/app/orchestration/agent_runtime.py` | Trusted clock/configuration, state-filtered registry, tool implementations, run coordinator, retry/guard/wait logic. |
| `backend/app/main.py` | Dependency-injectable coordinator and five additive agent-run routes. |
| `backend/tests/test_agent_runtime_contracts.py` | Contract, turn-schema, no-secret, and model-protocol unit tests. |
| `backend/tests/test_agent_runtime_repositories.py` | Persistence, unique active run, history, transaction, and crash/idempotency tests. |
| `backend/tests/test_agent_context.py` | Context compaction, trust classification, and state-filtered registry tests. |
| `backend/tests/test_agent_runtime_workflow.py` | Coordinator/tool/wait/guard/retry/authority tests plus hero/evaluation flows. |
| `backend/tests/test_agent_runtime_api.py` | Agent route, validation, conflict, history, and OpenAPI tests. |
| `backend/tests/test_agent_model_adapter.py` | Mocked Responses API conversion/error tests. |
| `backend/tests/test_live_agent_runtime_smoke.py` | Explicitly opt-in OpenAI smoke. |
| `shared/fixtures/canonical-agent-runtime-config.json` | Trusted canonical RTA timings and synthetic clock moments for COUNTER, ACCEPT, and SILENT runs. |

## Task 1: Define frozen runtime contracts and model turn schema

**Files:**
- Create: `backend/app/domain/agent_runtime.py`
- Create: `backend/tests/test_agent_runtime_contracts.py`

**Interfaces:** Produces `AgentRunState`, `AgentWaitKind`, `AgentStepKind`, `AgentToolInvocationStatus`, `AgentEscalationReason`, `AgentRun`, `AgentStep`, `AgentToolInvocation`, `AgentHistory`, `AgentToolDefinition`, `AgentToolCall`, `AgentModelTurn`, `InvalidAgentModelTurn`, and `AgentTurnContext`. Terminal-run timestamps and wait/escalation shape are validated in frozen Pydantic contracts.

- [ ] **Step 1: Write failing contract tests**

```python
def test_agent_step_records_prompt_version_and_run_rejects_invalid_wait_shape():
    assert "prompt_version" in AgentStep.model_fields
    with pytest.raises(ValidationError):
        AgentRun(state=AgentRunState.WAITING, wait_kind=None)

def test_agent_model_turn_has_exactly_one_action():
    with pytest.raises(ValidationError):
        AgentModelTurn(tool_call=call, control="COMPLETE")
```

- [ ] **Step 2: Run the contract test and verify it fails because the module is absent**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_contracts.py -v`

- [ ] **Step 3: Implement the minimal frozen contracts**

```python
class AgentEscalationReason(StrEnum):
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"

class AgentModelTurn(FrozenContract):
    tool_call: AgentToolCall | None = None
    control: AgentControlAction | None = None

class InvalidAgentModelTurn(FrozenContract):
    error_kind: str
```

Use bounded `action_summary`, `result_summary`, JSON-compatible arguments/evidence refs, UTC timestamps, `AgentStep.prompt_version`, and validators requiring a wait kind only for `WAITING`, an escalation reason only for `ESCALATED`, and exactly one model action.

- [ ] **Step 4: Run focused contract tests**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_contracts.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/app/domain/agent_runtime.py backend/tests/test_agent_runtime_contracts.py && git commit -m "feat: add agent runtime contracts"`

## Task 2: Add isolated SQLModel persistence and durable history

**Files:**
- Create: `backend/app/storage/agent_runtime.py`
- Create: `backend/tests/test_agent_runtime_repositories.py`

**Interfaces:** Consumes Task 1 contracts and existing `AuditRepository`; produces `AgentRuntimeRepository.create_run`, `get_run`, `list_runs`, `reserve_next_step`, `add_invocation_pending`, `complete_invocation`, `transition_run`, `link_audit`, and `history`.

- [ ] **Step 1: Write failing repository tests**

```python
def test_only_one_created_running_or_waiting_run_exists_per_incident(session, incident):
    repo.create_run(run_for(incident.id))
    with pytest.raises(AgentRuntimeConflict):
        repo.create_run(run_for(incident.id))

def test_pending_invocation_and_structured_history_survive_reload(session, incident):
    invocation = repo.add_invocation_pending(run.id, step.id, "prepare_rta_request", {"connection_id": "JV2"})
    assert AgentRuntimeRepository(session).history(run.id).tool_invocations == (invocation,)
```

- [ ] **Step 2: Run and verify the repository test fails**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_repositories.py -v`

- [ ] **Step 3: Implement records, constraints, and transactions**

Create `agent_runs`, `agent_steps`, `agent_tool_invocations`, and `agent_audit_links`. Use a SQLite partial unique index for active states; translate uniqueness races into `AgentRuntimeConflict`. Enforce unique `(run_id, step_number)`, durable invocation UUIDs, append-only terminal history, and compare-and-transition state updates in a repository-owned transaction.

- [ ] **Step 4: Verify concurrency, terminal immutability, audit links, and rollback**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_repositories.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/app/storage/agent_runtime.py backend/tests/test_agent_runtime_repositories.py && git commit -m "feat: persist durable agent run history"`

## Task 3: Implement model adapters without operational authority

**Files:**
- Create: `backend/app/services/agent_model.py`
- Create: `backend/tests/test_agent_model_adapter.py`
- Modify: `backend/tests/test_agent_runtime_contracts.py`

**Interfaces:** Produces `AgentModel.decide(context, available_tools) -> AgentModelTurn | InvalidAgentModelTurn`, `FakeAgentModel`, `OpenAIAgentModel`, `AgentModelProviderFailure`, `AGENT_PROMPT_VERSION`, and static responsibility-only instructions.

- [ ] **Step 1: Write failing fake and adapter tests**

```python
def test_fake_model_returns_scripted_single_turn_without_network():
    assert FakeAgentModel([turn]).decide(context, tools) == turn

def test_openai_adapter_maps_unknown_tool_to_invalid_turn(mock_client):
    assert isinstance(OpenAIAgentModel(client=mock_client).decide(context, tools), InvalidAgentModelTurn)
```

- [ ] **Step 2: Run and verify adapter tests fail**

Run: `uv run --extra dev pytest backend/tests/test_agent_model_adapter.py -v`

- [ ] **Step 3: Implement strict adapter conversion**

Use the already-installed `openai` SDK and `client.responses.create` tool definitions. Convert only a single function-tool call or one validated runtime control action into `AgentModelTurn`; preserve no raw provider object. Map API/provider failures to `AgentModelProviderFailure`. Refuse unset API key, tool names absent from `available_tools`, malformed arguments, and multiple calls as invalid turns rather than executing them.

- [ ] **Step 4: Run model and contract tests**

Run: `uv run --extra dev pytest backend/tests/test_agent_model_adapter.py backend/tests/test_agent_runtime_contracts.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/app/services/agent_model.py backend/tests/test_agent_model_adapter.py backend/tests/test_agent_runtime_contracts.py && git commit -m "feat: add constrained agent model adapters"`

## Task 4: Add trusted runtime clock and canonical carrier configuration

**Files:**
- Create: `shared/fixtures/canonical-agent-runtime-config.json`
- Modify: `shared/fixtures/README.md`
- Create: `backend/tests/test_agent_runtime_config.py`
- Create: `backend/app/orchestration/agent_runtime.py`

**Interfaces:** Produces immutable `AgentRuntimeClock.now()`, `FixedAgentRuntimeClock`, and `CanonicalAgentRuntimeConfiguration.prepare_command(incident_id, connection_id)` returning the unchanged Phase 3 command. It also supplies scenario-specific trusted synthetic clock values.

- [ ] **Step 1: Write failing configuration tests**

```python
def test_prepare_command_uses_fixture_timing_not_model_arguments(incident_id):
    command = configuration.prepare_command(incident_id, "JV2")
    assert command.requested_eta_pta.tzinfo is UTC

def test_fixed_clock_is_injectable_and_never_exposed_as_a_tool():
    assert FixedAgentRuntimeClock(now).now() == now
```

- [ ] **Step 2: Run and verify config tests fail**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_config.py -v`

- [ ] **Step 3: Implement fixture-backed trusted configuration**

Store canonical UTC `prepared_at`, `requested_eta_pta`, `response_deadline`, and pre/post-deadline synthetic clock values by carrier evaluation run. Validate the fixture with frozen Pydantic config contracts. The configuration takes only incident and connection identity, creates `PrepareCarrierRecoveryCaseCommand`, and never accepts LLM input for any time.

- [ ] **Step 4: Run configuration tests**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_config.py -v`

- [ ] **Step 5: Commit**

Run: `git add shared/fixtures/canonical-agent-runtime-config.json shared/fixtures/README.md backend/app/orchestration/agent_runtime.py backend/tests/test_agent_runtime_config.py && git commit -m "feat: add trusted agent runtime configuration"`

## Task 5: Build reconstructed context and state-filtered registry

**Files:**
- Create: `backend/app/orchestration/agent_context.py`
- Create: `backend/tests/test_agent_context.py`
- Modify: `backend/app/orchestration/agent_runtime.py`

**Interfaces:** Produces `build_agent_turn_context(session, run, registry) -> AgentTurnContext` and `AgentToolRegistry.available_tools(run, context) -> tuple[AgentToolDefinition, ...]`.

- [ ] **Step 1: Write failing context/registry tests**

```python
def test_context_contains_ids_and_summaries_not_raw_prompt_or_provider_data(session, run):
    context = build_agent_turn_context(session, run, registry)
    assert context.incident_id == run.incident_id
    assert "raw_response" not in context.model_dump_json()

def test_timeout_tool_is_absent_before_deadline_and_present_after_deadline(case):
    assert "evaluate_carrier_timeout" not in names(before_deadline_tools)
    assert "evaluate_carrier_timeout" in names(after_deadline_tools)
```

- [ ] **Step 2: Run and verify the focused tests fail**

Run: `uv run --extra dev pytest backend/tests/test_agent_context.py -v`

- [ ] **Step 3: Implement compact durable projection and registry**

Load incident, current decisions, scarcity report, carrier case/history, cargo safety review/history, typed approvals, external response, recent agent steps, audit/evidence references, and classify fields as trusted structured, external structured, untrusted text, or agent-generated. Expose only read tools initially; add prepare/send/timeout/safety/control tools only when durable state permits. Omit timeout before deadline, on response, or outside `AWAITING_CARRIER`.

- [ ] **Step 4: Run focused context tests**

Run: `uv run --extra dev pytest backend/tests/test_agent_context.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/app/orchestration/agent_context.py backend/app/orchestration/agent_runtime.py backend/tests/test_agent_context.py && git commit -m "feat: add durable agent context and tool registry"`

## Task 6: Implement read tools and Phase 3 carrier facade

**Files:**
- Modify: `backend/app/orchestration/agent_runtime.py`
- Create: `backend/tests/test_agent_runtime_tools.py`

**Interfaces:** Produces revalidating implementations for `get_incident_context`, `get_scarcity_evaluation`, `get_carrier_recovery_cases`, `get_carrier_recovery_history`, `prepare_rta_request(connection_id)`, `send_authorised_rta_request(case_id)`, and `evaluate_carrier_timeout(case_id)`.

- [ ] **Step 1: Write failing facade tests**

```python
def test_prepare_facade_uses_trusted_config_and_creates_phase3_case(runtime, run):
    result = runtime.invoke_tool(run.id, "prepare_rta_request", {"connection_id": "JV2"})
    assert result.case.state is CarrierRecoveryCaseState.AWAITING_REQUEST_APPROVAL

def test_send_without_typed_approval_is_rejected_and_does_not_dispatch(runtime, case):
    assert runtime.invoke_tool(...).status is AgentToolInvocationStatus.REJECTED

def test_timeout_reloads_case_and_uses_runtime_clock_not_arguments(runtime, sent_case):
    assert runtime.invoke_tool(...).status is AgentToolInvocationStatus.SUCCEEDED
```

- [ ] **Step 2: Run and verify tool tests fail**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_tools.py -v`

- [ ] **Step 3: Implement facade delegation and mandatory waits**

Each implementation reloads the run/case/approval/response state, validates it against the registry condition, records `PENDING` before mutation, and calls only `build_carrier_recovery_workflow(session).prepare`, `.send_authorised_request`, or `.evaluate_timeout`. After prepare set `WAITING / REQUEST_APPROVAL`; after send set `WAITING / CARRIER_RESPONSE_OR_TIMEOUT`; after detected counter set `WAITING / COUNTER_APPROVAL`. Pass the trusted configuration command or trusted clock command only.

- [ ] **Step 4: Run tool tests**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_tools.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/app/orchestration/agent_runtime.py backend/tests/test_agent_runtime_tools.py && git commit -m "feat: add agent carrier recovery facade"`

## Task 7: Implement Phase 4 and runtime-control facades

**Files:**
- Modify: `backend/app/orchestration/agent_runtime.py`
- Modify: `backend/tests/test_agent_runtime_tools.py`

**Interfaces:** Produces `request_cargo_safety_review(container_id)`, `pause_agent_run`, `complete_agent_run`, and `escalate_agent_run` implementations.

- [ ] **Step 1: Write failing safety/control tests**

```python
def test_safety_tool_evaluates_only_existing_pending_review_and_escalates_blocked_run(runtime, run):
    result = runtime.invoke_tool(run.id, "request_cargo_safety_review", {"container_id": "SYN-CNT-010"})
    assert runtime.get_run(run.id).escalation_reason is AgentEscalationReason.SAFETY_REVIEW_REQUIRED

def test_complete_is_rejected_with_actionable_case_or_pending_safety_review(runtime, run):
    assert runtime.invoke_tool(run.id, "complete_agent_run", {}).status is AgentToolInvocationStatus.REJECTED
```

- [ ] **Step 2: Run and verify safety/control tests fail**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_tools.py -v`

- [ ] **Step 3: Implement fail-closed delegation and controls**

Load only an existing matching `PENDING_CHECK` review and invoke `CargoSafetyWorkflow.evaluate`; never accept note text or safety override. On `automation_blocked`, persist agent escalation with safety evidence. Validate pause against a durable wait state. Validate completion by checking no unresolved carrier/actionable safety state exists. Escalation records a typed allowed reason and references structured evidence.

- [ ] **Step 4: Run tool tests**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_tools.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/app/orchestration/agent_runtime.py backend/tests/test_agent_runtime_tools.py && git commit -m "feat: add agent safety and control tools"`

## Task 8: Implement durable advance loop, retries, and guards

**Files:**
- Modify: `backend/app/orchestration/agent_runtime.py`
- Create: `backend/tests/test_agent_runtime_workflow.py`

**Interfaces:** Produces `AgentRuntimeCoordinator.create_run(incident_id)`, `advance(run_id)`, and `history(run_id)`. It accepts injected repository, model, clock, configuration, carrier workflow factory, and cargo-safety workflow factory.

- [ ] **Step 1: Write failing loop tests**

```python
def test_second_invalid_turn_escalates_invalid_model_output(runtime, run):
    runtime.advance(run.id)
    assert runtime.get_run(run.id).escalation_reason is AgentEscalationReason.INVALID_MODEL_OUTPUT

def test_second_provider_failure_escalates_model_unavailable(runtime, run):
    runtime.advance(run.id)
    assert runtime.get_run(run.id).escalation_reason is AgentEscalationReason.MODEL_UNAVAILABLE

def test_two_identical_calls_without_authoritative_change_escalate_loop_guard(runtime, run):
    runtime.advance(run.id)
    assert runtime.get_run(run.id).escalation_reason is AgentEscalationReason.AGENT_LOOP_GUARD
```

- [ ] **Step 2: Run and verify loop tests fail**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_workflow.py -v`

- [ ] **Step 3: Implement bounded restartable orchestration**

On advance reload durable state. If a wait remains unresolved, raise conflict before model invocation; if resolved, transition to `RUNNING`. For each turn rebuild context/tools, call model once, make exactly one corrective retry for invalid output or provider failure, reserve one step, persist model metadata/action summary, record one invocation before a mutation, reread state, and stop at mandatory wait/terminal state. Enforce defaults `AGENT_MAX_STEPS=12` and `AGENT_MAX_TOOL_CALLS_PER_ADVANCE=8`; two identical tool+argument calls without changed authoritative evidence escalate loop guard, and exhausted step budget escalates.

- [ ] **Step 4: Run workflow tests**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_workflow.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/app/orchestration/agent_runtime.py backend/tests/test_agent_runtime_workflow.py && git commit -m "feat: add durable agent advance loop"`

## Task 9: Prove crash safety, approvals, and full history

**Files:**
- Modify: `backend/tests/test_agent_runtime_repositories.py`
- Modify: `backend/tests/test_agent_runtime_workflow.py`

**Interfaces:** Verifies pending invocation recovery, Phase 3 send idempotency preservation, structured audit links, and exact typed-approval authority.

- [ ] **Step 1: Write failing durability tests**

```python
def test_retry_after_pending_send_invocation_does_not_duplicate_phase3_dispatch(runtime, approved_case):
    runtime.leave_pending_after_domain_send_for_test(approved_case)
    runtime.advance(run.id)
    assert count_events("rta.request_sent") == 1

def test_prompt_claimed_approval_cannot_send_without_persisted_binding(runtime, case):
    assert runtime.invoke_tool(...).status is AgentToolInvocationStatus.REJECTED
```

- [ ] **Step 2: Run and verify the new tests fail**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_repositories.py backend/tests/test_agent_runtime_workflow.py -v`

- [ ] **Step 3: Implement recovery reconciliation**

On an existing `PENDING` mutation invocation, reload Phase 3/4 durable history and reconcile an already-completed idempotent domain result before retrying. Record rejection/failure summaries without raw exception/provider payload. Link runtime audit events to each run and return ordered run/step/invocation/audit history.

- [ ] **Step 4: Run durability tests**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_repositories.py backend/tests/test_agent_runtime_workflow.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/tests/test_agent_runtime_repositories.py backend/tests/test_agent_runtime_workflow.py backend/app/orchestration/agent_runtime.py backend/app/storage/agent_runtime.py && git commit -m "test: cover agent crash safety and authority"`

## Task 10: Expose additive agent-run API and OpenAPI contracts

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_agent_runtime_api.py`

**Interfaces:** Adds `POST /incidents/{incident_id}/agent-runs`, `POST /agent-runs/{run_id}/advance`, `GET /incidents/{incident_id}/agent-runs`, `GET /agent-runs/{run_id}`, and `GET /agent-runs/{run_id}/history`; `create_app` accepts optional coordinator dependencies for tests.

- [ ] **Step 1: Write failing API tests**

```python
def test_create_advance_list_get_and_history(client, resolved_incident):
    created = client.post(f"/incidents/{resolved_incident.id}/agent-runs")
    assert client.post(f"/agent-runs/{created.json()['id']}/advance").status_code == 200
    assert client.get(f"/agent-runs/{created.json()['id']}/history").status_code == 200

def test_agent_api_rejects_body_authority_knobs(client, resolved_incident):
    assert client.post(f"/incidents/{resolved_incident.id}/agent-runs", json={"model": "x"}).status_code == 422
```

- [ ] **Step 2: Run and verify API tests fail**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_api.py -v`

- [ ] **Step 3: Implement route models and errors**

Use bodyless create/advance handlers and existing `RecordNotFound`/workflow-conflict patterns. Map unknown run/incident to 404, duplicate active/unresolved wait/stale conflict to 409, and request shape to 422. Use response models from Task 1 and verify the OpenAPI schema exposes no authority-changing input field.

- [ ] **Step 4: Run API and OpenAPI tests**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_api.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/app/main.py backend/tests/conftest.py backend/tests/test_agent_runtime_api.py && git commit -m "feat: expose agent runtime API"`

## Task 11: Add deterministic hero and branch evaluation coverage

**Files:**
- Modify: `backend/tests/test_agent_runtime_workflow.py`
- Modify: `backend/tests/test_agent_runtime_api.py`

**Interfaces:** Uses `FakeAgentModel` scripts plus existing synthetic carrier response plan and Phase 3 approval routes to prove COUNTER, ACCEPT, SILENT, prompt-injection, and missing-approval outcomes.

- [ ] **Step 1: Write failing canonical/evaluation tests**

```python
def test_counter_hero_waits_for_request_then_counter_and_ends_safety_escalated(runtime):
    assert run_until_terminal(runtime, "COUNTER-RUN").escalation_reason is AgentEscalationReason.SAFETY_REVIEW_REQUIRED

def test_accept_and_silent_paths_preserve_authority_boundaries(runtime):
    assert accept_run.state is AgentRunState.COMPLETED
    assert silent_run_has_no_carrier_response_and_uses_timeout is True
```

- [ ] **Step 2: Run and verify evaluation tests fail**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_workflow.py backend/tests/test_agent_runtime_api.py -v`

- [ ] **Step 3: Implement test fixtures and end-to-end assertions**

For COUNTER: persist scarcity, create run, inspect, prepare JV2, verify request wait, record exact existing approval, send, verify carrier wait, let only harness emit counter, verify counter wait, record counter approval, create pending SYN-CNT-010 review/note through Phase 4, evaluate safety, and assert safe escalation. For ACCEPT assert valid approval/send/accept/reconsideration reaches deterministic completion. For SILENT assert no response exists before or after timeout, the tool is absent before trusted deadline and valid afterward. For injection pass malicious text only as untrusted evidence and assert no new tool/approval. For missing approval attempt send and assert rejected invocation plus zero send audit events.

- [ ] **Step 4: Run evaluation tests**

Run: `uv run --extra dev pytest backend/tests/test_agent_runtime_workflow.py backend/tests/test_agent_runtime_api.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/tests/test_agent_runtime_workflow.py backend/tests/test_agent_runtime_api.py && git commit -m "test: cover agent recovery evaluations"`

## Task 12: Add opt-in live smoke and final regression verification

**Files:**
- Create: `backend/tests/test_live_agent_runtime_smoke.py`

**Interfaces:** The smoke invokes only `OpenAIAgentModel` under explicit environment opt-in; normal test collection skips it before any client construction.

- [ ] **Step 1: Write the opt-in smoke test**

```python
@pytest.mark.skipif(os.getenv("RUN_LIVE_LLM_TESTS") != "1", reason="opt-in live agent test")
def test_live_agent_selects_only_exposed_evidence_tool():
    turn = OpenAIAgentModel().decide(context, tools)
    assert isinstance(turn, AgentModelTurn)
    assert turn.tool_call.name in {tool.name for tool in tools}
```

- [ ] **Step 2: Verify normal test collection skips it with no network**

Run: `uv run --extra dev pytest backend/tests/test_live_agent_runtime_smoke.py -v`

- [ ] **Step 3: Run all required verification**

Run: `uv lock --check && uv run --extra dev pytest backend/tests/test_agent_runtime_contracts.py backend/tests/test_agent_model_adapter.py backend/tests/test_agent_runtime_config.py backend/tests/test_agent_runtime_repositories.py backend/tests/test_agent_context.py backend/tests/test_agent_runtime_tools.py backend/tests/test_agent_runtime_workflow.py backend/tests/test_agent_runtime_api.py backend/tests/test_live_agent_runtime_smoke.py -v && uv run --extra dev pytest && git diff --check`

- [ ] **Step 4: Confirm scope and commit**

Run: `git diff --name-only 7f38f1d...HEAD` and confirm no `web/` file, forbidden tool, raw provider persistence, or Phase 5B file appears. Then `git add backend/tests/test_live_agent_runtime_smoke.py && git commit -m "test: add opt-in agent runtime smoke test"`.

## Plan self-review

- **Spec coverage:** Tasks 1–2 cover contracts, one active run, durable history, audit links, and crash-safe invocation identity. Tasks 3–5 cover OpenAI/Fake models, trusted RTA config/clock, context, and tool filtering. Tasks 6–9 cover all approved tools, mandatory waits, one-action/retry, loop/budget controls, approvals, and idempotency. Task 10 covers the API; Tasks 11–12 cover hero, ACCEPT, SILENT, prompt injection, missing approval, opt-in live smoke, and full regression.
- **Red-flag scan:** The prohibited incomplete-plan patterns are absent, and every task names concrete files, tests, interfaces, commands, and expected assertions.
- **Type/interface consistency:** `AgentRuntimeCoordinator`, `AgentRuntimeRepository`, `AgentModel`, `AgentToolRegistry`, `FixedAgentRuntimeClock`, and the exact narrow tool names are introduced before consumers. All Phase 3 calls use existing `PrepareCarrierRecoveryCaseCommand`, `send_authorised_request`, and `evaluate_timeout`; no new Phase 3 interface is required.
