import type {
  AuditEvent,
  Decision,
  Incident,
  IncidentSnapshot,
  TriggerResponse,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Fall back to status text when the body is not JSON.
  }

  return response.statusText || "Request failed";
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response));
  }

  return (await response.json()) as T;
}

export async function triggerScheduleDelayScenario(): Promise<TriggerResponse> {
  return request<TriggerResponse>("/synthetic/scenarios/schedule-delay", {
    method: "POST",
  });
}

export async function getIncident(incidentId: string): Promise<Incident> {
  return request<Incident>(`/incidents/${incidentId}`);
}

export async function getDecisions(incidentId: string): Promise<Decision[]> {
  return request<Decision[]>(`/incidents/${incidentId}/decisions`);
}

export async function getAuditEvents(
  incidentId: string,
): Promise<AuditEvent[]> {
  return request<AuditEvent[]>(`/incidents/${incidentId}/audit-events`);
}

export async function loadIncidentSnapshot(
  incidentId: string,
): Promise<IncidentSnapshot> {
  const [incident, decisions, auditEvents] = await Promise.all([
    getIncident(incidentId),
    getDecisions(incidentId),
    getAuditEvents(incidentId),
  ]);

  return { incident, decisions, auditEvents };
}

export async function triggerAndLoadIncidentSnapshot(): Promise<{
  trigger: TriggerResponse;
  snapshot: IncidentSnapshot;
}> {
  const trigger = await triggerScheduleDelayScenario();
  const snapshot = await loadIncidentSnapshot(trigger.incident_id);

  return { trigger, snapshot };
}
