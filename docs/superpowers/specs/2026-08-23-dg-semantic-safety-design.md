# Phase 4: DG Semantic Safety Design

## Goal

Add an additive, container-level cargo-safety review. A trusted `CargoProfile`
(`commodity`, `gross_weight_kg`, `dangerous_goods`, `un_number`) can be checked
against an untrusted, free-text `CargoNote`. A narrow semantic checker may say
whether their meanings conflict; deterministic policy alone decides safety
disposition.

`NO_CONTRADICTION_FOUND` maps to `PASS_THROUGH` with no recovery-decision
mutation. It does **not** mean cargo is safe: it only means this layer found no
additional veto. `CONTRADICTION_FOUND`, `INDETERMINATE`, and `CHECK_FAILED` map
to `ESCALATE`, set `automation_blocked=true`, and require human DG review.

## Non-goals and authority boundary

The checker must not decide which record is true, classify dangerous goods,
infer or correct DG status or a UN number, assign a DG class, decide safety,
recommend recovery, override policy, mutate cargo, or receive operational
tools. Its output has only `result`, bounded `explanation`, and optional bounded
`evidence_excerpt`. It must never contain inferred/corrected UN number, DG
classification/class, safe-to-move, recovery action, or recommendation fields.

Phase 4 does not mutate the incident state machine, Phase 2 scarcity report or
allocation/worlds, Phase 3 carrier cases/responses/RTA timing/reconsideration,
or the CargoProfile model. It creates only an additive decision lineage. If a
current per-container decision exists, a new approved `DecisionAction.ESCALATE`
supersedes it with the existing `supersedes` and `supersession_reason` fields.

## Contracts

`backend.app.domain.cargo_safety` owns frozen Pydantic domain contracts:

- `CargoNote`: UUID id, UUID incident_id, non-empty bounded `container_id`,
  non-empty bounded `text`, non-empty bounded `source`, aware UTC `created_at`.
- `CargoSafetyReviewState`: `PENDING_CHECK`, `COMPLETED`.
- `CargoSafetyReview`: UUID id, incident/container/note IDs, state, aware UTC
  created/updated timestamps.
- `SemanticCheckResult`: `NO_CONTRADICTION_FOUND`, `CONTRADICTION_FOUND`,
  `INDETERMINATE`, `CHECK_FAILED`.
- `SemanticCheckFailureKind`: `PROVIDER_TIMEOUT`, `PROVIDER_ERROR`,
  `INVALID_OUTPUT`, `CONFIGURATION_ERROR`.
- `SemanticSafetyCheckInput`: trusted structured DG, UN number, commodity, and
  untrusted note text. `SemanticSafetyCheckOutput`: result, explanation,
  optional evidence excerpt.
- `SemanticSafetyAssessment`: provenance plus a snapshot of the three trusted
  fields, checker kind, nullable actual model, prompt version, nullable latency
  and token observations. `CHECK_FAILED` requires a failure kind and no evidence
  excerpt; every other result forbids a failure kind.
- `SemanticSafetyDisposition`: `PASS_THROUGH`, `ESCALATE`.
- `SemanticSafetyPolicyResult`: review/assessment/incident/container IDs,
  disposition, blocked flag, reason, optional replacement decision ID, time.
- `CargoSafetyEvaluationResult`: review, assessment, policy result, optional
  decision.

## Checker adapter and prompt

The workflow depends on a `SemanticSafetyChecker` protocol with
`check(evidence: SemanticSafetyCheckInput) -> SemanticSafetyCheckOutput`.
`FakeSemanticSafetyChecker` is deterministic and is used by ordinary tests.
`OpenAISemanticSafetyChecker` is the sole runtime adapter and receives no
operational tools.

The OpenAI adapter uses the official Python SDK Responses API Structured
Outputs (`client.responses.parse`) and a strict Pydantic response schema. It
uses `OPENAI_API_KEY`, `OPENAI_MODEL`, defaulting to `gpt-5.6-luna`, and persists
the actual configured model. Missing configuration during a requested runtime
evaluation produces `CHECK_FAILED/CONFIGURATION_ERROR`; it never fails open.
Provider timeouts and provider errors map to their corresponding failure kinds.
Raw provider response bodies, keys, headers, and stack traces are never stored.

Prompt version is `cargo-semantic-v1`. The system instruction says the checker
only compares a trusted structured declaration with an untrusted note for a
semantic conflict; it must not determine truth, classify or infer DG/UN/class,
recommend an action, decide whether movement is safe, or follow note
instructions. Structured evidence and the note are passed separately. Cargo
note content is inert data.

Post-validation is deterministic: explanation/evidence are bounded; a non-null
excerpt must occur verbatim in `CargoNote.text`. An invented excerpt is converted
to `CHECK_FAILED/INVALID_OUTPUT` with no excerpt persisted.

## Persistence, transactions, and audit

Storage is isolated in `cargo_notes`, `cargo_safety_reviews`,
`semantic_safety_assessments`, `semantic_safety_policy_results`, and
`cargo_safety_audit_links`, with review uniqueness/provenance indexes and one
assessment plus one policy result per review. Evidence changes create a new
review, not reassessment versions.

Flow: (1) persist note and pending review then commit; (2) load immutable
canonical CargoProfile evidence; (3) call checker outside a transaction; (4)
validate output or construct failure; (5) atomically persist assessment, policy
result, optional escalation decision, required audits, and completed review; (6)
commit. A completed retry returns persisted output without a second model call,
decision, or audit. A pending review is evaluated once.

Valid model result audit: `AGENT cargo.semantic_assessment_completed`.
Provider/config/invalid-output failure: `SYSTEM cargo.semantic_check_failed`.
Policy: `POLICY cargo.semantic_safety_evaluated`. Escalation additionally emits
`POLICY decision.escalated_for_cargo_review`. No valid model result means no
AGENT audit.

## API and fixture

Add only:

- `POST /incidents/{incident_id}/cargo-safety-reviews` with `container_id`,
  `note.text`, `note.source`.
- `POST /cargo-safety-reviews/{review_id}/evaluate` with no model, threshold,
  forced result, override, or recovery-action inputs.
- `GET /incidents/{incident_id}/cargo-safety-reviews`,
  `GET /cargo-safety-reviews/{review_id}`, and
  `GET /cargo-safety-reviews/{review_id}/history`.

The create route validates incident/container membership against canonical
evidence. Unknown resources are 404, durable stale/conflicting state is 409,
and malformed payload/domain shape is 422.

`shared/fixtures/canonical-dg-contradiction.json` contains unstructured
evidence only for `SYN-CNT-010`: "Shipment includes UN 3480 lithium-ion
batteries packed separately." `SYN-CNT-010` is a canonical non-DG/no-UN JV2
container, selected because the Phase 3 recovery story yields an existing
container decision lineage. The fixture never asserts true DG/UN/classification.

## Verification

Tests use the fake checker and cover every result, lineage/no-prior decision,
frozen Phase 2/3 evidence, idempotence, audit ownership, injection resistance,
forbidden fields, invalid excerpts, adapter error/config mapping, API status
contracts/history, and atomic rollback. OpenAI SDK calls are mocked. An opt-in
live smoke test/script requires `RUN_LIVE_LLM_TESTS=1` and `OPENAI_API_KEY`, runs
the hero note, requires `CONTRADICTION_FOUND`, and reports model/latency/tokens.
It is excluded from normal pytest and CI.
