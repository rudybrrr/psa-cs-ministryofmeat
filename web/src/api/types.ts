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

export interface TriggerResponse {
  incident_id: string;
  decision_id: string;
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

export interface IncidentSnapshot {
  incident: Incident;
  decisions: Decision[];
  auditEvents: AuditEvent[];
}
