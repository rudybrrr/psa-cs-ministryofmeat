# DG Semantic Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add additive cargo-note semantic contradiction detection whose deterministic policy blocks automation and escalates unresolved safety evidence.

**Architecture:** A frozen Phase 4 domain module and isolated repository preserve notes/reviews/assessments/policy/audit links. The workflow commits the pending review before calling an injected checker, then performs the final assessment/policy/decision/audit transaction atomically. OpenAI is a narrow structured-output adapter; all operational and safety authority remains deterministic.

**Tech Stack:** Python 3.12, Pydantic v2, SQLModel/SQLite, FastAPI, official OpenAI Python SDK Responses API, pytest/httpx.

**Spec:** `docs/superpowers/specs/2026-08-23-dg-semantic-safety-design.md`

## Global Constraints

- Preserve every Phase 1–3 domain contract, storage row, workflow, API, and frontend file.
- Reuse canonical `CargoProfile`; do not add a competing DG declaration.
- Checker output is strictly limited to result/explanation/evidence excerpt and gets no tools.
- `CONTRADICTION_FOUND`, `INDETERMINATE`, and all failures fail closed to an approved escalation.
- Never hold a DB transaction open for the model call.
- Ordinary tests use `FakeSemanticSafetyChecker` and make no network calls.
- Use `SYN-CNT-010` hero evidence solely as unstructured note text.

---

### Task 1: Define frozen Phase 4 contracts and checker boundary

**Files:**
- Create: `backend/app/domain/cargo_safety.py`
- Create: `backend/app/services/semantic_safety.py`
- Modify: `pyproject.toml`, `uv.lock`
- Test: `backend/tests/test_cargo_safety_contracts.py`

**Interfaces:** Produces domain types from the spec, `SemanticSafetyChecker`,
`FakeSemanticSafetyChecker`, `OpenAISemanticSafetyChecker`, prompt version, and
strict Pydantic wire model.

- [ ] **Step 1: Write failing contract and boundary tests**

```python
def test_failed_assessment_requires_failure_kind_and_forbids_excerpt():
    with pytest.raises(ValidationError):
        SemanticSafetyAssessment(result=SemanticCheckResult.CHECK_FAILED)

def test_checker_output_has_only_semantic_fields():
    assert set(SemanticSafetyCheckOutput.model_fields) == {"result", "explanation", "evidence_excerpt"}
```

- [ ] **Step 2: Run the contract test and verify it fails because the module is absent**

Run: `uv run --extra dev pytest backend/tests/test_cargo_safety_contracts.py -v`

- [ ] **Step 3: Implement minimal frozen contracts and adapter protocol**

```python
class SemanticSafetyChecker(Protocol):
    def check(self, evidence: SemanticSafetyCheckInput) -> SemanticSafetyCheckOutput: ...
```

Implement bounded Pydantic fields, UTC-aware timestamps, assessment validation,
and SDK configuration/error mapping. Add `openai>=1,<2` with `uv add`/lock.

- [ ] **Step 4: Run the focused tests and adapter mock tests**

Run: `uv run --extra dev pytest backend/tests/test_cargo_safety_contracts.py backend/tests/test_semantic_safety_adapter.py -v`

- [ ] **Step 5: Commit**

Run: `git add pyproject.toml uv.lock backend/app/domain/cargo_safety.py backend/app/services/semantic_safety.py backend/tests/test_cargo_safety_contracts.py backend/tests/test_semantic_safety_adapter.py && git commit -m "feat: add cargo semantic checker contracts"`

### Task 2: Persist isolated cargo-safety records

**Files:**
- Create: `backend/app/storage/cargo_safety.py`
- Test: `backend/tests/test_cargo_safety_repositories.py`

**Interfaces:** Consumes Phase 4 contracts; produces create/load/list/history,
atomic transaction, immutable evidence snapshots, and audit-link persistence.

- [ ] **Step 1: Write failing repository tests**

```python
def test_review_persists_one_assessment_policy_and_linked_audit(session):
    repository = CargoSafetyRepository(session)
    repository.create_note_and_review(note, review)
    repository.complete(review, assessment, policy, decision=None, events=(event,))
    assert repository.history(review.id).assessment == assessment
```

- [ ] **Step 2: Run and verify the repository test fails because the repository is absent**

Run: `uv run --extra dev pytest backend/tests/test_cargo_safety_repositories.py -v`

- [ ] **Step 3: Implement SQLModel records and repository**

Use named isolated tables, unique `cargo_note_id` per review and unique review IDs
for assessment/policy. Reuse `AuditRepository.add_uncommitted` and the existing
decision record conversion only inside caller-owned transactions.

- [ ] **Step 4: Verify atomic persistence and history**

Run: `uv run --extra dev pytest backend/tests/test_cargo_safety_repositories.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/app/storage/cargo_safety.py backend/tests/test_cargo_safety_repositories.py && git commit -m "feat: persist cargo safety reviews"`

### Task 3: Implement fail-closed workflow and policy

**Files:**
- Create: `backend/app/orchestration/cargo_safety.py`
- Test: `backend/tests/test_cargo_safety_workflow.py`

**Interfaces:** Consumes repository/checker/canonical fixture/decision and audit
repositories; produces `create_review`, `evaluate`, `get`, `list`, `history`.

- [ ] **Step 1: Write failing behavior tests**

```python
def test_contradiction_supersedes_current_container_decision(session):
    result = workflow_with(CONTRADICTION_FOUND).evaluate(review.id)
    assert result.policy_result.disposition is SemanticSafetyDisposition.ESCALATE
    assert result.decision.supersedes == prior.id

def test_completed_retry_does_not_call_checker_or_duplicate_audit(session):
    first = workflow.evaluate(review.id)
    second = workflow.evaluate(review.id)
    assert second == first
```

Add literals for pass-through, indeterminate, failed check, no prior decision,
frozen Phase 2/3 evidence, all audit actors/events, injection note, fabricated
excerpt conversion, and rollback failure.

- [ ] **Step 2: Run and verify workflow tests fail because the workflow is absent**

Run: `uv run --extra dev pytest backend/tests/test_cargo_safety_workflow.py -v`

- [ ] **Step 3: Implement the workflow without a transaction around checker.check**

Persist pending note/review first. Load canonical profile by exact container ID.
Validate checker output excerpts. Map all non-pass outcomes to the exact human
review rationale and `DecisionAction.ESCALATE`; find the sole non-superseded
container decision and supersede it. Atomically persist outcome/audits/completed
review. Return durable results on completed retries.

- [ ] **Step 4: Run focused workflow tests**

Run: `uv run --extra dev pytest backend/tests/test_cargo_safety_workflow.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/app/orchestration/cargo_safety.py backend/tests/test_cargo_safety_workflow.py && git commit -m "feat: add fail-closed cargo safety workflow"`

### Task 4: Expose additive API and canonical note fixture

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_cargo_safety_api.py`
- Create: `shared/fixtures/canonical-dg-contradiction.json`
- Modify: `shared/fixtures/README.md`

**Interfaces:** Adds only the five specified routes and dependency-injectable
checker configuration, without user-provided model/safety/action controls.

- [ ] **Step 1: Write failing API tests**

```python
def test_create_evaluate_list_get_and_history(client):
    created = client.post(f"/incidents/{incident_id}/cargo-safety-reviews", json=body)
    assert created.status_code == 201
    assert client.post(f"/cargo-safety-reviews/{created.json()['id']}/evaluate").status_code == 201

def test_invalid_container_is_422_and_unknown_review_is_404(client): ...
```

- [ ] **Step 2: Run and verify API tests fail because routes are absent**

Run: `uv run --extra dev pytest backend/tests/test_cargo_safety_api.py -v`

- [ ] **Step 3: Implement API models/routes and fixture**

Use `extra="forbid"` input models, translate known missing resources to 404 and
workflow conflicts to 409. The fixture holds `SYN-CNT-010`, a source, and exactly
the hero note; it does not encode any asserted cargo truth.

- [ ] **Step 4: Run API tests and OpenAPI sanity test**

Run: `uv run --extra dev pytest backend/tests/test_cargo_safety_api.py -v`

- [ ] **Step 5: Commit**

Run: `git add backend/app/main.py backend/tests/conftest.py backend/tests/test_cargo_safety_api.py shared/fixtures && git commit -m "feat: expose cargo safety review API"`

### Task 5: Add opt-in live smoke test and complete verification

**Files:**
- Create: `backend/tests/test_live_semantic_safety_smoke.py`
- Test: all cargo-safety and existing backend tests

**Interfaces:** The smoke test uses `RUN_LIVE_LLM_TESTS=1`, `OPENAI_API_KEY`, and
the environment-configured/default model; otherwise it skips.

- [ ] **Step 1: Write the opt-in smoke test**

```python
@pytest.mark.skipif(os.getenv("RUN_LIVE_LLM_TESTS") != "1", reason="opt-in live LLM test")
def test_live_hero_contradiction():
    assert checker.check(hero_input).result is SemanticCheckResult.CONTRADICTION_FOUND
```

- [ ] **Step 2: Verify normal pytest skips it without network**

Run: `uv run --extra dev pytest backend/tests/test_live_semantic_safety_smoke.py -v`

- [ ] **Step 3: Run targeted and full verification**

Run: `uv lock --check && uv run --extra dev pytest backend/tests/test_cargo_safety_contracts.py backend/tests/test_semantic_safety_adapter.py backend/tests/test_cargo_safety_repositories.py backend/tests/test_cargo_safety_workflow.py backend/tests/test_cargo_safety_api.py -v && uv run --extra dev pytest && git diff --check`

- [ ] **Step 4: Confirm scope and commit**

Run: `git diff --name-only origin/main...HEAD` and confirm no frontend files or
Phase 1–3 contract changes. Then `git add backend/tests/test_live_semantic_safety_smoke.py && git commit -m "test: add opt-in cargo semantic smoke test"`.
