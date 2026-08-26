export const IncidentState = {
  INCIDENT_RECEIVED: "INCIDENT_RECEIVED",
  COLLECTING_STATE: "COLLECTING_STATE",
  CONSTRAINT_VALIDATION: "CONSTRAINT_VALIDATION",
  RECOVERY_ANALYSIS: "RECOVERY_ANALYSIS",
  RESOLVED: "RESOLVED",
  ESCALATED: "ESCALATED",
} as const;

export type IncidentState =
  (typeof IncidentState)[keyof typeof IncidentState];

export const DecisionAction = {
  EXPEDITE: "EXPEDITE",
  REQUEST_RTA: "REQUEST_RTA",
  ROLL: "ROLL",
  ESCALATE: "ESCALATE",
  PRESERVE_VIA_RTA: "PRESERVE_VIA_RTA",
} as const;

export type DecisionAction =
  (typeof DecisionAction)[keyof typeof DecisionAction];

export const DecisionStatus = {
  PROPOSED: "PROPOSED",
  APPROVED: "APPROVED",
  REJECTED: "REJECTED",
  SUPERSEDED: "SUPERSEDED",
} as const;

export type DecisionStatus =
  (typeof DecisionStatus)[keyof typeof DecisionStatus];

export const AuditActor = {
  AGENT: "AGENT",
  SOLVER: "SOLVER",
  POLICY: "POLICY",
  OPERATOR: "OPERATOR",
  CARRIER: "CARRIER",
  SYSTEM: "SYSTEM",
} as const;

export type AuditActor = (typeof AuditActor)[keyof typeof AuditActor];

export const AllocationStrategy = {
  P50_GREEDY: "P50_GREEDY",
  SCENARIO_AWARE: "SCENARIO_AWARE",
} as const;

export type AllocationStrategy =
  (typeof AllocationStrategy)[keyof typeof AllocationStrategy];

export const CarrierRecoveryCaseState = {
  PREPARED: "PREPARED",
  AWAITING_REQUEST_APPROVAL: "AWAITING_REQUEST_APPROVAL",
  AWAITING_CARRIER: "AWAITING_CARRIER",
  AWAITING_COUNTER_APPROVAL: "AWAITING_COUNTER_APPROVAL",
  RECOMPUTING: "RECOMPUTING",
  COMPLETED: "COMPLETED",
  ESCALATED: "ESCALATED",
} as const;

export type CarrierRecoveryCaseState =
  (typeof CarrierRecoveryCaseState)[keyof typeof CarrierRecoveryCaseState];

export const ApprovalStatus = {
  APPROVED: "APPROVED",
  REJECTED: "REJECTED",
} as const;

export type ApprovalStatus =
  (typeof ApprovalStatus)[keyof typeof ApprovalStatus];

export const CarrierResponseType = {
  ACCEPT: "ACCEPT",
  COUNTER: "COUNTER",
} as const;

export type CarrierResponseType =
  (typeof CarrierResponseType)[keyof typeof CarrierResponseType];

export const RTARequestStatus = {
  PENDING: "PENDING",
  SENT: "SENT",
  CLOSED: "CLOSED",
} as const;

export type RTARequestStatus =
  (typeof RTARequestStatus)[keyof typeof RTARequestStatus];

export const AuthorizationSubjectKind = {
  OUTBOUND_REQUEST: "OUTBOUND_REQUEST",
  COUNTER_PROPOSAL: "COUNTER_PROPOSAL",
} as const;

export type AuthorizationSubjectKind =
  (typeof AuthorizationSubjectKind)[keyof typeof AuthorizationSubjectKind];

export const CarrierRecoveryDisposition = {
  PRESERVED_VIA_RTA: "PRESERVED_VIA_RTA",
  STILL_ROLL: "STILL_ROLL",
  ESCALATE: "ESCALATE",
} as const;

export type CarrierRecoveryDisposition =
  (typeof CarrierRecoveryDisposition)[keyof typeof CarrierRecoveryDisposition];

export const ReconsiderationEvidenceKind = {
  EFFECTIVE_CONNECTION_TIMING: "EFFECTIVE_CONNECTION_TIMING",
  REQUEST_REJECTED: "REQUEST_REJECTED",
  COUNTER_REJECTED: "COUNTER_REJECTED",
  RESPONSE_TIMEOUT: "RESPONSE_TIMEOUT",
} as const;

export type ReconsiderationEvidenceKind =
  (typeof ReconsiderationEvidenceKind)[keyof typeof ReconsiderationEvidenceKind];

export const EffectiveTimingSourceKind = {
  ACCEPT: "ACCEPT",
  APPROVED_COUNTER: "APPROVED_COUNTER",
} as const;

export type EffectiveTimingSourceKind =
  (typeof EffectiveTimingSourceKind)[keyof typeof EffectiveTimingSourceKind];

export const RequestCloseReason = {
  REQUEST_REJECTED: "REQUEST_REJECTED",
  RESPONSE_TIMEOUT: "RESPONSE_TIMEOUT",
} as const;

export type RequestCloseReason =
  (typeof RequestCloseReason)[keyof typeof RequestCloseReason];

export const CargoKind = {
  DRY: "DRY",
  REEFER: "REEFER",
  DG: "DG",
} as const;

export type CargoKind = (typeof CargoKind)[keyof typeof CargoKind];

export interface TriggerResponse {
  incident_id: string;
  decision_id: string;
}

export interface ScarcityTriggerResponse {
  incident_id: string;
  evaluation_id: string;
  decision_ids: string[];
  reproducibility_key: string;
}

export interface Incident {
  id: string;
  source_event_id: string;
  state: IncidentState;
  created_at: string;
}

export interface Decision {
  id: string;
  incident_id: string;
  container_id: string | null;
  action: DecisionAction;
  status: DecisionStatus;
  rationale: string;
  supersedes: string | null;
  supersession_reason: string | null;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  actor: AuditActor;
  actor_id: string | null;
  incident_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

export interface Approval {
  id: string;
  decision_id: string;
  operator_id: string;
  status: ApprovalStatus;
  reason: string | null;
  created_at: string;
}

export interface Connection {
  id: string;
  outbound_vessel_name: string;
  outbound_voyage: string;
  destination_port: string;
  cutoff_at: string;
  departure_at: string;
  minimum_transfer_minutes: number;
  expedited_transfer_minutes: number;
}

export interface CargoProfile {
  commodity: string;
  gross_weight_kg: number;
  dangerous_goods: boolean;
  un_number: string | null;
}

export interface Container {
  id: string;
  origin_port: string;
  destination_port: string;
  cargo: CargoProfile;
  inbound_vessel_call_id: string;
  onward_connection: Connection;
}

export interface ScheduleEvent {
  id: string;
  vessel_call_id: string;
  vessel_name: string;
  terminal_id: string;
  scheduled_arrival: string;
  estimated_arrival: string;
  delay_minutes: number;
  occurred_at: string;
}

export interface ServiceWindow {
  service_id: string;
  connection: Connection;
  planned_time_of_arrival: string;
  ready_boundary: string;
}

export interface ContainerRecoveryProfile {
  container: Container;
  service_id: string;
  handling_group_id: string;
  cargo_kind: CargoKind;
  base_ready_at: string;
  expedite_minutes_saved: number;
  reefer_continuity_available: boolean;
  dg_structurally_cleared: boolean;
}

export interface HandlingGroupLimit {
  handling_group_id: string;
  slots: number;
}

export interface ExpediteCapacityPlan {
  id: string;
  terminal_id: string;
  window_start: string;
  window_end: string;
  overlap_service_ids: string[];
  total_slots: number;
  handling_group_limits: HandlingGroupLimit[];
  max_reefer_slots: number;
  max_dg_slots: number;
}

export interface CanonicalIncidentFixture {
  fixture_id: string;
  event: ScheduleEvent;
  services: ServiceWindow[];
  profiles: ContainerRecoveryProfile[];
  capacity: ExpediteCapacityPlan;
}

export interface AllocationPlan {
  strategy: AllocationStrategy;
  allocated_container_ids: string[];
}

export interface ServiceOutcome {
  service_id: string;
  preserved_connection_total: number;
}

export interface StrategyEvaluation {
  allocation: AllocationPlan;
  world_count: number;
  preserved_connection_total: number;
  expected_preserved_connections: number;
  rollover_total: number;
  expected_rollovers: number;
  p10_preserved_connections: number;
  allocation_slot_count: number;
  capacity_violations: number;
  unsafe_allocations: number;
  runtime_ms: number;
  service_outcomes: ServiceOutcome[];
}

export interface ScarcityEvaluationReport {
  id: string;
  incident_id: string;
  fixture_id: string;
  seed: number;
  scenario_count: number;
  baseline: StrategyEvaluation;
  scenario_aware_evaluations: StrategyEvaluation[];
  pareto_evaluations: StrategyEvaluation[];
  selected_allocation: AllocationPlan | null;
  reproducibility_key: string;
  created_at: string;
}

export interface CarrierRecoveryCase {
  id: string;
  incident_id: string;
  connection_id: string;
  source_evaluation_id: string;
  affected_container_ids: string[];
  state: CarrierRecoveryCaseState;
  created_at: string;
  updated_at: string;
}

export interface RTARequest {
  id: string;
  incident_id: string;
  connection_id: string;
  requested_eta_pta: string;
  status: RTARequestStatus;
  created_at: string;
}

export interface RTARequestContext {
  case_id: string;
  request_id: string;
  payload_fingerprint: string;
  prepared_at: string;
  response_deadline: string;
  sent_at: string | null;
  closed_at: string | null;
  close_reason: RequestCloseReason | null;
  timeout_observed_at: string | null;
}

export interface CarrierResponse {
  id: string;
  request_id: string;
  carrier_id: string;
  response: CarrierResponseType;
  counter_eta_pta: string | null;
  message: string | null;
  received_at: string;
}

export interface ApprovalBinding {
  case_id: string;
  proposal_decision_id: string;
  subject_kind: AuthorizationSubjectKind;
  subject_id: string;
  payload_fingerprint: string;
  created_at: string;
}

export interface EffectiveConnectionTiming {
  id: string;
  case_id: string;
  request_id: string;
  carrier_response_id: string;
  source_kind: EffectiveTimingSourceKind;
  effective_eta_pta: string;
  created_at: string;
}

export interface CarrierRecoveryDecisionLink {
  case_id: string;
  decision_id: string;
  role: string;
  created_at: string;
}

export interface ContainerReconsiderationResult {
  id: string;
  case_id: string;
  container_id: string;
  disposition: CarrierRecoveryDisposition;
  prior_decision_id: string;
  replacement_decision_id: string | null;
  preserved_world_count: number;
  world_count: number;
  hard_constraints_satisfied: boolean;
  reconsideration_evidence_kind: ReconsiderationEvidenceKind;
  effective_connection_timing_id: string | null;
  rejected_approval_id: string | null;
  timeout_request_context_id: string | null;
  created_at: string;
}

export interface CarrierSimulationResult {
  case_id: string;
  carrier_response_id: string | null;
  no_response_emitted: boolean;
}

export interface CarrierRecoveryHistory {
  case: CarrierRecoveryCase;
  request: RTARequest | null;
  request_context: RTARequestContext | null;
  bindings: ApprovalBinding[];
  approvals: Approval[];
  carrier_responses: CarrierResponse[];
  effective_timings: EffectiveConnectionTiming[];
  decision_links: CarrierRecoveryDecisionLink[];
  decisions: Decision[];
  results: ContainerReconsiderationResult[];
  audit_events: AuditEvent[];
}

export interface PrepareCarrierRecoveryBody {
  connection_id: string;
  prepared_at: string;
  requested_eta_pta: string;
  response_deadline: string;
}

export interface RequestApprovalBody {
  proposal_decision_id: string;
  request_id: string;
  expected_payload_fingerprint: string;
  operator_id: string;
  status: ApprovalStatus;
}

export interface CounterApprovalBody {
  proposal_decision_id: string;
  carrier_response_id: string;
  expected_payload_fingerprint: string;
  operator_id: string;
  status: ApprovalStatus;
}

export interface EffectiveAtBody {
  effective_at: string;
}

export interface IncidentSnapshot {
  incident: Incident;
  decisions: Decision[];
  auditEvents: AuditEvent[];
}

export interface RecoveryConsoleSnapshot {
  incident: Incident;
  fixture: CanonicalIncidentFixture;
  scarcityEvaluation: ScarcityEvaluationReport;
  decisions: Decision[];
  auditEvents: AuditEvent[];
  carrierCases: CarrierRecoveryCase[];
}

export const AgentRunState = { CREATED: "CREATED", RUNNING: "RUNNING", WAITING: "WAITING", COMPLETED: "COMPLETED", ESCALATED: "ESCALATED", FAILED: "FAILED" } as const;
export type AgentRunState = (typeof AgentRunState)[keyof typeof AgentRunState];
export const AgentWaitKind = { REQUEST_APPROVAL: "REQUEST_APPROVAL", COUNTER_APPROVAL: "COUNTER_APPROVAL", CARRIER_RESPONSE_OR_TIMEOUT: "CARRIER_RESPONSE_OR_TIMEOUT", NEW_OPERATIONAL_EVIDENCE: "NEW_OPERATIONAL_EVIDENCE", HUMAN_TRADEOFF_DECISION: "HUMAN_TRADEOFF_DECISION" } as const;
export type AgentWaitKind = (typeof AgentWaitKind)[keyof typeof AgentWaitKind];
export interface AgentRun { id: string; incident_id: string; state: AgentRunState; model_name: string; prompt_version: string; step_count: number; max_steps: number; wait_kind: AgentWaitKind | null; wait_subject_id: string | null; escalation_reason: string | null; started_at: string; updated_at: string; completed_at: string | null; }
export interface AgentStep { id: string; run_id: string; step_number: number; kind: string; action_summary: string; evidence_refs: string[]; model_name: string; prompt_version: string; latency_ms: number | null; input_tokens: number | null; output_tokens: number | null; created_at: string; }
export interface AgentToolInvocation { id: string; run_id: string; step_id: string; tool_name: string; arguments: Record<string, unknown>; status: string; result_summary: string | null; error_kind: string | null; started_at: string; completed_at: string | null; }
export interface AgentHistory { run: AgentRun; steps: AgentStep[]; tool_invocations: AgentToolInvocation[]; }
export interface ContainerReadyForecast { container_id: string; p10_ready_at: string; p50_ready_at: string; p90_ready_at: string; }
export interface YardForecastSnapshot { id: string; incident_id: string; stage: "PRE_DISCHARGE" | "DISCHARGE_ACTIVE"; generated_at: string; source: string; container_forecasts: ContainerReadyForecast[]; }
export interface AllocationRevision { id: string; incident_id: string; source_phase2_evaluation_id: string; source_forecast_snapshot_id: string; parent_revision_id: string | null; allocated_container_ids: string[]; locked_container_ids: string[]; preserved_connection_total: number; expected_preserved_connections: number; reason: string; created_at: string; }
export interface ExpediteCommitment { id: string; incident_id: string; origin_revision_id: string; container_id: string; status: "PLANNED" | "COMMITTED" | "EXECUTED" | "CANCELLED"; created_at: string; updated_at: string; }
export interface ExpediteReconsiderationAssessment { id: string; incident_id: string; source_snapshot_id: string; prior_allocation_revision_id: string; locked_container_ids: string[]; candidate_options: Array<{ id: string; allocated_container_ids: string[]; preserved_connection_total: number; expected_preserved_connections: number }>; preserved_connection_total_before: number; preserved_connection_total_after: number; expected_preserved_connections_before: number; expected_preserved_connections_after: number; disposition: string; reason: string; handled_at: string | null; created_at: string; }
export interface AllocationTradeoffReview { id: string; incident_id: string; reconsideration_assessment_id: string; option_ids: string[]; options_fingerprint: string; state: "OPEN" | "RESOLVED"; created_at: string; }
export interface AllocationTradeoffOption { id: string; review_id: string; allocated_container_ids: string[]; preserved_connection_total: number; expected_preserved_connections: number; }
export interface AllocationTradeoffSelectionBody { selected_option_id: string; expected_options_fingerprint: string; operator_id: string; }
export interface CargoSafetyReview { id: string; incident_id: string; container_id: string; cargo_note_id: string; state: "PENDING_CHECK" | "COMPLETED"; created_at: string; updated_at: string; }
export interface CargoNote { id: string; incident_id: string; container_id: string; text: string; source: string; created_at: string; }
export interface SemanticSafetyAssessment { id: string; review_id: string; incident_id: string; container_id: string; cargo_note_id: string; result: string; explanation: string; evidence_excerpt: string | null; failure_kind: string | null; structured_dangerous_goods: boolean; structured_un_number: string | null; structured_commodity: string; checker_kind: string; model_name: string | null; prompt_version: string; latency_ms: number | null; input_tokens: number | null; output_tokens: number | null; created_at: string; }
export interface SemanticSafetyPolicyResult { id: string; review_id: string; assessment_id: string; incident_id: string; container_id: string; disposition: string; automation_blocked: boolean; reason: string; replacement_decision_id: string | null; created_at: string; }
export interface CargoSafetyEvaluationResult { review: CargoSafetyReview; assessment: SemanticSafetyAssessment; policy_result: SemanticSafetyPolicyResult; decision: Decision | null; }
export interface CargoSafetyHistory { review: CargoSafetyReview; note: CargoNote; assessment: SemanticSafetyAssessment | null; policy_result: SemanticSafetyPolicyResult | null; audit_events: AuditEvent[]; }

export const CanonicalReplayStage = {
  READY_TO_CREATE: "READY_TO_CREATE",
  READY_FOR_PRE_DISCHARGE: "READY_FOR_PRE_DISCHARGE",
  READY_TO_START_AGENT: "READY_TO_START_AGENT",
  READY_TO_ADVANCE_TO_EVIDENCE_WAIT: "READY_TO_ADVANCE_TO_EVIDENCE_WAIT",
  WAITING_FOR_ACTIVE_EVIDENCE: "WAITING_FOR_ACTIVE_EVIDENCE",
  READY_TO_RECONSIDER: "READY_TO_RECONSIDER",
  READY_TO_PREPARE_RTA: "READY_TO_PREPARE_RTA",
  REQUEST_APPROVAL_REQUIRED: "REQUEST_APPROVAL_REQUIRED",
  REQUEST_APPROVED_READY_TO_SEND: "REQUEST_APPROVED_READY_TO_SEND",
  WAITING_FOR_CARRIER: "WAITING_FOR_CARRIER",
  CARRIER_COUNTER_RECEIVED: "CARRIER_COUNTER_RECEIVED",
  COUNTER_APPROVAL_REQUIRED: "COUNTER_APPROVAL_REQUIRED",
  COUNTER_APPROVED_READY_TO_RESUME: "COUNTER_APPROVED_READY_TO_RESUME",
  READY_FOR_SAFETY_EVIDENCE: "READY_FOR_SAFETY_EVIDENCE",
  SAFETY_REVIEW_PENDING: "SAFETY_REVIEW_PENDING",
  SAFETY_BLOCKED: "SAFETY_BLOCKED",
  COMPLETE: "COMPLETE",
  FAILED: "FAILED",
  TRADEOFF_DECISION_REQUIRED: "TRADEOFF_DECISION_REQUIRED",
  OFF_CANONICAL_PATH: "OFF_CANONICAL_PATH",
} as const;
export type CanonicalReplayStage =
  (typeof CanonicalReplayStage)[keyof typeof CanonicalReplayStage];

export const CanonicalReplayStatus = {
  PENDING_ACTION: "PENDING_ACTION",
  WAITING_HUMAN: "WAITING_HUMAN",
  WAITING_EXTERNAL: "WAITING_EXTERNAL",
  TERMINAL_SUCCESS: "TERMINAL_SUCCESS",
  TERMINAL_HALTED: "TERMINAL_HALTED",
} as const;
export type CanonicalReplayStatus =
  (typeof CanonicalReplayStatus)[keyof typeof CanonicalReplayStatus];

export const CanonicalReplayActionType = {
  CREATE_CANONICAL_INCIDENT: "CREATE_CANONICAL_INCIDENT",
  BOOTSTRAP_PRE_DISCHARGE: "BOOTSTRAP_PRE_DISCHARGE",
  START_DEMO_AGENT_RUN: "START_DEMO_AGENT_RUN",
  ADVANCE_AGENT: "ADVANCE_AGENT",
  PUBLISH_DISCHARGE_ACTIVE: "PUBLISH_DISCHARGE_ACTIVE",
  SIMULATE_CARRIER_RESPONSE: "SIMULATE_CARRIER_RESPONSE",
  APPROVE_REQUEST: "APPROVE_REQUEST",
  APPROVE_COUNTER: "APPROVE_COUNTER",
  PERSIST_SAFETY_REVIEW: "PERSIST_SAFETY_REVIEW",
  SELECT_TRADEOFF_OPTION: "SELECT_TRADEOFF_OPTION",
  NONE: "NONE",
} as const;
export type CanonicalReplayActionType =
  (typeof CanonicalReplayActionType)[keyof typeof CanonicalReplayActionType];

export interface CanonicalReplayStageView {
  stage: CanonicalReplayStage;
  ordinal: number;
  progress_label: string;
  status: CanonicalReplayStatus;
  explanation: string;
  next_allowed_action: CanonicalReplayActionType;
  guided_can_execute: boolean;
  auto_replay_may_execute: boolean;
  requires_human_authority: boolean;
  deviation_reason: string | null;
}
