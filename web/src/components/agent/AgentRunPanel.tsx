import type { AgentHistory, AgentRun } from "../../api/types";
import { truncateId } from "../../lib/formatters";

const waitCopy: Record<string, string> = {
  NEW_OPERATIONAL_EVIDENCE: "Waiting for updated yard forecast",
  REQUEST_APPROVAL: "Operator approval required",
  CARRIER_RESPONSE_OR_TIMEOUT: "Waiting for carrier response",
  COUNTER_APPROVAL: "Operator approval required for carrier counter",
  HUMAN_TRADEOFF_DECISION: "Operator must select one persisted feasible option",
};

export function AgentRunPanel({
  run,
  history,
  loading,
  canAdvance,
  onStart,
  onAdvance,
  onRefresh,
}: {
  run: AgentRun | null;
  history: AgentHistory | null;
  loading: boolean;
  canAdvance: boolean;
  onStart(): void;
  onAdvance(): void;
  onRefresh(): void;
}) {
  const latest = history?.tool_invocations.at(-1);

  return (
    <section className="psa-surface rounded-[10px] p-4">
      <p className="psa-label">Durable agent orchestration</p>
      <h2 className="mt-1 text-sm font-semibold text-psa-snow">AgentRun</h2>
      {run ? (
        <>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div>
              <dt className="text-psa-steel">Run</dt>
              <dd className="font-mono text-psa-chalk">{truncateId(run.id)}</dd>
            </div>
            <div>
              <dt className="text-psa-steel">State</dt>
              <dd className="text-psa-chalk">{run.state}</dd>
            </div>
            <div>
              <dt className="text-psa-steel">Steps</dt>
              <dd className="text-psa-chalk">
                {run.step_count} / {run.max_steps}
              </dd>
            </div>
            <div>
              <dt className="text-psa-steel">Latest tool</dt>
              <dd className="text-psa-chalk">
                {latest ? `${latest.tool_name} · ${latest.status}` : "—"}
              </dd>
            </div>
          </dl>
          {run.state === "WAITING" && run.wait_kind ? (
            <div className="mt-3 rounded-[6px] border border-psa-amber/40 bg-psa-amber/10 p-3 text-psa-snow">
              <b className="font-mono text-xs">{run.wait_kind}</b>
              <p className="mt-1 text-sm">
                {waitCopy[run.wait_kind] ?? "Waiting for persisted external state"}
              </p>
            </div>
          ) : null}
          {run.escalation_reason ? (
            <p className="mt-3 text-sm text-psa-coral">
              Escalated: {run.escalation_reason}
            </p>
          ) : null}
          <p className="mt-3 text-xs text-psa-steel">
            {history?.steps.at(-1)?.action_summary ?? "No action summary persisted."}
          </p>
          <div className="mt-3 flex gap-2">
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
        </>
      ) : (
        <div className="mt-3">
          <p className="text-sm text-psa-fog">No persisted AgentRun.</p>
          <button
            type="button"
            disabled={loading}
            onClick={onStart}
            className="psa-btn-secondary mt-2 px-3 py-2 text-xs"
          >
            Start agent
          </button>
        </div>
      )}
    </section>
  );
}
