# Phase 8 Deterministic Evidence Summary

## Metadata and fingerprint

- Schema: `phase8-evidence-v1`
- Suite: `phase8-deterministic-evidence`
- Evaluation base: `71716a0eee8413358dfc1e125a942945fc4be18c`
- Source revision: `6677dbbac0f9e5ef6ccb1d751519e9a18f5ed5ec`
- Generated at: `2026-08-27T16:43:19.225757+00:00`
- Fixture IDs: `SYN-CANONICAL-24-V1`
- Seed manifest: `SYN-CANONICAL-24-HOLDOUT-V1`
- Canonical model: `canonical-replay-agent-v1`
- Canonical checker: `canonical-replay-deterministic`
- Fingerprint: `d707b991f87cc865300e431594c6792766744ee69523da98c796d67f015ee543`

## Verified headline

- `agent_terminal_state` — **VERIFIED** — {"reason":"SAFETY_REVIEW_REQUIRED","state":"ESCALATED"} — Credential-free deterministic canonical replay only.
- `audit_material_action_coverage` — **VERIFIED** — {"covered_categories":8,"missing_categories":[],"required_categories":8} — Credential-free deterministic canonical replay with a retained same-session supplemental human-tradeoff fixture.
- `safety_terminal_escalation` — **VERIFIED** — {"reason":"SAFETY_REVIEW_REQUIRED","state":"ESCALATED"} — Credential-free deterministic canonical replay only.
- `scarcity_expected_preserved_delta` — **VERIFIED** — {"baseline_expected_preserved":12.0136,"delta":0.49520000000000053,"relative_improvement_percent":4.121995072251453,"scenario_aware_expected_preserved":12.5088} — Synthetic canonical fixture and frozen holdout manifest only.

## Frozen scarcity

- `scarcity_expected_preserved_delta` — **VERIFIED** — {"baseline_expected_preserved":12.0136,"delta":0.49520000000000053,"relative_improvement_percent":4.121995072251453,"scenario_aware_expected_preserved":12.5088} — Synthetic canonical fixture and frozen holdout manifest only.
- `scarcity_expedite_slot_cap` — **VERIFIED** — {"baseline_slot_count":8,"scenario_aware_slot_count":8,"slot_cap":8} — Synthetic canonical fixture and frozen holdout manifest only.
- `scarcity_holdout_world_count` — **VERIFIED** — {"seed_count":50,"world_count":2500,"worlds_per_seed":50} — Synthetic canonical fixture and frozen holdout manifest only.
- `scarcity_reproducibility_key` — **VERIFIED** — "d0dc76fb9239f4f77320f4b0a0fd5572d0b9a86a80da0448892d5336f205fe21" — Synthetic canonical fixture and frozen holdout manifest only.
- `scarcity_scenario_aware_beats_p50` — **VERIFIED** — {"baseline_preserved_total":30034,"scenario_aware_beats_p50":true,"scenario_aware_preserved_total":31272} — Synthetic canonical fixture and frozen holdout manifest only.
- `scarcity_zero_capacity_violations` — **VERIFIED** — {"baseline":0,"scenario_aware":0} — Synthetic canonical fixture and frozen holdout manifest only.
- `scarcity_zero_unsafe_allocations` — **VERIFIED** — {"baseline":0,"scenario_aware":0} — Synthetic canonical fixture and frozen holdout manifest only.

Frozen expected-preserved improvement: `0.4952` (`+4.1220%`).

## Dynamic reconsideration

- `dynamic_committed_allocations_immutable` — **VERIFIED** — {"commitment_origin":"R0","committed":["SYN-CNT-002","SYN-CNT-004"],"r0_locked":["SYN-CNT-002","SYN-CNT-004"],"r1_locked":["SYN-CNT-002","SYN-CNT-004"]} — Synthetic canonical dynamic-yard scenarios only.
- `dynamic_evidence_precedes_carrier_mutation` — **VERIFIED** — {"case_count_after":0,"case_count_before":0,"exception_type":"ValueError","request_count_after":0,"request_count_before":0,"scenario_key":"dynamic-unhandled-evidence-carrier-guard-v1","unhandled_assessment":true} — Synthetic canonical dynamic-yard scenarios only.
- `dynamic_expected_preserved_change` — **VERIFIED** — {"after":12.04,"before":12.02} — Synthetic canonical dynamic-yard scenarios only.
- `dynamic_phase2_worlds_reconstructed` — **VERIFIED** — {"comparison_key":"4736cc73efa6123c62ba1e690b4c08c7d930a6e4a01ffd21aaadf7e527f65367","seed":20260822,"world_count":50} — Synthetic canonical Phase 2 fixture and seed only.
- `dynamic_phase3_incompatible_plan_blocked` — **VERIFIED** — {"case_count_after":0,"case_count_before":0,"exception_type":"ValueError","phase3_compatible":false,"request_count_after":0,"request_count_before":0,"scenario_key":"dynamic-phase3-forecast-mismatch-v1"} — Synthetic canonical dynamic-yard scenarios only.
- `dynamic_preserved_total_change` — **VERIFIED** — {"after":602,"before":601} — Synthetic canonical dynamic-yard scenarios only.
- `dynamic_reconsideration_r0_r1` — **VERIFIED** — {"cancelled":["SYN-CNT-005"],"committed":["SYN-CNT-002","SYN-CNT-004"],"planned":["SYN-CNT-001"],"r0":["SYN-CNT-002","SYN-CNT-004","SYN-CNT-005","SYN-CNT-010","SYN-CNT-011","SYN-CNT-012","SYN-CNT-014","SYN-CNT-015"],"r1":["SYN-CNT-001","SYN-CNT-002","SYN-CNT-004","SYN-CNT-010","SYN-CNT-011","SYN-CNT-012","SYN-CNT-014","SYN-CNT-015"]} — Synthetic canonical dynamic-yard scenarios only.

## Authority and tradeoff

- `authority_carrier_silence_is_absence` — **VERIFIED** — {"carrier_response_count":0} — Synthetic carrier plans and isolated backend state only.
- `authority_counter_approval_required` — **VERIFIED** — {"carrier_response_count":1,"effective_timing_count_before_approval":0} — Synthetic carrier plans and isolated backend state only.
- `authority_counter_fingerprint_bound` — **VERIFIED** — {"effective_timing_count":0,"wrong_fingerprint_exception":"CarrierRecoveryConflict"} — Synthetic carrier plans and isolated backend state only.
- `authority_no_agent_approval` — **VERIFIED** — {"agent_approval_authority_tools":[]} — Synthetic carrier plans and isolated backend state only.
- `authority_no_carrier_schedule_mutation` — **VERIFIED** — {"fixture_connection_unchanged":true} — Synthetic carrier plans and isolated backend state only.
- `authority_no_forbidden_tools` — **VERIFIED** — {"forbidden_runtime_tools":[]} — Synthetic carrier plans and isolated backend state only.
- `authority_request_approval_required` — **VERIFIED** — {"history_unchanged":true,"unapproved_send_exception":"CarrierRecoveryConflict"} — Synthetic carrier plans and isolated backend state only.
- `authority_request_fingerprint_bound` — **VERIFIED** — {"persisted_approval_count":0,"wrong_fingerprint_exception":"CarrierRecoveryConflict"} — Synthetic carrier plans and isolated backend state only.
- `authority_timeout_recomputes` — **VERIFIED** — {"terminal_state":"COMPLETED"} — Synthetic carrier plans and isolated backend state only.
- `human_tradeoff_agent_cannot_select` — **VERIFIED** — {"agent_approval_authority_tools":[],"selection_tool_exposed":false} — This proves backend projector and persisted workflow behavior only; it does not execute any frontend controller.
- `human_tradeoff_auto_replay_halts` — **VERIFIED** — {"auto_replay_may_execute":false,"next_action":"SELECT_TRADEOFF_OPTION","requires_human_authority":true,"stage":"TRADEOFF_DECISION_REQUIRED"} — This proves backend projector and persisted workflow behavior only; it does not execute any frontend controller.
- `human_tradeoff_boundary` — **VERIFIED** — {"model_calls_to_wait":1,"model_calls_while_waiting":0,"requires_human_authority":true,"review_state":"OPEN"} — This proves backend projector and persisted workflow behavior only; it does not execute any frontend controller.
- `human_tradeoff_committed_slots_immutable` — **VERIFIED** — {"committed_slots":["SYN-CNT-002","SYN-CNT-004"]} — This proves backend projector and persisted workflow behavior only; it does not execute any frontend controller.
- `human_tradeoff_fingerprint_bound` — **VERIFIED** — {"exception":"DynamicYardConflict","persisted_state_unchanged":true} — This proves backend projector and persisted workflow behavior only; it does not execute any frontend controller.

## Safety and agent

- `agent_approval_identities` — **VERIFIED** — ["operator-console","operator-console"] — Credential-free deterministic canonical replay only.
- `agent_no_unavailable_tool_execution` — **VERIFIED** — {"exposed":[],"invoked":[],"unavailable_tools":["change_carrier_schedule","hold_feeder","override_dg_rule","set_yard_capacity"]} — Credential-free deterministic canonical replay only.
- `agent_step_count` — **VERIFIED** — 6 — Credential-free deterministic canonical replay only.
- `agent_successful_tool_order` — **VERIFIED** — ["pause_agent_run","request_expedite_feasibility","prepare_rta_request","send_authorised_rta_request","request_cargo_safety_review"] — Credential-free deterministic canonical replay only.
- `agent_terminal_state` — **VERIFIED** — {"reason":"SAFETY_REVIEW_REQUIRED","state":"ESCALATED"} — Credential-free deterministic canonical replay only.
- `agent_wait_kinds` — **VERIFIED** — ["NEW_OPERATIONAL_EVIDENCE","REQUEST_APPROVAL","CARRIER_RESPONSE_OR_TIMEOUT","COUNTER_APPROVAL"] — Credential-free deterministic canonical replay only.
- `agent_zero_model_credentials` — **VERIFIED** — {"canonical_checker_identity":"canonical-replay-deterministic","canonical_model_identity":"canonical-replay-agent-v1","openai_api_key_present":false,"provider_client_construction_count":0} — Credential-free deterministic canonical replay only; live use is deferred.
- `deterministic_tool_call_count` — **VERIFIED** — 5 — Credential-free deterministic canonical replay only.
- `safety_automation_blocked` — **VERIFIED** — true — Credential-free deterministic canonical replay only.
- `safety_canonical_contradiction` — **VERIFIED** — "CONTRADICTION_FOUND" — Credential-free deterministic canonical replay only.
- `safety_checker_failure_fails_closed` — **VERIFIED** — {"assessment_result":"CHECK_FAILED","automation_blocked":true} — Isolated deterministic failure probe; no provider client or network call.
- `safety_checker_scope_limited` — **VERIFIED** — {"dangerous_goods_field_present":false,"disposition_field_present":false,"output_fields":["result","explanation","evidence_excerpt"],"un_number_field_present":false} — Deterministic canonical checker output contract only.
- `safety_pending_review_blocks_bypass` — **VERIFIED** — {"completion_exposed":true,"selected_tool":"request_cargo_safety_review","terminal_reason":"SAFETY_REVIEW_REQUIRED"} — Credential-free deterministic canonical replay only.
- `safety_policy_owns_disposition` — **VERIFIED** — {"automation_blocked":true,"checker_result":"CONTRADICTION_FOUND","policy_disposition":"ESCALATE"} — Credential-free deterministic canonical replay only.
- `safety_terminal_escalation` — **VERIFIED** — {"reason":"SAFETY_REVIEW_REQUIRED","state":"ESCALATED"} — Credential-free deterministic canonical replay only.

## Audit and provenance

- `audit_material_action_coverage` — **VERIFIED** — {"covered_categories":8,"missing_categories":[],"required_categories":8} — Credential-free deterministic canonical replay with a retained same-session supplemental human-tradeoff fixture.
- `audit_provenance_map_complete` — **VERIFIED** — {"claim_count":50,"provenance_row_count":100,"reference_count":100} — Validated composite Phase 8 report registry only.

- `audit_material_action_coverage` → `AgentHistory` / `canonical-run:agent-history` (TYPED_HISTORY; `AgentRuntimeRepository.history`)
- `audit_material_action_coverage` → `AgentRun` / `canonical-run:agent-run` (PRIMARY_RECORD; `AgentRuntimeRepository.history`)
- `audit_material_action_coverage` → `AgentStep` / `canonical-run:agent-step` (PRIMARY_RECORD; `AgentRuntimeRepository.history`)
- `audit_material_action_coverage` → `AgentToolInvocation` / `canonical-run:agent-tool-invocation` (PRIMARY_RECORD; `AgentRuntimeRepository.history`)
- `audit_material_action_coverage` → `AllocationRevision` / `canonical-run:allocation-revision` (PRIMARY_RECORD; `DynamicYardRepository.history`)
- `audit_material_action_coverage` → `AllocationRevision` / `supplemental-tradeoff:child-revision` (PRIMARY_RECORD; `DynamicYardWorkflow.select_tradeoff`)
- `audit_material_action_coverage` → `AllocationTradeoffHistory` / `canonical-run:dynamic-history` (TYPED_HISTORY; `DynamicYardWorkflow.history`)
- `audit_material_action_coverage` → `AllocationTradeoffOption` / `supplemental-tradeoff:option` (PRIMARY_RECORD; `DynamicYardWorkflow.select_tradeoff`)
- `audit_material_action_coverage` → `AllocationTradeoffReview` / `supplemental-tradeoff:review` (PRIMARY_RECORD; `DynamicYardWorkflow.select_tradeoff`)
- `audit_material_action_coverage` → `AllocationTradeoffSelection` / `supplemental-tradeoff:selection` (PRIMARY_RECORD; `DynamicYardWorkflow.select_tradeoff`)
- `audit_material_action_coverage` → `Approval` / `canonical-run:operator-approval` (PRIMARY_RECORD; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `ApprovalBinding` / `canonical-run:approval-binding` (PRIMARY_RECORD; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:allocation_revision.applied` (AUDIT_EVENT; `AuditRepository.list_for_incident`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:cargo.semantic_assessment_completed` (AUDIT_EVENT; `CargoSafetyRepository.history`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:cargo.semantic_safety_evaluated` (AUDIT_EVENT; `CargoSafetyRepository.history`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:carrier.counter_approval_recorded` (AUDIT_EVENT; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:carrier.response_received` (AUDIT_EVENT; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:carrier_recovery.replacement_recorded` (AUDIT_EVENT; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:carrier_recovery.request_approval_recorded` (AUDIT_EVENT; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:decision.created` (AUDIT_EVENT; `AuditRepository.list_for_incident`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:decision.escalated_for_cargo_review` (AUDIT_EVENT; `CargoSafetyRepository.history`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:expedite_reconsideration.assessed` (AUDIT_EVENT; `AuditRepository.list_for_incident`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:incident.created` (AUDIT_EVENT; `AuditRepository.list_for_incident`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:scarcity.evaluation_persisted` (AUDIT_EVENT; `AuditRepository.list_for_incident`)
- `audit_material_action_coverage` → `AuditEvent` / `canonical-run:audit:yard_forecast.snapshot_ingested` (AUDIT_EVENT; `AuditRepository.list_for_incident`)
- `audit_material_action_coverage` → `AuditEvent` / `supplemental-tradeoff:audit:allocation_revision.applied` (AUDIT_EVENT; `AuditRepository.list_for_incident`)
- `audit_material_action_coverage` → `AuditEvent` / `supplemental-tradeoff:audit:option_selected` (AUDIT_EVENT; `AuditRepository.list_for_incident`)
- `audit_material_action_coverage` → `CargoNote` / `canonical-run:cargo-note` (PRIMARY_RECORD; `CargoSafetyRepository.history`)
- `audit_material_action_coverage` → `CargoSafetyHistory` / `canonical-run:safety-history` (TYPED_HISTORY; `CargoSafetyRepository.history`)
- `audit_material_action_coverage` → `CargoSafetyReview` / `canonical-run:cargo-safety-review` (PRIMARY_RECORD; `CargoSafetyRepository.history`)
- `audit_material_action_coverage` → `CarrierRecoveryDecisionLink` / `canonical-run:carrier-decision-link` (PRIMARY_RECORD; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `CarrierRecoveryHistory` / `canonical-run:carrier-history` (TYPED_HISTORY; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `CarrierResponse` / `canonical-run:carrier-response` (PRIMARY_RECORD; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `ContainerReconsiderationResult` / `canonical-run:carrier-reconsideration-result` (PRIMARY_RECORD; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `Decision` / `canonical-run:carrier-replacement-decision` (PRIMARY_RECORD; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `Decision` / `canonical-run:phase2-decision` (PRIMARY_RECORD; `build_scarce_capacity_workflow.run`)
- `audit_material_action_coverage` → `Decision` / `canonical-run:safety-escalation-decision` (PRIMARY_RECORD; `CargoSafetyHistory.policy_result`)
- `audit_material_action_coverage` → `EffectiveConnectionTiming` / `canonical-run:effective-connection-timing` (PRIMARY_RECORD; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `ExpediteCommitment` / `canonical-run:expedite-commitment` (PRIMARY_RECORD; `DynamicYardRepository.history`)
- `audit_material_action_coverage` → `ExpediteReconsiderationAssessment` / `canonical-run:reconsideration-assessment` (PRIMARY_RECORD; `DynamicYardRepository.history`)
- `audit_material_action_coverage` → `Incident` / `canonical-run:incident` (PRIMARY_RECORD; `CanonicalEvidenceRun`)
- `audit_material_action_coverage` → `RTARequest` / `canonical-run:rta-request` (PRIMARY_RECORD; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `RTARequestContext` / `canonical-run:rta-request-context` (PRIMARY_RECORD; `CarrierRecoveryRepository.history`)
- `audit_material_action_coverage` → `ScarcityEvaluationReport` / `canonical-run:phase2-evaluation` (PRIMARY_RECORD; `build_scarce_capacity_workflow.run`)
- `audit_material_action_coverage` → `SemanticSafetyAssessment` / `canonical-run:semantic-safety-assessment` (PRIMARY_RECORD; `CargoSafetyRepository.history`)
- `audit_material_action_coverage` → `SemanticSafetyPolicyResult` / `canonical-run:semantic-safety-policy` (PRIMARY_RECORD; `CargoSafetyRepository.history`)
- `audit_material_action_coverage` → `YardForecastSnapshot` / `canonical-run:yard-snapshot` (PRIMARY_RECORD; `DynamicYardRepository.history`)
- `audit_provenance_map_complete` → `EvidenceRegistryProbe` / `phase8-report:provenance-completeness` (PRIMARY_RECORD; `build_provenance_map and EvidenceReportBody validation`)

## Runtime and resource label

- Label: `LOCAL_MACHINE_DEPENDENT`
- Production SLA claimed: `false`
- `deterministic_local_runtime` — **VERIFIED** — {"canonical_run_wall_clock_ms":579.8507,"p50_local_runtime_ms":610.0260000000001,"p95_local_runtime_ms":671.7716,"platform":"Windows-11-10.0.26200-SP0","python_version":"3.12.13 (main, Jun 23 2026, 15:23:43) [MSC v.1944 64 bit (AMD64)]","repetitions":20,"run_durations_ms":[579.8507,605.5361,544.3329,624.0044,532.3369,638.929,603.3304,601.6444,613.9197,633.9367,671.7716,622.1912,584.8642,582.1826,648.1194,582.7135,606.1323,618.9343,685.1354,648.9133]} — LOCAL_MACHINE_DEPENDENT measurement only; it is not a production SLA or a deterministic timing claim.

## NOT_ESTABLISHED

- `full_18_preserved_5_rolled_1_escalated` — **NOT_ESTABLISHED** — {"carrier_affected_container_ids":["SYN-CNT-017"],"complete_terminal_classification_count":2,"r1_allocation_count":8,"required_container_count":24,"safety_escalation_container_id":"SYN-CNT-010"} — NOT_ESTABLISHED: no complete disjoint durable terminal ledger classifies all 24 containers.

## DEFERRED

- `live_model_cost` — **DEFERRED** — "DEFERRED_TO_PHASE_9" — DEFERRED_TO_PHASE_9
- `live_model_latency` — **DEFERRED** — "DEFERRED_TO_PHASE_9" — DEFERRED_TO_PHASE_9
- `live_model_token_usage` — **DEFERRED** — "DEFERRED_TO_PHASE_9" — DEFERRED_TO_PHASE_9

## Regeneration command

```text
uv run --python 3.12 --extra dev python -m backend.app.evaluation.evidence --output-json docs/evaluations/phase8-evidence-report.json --output-markdown docs/evaluations/phase8-evidence-summary.md --runtime-repetitions 20
```
