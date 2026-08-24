import { request } from "./client";
import type { AgentHistory, AgentRun } from "./types";
export const createAgentRun = (incidentId: string) => request<AgentRun>(`/incidents/${incidentId}/agent-runs`, { method: "POST" });
export const advanceAgentRun = (runId: string) => request<AgentRun>(`/agent-runs/${runId}/advance`, { method: "POST" });
export const listAgentRuns = (incidentId: string) => request<AgentRun[]>(`/incidents/${incidentId}/agent-runs`);
export const getAgentRunHistory = (runId: string) => request<AgentHistory>(`/agent-runs/${runId}/history`);
