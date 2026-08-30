import type { ReactNode } from "react";
import type { AgentHistory, AgentRun } from "../../../api/types";

const waitCopy: Record<string, string> = {
  NEW_OPERATIONAL_EVIDENCE: "Waiting for updated yard forecast",
  REQUEST_APPROVAL: "Operator approval required",
  CARRIER_RESPONSE_OR_TIMEOUT: "Waiting for carrier response",
  COUNTER_APPROVAL: "Operator approval required for carrier counter",
  HUMAN_TRADEOFF_DECISION: "Operator must select one persisted feasible option",
};

export function GuidedAgentStrip({
  run,
  history,
  loading,
  canAdvance,
  onAdvance,
  onRefresh,
  yardActions,
}: {
  run: AgentRun | null;
  history: AgentHistory | null;
  loading: boolean;
  canAdvance: boolean;
  onAdvance(): void;
  onRefresh(): void;
  yardActions?: ReactNode;
}) {
  if (!run) return null;

  const latest = history?.tool_invocations.at(-1);

  return (
    <div className="psa-surface-nested space-y-3 rounded-[8px] px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="psa-label">Agent orchestration</p>
          <p className="mt-1 font-mono text-sm text-psa-snow">{run.state}</p>
          {latest ? (
            <p className="mt-1 text-xs text-psa-steel">
              Latest tool: {latest.tool_name} · {latest.status}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {yardActions}
          <button
            type="button"
            disabled={
              loading ||
              !canAdvance ||
              ["COMPLETED", "ESCALATED", "FAILED"].includes(run.state)
            }
            onClick={onAdvance}
            className="psa-btn-secondary px-3 py-2 text-xs disabled:opacity-50"
          >
            Advance agent once
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={onRefresh}
            className="psa-btn-ghost px-3 py-2 text-xs"
          >
            Refresh
          </button>
        </div>
      </div>

      {run.state === "WAITING" && run.wait_kind ? (
        <div className="rounded-[6px] border border-psa-amber/40 bg-psa-amber/10 px-3 py-3 text-sm text-psa-snow">
          <p className="font-mono text-xs text-psa-amber">{run.wait_kind}</p>
          <p className="mt-1">{waitCopy[run.wait_kind] ?? "Waiting for persisted external state"}</p>
        </div>
      ) : null}

      {run.escalation_reason ? (
        <p className="text-sm text-psa-coral">
          Escalated: {run.escalation_reason}
        </p>
      ) : null}

      <p className="text-xs text-psa-steel">
        {history?.steps.at(-1)?.action_summary ?? "No action summary persisted."}
      </p>
    </div>
  );
}
