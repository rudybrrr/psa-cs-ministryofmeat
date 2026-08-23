# Phase 5B: Dynamic Yard Reconsideration Design

**Status:** Approved architectural design, ready for user specification review

**Date:** 2026-08-24

**Scope:** Add deterministic dynamic-yard evidence and uncertainty-driven reconsideration to the existing incident-level Phase 5A `AgentRun`, without changing Phase 2 historical evidence or creating another agent, worker, frontend, or generic optimisation surface.

## 1. Purpose and governing invariant

Phase 5B models a later, durable `DISCHARGE_ACTIVE` yard forecast that can narrow or change the original `PRE_DISCHARGE` readiness bands. It projects that new evidence onto the exact frozen Phase 2 scenario worlds, deterministically assesses whether an operational allocation revision is authorised, and leaves the existing agent to choose only the single exposed capability that applies that already-determined result.

The governing invariant is literal:

> Yard evidence, scenario projection, feasibility, materiality, allocation revision, commitment lifecycle, and tradeoff options are deterministic and durable. The LLM can read evidence and select `request_expedite_feasibility()` only when it is exposed. It cannot supply forecasts, capacity, commitments, container IDs, allocations, weights, thresholds, or a tradeoff selection.

Phase 2 remains immutable experimental evidence. Its `ScarcityEvaluationReport.selected_allocation`, fixture, seed, scenario identities, factor values, stochastic distribution, constraints, dominance policy, and historical decisions are never mutated or rerun as a new random experiment.

## 2. Existing repository facts and compatibility boundary

The current canonical Phase 2 report uses seed `20260822`, 50 worlds, and selected allocation:

```text
SYN-CNT-002, 004, 005, 010, 011, 012, 014, 015
```

The current fixture has total capacity 8, handling-group limits A=4, B=3, C=3, reefer maximum 3, and DG maximum 1. The existing scenario generator records exactly the required correlated components: shared discharge, handling-group, and container noise factors, with standard deviations 12, 7, and 2 minutes respectively; positive factor means earlier readiness. The existing allocator maximises integer incremental preserved connections under those hard constraints.

Phase 5A already declares `NEW_OPERATIONAL_EVIDENCE` and `HUMAN_TRADEOFF_DECISION` wait kinds, but currently only resolves carrier-case waits and rejects `pause_agent_run`. Phase 5B extends that runtime boundary; it does not change the existing request-approval, carrier-response/timeout, counter-approval, Phase 3 carrier, or Phase 4 safety authority.

Phase 3's existing `CarrierRecoveryWorkflow.prepare()` and `recompute()` deliberately use the frozen Phase 2 `report.selected_allocation`. Its canonical JV2 preparation therefore affects only `SYN-CNT-017`. Phase 5B does not alter those internals. Instead, before `prepare_rta_request(connection_id)` is exposed or executed where dynamic-yard state exists, a deterministic Phase 5B compatibility guard must prove both:

- the connection's membership in the active `AllocationRevision` is identical to frozen Phase 2 selected-allocation membership; and
- every container on that connection has dynamic projected ready-time evidence exactly equivalent, world by world, to the frozen Phase 2 mapping used by Phase 3.

If either predicate fails, `prepare_rta_request` is omitted from the registry and direct execution is rejected before Phase 3 is called. Safe evidence reads and escalation remain available. The canonical revision is intentionally SF1-only and canonical JV2 forecasts reconstruct the frozen mapping, so JV2 passes this guard and retains its existing affected set `SYN-CNT-017`.

Storage is SQLModel with JSON columns for frozen reports and explicit transactional repository methods. Phase 5B follows its append-only record pattern and uses a single shared unit of work for an operational supersession. Existing Phase 5A runtime context is rebuilt from durable state each turn, so Phase 5B facts enter that context and tool registry rather than a prompt transcript.

## 3. Forecast evidence contracts

Add the following frozen domain contracts in a dedicated dynamic-yard module.

```text
ForecastStage
  PRE_DISCHARGE | DISCHARGE_ACTIVE

ContainerReadyForecast
  container_id
  p10_ready_at
  p50_ready_at
  p90_ready_at

YardForecastSnapshot
  id
  incident_id
  stage
  generated_at
  source
  container_forecasts
```

Every forecast timestamp is explicit UTC (`tzinfo` aware and zero UTC offset), and every container row requires `p10_ready_at <= p50_ready_at <= p90_ready_at`. A snapshot contains exactly one forecast for every container in the frozen canonical incident, with no unknown or duplicate IDs. `PRE_DISCHARGE` is the only permissible first stage; `DISCHARGE_ACTIVE` requires a durable preceding `PRE_DISCHARGE` snapshot for the same incident.

Snapshots are immutable. Their canonical content fingerprint includes incident, stage, source, generated time, and the sorted container forecasts. Retrying identical content for a stage returns the existing snapshot/result idempotently. A second non-identical submission for a stage, an attempted stage regression, a skipped first stage, or a different duplicate evidence payload is rejected with conflict. A real yard/TOS adapter will call the same internal ingestion service as the synthetic endpoint; no client-provided forecast override path exists.

## 4. Fixed latent-world projection

Reconsideration obtains the original report's exact `seed` and `scenario_count`, regenerates the Phase 2 `ScenarioSet` once through the existing seeded generator, and verifies its identities and factor payload against the report's reproducibility evidence before use. It must not draw, persist, or consume any new random value. The regenerated set is an implementation reconstruction of the original immutable world set, not a newly sampled evaluation.

For every existing world and container, calculate:

```text
combined_factor = shared_discharge + handling_group + container_noise
latent_z = combined_factor / sqrt(12^2 + 7^2 + 2^2)
z90 = 1.2815515655

if latent_z >= 0:
    projected_ready = p50 - (latent_z / z90) * (p50 - p10)
else:
    projected_ready = p50 + (-latent_z / z90) * (p90 - p50)
```

Positive existing factors remain earlier readiness. Preserve the full timestamp precision produced by the arithmetic; comparison remains `projected_ready - expedite_minutes_saved <= frozen service.ready_boundary` for expedited containers and `projected_ready <= boundary` otherwise. This is a deterministic split-quantile projection anchored exactly at p10/p50/p90. It is not a claim that terminal uncertainty is Gaussian. The existing 30-minute per-container expedite saving, structural eligibility, service boundaries, and all Phase 2 hard constraints remain authoritative.

## 5. Operational commitment and revision lineage

Add the following operational contracts:

```text
ExpediteCommitmentStatus
  PLANNED | COMMITTED | EXECUTED | CANCELLED

ExpediteCommitment
  id, incident_id, origin_revision_id, container_id, status, created_at

AllocationRevision
  id, incident_id, source_phase2_evaluation_id, source_forecast_snapshot_id
  parent_revision_id nullable
  allocated_container_ids, locked_container_ids
  preserved_connection_total, expected_preserved_connections
  reason, created_at
```

`AllocationRevision` records are append-only and immutable. `ExpediteCommitment` is a simple durable record with a monotonic persisted status, not an event-sourced record. Its only legal transitions are `PLANNED -> COMMITTED`, `PLANNED -> CANCELLED`, and `COMMITTED -> EXECUTED`; every transition is audited and no reverse transition exists. `COMMITTED` and `EXECUTED` are immutable for allocation purposes. The agent has no commitment-state tool. The synthetic harness (and, later, a real operational adapter) alone creates/promotes operational commitments.

Bootstrap creates R0 from the frozen Phase 2 selected allocation, references the PRE_DISCHARGE snapshot and source report, and creates one `PLANNED` commitment for each allocated container. It then promotes only canonical 002 and 004 to `COMMITTED`. R0 itself is never changed.

On every assessment, `locked_container_ids` are the current `COMMITTED` and `EXECUTED` commitments. `remaining_capacity` is total capacity minus those locked slots. The solver holds all locked IDs fixed and optimises only the available planned/unallocated slots, while evaluating the entire allocation with the same hard limits. A solution may never remove a locked ID, exceed 8 slots, violate a handling-group limit, exceed reefer/DG limits, or include a structurally ineligible container.

R1, R2, and later revisions point to their immutable parent. `origin_revision_id` means the revision that originally created the commitment; it does not imply membership only in that revision. Current membership is always `AllocationRevision.allocated_container_ids`. Thus 002 can originate in R0, become `COMMITTED`, remain the same commitment through R1, and still occur in `R1.allocated_container_ids`. Unchanged `PLANNED` commitments may likewise retain their older origin.

An auto-supersession atomically creates the child revision, cancels every currently active `PLANNED` commitment displaced by the child allocation regardless of origin revision, creates `PLANNED` commitments only for new replacement containers, preserves surviving/locked commitments as-is, records audits, and marks the assessment handled. There is no rewrite of R0, carrier history, Phase 2 report, or prior commitment event.

## 6. Deterministic assessment and human boundary

Persist one immutable `ExpediteReconsiderationAssessment` for each accepted DISCHARGE_ACTIVE snapshot:

```text
ReconsiderationDisposition
  NO_CHANGE | AUTO_SUPERSEDE | HUMAN_REVIEW_REQUIRED

ExpediteReconsiderationAssessment
  id, incident_id, source_snapshot_id, prior_allocation_revision_id
  locked_container_ids, candidate_options
  preserved_total_before, preserved_total_after
  expected_preserved_before, expected_preserved_after
  disposition, reason
  handled_at nullable, handled_by_run_id nullable, created_at
```

Allocation-revision metrics describe the evidence at the time each revision was created. Materiality never compares metrics calculated under different snapshots. For an assessment, first re-evaluate its active current allocation under `source_snapshot_id` and its projected frozen worlds; then evaluate every feasible candidate under that same snapshot, world identities, constraints, and service boundaries. Therefore `preserved_total_before` means the current allocation under the assessment snapshot, not a PRE_DISCHARGE metric copied from its parent revision; `preserved_total_after` means the candidate allocation under that same assessment snapshot. Expected fields are the corresponding `total / world_count` audit values.

`preserved_connection_total` is the strict improvement gate: `preserved_total_after > preserved_total_before`, with no epsilon. Phase 5B applies the existing Phase 2 `pareto_front` and `AllocationDominancePolicy` semantics without adding a ranking or tie-breaker. That policy considers hard safety/capacity validity, expected preserved connections, p10 preserved connections, ordered per-service preserved totals, and allocation slot count.

For each assessment the deterministic sequence is: (1) evaluate the active allocation under the new projected worlds; (2) solve the hard-safe optimal candidate allocations with locked commitments fixed; (3) evaluate those candidates under the same worlds; and (4) apply existing `pareto_front` then `AllocationDominancePolicy`. The solver and policy receive no Phase 5B-specific weights or tie-break inputs.

`NO_CHANGE` applies if no hard-safe candidate strictly improves preserved total over the current allocation under the same snapshot. `AUTO_SUPERSEDE` applies only when strict improvement exists and existing deterministic dominance selects one exact winner while all locked commitments stay fixed. `HUMAN_REVIEW_REQUIRED` applies only when strict-improving hard-safe alternatives remain non-dominated and existing policy selects none. A worse expected-preservation candidate is not promoted to a human tradeoff by assigning unsupported commercial importance.

The human boundary is separate from Phase 3 approval:

```text
AllocationTradeoffReview
  id, incident_id, reconsideration_assessment_id
  exact immutable option IDs, options_fingerprint, state, created_at

AllocationTradeoffOption
  id, review_id, exact solver-generated allocation, objective/evidence summary

AllocationTradeoffSelection
  id, review_id, selected_option_id, expected_options_fingerprint
  operator_id, created_at
```

The only selection API is:

```text
POST /allocation-tradeoff-reviews/{review_id}/selection
{
  "selected_option_id": "...",
  "expected_options_fingerprint": "...",
  "operator_id": "..."
}
```

It accepts only an open review's exact persisted option and exact fingerprint. Stale, foreign, altered, duplicate, or closed selections conflict. There is no custom allocation, forecast, weight, or LLM selection path. A valid selection creates the corresponding child revision/commitment transition atomically and resolves the review and assessment.

## 7. Agent runtime, wait priority, and stale-plan gate

Add exactly one agent action:

```text
request_expedite_feasibility()
```

Every accepted DISCHARGE_ACTIVE snapshot creates exactly one durable unhandled reconsideration assessment, regardless of disposition. The tool has zero arguments and is exposed while an unhandled reconsideration assessment exists, no stronger wait is active, and the run is non-terminal. It reloads the latest unhandled assessment and determines its result entirely from durable state:

- `NO_CHANGE`: mark assessment handled and continue.
- `AUTO_SUPERSEDE`: use one transaction to create the new revision, cancel only displaced `PLANNED` commitments, create replacements as `PLANNED`, preserve `COMMITTED`/`EXECUTED`, audit, and mark handled.
- `HUMAN_REVIEW_REQUIRED`: persist exact immutable review/options if not already present, mark the assessment handled by that review, and set `WAITING / HUMAN_TRADEOFF_DECISION` with the review ID.

The tool is idempotent by assessment ID and prior revision ID. A crash retry observes either the completed durable result or no partial result; it never creates two revisions, cancels a commitment twice, or duplicates an option set.

Wait precedence is strict. Existing `REQUEST_APPROVAL`, `COUNTER_APPROVAL`, and `CARRIER_RESPONSE_OR_TIMEOUT`, plus `HUMAN_TRADEOFF_DECISION`, are stronger than incoming yard evidence. Ingestion always persists the forecast/assessment but never rewrites one of those current waits. Once that wait resolves, the unhandled reconsideration assessment is mandatory next work before unrelated state-changing actions. If the run is `WAITING / NEW_OPERATIONAL_EVIDENCE`, any accepted DISCHARGE_ACTIVE assessment resolves that wait. If it is `RUNNING`, ingestion does not invoke the model. If terminal (`COMPLETED`, `ESCALATED`, or `FAILED`), evidence remains auditable and does not resurrect it.

When an unhandled reconsideration assessment exists and no stronger wait is active, state-filter the registry to evidence reads, `request_expedite_feasibility`, valid safe runtime controls, and any required safety action. Omit unrelated new carrier mutation tools; the Phase 3 compatibility guard may expose `prepare_rta_request` only after the assessment is handled and its connection-specific evidence/membership proof succeeds. Tool-side validation repeats both guards. Completion rejects while an unhandled reconsideration assessment, open allocation-tradeoff review, or existing actionable Phase 5A work remains.

`pause_agent_run` may create `WAITING / NEW_OPERATIONAL_EVIDENCE` only when durable state proves dynamic-yard bootstrap completed, the newest forecast is PRE_DISCHARGE, and no DISCHARGE_ACTIVE evidence has arrived. The model cannot manufacture an evidence wait, name a forecast, or set a deadline.

## 8. Synthetic harness and canonical hero calibration

Add a separate fixed Phase 5B harness; do not modify the frozen Phase 2 trigger:

```text
POST /synthetic/scenarios/{incident_id}/dynamic-yard/bootstrap
POST /synthetic/scenarios/{incident_id}/dynamic-yard/discharge-active
```

Both accept no body. Bootstrap creates the canonical PRE_DISCHARGE snapshot, R0, all initial planned commitments, and promotes 002 and 004 to `COMMITTED`. Discharge-active ingests the frozen later snapshot and persists its deterministic assessment. Neither endpoint invokes an agent.

For both canonical snapshots, use the symmetric half-width derived from the approved constants:

```text
half_width_minutes = 1.2815515655 * sqrt(12^2 + 7^2 + 2^2)
                   = 17.987433384504683 minutes
p10 = p50 - half_width_minutes
p90 = p50 + half_width_minutes
```

`PRE_DISCHARGE` uses every frozen fixture `base_ready_at` as p50. `DISCHARGE_ACTIVE` changes only SF1 container 005: its p50 is `2026-08-22T05:56:00Z`, three minutes earlier than the frozen `05:59:00Z`. Every other container, including all JV2 containers, keeps `p50 = base_ready_at` and the same full-precision symmetric half-width. This reconstructs the Phase 2 ready-time mapping exactly for unchanged containers: with this width, `latent_z / z90 * half_width_minutes` equals the existing combined factor. The source is the fixed synthetic dynamic-yard harness and all snapshot timestamps are UTC.

Read-only calibration against the exact current 50 worlds, the approved split-quantile projection, existing Phase 2 constraints, and existing Pareto/dominance policy yields one valid strict SF1-only revision:

```text
R0: 002, 004, 005, 010, 011, 012, 014, 015
R1: 001, 002, 004, 010, 011, 012, 014, 015
locked: 002, 004

SF1 change: 005 OUT -> 001 IN
preserved total under the same DISCHARGE_ACTIVE snapshot: 601 -> 602
expected preserved under that same snapshot: 12.02 -> 12.04
strict improvement: +1 total world (+0.02 expected)
```

The read-only enumeration found this to be the unique hard-safe optimum (integer incremental objective 243) and the existing `AllocationDominancePolicy` therefore selects it without a new tie-breaker. Thus 005 is cancelled only while `PLANNED`; 001 becomes `PLANNED`; 002 and 004 remain fixed. The change uses the minimum calibrated p50 movement found by minute-resolution search. It does not alter the projection, objective, constraints, capacity, commitment authority, or dominance policy.

JV2 allocation membership is unchanged between R0 and R1, and every JV2 forecast exactly reconstructs the frozen Phase 2 mapping. The Phase 3 compatibility guard therefore admits `prepare_rta_request(SYN-CONN-JV2)`, and the existing Phase 3 canonical preparation continues to affect only `SYN-CNT-017`.

The same-run hero is: Phase 2 allocation → Phase 5B bootstrap → AgentRun → `WAITING / NEW_OPERATIONAL_EVIDENCE` → discharge-active ingestion → `request_expedite_feasibility()` → R0 superseded by R1 → existing JV2 carrier recovery → request approval → carrier `COUNTER` → counter approval → existing `SYN-CNT-010` Phase 4 semantic contradiction → `ESCALATED / SAFETY_REVIEW_REQUIRED`.

## 9. APIs, audit, and observability

The dynamic-yard endpoints and tradeoff-selection endpoint are additive. Add read-only incident-scoped histories for forecasts, allocation revisions/commitments, assessments, and tradeoff reviews so the agent/context and operators can retrieve durable evidence. Unknown resource is 404; duplicate contradictory stage/evidence, invalid lifecycle state, stale selection fingerprint, unavailable selection, unresolved wait, or atomic concurrency conflict is 409; invalid timestamp/shape/body is 422.

Audit ownership is explicit: synthetic/real adapter ingestion is `SYSTEM`; fixed-world projection and revision persistence are `SOLVER` or `POLICY` according to the existing scarcity audit convention; commitment transitions, materiality disposition, and stale-plan rejection are `POLICY`; the agent only records its zero-argument tool invocation/brief summary. No raw LLM content, hidden reasoning, forecast text, or client policy input becomes authority.

## 10. Required deterministic verification

Ordinary tests make zero external network calls and must cover at least:

- p10/p50/p90 ordering, strict UTC, stage progression, identical retry idempotency, and contradictory duplicate rejection;
- exact Phase 2 world identity/factor reuse, zero new RNG, and both branches plus anchors of the split-quantile transform;
- locked committed/executed IDs never moving; maximum eight slots; handling-group, reefer, DG, and structural-safety constraints preserved;
- unchanged original Phase 2 report and allocation;
- every accepted DISCHARGE_ACTIVE snapshot creating an unhandled assessment; `NO_CHANGE` remaining reachable, creating no revision, and becoming handled only through the zero-argument tool;
- before/after assessment totals both being recomputed under the same source snapshot/worlds rather than copied from a prior revision; auto-supersede retaining R0 and creating R1; displaced planned commitment cancelled and replacement planned;
- allocation revisions remaining immutable; commitment status being monotonic/audited; surviving commitment membership being read from the current revision rather than `origin_revision_id`; and displaced active planned commitments being cancelled even when they originated before the parent revision;
- locked solver candidates being evaluated through existing `pareto_front`/`AllocationDominancePolicy` semantics with no Phase 5B tie-breaker; strict improvement with one selected winner versus non-dominated improving options requiring human review;
- human review option immutability; agent inability to choose an option; stale/invalid tradeoff fingerprint rejection;
- evidence queued without preempting request, carrier, counter, or human-tradeoff waits; every accepted DISCHARGE_ACTIVE assessment resolving the operational-evidence wait; stale-plan mutations blocked; terminal runs not resurrected; completion rejected with pending reconsideration/tradeoff or existing actionable Phase 5A work;
- valid `pause_agent_run` evidence wait and invalid fabricated pause rejection;
- Phase 3 compatibility guard: unchanged/equivalent canonical JV2 evidence exposes and admits prepare with its existing affected set `SYN-CNT-017`, while changed membership or projected evidence for any carrier connection filters prepare out and rejects a direct stale attempt before Phase 3;
- the exact canonical SF1-only 005-to-001 revision with 002/004 locked and observed same-snapshot 601-to-602 metrics;
- Phase 1 through 5A regression suite green, no frontend files changed, and no ordinary test network call.

## 11. Explicit exclusions

Phase 5B excludes a second agent, background polling/worker, LangGraph, Phase 2 redesign or mutation, Phase 3 approval redesign, Phase 4 safety redesign, frontend, arbitrary forecast UI or ingestion, model-supplied forecasts/capacity/commitment state/allocation/weights/thresholds, agent commitment/execution tools, generic optimisation weights, generic execution tools, authentication, deployment, and any automatic agent invocation after evidence ingestion.
