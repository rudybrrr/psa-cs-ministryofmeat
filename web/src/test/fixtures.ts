import type { AuditEvent, Decision, Incident } from "../api/types";

export const sampleIncident: Incident = {
  id: "aaaaaaaa-bbbb-4ccc-dddd-eeeeeeeeeeee",
  source_event_id: "SYN-EVT-20260821-001",
  state: "RESOLVED",
  created_at: "2026-08-21T10:15:00+08:00",
};

export const sampleDecision: Decision = {
  id: "bbbbbbbb-cccc-4ddd-eeee-ffffffffffff",
  incident_id: sampleIncident.id,
  container_id: "PSAU1234567",
  action: "EXPEDITE",
  status: "APPROVED",
  rationale:
    "Normal transfer misses the synthetic cutoff; expedited handling preserves the onward connection.",
  supersedes: null,
  supersession_reason: null,
  created_at: "2026-08-21T10:16:00+08:00",
};

export const sampleAuditEvents: AuditEvent[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    actor: "SYSTEM",
    actor_id: "synthetic-schedule-service",
    incident_id: sampleIncident.id,
    event_type: "schedule.delay_ingested",
    payload: {
      event_id: "SYN-EVT-20260821-001",
      delay_minutes: 90,
    },
    timestamp: "2026-08-21T10:15:01+08:00",
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    actor: "POLICY",
    actor_id: "connection-feasibility-policy",
    incident_id: sampleIncident.id,
    event_type: "connection.feasibility_evaluated",
    payload: {
      container_id: "PSAU1234567",
      feasible: true,
    },
    timestamp: "2026-08-21T10:15:45+08:00",
  },
  {
    id: "33333333-3333-4333-8333-333333333333",
    actor: "POLICY",
    actor_id: "dominance-policy",
    incident_id: sampleIncident.id,
    event_type: "decision.created",
    payload: {
      action: "EXPEDITE",
      container_id: "PSAU1234567",
    },
    timestamp: "2026-08-21T10:16:00+08:00",
  },
];

export function jsonResponse<T>(body: T, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
