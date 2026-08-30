import type { ReactNode } from "react";
import type { AgentHistory, AgentRun } from "../../../api/types";
import { agentStateLabel } from "../../../lib/agentRunPresentation";
import { waitKindPresentation } from "../../../lib/waitKindCopy";

export function GuidedAgentStrip({
  run,
  history,
  loading,
  canAdvance,
  onAdvance,
  onRefresh,
  yardActions,
  guided = false,
}: {
  run: AgentRun | null;
  history: AgentHistory | null;
  loading: boolean;
  canAdvance: boolean;
  onAdvance(): void;
  onRefresh(): void;
  yardActions?: ReactNode;
  guided?: boolean;
}) {
  if (!run) return null;

  const latest = history?.tool_invocations.at(-1);
  const showControls = !guided;
  const waiting = waitKindPresentation(run.wait_kind);

  if (guided && run.state !== "WAITING" && !run.escalation_reason && !latest) {
    return null;
  }

  return (
    <div className="border-t border-white/8 pt-4">
      {run.state === "WAITING" && waiting ? (
        <>
          <p className="text-xs font-medium text-psa-amber">{waiting.label}</p>
          <p className="mt-1 text-sm text-psa-chalk">{waiting.detail}</p>
        </>
      ) : (
        <>
          <p className="psa-meta">Agent status</p>
          <p className="mt-1 text-sm text-psa-snow">{agentStateLabel(run.state)}</p>
        </>
      )}

      {latest && !guided ? (
        <p className="mt-1 text-xs text-psa-steel">
          Latest tool: {latest.tool_name} · {latest.status}
        </p>
      ) : null}

      {run.escalation_reason ? (
        <p className="mt-2 text-sm text-psa-coral">Escalated: {run.escalation_reason}</p>
      ) : null}

      {showControls ? (
        <div className="mt-3 flex flex-wrap gap-2">
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
      ) : null}

      {!guided && history?.steps.at(-1)?.action_summary ? (
        <p className="mt-2 text-xs text-psa-steel">{history.steps.at(-1)?.action_summary}</p>
      ) : null}
    </div>
  );
}
