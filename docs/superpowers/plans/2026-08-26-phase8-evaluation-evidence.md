# Phase 8 Deterministic Evaluation and Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one credential-free command that proves repository-supported Phase 1–7 claims, fails on verified-invariant drift, and generates a validated JSON evidence report plus a Markdown projection with a stable deterministic fingerprint.

**Architecture:** Add frozen evidence contracts, focused collectors that invoke existing evaluators/workflows, one reusable canonical evidence scenario result, a normalized fingerprint service, and a composite CLI. JSON remains the source of truth; Markdown is a pure projection. Existing scarcity, dynamic-yard, carrier, safety, agent, and replay business behavior remains untouched.

**Tech Stack:** Python 3.12, Pydantic 2, SQLModel/SQLite in-memory evaluation sessions, pytest, existing OR-Tools-backed scarcity workflow; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-26-phase8-evaluation-evidence-design.md`

## Global Constraints

- Implement only on `feat/phase8-evaluation-evidence`, based on frozen Phase 7 main `71716a0eee8413358dfc1e125a942945fc4be18c`.
- Python remains `>=3.12,<3.13`; use only packages already declared in `pyproject.toml`.
- Phase 8 must succeed without `OPENAI_API_KEY`, provider network calls, live-model tokens, live-model cost, or live-model latency.
- Do not modify scarcity optimization, scenario generation, dynamic-yard allocation, carrier state machines, approval validation, cargo-safety policy, agent runtime, canonical replay model/checker/projector, or frontend behavior.
- JSON is the machine-verifiable source of truth; Markdown is generated only from the validated JSON model.
- A failed `VERIFIED` invariant exits 1. `NOT_ESTABLISHED` and `DEFERRED` claims may coexist with exit 0. CLI/config/artifact failures exit 2.
- Exclude timestamps, runtime measurements, current source SHA, database UUIDs/sequences, and machine metadata from the deterministic fingerprint.
- Keep frozen holdout `runtime_ms` and `created_at` out of reproducibility comparisons.
- `live_model_token_usage`, `live_model_cost`, and `live_model_latency` must report `DEFERRED_TO_PHASE_9`, never numeric zero.
- `full_18_preserved_5_rolled_1_escalated` must remain `NOT_ESTABLISHED` unless complete durable evidence classifies all 24 containers into disjoint terminal outcomes and observes exactly 18/5/1.
- No frontend files are planned. A frontend change is scope expansion and requires approval before implementation.
- Do not add charts, screenshots, dashboards, deployment changes, deck/video material, business-impact dollars, or invented statistics.

## File structure and interfaces

### Production/evaluation files

| File | Responsibility and exported interface |
|---|---|
| `backend/app/domain/evidence.py` | `ClaimStatus`, `CoverageRole`, `EvidenceReference`, `ClaimReproducibility`, `EvidenceClaim`, `ProvenanceEntry`, `DeterministicRuntimeMetrics`, `EvidenceReportBody`, `Phase8EvidenceReport`, `EvidenceInvariantFailure`, `assert_verified()` |
| `backend/app/evaluation/evidence_scarcity.py` | `collect_scarcity_claims(repo_root: Path) -> tuple[EvidenceClaim, ...]` |
| `backend/app/evaluation/evidence_dynamic_yard.py` | `DynamicYardEvidenceResult`; `collect_dynamic_yard_claims(session: Session) -> DynamicYardEvidenceResult` |
| `backend/app/evaluation/evidence_authority.py` | `collect_authority_claims(session: Session) -> tuple[EvidenceClaim, ...]`; `collect_tradeoff_claims(session: Session) -> tuple[EvidenceClaim, ...]` |
| `backend/app/evaluation/evidence_safety_agent.py` | `CanonicalEvidenceRun`; `run_canonical_evidence_scenario(session: Session) -> CanonicalEvidenceRun`; `claims_from_canonical_run(result) -> tuple[EvidenceClaim, ...]` |
| `backend/app/evaluation/evidence_audit.py` | `REQUIRED_MATERIAL_COVERAGE`; `collect_audit_claims(result) -> tuple[EvidenceClaim, ...]`; `build_provenance_map(claims) -> tuple[ProvenanceEntry, ...]` |
| `backend/app/evaluation/evidence_runtime.py` | `nearest_rank_percentile()`; `measure_local_runtime(run_once, repetitions) -> DeterministicRuntimeMetrics`; `runtime_claims(metrics) -> tuple[EvidenceClaim, ...]` |
| `backend/app/evaluation/evidence_markdown.py` | `render_evidence_summary(report: Phase8EvidenceReport) -> str` |
| `backend/app/evaluation/evidence.py` | `normalized_evidence_payload()`; `evidence_fingerprint()`; `Phase8EvidenceService.run()`; `write_evidence_artifacts()`; `main()` |

### Tests and generated artifacts

| File | Responsibility |
|---|---|
| `backend/tests/test_evidence_contracts.py` | Contract/status/provenance validation. |
| `backend/tests/test_evidence_fingerprint.py` | Volatile-field exclusion and deterministic sensitivity. |
| `backend/tests/test_evidence_scarcity.py` | Frozen benchmark regeneration and drift failures. |
| `backend/tests/test_evidence_dynamic_yard.py` | R0/R1, latent worlds, commitments, compatibility, evidence-before-carrier. |
| `backend/tests/test_evidence_authority.py` | Request/counter, silence/timeout, immutable connection, forbidden tool inventory. |
| `backend/tests/test_evidence_tradeoff.py` | Human-only selection, fingerprint, commitments, Auto Replay halt. |
| `backend/tests/test_evidence_safety_agent.py` | Credential-free canonical run, safety, tool order/waits, rejection evidence. |
| `backend/tests/test_evidence_audit.py` | Material-action coverage and provenance failure. |
| `backend/tests/test_evidence_runtime.py` | Repetition/percentile/count reporting and timing exclusion. |
| `backend/tests/test_evidence_cli.py` | CLI exit semantics, validated output, atomic no-overwrite behavior. |
| `backend/tests/test_phase8_evidence_acceptance.py` | Complete registry, two-run fingerprint, committed artifact regeneration. |
| `docs/evaluations/phase8-evidence-report.json` | Generated machine source of truth. |
| `docs/evaluations/phase8-evidence-summary.md` | Generated human-readable projection. |
| `docs/coordination/logs/win-codex.md` | Final Phase 8 implementation record. |

---

### Task 1: Evidence contracts, registry rules, and fingerprint semantics

**Files:**
- Create: `backend/app/domain/evidence.py`
- Create: `backend/tests/test_evidence_contracts.py`
- Create: `backend/tests/test_evidence_fingerprint.py`

**Interfaces:**
- Produces: the exact contracts listed in the file map; every later task consumes them.
- Produces: `normalized_evidence_payload(body: EvidenceReportBody) -> dict[str, object]` and `evidence_fingerprint(body: EvidenceReportBody) -> str` initially in `backend/app/domain/evidence.py`; Task 8 re-exports them from the CLI module without changing signatures.

- [ ] **Step 1: Write failing contract-shape tests**

```python
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.domain.evidence import (
    ClaimStatus,
    CoverageRole,
    DeterministicRuntimeMetrics,
    EvidenceClaim,
    EvidenceReportBody,
    EvidenceReference,
    ProvenanceEntry,
    evidence_fingerprint,
    normalized_evidence_payload,
)


def ref(record_id: str | None = "runtime-uuid") -> EvidenceReference:
    return EvidenceReference(
        record_type="AgentHistory",
        stable_key="canonical-run:agent-history",
        source="AgentRuntimeRepository.history",
        record_id=record_id,
    )


def test_verified_claim_requires_observation_and_reference() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            claim_id="agent_terminal_state",
            statement="Canonical run terminates safely.",
            status=ClaimStatus.VERIFIED,
            observed_value=None,
            evidence_refs=(),
            caveat="Credential-free canonical replay only.",
        )


def test_deferred_claim_rejects_fabricated_numeric_value() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            claim_id="live_model_cost",
            statement="Live model cost is measured.",
            status=ClaimStatus.DEFERRED,
            observed_value=0,
            evidence_refs=(),
            caveat="DEFERRED_TO_PHASE_9",
        )
```

- [ ] **Step 2: Run the contract tests and verify RED**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_contracts.py -q
```

Expected: collection fails because `backend.app.domain.evidence` does not exist.

- [ ] **Step 3: Implement frozen contracts and invariant failure helper**

Implement these exact public shapes:

```python
class ClaimStatus(StrEnum):
    VERIFIED = "VERIFIED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    DEFERRED = "DEFERRED"


class CoverageRole(StrEnum):
    PRIMARY_RECORD = "PRIMARY_RECORD"
    TYPED_HISTORY = "TYPED_HISTORY"
    AUDIT_EVENT = "AUDIT_EVENT"
    FROZEN_ARTIFACT = "FROZEN_ARTIFACT"


class EvidenceReference(FrozenContract):
    record_type: str = Field(min_length=1)
    stable_key: str = Field(min_length=1)
    source: str = Field(min_length=1)
    record_id: str | None = None


class ClaimReproducibility(FrozenContract):
    deterministic: bool
    included_in_fingerprint: bool
    fixture_ids: tuple[str, ...] = ()
    seed_manifest_id: str | None = None
    benchmark_reproducibility_key: str | None = None


class EvidenceClaim(FrozenContract):
    claim_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    statement: str = Field(min_length=1)
    status: ClaimStatus
    observed_value: JsonValue | None
    evidence_refs: tuple[EvidenceReference, ...] = ()
    caveat: str = Field(min_length=1)
    reproducibility: ClaimReproducibility | None = None


class ProvenanceEntry(FrozenContract):
    claim_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    record_type: str = Field(min_length=1)
    stable_key: str = Field(min_length=1)
    source: str = Field(min_length=1)
    record_id: str | None = None
    coverage_role: CoverageRole


class DeterministicRuntimeMetrics(FrozenContract):
    repetitions: int = Field(ge=1)
    run_durations_ms: tuple[float, ...]
    canonical_run_wall_clock_ms: float = Field(ge=0)
    p50_local_runtime_ms: float = Field(ge=0)
    p95_local_runtime_ms: float = Field(ge=0)
    step_count: int = Field(ge=0)
    successful_tool_call_count: int = Field(ge=0)
    label: Literal["LOCAL_MACHINE_DEPENDENT"] = "LOCAL_MACHINE_DEPENDENT"
    production_sla_claimed: Literal[False] = False
    python_version: str = Field(min_length=1)
    platform: str = Field(min_length=1)


class EvidenceReportBody(FrozenContract):
    schema_version: Literal["phase8-evidence-v1"] = "phase8-evidence-v1"
    suite_id: Literal["phase8-deterministic-evidence"] = "phase8-deterministic-evidence"
    evaluation_base_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    generated_at: AwareDatetime
    command: str = Field(min_length=1)
    cli_version: str = Field(min_length=1)
    fixture_ids: tuple[str, ...]
    seed_manifest_id: str
    canonical_model_identity: str
    canonical_checker_identity: str
    claims: tuple[EvidenceClaim, ...]
    provenance: tuple[ProvenanceEntry, ...]
    runtime: DeterministicRuntimeMetrics


class Phase8EvidenceReport(EvidenceReportBody):
    deterministic_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    def body(self) -> EvidenceReportBody:
        return EvidenceReportBody.model_validate(
            self.model_dump(exclude={"deterministic_fingerprint"})
        )


class EvidenceInvariantFailure(RuntimeError):
    def __init__(self, claim_id: str, detail: str) -> None:
        super().__init__(f"{claim_id}: {detail}")
        self.claim_id = claim_id


def assert_verified(condition: bool, claim_id: str, detail: str) -> None:
    if not condition:
        raise EvidenceInvariantFailure(claim_id, detail)
```

Add model validators for the status rules, duplicate references, runtime duration count matching `repetitions`, unique report claim IDs, and claim/provenance consistency.

- [ ] **Step 4: Write failing fingerprint normalization tests**

Add this complete helper above the fingerprint tests:

```python
def make_report_body(
    *,
    source_revision: str = "a" * 40,
    generated_at: datetime = datetime(2026, 8, 26, tzinfo=UTC),
    record_id: str = "11111111-1111-4111-8111-111111111111",
    local_runtime_ms: float = 10.0,
    observed_value: object = None,
) -> EvidenceReportBody:
    value = {"step_count": 6} if observed_value is None else observed_value
    reference = ref(record_id)
    claim = EvidenceClaim(
        claim_id="agent_step_count",
        statement="Canonical run has the exact deterministic step count.",
        status=ClaimStatus.VERIFIED,
        observed_value=value,
        evidence_refs=(reference,),
        caveat="Credential-free canonical replay only.",
    )
    provenance = ProvenanceEntry(
        claim_id=claim.claim_id,
        record_type=reference.record_type,
        stable_key=reference.stable_key,
        source=reference.source,
        record_id=reference.record_id,
        coverage_role=CoverageRole.TYPED_HISTORY,
    )
    runtime = DeterministicRuntimeMetrics(
        repetitions=1,
        run_durations_ms=(local_runtime_ms,),
        canonical_run_wall_clock_ms=local_runtime_ms,
        p50_local_runtime_ms=local_runtime_ms,
        p95_local_runtime_ms=local_runtime_ms,
        step_count=6,
        successful_tool_call_count=5,
        python_version="3.12-test",
        platform="test-platform",
    )
    return EvidenceReportBody(
        evaluation_base_sha="71716a0eee8413358dfc1e125a942945fc4be18c",
        source_revision=source_revision,
        generated_at=generated_at,
        command="python -m backend.app.evaluation.evidence",
        cli_version="phase8-evidence-v1",
        fixture_ids=("SYN-CANONICAL-24-V1",),
        seed_manifest_id="SYN-CANONICAL-24-HOLDOUT-V1",
        canonical_model_identity="canonical-replay-agent-v1",
        canonical_checker_identity="canonical-replay-deterministic",
        claims=(claim,),
        provenance=(provenance,),
        runtime=runtime,
    )


def test_fingerprint_ignores_runtime_ids_timestamps_source_sha_and_timings() -> None:
    first = make_report_body(
        source_revision="a" * 40,
        generated_at=datetime(2026, 8, 26, tzinfo=UTC),
        record_id="11111111-1111-4111-8111-111111111111",
        local_runtime_ms=10.0,
    )
    second = make_report_body(
        source_revision="b" * 40,
        generated_at=datetime(2026, 8, 27, tzinfo=UTC),
        record_id="22222222-2222-4222-8222-222222222222",
        local_runtime_ms=999.0,
    )
    assert normalized_evidence_payload(first) == normalized_evidence_payload(second)
    assert evidence_fingerprint(first) == evidence_fingerprint(second)


def test_fingerprint_changes_when_deterministic_observation_changes() -> None:
    first = make_report_body(observed_value={"step_count": 6})
    second = make_report_body(observed_value={"step_count": 7})
    assert evidence_fingerprint(first) != evidence_fingerprint(second)
```

- [ ] **Step 5: Implement canonical JSON normalization and SHA-256**

Use one function that sorts claims by `claim_id`, reduces each reference to `record_type`, `stable_key`, and `source`, excludes the runtime section except `step_count`/`successful_tool_call_count`, and omits a claim's volatile `observed_value` whenever `claim.reproducibility.included_in_fingerprint` is false. The runtime claim remains in the normalized registry by ID/status/statement/caveat, but its duration values do not. Serialize with:

```python
encoded = json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
return hashlib.sha256(encoded).hexdigest()
```

- [ ] **Step 6: Run focused tests and commit**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_contracts.py backend/tests/test_evidence_fingerprint.py -q
git diff --check
```

Expected: all focused tests pass and diff check exits 0.

Commit:

```powershell
git add backend/app/domain/evidence.py backend/tests/test_evidence_contracts.py backend/tests/test_evidence_fingerprint.py
git commit -m "feat: add phase 8 evidence contracts and fingerprint semantics"
```

---

### Task 2: Frozen scarcity holdout verification adapter

**Files:**
- Create: `backend/app/evaluation/evidence_scarcity.py`
- Create: `backend/tests/test_evidence_scarcity.py`

**Interfaces:**
- Consumes: `EvidenceClaim`, `EvidenceReference`, `ClaimReproducibility`, `assert_verified`.
- Consumes unchanged: `ScarcityComparisonService`, `HoldoutBenchmarkService`, `load_evaluation_seed_manifest`, `ScarcityBenchmarkReport`.
- Produces: `collect_scarcity_claims(repo_root: Path) -> tuple[EvidenceClaim, ...]`.

- [ ] **Step 1: Write the real frozen-regeneration test**

```python
def test_scarcity_collector_regenerates_exact_frozen_evidence() -> None:
    claims = {claim.claim_id: claim for claim in collect_scarcity_claims(REPO_ROOT)}
    assert claims["scarcity_holdout_world_count"].observed_value == {
        "seed_count": 50,
        "worlds_per_seed": 50,
        "world_count": 2500,
    }
    assert claims["scarcity_expected_preserved_delta"].observed_value == {
        "baseline_expected_preserved": 12.0136,
        "scenario_aware_expected_preserved": 12.5088,
        "delta": 0.49520000000000053,
        "relative_improvement_percent": pytest.approx(4.12199507225145),
    }
    assert claims["scarcity_reproducibility_key"].observed_value == (
        "d0dc76fb9239f4f77320f4b0a0fd5572d0b9a86a80da0448892d5336f205fe21"
    )
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_scarcity.py -q
```

Expected: collection fails because the collector module does not exist.

- [ ] **Step 3: Implement the thin holdout adapter**

Implement `collect_scarcity_claims()` with the existing service sequence:

```python
fixture = SyntheticCanonicalIncidentService().load()
development_scenarios = SeededScenarioGenerator().generate(
    fixture,
    seed=20260822,
    world_count=50,
)
development = ScarcityComparisonService().compare(
    incident_id=UUID("00000000-0000-4000-8000-000000000000"),
    fixture=fixture,
    scenarios=development_scenarios,
)
manifest = load_evaluation_seed_manifest()
regenerated = HoldoutBenchmarkService().evaluate(fixture, development, manifest)
committed = ScarcityBenchmarkReport.model_validate_json(
    (repo_root / "docs/evaluations/2026-08-22-scarcity-benchmark.json").read_text(encoding="utf-8")
)
```

Normalize both reports with `model_dump(mode="json", exclude={"created_at", "baseline": {"runtime_ms"}, "scenario_aware": {"__all__": {"evaluation": {"runtime_ms"}}}})` and assert equality. Assert every frozen value separately so failure messages identify the regressed claim.

- [ ] **Step 4: Add drift and runtime-exclusion tests**

Monkeypatch the committed report's key and deterministic total separately and assert `EvidenceInvariantFailure`. Change only `runtime_ms`/`created_at` and assert claims remain identical.

- [ ] **Step 5: Run focused and existing benchmark suites, then commit**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_scarcity.py backend/tests/test_scarcity_benchmark.py backend/tests/test_scarcity_evaluation.py -q
git diff --check
```

Commit:

```powershell
git add backend/app/evaluation/evidence_scarcity.py backend/tests/test_evidence_scarcity.py
git commit -m "feat: verify frozen scarcity holdout evidence"
```

---

### Task 3: Dynamic-yard and reconsideration evidence adapter

**Files:**
- Create: `backend/app/evaluation/evidence_dynamic_yard.py`
- Create: `backend/tests/test_evidence_dynamic_yard.py`

**Interfaces:**
- Consumes unchanged: `build_scarce_capacity_workflow`, `DynamicYardWorkflow`, `CanonicalDynamicYardHarness`, `reconstruct_phase2_worlds`, `AgentRuntimeCoordinator` guards.
- Produces:

```python
class DynamicYardEvidenceResult(FrozenContract):
    incident_id: UUID
    phase2_report: ScarcityEvaluationReport
    history: AllocationTradeoffHistory
    claims: tuple[EvidenceClaim, ...]
```

- [ ] **Step 1: Write exact R0/R1 and latent-world tests**

```python
def test_dynamic_collector_proves_exact_canonical_reconsideration(session) -> None:
    result = collect_dynamic_yard_claims(session)
    claims = {claim.claim_id: claim for claim in result.claims}
    assert claims["dynamic_reconsideration_r0_r1"].observed_value == {
        "r0": ["SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-005", "SYN-CNT-010", "SYN-CNT-011", "SYN-CNT-012", "SYN-CNT-014", "SYN-CNT-015"],
        "r1": ["SYN-CNT-001", "SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-010", "SYN-CNT-011", "SYN-CNT-012", "SYN-CNT-014", "SYN-CNT-015"],
        "cancelled": ["SYN-CNT-005"],
        "planned": ["SYN-CNT-001"],
        "committed": ["SYN-CNT-002", "SYN-CNT-004"],
    }
    assert claims["dynamic_preserved_total_change"].observed_value == {"before": 601, "after": 602}
    assert claims["dynamic_expected_preserved_change"].observed_value == {"before": 12.02, "after": 12.04}
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_dynamic_yard.py -q
```

- [ ] **Step 3: Implement the canonical dynamic collector using real workflows**

Call `build_scarce_capacity_workflow(session).run()`, `yard.initialize()`, `yard.ingest()`, and `yard.apply_latest_assessment()`. Read all facts back through `yard.history()`. Use `reconstruct_phase2_worlds(phase2.report, fixture)` and assert the reconstructed seed/world count/key without duplicating latent math.

```python
phase2 = build_scarce_capacity_workflow(session).run()
yard = DynamicYardWorkflow.for_session(session)
harness = CanonicalDynamicYardHarness()
yard.initialize(phase2.incident.id, harness.bootstrap_snapshot(phase2.incident.id))
assessment = yard.ingest(harness.discharge_active_snapshot(phase2.incident.id))
assert_verified(assessment is not None, "dynamic_reconsideration_r0_r1", "active evidence produced no assessment")
yard.apply_latest_assessment(phase2.incident.id)
history = yard.history(phase2.incident.id)
fixture = SyntheticCanonicalIncidentService().load()
worlds = reconstruct_phase2_worlds(phase2.report, fixture)
assert_verified(worlds.assumptions.seed == phase2.report.seed, "dynamic_phase2_worlds_reconstructed", "seed drift")
assert_verified(len(worlds.worlds) == phase2.report.scenario_count, "dynamic_phase2_worlds_reconstructed", "world-count drift")
```

- [ ] **Step 4: Add isolated negative probes**

Create one test that tampers an isolated persisted active revision/forecast and asserts `phase3_compatible()` is false and `prepare_rta_request` cannot create a case. Create another unhandled assessment and invoke an exposed carrier mutation through `AgentRuntimeCoordinator`; assert the existing `material dynamic-yard reconsideration must be handled before carrier mutation` error and unchanged case/request counts.

```python
before_cases = tuple(CarrierRecoveryRepository(session).list_cases(incident_id))
rejected = runtime._execute_turn(
    run,
    "prepare_rta_request",
    {"connection_id": "SYN-CONN-JV2"},
)
invocation = runtime._repository.history(run.id).tool_invocations[-1]
assert invocation.status is AgentToolInvocationStatus.REJECTED
assert invocation.error_kind == "ValueError"
assert rejected.step_count == 1
assert tuple(CarrierRecoveryRepository(session).list_cases(incident_id)) == before_cases
```

- [ ] **Step 5: Run focused dynamic suites and commit**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_dynamic_yard.py backend/tests/test_dynamic_yard_canonical_hero.py backend/tests/test_dynamic_yard_phase3_compatibility.py backend/tests/test_dynamic_yard_workflow.py -q
git diff --check
```

Commit:

```powershell
git add backend/app/evaluation/evidence_dynamic_yard.py backend/tests/test_evidence_dynamic_yard.py
git commit -m "feat: collect deterministic dynamic yard evidence"
```

---

### Task 4: Authority and human-tradeoff invariant evaluation

**Files:**
- Create: `backend/app/evaluation/evidence_authority.py`
- Create: `backend/tests/test_evidence_authority.py`
- Create: `backend/tests/test_evidence_tradeoff.py`

**Interfaces:**
- Produces: `collect_authority_claims(session)` and `collect_tradeoff_claims(session)`.
- Consumes unchanged: carrier workflow/history, simulator plans, `AgentToolRegistry`, dynamic tradeoff workflow/repository, canonical projector.

- [ ] **Step 1: Write request/counter negative authority tests**

```python
def test_authority_collector_proves_exact_approval_boundaries(session) -> None:
    claims = {claim.claim_id: claim for claim in collect_authority_claims(session)}
    assert claims["authority_request_approval_required"].observed_value["unapproved_send_rejected"] is True
    assert claims["authority_request_fingerprint_bound"].observed_value["wrong_fingerprint_persisted_approvals"] == 0
    assert claims["authority_counter_approval_required"].observed_value["effective_timings_before_approval"] == 0
    assert claims["authority_counter_fingerprint_bound"].observed_value["wrong_fingerprint_effective_timings"] == 0
```

- [ ] **Step 2: Write silence, timeout, schedule, and registry tests**

Assert `SILENT-RUN` yields no `CarrierResponse`; timeout reaches `COMPLETED` or `ESCALATED`; fixture connection `model_dump(mode="json")` is identical before/after; and the union of captured registry tool names is disjoint from:

```python
FORBIDDEN_AUTHORITY_TOOLS = {
    "hold_feeder",
    "change_carrier_schedule",
    "override_dg_rule",
    "set_yard_capacity",
}
```

- [ ] **Step 3: Run authority tests and verify RED**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_authority.py -q
```

- [ ] **Step 4: Implement authority probes with before/after durable counts**

Each rejected action must capture the expected `CarrierRecoveryConflict` and assert unchanged relevant history lengths before returning a `VERIFIED` claim. Do not catch unexpected exceptions. Use runtime registry inventories as the primary forbidden-tool evidence; retain source scanning only in the existing Phase 3 regression test.

```python
before = workflow.history(case.id)
wrong = RequestApprovalCommand(
    case_id=case.id,
    proposal_decision_id=binding.proposal_decision_id,
    request_id=binding.subject_id,
    expected_payload_fingerprint="wrong-fingerprint",
    operator_id="operator-console",
    status=ApprovalStatus.APPROVED,
)
with pytest.raises(CarrierRecoveryConflict):
    workflow.record_request_approval(wrong)
after = workflow.history(case.id)
assert len(after.approvals) == len(before.approvals) == 0
assert after.request == before.request
```

- [ ] **Step 5: Write and implement tradeoff evidence tests**

Use the existing deterministic `HUMAN_REVIEW_REQUIRED` setup to assert an OPEN review, no model calls before exact selection, no selection tool in the registry, stale fingerprint rejection without mutation, committed slots retained, and:

```python
view = project_canonical_replay_stage(session, incident_id)
assert view.stage is CanonicalReplayStage.TRADEOFF_DECISION_REQUIRED
assert view.next_allowed_action is CanonicalReplayActionType.SELECT_TRADEOFF_OPTION
assert view.auto_replay_may_execute is False
assert view.requires_human_authority is True
```

- [ ] **Step 6: Run focused authority/tradeoff regressions and commit**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_authority.py backend/tests/test_evidence_tradeoff.py backend/tests/test_carrier_recovery_authority.py backend/tests/test_carrier_recovery_workflow.py backend/tests/test_carrier_recovery_recomputation.py backend/tests/test_dynamic_yard_tradeoff_selection.py backend/tests/test_dynamic_yard_agent_runtime.py -q
git diff --check
```

Commit:

```powershell
git add backend/app/evaluation/evidence_authority.py backend/tests/test_evidence_authority.py backend/tests/test_evidence_tradeoff.py
git commit -m "feat: evaluate authority and human tradeoff invariants"
```

---

### Task 5: Safety and agent/tool invariant evaluation

**Files:**
- Create: `backend/app/evaluation/evidence_safety_agent.py`
- Create: `backend/tests/test_evidence_safety_agent.py`

**Interfaces:**
- Produces `CanonicalEvidenceRun`, the one reusable successful scenario result consumed by Tasks 6–10.
- Produces `run_canonical_evidence_scenario(session)` and `claims_from_canonical_run(result)`.

Define the result contract with exact durable aggregates:

```python
class CanonicalEvidenceRun(FrozenContract):
    incident_id: UUID
    agent_run: AgentRun
    agent_history: AgentHistory
    dynamic_history: AllocationTradeoffHistory
    carrier_history: CarrierRecoveryHistory
    safety_history: CargoSafetyHistory
    stage_names: tuple[str, ...]
    wait_kinds: tuple[str, ...]
    registry_inventories: tuple[tuple[str, ...], ...]
    approval_operator_ids: tuple[str, ...]
```

- [ ] **Step 1: Write the full canonical result test**

```python
def test_canonical_evidence_run_is_credential_free_and_exact(session, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_canonical_evidence_scenario(session)
    assert result.agent_run.state is AgentRunState.ESCALATED
    assert result.agent_run.escalation_reason is AgentEscalationReason.SAFETY_REVIEW_REQUIRED
    assert result.agent_run.step_count == 6
    assert [item.tool_name for item in result.agent_history.tool_invocations] == [
        "pause_agent_run",
        "request_expedite_feasibility",
        "prepare_rta_request",
        "send_authorised_rta_request",
        "request_cargo_safety_review",
    ]
    assert result.safety_history.assessment.result is SemanticCheckResult.CONTRADICTION_FOUND
    assert result.safety_history.policy_result.automation_blocked is True
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_safety_agent.py -q
```

- [ ] **Step 3: Implement one canonical driver over existing public workflows**

Follow the Phase 7 sequence through existing methods only: scarcity run; PRE_DISCHARGE initialize; canonical run create/advance; DISCHARGE_ACTIVE ingest; reconsider; prepare; exact request approval; send; COUNTER simulation; expected counter wait-upgrade conflict; exact counter approval; persist `SYN-CNT-010` review; final advance. Call `project_canonical_replay_stage()` between mutations and capture names. Capture the registry inventory before every model turn. Do not call `_execute_turn()` directly.

```python
phase2 = build_scarce_capacity_workflow(session).run()
yard = DynamicYardWorkflow.for_session(session)
harness = CanonicalDynamicYardHarness()
yard.initialize(phase2.incident.id, harness.bootstrap_snapshot(phase2.incident.id))
configuration = CanonicalAgentRuntimeConfiguration.load()
runtime = AgentRuntimeCoordinator(
    session=session,
    model=CanonicalReplayAgentModel(),
    clock=configuration.clock("before_deadline"),
    configuration=configuration,
    cargo_safety_checker=CanonicalReplaySemanticChecker(),
)
run = runtime.create_run(phase2.incident.id)
runtime.advance(run.id)
yard.ingest(harness.discharge_active_snapshot(phase2.incident.id))
runtime.advance(run.id)
prepared = runtime.advance(run.id)
case_id = UUID(prepared.wait_subject_id)
carrier = build_carrier_recovery_workflow(session)
request_binding = carrier.history(case_id).bindings[0]
carrier.record_request_approval(exact_request_approval(case_id, request_binding, "operator-console"))
runtime.advance(run.id)
carrier.simulate_response(SimulateCarrierResponseCommand(case_id=case_id, effective_at=CANONICAL_COUNTER_EFFECTIVE_AT))
try:
    runtime.advance(run.id)
except AgentRuntimeConflict:
    pass
else:
    raise EvidenceInvariantFailure("agent_wait_kinds", "COUNTER did not produce the expected wait-upgrade conflict")
counter_binding = carrier.history(case_id).bindings[-1]
carrier.record_counter_approval(exact_counter_approval(case_id, counter_binding, "operator-console"))
safety = CargoSafetyWorkflow.for_session(session, checker=CanonicalReplaySemanticChecker())
safety.create_review(phase2.incident.id, CANONICAL_SAFETY_CONTAINER_ID, CANONICAL_SAFETY_NOTE_TEXT, CANONICAL_SAFETY_NOTE_SOURCE)
terminal = runtime.advance(run.id)
```

Implement `exact_request_approval()` and `exact_counter_approval()` in this module as small constructors that copy IDs/fingerprints only from the supplied persisted binding/history; they must accept no caller-supplied fingerprint.

```python
def exact_request_approval(
    case_id: UUID,
    binding: ApprovalBinding,
    operator_id: str,
) -> RequestApprovalCommand:
    return RequestApprovalCommand(
        case_id=case_id,
        proposal_decision_id=binding.proposal_decision_id,
        request_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id=operator_id,
        status=ApprovalStatus.APPROVED,
    )


def exact_counter_approval(
    case_id: UUID,
    binding: ApprovalBinding,
    operator_id: str,
) -> CounterApprovalCommand:
    return CounterApprovalCommand(
        case_id=case_id,
        proposal_decision_id=binding.proposal_decision_id,
        carrier_response_id=binding.subject_id,
        expected_payload_fingerprint=binding.payload_fingerprint,
        operator_id=operator_id,
        status=ApprovalStatus.APPROVED,
    )
```

- [ ] **Step 4: Add safety-policy and unavailable-tool negative tests**

Assert checker output keys are exactly `result`, `explanation`, `evidence_excerpt`; fake checker failure persists `CHECK_FAILED` and `automation_blocked = true`; pending safety outranks other automation; and a fake model selecting `hold_feeder` creates no invocation with that name and escalates `INVALID_MODEL_OUTPUT`.

- [ ] **Step 5: Build claims from durable histories**

Map the result to safety and agent claims. Set `agent_step_count` to 6, `deterministic_tool_call_count` to 5, exact waits to `NEW_OPERATIONAL_EVIDENCE`, `REQUEST_APPROVAL`, `CARRIER_RESPONSE_OR_TIMEOUT`, `COUNTER_APPROVAL`, and approval identities to `operator-console`. Add the auto-shaped synthetic identity as a separate authority probe, not as an agent action.

```python
CANONICAL_TOOL_ORDER = (
    "pause_agent_run",
    "request_expedite_feasibility",
    "prepare_rta_request",
    "send_authorised_rta_request",
    "request_cargo_safety_review",
)

tool_order = tuple(invocation.tool_name for invocation in result.agent_history.tool_invocations)
assert_verified(tool_order == CANONICAL_TOOL_ORDER, "agent_successful_tool_order", f"observed {tool_order}")
assert_verified(result.agent_run.step_count == 6, "agent_step_count", f"observed {result.agent_run.step_count}")
assert_verified(
    result.safety_history.policy_result.automation_blocked is True,
    "safety_automation_blocked",
    "canonical safety policy did not block automation",
)
```

- [ ] **Step 6: Run focused canonical regressions and commit**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_safety_agent.py backend/tests/test_canonical_replay_hero_api.py backend/tests/test_canonical_replay_agent_model.py backend/tests/test_canonical_replay_semantic_checker.py backend/tests/test_agent_runtime_workflow.py backend/tests/test_cargo_safety_workflow.py -q
git diff --check
```

Commit:

```powershell
git add backend/app/evaluation/evidence_safety_agent.py backend/tests/test_evidence_safety_agent.py
git commit -m "feat: collect safety and agent orchestration evidence"
```

---

### Task 6: Audit coverage and provenance extraction

**Files:**
- Create: `backend/app/evaluation/evidence_audit.py`
- Create: `backend/tests/test_evidence_audit.py`

**Interfaces:**
- Consumes: `CanonicalEvidenceRun` and all collected `EvidenceClaim` values.
- Produces: `collect_audit_claims(result)` and `build_provenance_map(claims)`.

- [ ] **Step 1: Write complete-coverage and missing-coverage tests**

```python
def test_material_action_coverage_is_complete(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)
    claims = {claim.claim_id: claim for claim in collect_audit_claims(canonical_evidence_run)}
    observed = claims["audit_material_action_coverage"].observed_value
    assert observed["required_categories"] == 8
    assert observed["covered_categories"] == 8
    assert observed["missing_categories"] == []


def test_missing_agent_invocation_history_fails_verified_coverage(session) -> None:
    canonical_evidence_run = run_canonical_evidence_scenario(session)
    broken = canonical_evidence_run.model_copy(
        update={"agent_history": canonical_evidence_run.agent_history.model_copy(update={"tool_invocations": ()})}
    )
    with pytest.raises(EvidenceInvariantFailure, match="agent_orchestration"):
        collect_audit_claims(broken)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_audit.py -q
```

- [ ] **Step 3: Implement the eight-category coverage matrix**

Use exact keys:

```python
REQUIRED_MATERIAL_COVERAGE = (
    "incident_recovery_decisions",
    "allocation_reconsideration",
    "allocation_supersession_tradeoff",
    "operator_approvals",
    "carrier_response_timeout",
    "carrier_recovery_replacement",
    "safety_escalation",
    "agent_orchestration",
)
```

Each checker must require the primary records and the linked audit/typed history specified in spec §12. `AgentStep` plus `AgentToolInvocation` satisfies agent orchestration without fabricating an `AuditEvent`.

- [ ] **Step 4: Implement provenance flattening and validation**

`build_provenance_map()` sorts by `(claim_id, record_type, stable_key, source)`, maps coverage roles, preserves runtime `record_id`, and asserts every non-deferred claim reference appears in the map. Deferred claims produce no fake provenance row.

```python
def coverage_role_for(record_type: str) -> CoverageRole:
    if record_type == "AuditEvent":
        return CoverageRole.AUDIT_EVENT
    if record_type.endswith("History"):
        return CoverageRole.TYPED_HISTORY
    if record_type in {"ScarcityBenchmarkReport", "EvaluationSeedManifest"}:
        return CoverageRole.FROZEN_ARTIFACT
    return CoverageRole.PRIMARY_RECORD


def build_provenance_map(claims: Sequence[EvidenceClaim]) -> tuple[ProvenanceEntry, ...]:
    rows = [
        ProvenanceEntry(
            claim_id=claim.claim_id,
            record_type=reference.record_type,
            stable_key=reference.stable_key,
            source=reference.source,
            record_id=reference.record_id,
            coverage_role=coverage_role_for(reference.record_type),
        )
        for claim in claims
        if claim.status is not ClaimStatus.DEFERRED
        for reference in claim.evidence_refs
    ]
    return tuple(sorted(rows, key=lambda row: (row.claim_id, row.record_type, row.stable_key, row.source)))
```

- [ ] **Step 5: Run audit/storage regressions and commit**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_audit.py backend/tests/test_audit.py backend/tests/test_agent_runtime_repositories.py backend/tests/test_dynamic_yard_repositories.py backend/tests/test_carrier_recovery_repositories.py backend/tests/test_cargo_safety_contracts.py backend/tests/test_cargo_safety_api.py -q
git diff --check
```

Commit:

```powershell
git add backend/app/evaluation/evidence_audit.py backend/tests/test_evidence_audit.py
git commit -m "feat: enforce material audit and provenance coverage"
```

---

### Task 7: Deterministic runtime and resource measurement

**Files:**
- Create: `backend/app/evaluation/evidence_runtime.py`
- Create: `backend/tests/test_evidence_runtime.py`

**Interfaces:**
- Produces `nearest_rank_percentile(values: Sequence[float], percentile: float) -> float`.
- Produces `measure_local_runtime(run_once: Callable[[], CanonicalEvidenceRun], repetitions: int) -> DeterministicRuntimeMetrics`.

- [ ] **Step 1: Write percentile, repetition, and label tests**

```python
def test_nearest_rank_p95_is_exact() -> None:
    values = [float(value) for value in range(1, 21)]
    assert nearest_rank_percentile(values, 0.50) == 10.0
    assert nearest_rank_percentile(values, 0.95) == 19.0


def test_runtime_measurement_reports_counts_and_machine_dependent_label(monkeypatch) -> None:
    from types import SimpleNamespace

    fake_result = SimpleNamespace(
        agent_run=SimpleNamespace(step_count=6),
        agent_history=SimpleNamespace(tool_invocations=(1, 2, 3, 4, 5)),
    )

    def fake_run_once():
        return fake_result

    clock = iter([0, 10_000_000, 10_000_000, 30_000_000])
    monkeypatch.setattr("backend.app.evaluation.evidence_runtime.perf_counter_ns", lambda: next(clock))
    metrics = measure_local_runtime(fake_run_once, repetitions=2)
    assert metrics.repetitions == 2
    assert metrics.run_durations_ms == (10.0, 20.0)
    assert metrics.step_count == 6
    assert metrics.successful_tool_call_count == 5
    assert metrics.label == "LOCAL_MACHINE_DEPENDENT"
    assert metrics.production_sla_claimed is False
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_runtime.py -q
```

- [ ] **Step 3: Implement validation and measurement**

Reject `repetitions < 1` and percentile values outside `(0, 1]`. Time each complete isolated canonical evaluation run, calculate median p50 and nearest-rank p95, assert all repeated runs retain step count 6/tool count 5, and keep durations out of claim reproducibility metadata.

```python
def nearest_rank_percentile(values: Sequence[float], percentile: float) -> float:
    if not values or not 0 < percentile <= 1:
        raise ValueError("percentile requires values and a percentile in (0, 1]")
    ordered = sorted(values)
    return ordered[ceil(percentile * len(ordered)) - 1]


def runtime_claims(metrics: DeterministicRuntimeMetrics) -> tuple[EvidenceClaim, ...]:
    reference = EvidenceReference(
        record_type="DeterministicRuntimeMetrics",
        stable_key="phase8-runtime:canonical-replay",
        source="backend.app.evaluation.evidence_runtime.measure_local_runtime",
    )
    return (
        EvidenceClaim(
            claim_id="deterministic_tool_call_count",
            statement="Canonical run used the exact deterministic tool-call count.",
            status=ClaimStatus.VERIFIED,
            observed_value=metrics.successful_tool_call_count,
            evidence_refs=(reference,),
            caveat="Credential-free canonical replay only.",
            reproducibility=ClaimReproducibility(
                deterministic=True,
                included_in_fingerprint=True,
            ),
        ),
        EvidenceClaim(
            claim_id="deterministic_local_runtime",
            statement="Local deterministic canonical runtime was measured.",
            status=ClaimStatus.VERIFIED,
            observed_value=metrics.model_dump(mode="json"),
            evidence_refs=(reference,),
            caveat="LOCAL_MACHINE_DEPENDENT; not a production SLA.",
            reproducibility=ClaimReproducibility(
                deterministic=False,
                included_in_fingerprint=False,
            ),
        ),
    )
```

- [ ] **Step 4: Add fingerprint-exclusion integration test**

Build two otherwise identical report bodies with different duration arrays, p50/p95, platform, and interpreter metadata; assert identical normalized payloads and fingerprints while the serialized runtime sections differ.

- [ ] **Step 5: Run focused tests and commit**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_runtime.py backend/tests/test_evidence_fingerprint.py -q
git diff --check
```

Commit:

```powershell
git add backend/app/evaluation/evidence_runtime.py backend/tests/test_evidence_runtime.py
git commit -m "feat: measure local deterministic evidence runtime"
```

---

### Task 8: Composite Phase 8 runner and CLI

**Files:**
- Create: `backend/app/evaluation/evidence.py`
- Create: `backend/app/evaluation/evidence_markdown.py`
- Create: `backend/tests/test_evidence_cli.py`

**Interfaces:**
- Re-exports `normalized_evidence_payload` and `evidence_fingerprint` from Task 1.
- Produces `Phase8EvidenceService(repo_root: Path).run(runtime_repetitions: int = 20) -> Phase8EvidenceReport`.
- Produces `render_evidence_summary(report: Phase8EvidenceReport) -> str`.
- Produces `write_evidence_artifacts(report, json_path, markdown_path)` and module `main()`.

- [ ] **Step 1: Write the complete-service registry test**

```python
EXPECTED_CLAIM_IDS = {
    "scarcity_holdout_world_count",
    "scarcity_scenario_aware_beats_p50",
    "scarcity_expected_preserved_delta",
    "scarcity_expedite_slot_cap",
    "scarcity_zero_capacity_violations",
    "scarcity_zero_unsafe_allocations",
    "scarcity_reproducibility_key",
    "dynamic_reconsideration_r0_r1",
    "dynamic_preserved_total_change",
    "dynamic_expected_preserved_change",
    "dynamic_committed_allocations_immutable",
    "dynamic_phase2_worlds_reconstructed",
    "dynamic_phase3_incompatible_plan_blocked",
    "dynamic_evidence_precedes_carrier_mutation",
    "authority_request_approval_required",
    "authority_request_fingerprint_bound",
    "authority_counter_approval_required",
    "authority_counter_fingerprint_bound",
    "authority_carrier_silence_is_absence",
    "authority_timeout_recomputes",
    "authority_no_carrier_schedule_mutation",
    "authority_no_forbidden_tools",
    "authority_no_agent_approval",
    "human_tradeoff_boundary",
    "human_tradeoff_agent_cannot_select",
    "human_tradeoff_fingerprint_bound",
    "human_tradeoff_committed_slots_immutable",
    "human_tradeoff_auto_replay_halts",
    "safety_canonical_contradiction",
    "safety_automation_blocked",
    "safety_terminal_escalation",
    "safety_checker_scope_limited",
    "safety_policy_owns_disposition",
    "safety_checker_failure_fails_closed",
    "safety_pending_review_blocks_bypass",
    "agent_terminal_state",
    "agent_step_count",
    "agent_successful_tool_order",
    "agent_wait_kinds",
    "agent_approval_identities",
    "agent_no_unavailable_tool_execution",
    "agent_zero_model_credentials",
    "audit_material_action_coverage",
    "audit_provenance_map_complete",
    "deterministic_tool_call_count",
    "deterministic_local_runtime",
    "live_model_token_usage",
    "live_model_cost",
    "live_model_latency",
    "full_18_preserved_5_rolled_1_escalated",
}


def test_service_builds_complete_sorted_registry() -> None:
    report = Phase8EvidenceService(REPO_ROOT).run(runtime_repetitions=1)
    assert {claim.claim_id for claim in report.claims} == EXPECTED_CLAIM_IDS
    assert [claim.claim_id for claim in report.claims] == sorted(EXPECTED_CLAIM_IDS)
```

- [ ] **Step 2: Run the service test and verify RED**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_cli.py -q
```

- [ ] **Step 3: Implement isolated session creation and collector composition**

Use the repository's established in-memory pattern:

```python
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)
try:
    with Session(engine) as session:
        result = collector(session)
finally:
    engine.dispose()
```

Use a fresh engine for collectors that require incompatible scenario states and for each timing repetition. Never touch `backend/transshipment.db`.

- [ ] **Step 4: Add deferred and not-established claims**

Create the three live claims with `status=DEFERRED`, `observed_value="DEFERRED_TO_PHASE_9"`, and no numeric metrics. Derive the 18/5/1 claim from durable records. Until a complete disjoint 24-container classification exists, emit `NOT_ESTABLISHED` with observed partial facts: Phase 2/R1 allocation count 8, carrier affected set `SYN-CNT-017`, safety escalation `SYN-CNT-010`, and `complete_terminal_classification_count < 24`.

```python
def deferred_claim(claim_id: str, statement: str) -> EvidenceClaim:
    return EvidenceClaim(
        claim_id=claim_id,
        statement=statement,
        status=ClaimStatus.DEFERRED,
        observed_value="DEFERRED_TO_PHASE_9",
        evidence_refs=(),
        caveat="DEFERRED_TO_PHASE_9",
        reproducibility=ClaimReproducibility(
            deterministic=True,
            included_in_fingerprint=True,
        ),
    )


LIVE_DEFERRED_CLAIMS = (
    deferred_claim("live_model_token_usage", "Live model token usage is measured."),
    deferred_claim("live_model_cost", "Live model API cost is measured."),
    deferred_claim("live_model_latency", "Live model latency is measured."),
)
```

- [ ] **Step 5: Write and implement the pure Markdown renderer**

```python
def test_markdown_is_a_projection_of_validated_report() -> None:
    report = Phase8EvidenceService(REPO_ROOT).run(runtime_repetitions=1)
    rendered = render_evidence_summary(report)
    assert rendered.startswith("# Phase 8 Deterministic Evidence Summary\n")
    assert report.deterministic_fingerprint in rendered
    assert "DEFERRED_TO_PHASE_9" in rendered
    assert "NOT_ESTABLISHED" in rendered
    assert "LOCAL_MACHINE_DEPENDENT" in rendered
    assert "```mermaid" not in rendered
    assert "![" not in rendered
```

Render sections in this order: metadata/fingerprint, verified headline claims, frozen scarcity, dynamic reconsideration, authority/tradeoff, safety/agent, audit/provenance, runtime/resource label, `NOT_ESTABLISHED`, `DEFERRED`, regeneration command. Sort claims by ID inside status sections. Format the scarcity delta as `0.4952` and relative improvement as `+4.1220%`; retain exact numeric values in JSON.

- [ ] **Step 6: Implement CLI parsing and exit mapping**

Arguments are exactly:

```text
--output-json PATH        required
--output-markdown PATH    required
--runtime-repetitions N   default 20, minimum 1
```

Catch only at the CLI boundary: `EvidenceInvariantFailure` prints a concise claim/detail to stderr and exits 1; `ValidationError`, `ValueError`, `OSError`, malformed artifact errors, and argparse failures exit 2. Successful reports exit 0.

```python
REPO_ROOT = Path(__file__).resolve().parents[3]


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = Phase8EvidenceService(REPO_ROOT).run(
            runtime_repetitions=args.runtime_repetitions
        )
        write_evidence_artifacts(report, args.output_json, args.output_markdown)
    except EvidenceInvariantFailure as error:
        print(f"VERIFIED invariant failed: {error}", file=sys.stderr)
        return 1
    except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"Phase 8 evidence error: {error}", file=sys.stderr)
        return 2
    return 0
```

- [ ] **Step 7: Implement validation-before-write and atomic sibling replacement**

Serialize JSON and render Markdown in memory, write sibling files ending `.tmp`, and use `Path.replace()` only after both temporary writes succeed. On any exception, delete only those exact temporary siblings and leave existing outputs untouched.

```python
json_text = report.model_dump_json(indent=2) + "\n"
markdown_text = render_evidence_summary(report)
json_tmp = json_path.with_name(json_path.name + ".tmp")
markdown_tmp = markdown_path.with_name(markdown_path.name + ".tmp")
try:
    json_tmp.write_text(json_text, encoding="utf-8")
    markdown_tmp.write_text(markdown_text, encoding="utf-8")
    json_tmp.replace(json_path)
    markdown_tmp.replace(markdown_path)
finally:
    json_tmp.unlink(missing_ok=True)
    markdown_tmp.unlink(missing_ok=True)
```

- [ ] **Step 8: Run CLI-focused tests and commit**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_cli.py backend/tests/test_evidence_contracts.py backend/tests/test_evidence_fingerprint.py -q
git diff --check
```

Commit:

```powershell
git add backend/app/evaluation/evidence.py backend/app/evaluation/evidence_markdown.py backend/tests/test_evidence_cli.py
git commit -m "feat: add composite phase 8 evidence cli"
```

---

### Task 9: JSON and Markdown evidence artifacts

**Files:**
- Create: `docs/evaluations/phase8-evidence-report.json`
- Create: `docs/evaluations/phase8-evidence-summary.md`
- Modify: `backend/tests/test_evidence_cli.py`

**Interfaces:**
- Consumes `Phase8EvidenceService`, `Phase8EvidenceReport`, and `render_evidence_summary()` from Task 8.
- Produces no new production interface; this task commits the first generated package.

- [ ] **Step 1: Write committed-artifact validation tests**

```python
def test_committed_artifacts_are_validated_and_consistent() -> None:
    report = Phase8EvidenceReport.model_validate_json(
        (REPO_ROOT / "docs/evaluations/phase8-evidence-report.json").read_text(encoding="utf-8")
    )
    markdown = (REPO_ROOT / "docs/evaluations/phase8-evidence-summary.md").read_text(encoding="utf-8")
    assert markdown == render_evidence_summary(report)
    assert report.deterministic_fingerprint in markdown
```

- [ ] **Step 2: Run artifact validation and verify RED**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_cli.py -q
```

Expected: test fails because the committed Phase 8 artifacts do not exist.

- [ ] **Step 3: Generate the committed evidence package**

Run:

```powershell
$env:OPENAI_API_KEY = $null
uv run --python 3.12 --extra dev python -m backend.app.evaluation.evidence --output-json docs/evaluations/phase8-evidence-report.json --output-markdown docs/evaluations/phase8-evidence-summary.md --runtime-repetitions 20
```

Expected: exit 0; both files exist; JSON contains the exact schema, registry, provenance, runtime label, and fingerprint; no live metric is numeric.

- [ ] **Step 4: Re-load generated JSON and compare Markdown**

Run a test that validates the committed JSON with `Phase8EvidenceReport.model_validate_json()` and asserts the committed Markdown equals `render_evidence_summary(validated_report)` byte-for-byte.

- [ ] **Step 5: Run focused tests and commit**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_cli.py -q
git diff --check
```

Commit:

```powershell
git add backend/tests/test_evidence_cli.py docs/evaluations/phase8-evidence-report.json docs/evaluations/phase8-evidence-summary.md
git commit -m "docs: add generated phase 8 evidence package"
```

---

### Task 10: End-to-end acceptance and reproducibility tests

**Files:**
- Create: `backend/tests/test_phase8_evidence_acceptance.py`
- Modify only if acceptance exposes a defect: the owning Phase 8 module and its focused test from Tasks 1–9.

**Interfaces:**
- Consumes the public `Phase8EvidenceService` and generated artifact paths.
- Produces no new production interface.

- [ ] **Step 1: Write the two-run fingerprint acceptance test**

```python
def test_two_unchanged_runs_have_equal_deterministic_evidence() -> None:
    first = Phase8EvidenceService(REPO_ROOT).run(runtime_repetitions=2)
    second = Phase8EvidenceService(REPO_ROOT).run(runtime_repetitions=2)
    assert first.deterministic_fingerprint == second.deterministic_fingerprint
    assert normalized_evidence_payload(first.body()) == normalized_evidence_payload(second.body())
    assert first.runtime.run_durations_ms != ()
    assert second.runtime.run_durations_ms != ()
```

- [ ] **Step 2: Write exact status and acceptance assertions**

Assert every expected verified claim is `VERIFIED`; the three live claims are `DEFERRED` with `DEFERRED_TO_PHASE_9`; 18/5/1 is `NOT_ESTABLISHED` unless the complete-classification predicate is true; the key is exact; tool order/step count are exact; provenance covers all non-deferred references.

```python
claims = {claim.claim_id: claim for claim in report.claims}
assert {claims[claim_id].status for claim_id in LIVE_CLAIM_IDS} == {ClaimStatus.DEFERRED}
assert {claims[claim_id].observed_value for claim_id in LIVE_CLAIM_IDS} == {"DEFERRED_TO_PHASE_9"}
assert claims["full_18_preserved_5_rolled_1_escalated"].status is ClaimStatus.NOT_ESTABLISHED
assert claims["scarcity_reproducibility_key"].observed_value == "d0dc76fb9239f4f77320f4b0a0fd5572d0b9a86a80da0448892d5336f205fe21"
assert claims["agent_step_count"].observed_value == 6
assert claims["deterministic_tool_call_count"].observed_value == 5
```

Define `LIVE_CLAIM_IDS = {"live_model_token_usage", "live_model_cost", "live_model_latency"}` in this test file.

- [ ] **Step 3: Write failure-semantics CLI-boundary tests**

Define `main(argv: Sequence[str] | None = None) -> int` and keep `if __name__ == "__main__": raise SystemExit(main())`. Invoke `main()` against temporary output paths while monkeypatching `Phase8EvidenceService.run` to raise `EvidenceInvariantFailure`; assert return code 1 and sentinel output files unchanged. Pass an invalid repetition count and assert return code 2. Run normally and assert return code 0. Add one real subprocess smoke that runs `python -m backend.app.evaluation.evidence` successfully with credentials absent; do not add an environment-controlled production test seam.

```python
def test_invariant_failure_returns_one_without_overwrite(tmp_path, monkeypatch) -> None:
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "summary.md"
    json_path.write_text("sentinel-json", encoding="utf-8")
    markdown_path.write_text("sentinel-markdown", encoding="utf-8")
    monkeypatch.setattr(
        Phase8EvidenceService,
        "run",
        lambda self, runtime_repetitions: (_ for _ in ()).throw(
            EvidenceInvariantFailure("agent_step_count", "observed 7")
        ),
    )
    code = main([
        "--output-json", str(json_path),
        "--output-markdown", str(markdown_path),
        "--runtime-repetitions", "1",
    ])
    assert code == 1
    assert json_path.read_text(encoding="utf-8") == "sentinel-json"
    assert markdown_path.read_text(encoding="utf-8") == "sentinel-markdown"
```

- [ ] **Step 4: Write committed-artifact semantic regeneration test**

Run the service once, validate committed JSON, and compare `normalized_evidence_payload()` plus fingerprint. Do not compare timestamps, current source SHA, runtime measurements, or runtime record IDs.

```python
generated = Phase8EvidenceService(REPO_ROOT).run(runtime_repetitions=1)
committed = Phase8EvidenceReport.model_validate_json(
    (REPO_ROOT / "docs/evaluations/phase8-evidence-report.json").read_text(encoding="utf-8")
)
assert generated.deterministic_fingerprint == committed.deterministic_fingerprint
assert normalized_evidence_payload(generated.body()) == normalized_evidence_payload(committed.body())
```

- [ ] **Step 5: Run the complete Phase 8 suite and fix only owner-scoped defects**

Run:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_contracts.py backend/tests/test_evidence_fingerprint.py backend/tests/test_evidence_scarcity.py backend/tests/test_evidence_dynamic_yard.py backend/tests/test_evidence_authority.py backend/tests/test_evidence_tradeoff.py backend/tests/test_evidence_safety_agent.py backend/tests/test_evidence_audit.py backend/tests/test_evidence_runtime.py backend/tests/test_evidence_cli.py backend/tests/test_phase8_evidence_acceptance.py -q
```

- [ ] **Step 6: Commit acceptance coverage**

```powershell
git add backend/tests/test_phase8_evidence_acceptance.py backend/app/evaluation/evidence.py backend/app/evaluation/evidence_scarcity.py backend/app/evaluation/evidence_dynamic_yard.py backend/app/evaluation/evidence_authority.py backend/app/evaluation/evidence_safety_agent.py backend/app/evaluation/evidence_audit.py backend/app/evaluation/evidence_runtime.py backend/app/evaluation/evidence_markdown.py backend/app/domain/evidence.py backend/tests/test_evidence_contracts.py backend/tests/test_evidence_fingerprint.py backend/tests/test_evidence_scarcity.py backend/tests/test_evidence_dynamic_yard.py backend/tests/test_evidence_authority.py backend/tests/test_evidence_tradeoff.py backend/tests/test_evidence_safety_agent.py backend/tests/test_evidence_audit.py backend/tests/test_evidence_runtime.py backend/tests/test_evidence_cli.py docs/evaluations/phase8-evidence-report.json docs/evaluations/phase8-evidence-summary.md
git commit -m "test: prove phase 8 evidence reproducibility and failure semantics"
```

---

### Task 11: Full verification, review, regeneration, and coordination record

**Files:**
- Modify: `docs/coordination/logs/win-codex.md`
- Regenerate after final fixes: `docs/evaluations/phase8-evidence-report.json`
- Regenerate after final fixes: `docs/evaluations/phase8-evidence-summary.md`

**Interfaces:**
- No new interface. This is the final release gate for the Phase 8 implementation branch.

- [ ] **Step 1: Run the full backend regression and lock check**

```powershell
uv run --python 3.12 --extra dev pytest backend/tests -q
uv lock --check
```

Expected: all backend tests pass; only previously accepted warnings/skips remain; lock check exits 0 with no dependency change.

- [ ] **Step 2: Regenerate evidence with credentials absent**

```powershell
$env:OPENAI_API_KEY = $null
uv run --python 3.12 --extra dev python -m backend.app.evaluation.evidence --output-json docs/evaluations/phase8-evidence-report.json --output-markdown docs/evaluations/phase8-evidence-summary.md --runtime-repetitions 20
```

Expected: exit 0; fingerprint matches the acceptance test and committed semantic projection.

- [ ] **Step 3: Run a second unchanged regeneration to temporary paths**

```powershell
uv run --python 3.12 --extra dev python -m backend.app.evaluation.evidence --output-json .phase8-second-report.json --output-markdown .phase8-second-summary.md --runtime-repetitions 20
```

Validate both reports, assert fingerprint and normalized payload equality, then delete only the two resolved temporary workspace files after confirming their absolute paths remain under the repository root.

- [ ] **Step 4: Perform final code review over the frozen base**

Review:

```powershell
git diff --stat 71716a0eee8413358dfc1e125a942945fc4be18c..HEAD
git diff 71716a0eee8413358dfc1e125a942945fc4be18c..HEAD -- backend/app backend/tests docs/evaluations
```

Classify Critical/Important/Minor and explicitly inspect for: duplicated evaluator/business logic; fake live metrics; hard-coded 18/5/1 verification; provider/network use; unstable fingerprint fields; vague audit coverage; missing forbidden tools; source-scan-only authority proof; missing dynamic guard evidence; swallowed invariant failures; report/Markdown divergence; writes to the development database; chain-of-thought exposure; frontend/deployment scope creep. Fix every Critical/Important finding with a focused regression test and rerun Steps 1–3.

- [ ] **Step 5: Record the implementation in the coordination log**

Append one dated Phase 8 entry to `docs/coordination/logs/win-codex.md` containing branch/base, spec/plan commits, implementation commits, files, full/focused test counts, frozen benchmark result/key, claim statuses, exact fingerprint, deferred metrics, 18/5/1 disposition, runtime machine-dependence label, review findings/fixes, deviations, and push state.

- [ ] **Step 6: Run final repository hygiene checks**

```powershell
git diff --check
git status --short
```

Expected before the final documentation commit: only the intended regenerated artifacts and coordination-log entry are modified.

- [ ] **Step 7: Commit final regeneration and coordination record**

```powershell
git add docs/evaluations/phase8-evidence-report.json docs/evaluations/phase8-evidence-summary.md docs/coordination/logs/win-codex.md
git commit -m "docs: record phase 8 deterministic evidence verification"
```

- [ ] **Step 8: Push for external review without merging**

```powershell
git push -u origin feat/phase8-evaluation-evidence
git rev-parse HEAD
git rev-parse origin/feat/phase8-evaluation-evidence
git status --short
```

Expected: local and origin SHAs match, worktree is clean, Phase 8 remains unmerged, and Phase 9 has not started.
