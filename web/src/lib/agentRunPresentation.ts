const AGENT_STATE_LABELS: Record<string, string> = {
  CREATED: "Created",
  RUNNING: "Running",
  WAITING: "Waiting",
  COMPLETED: "Completed",
  ESCALATED: "Escalated",
  FAILED: "Failed",
};

export function agentStateLabel(state: string): string {
  return AGENT_STATE_LABELS[state] ?? state.replaceAll("_", " ").toLowerCase();
}
