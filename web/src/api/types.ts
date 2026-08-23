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
