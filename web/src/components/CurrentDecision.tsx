import type { Decision } from "../api/types";
import { formatTimestamp } from "../lib/format";

interface CurrentDecisionProps {
  decisions: Decision[];
  highlightDecisionId: string | null;
  loading: boolean;
}

function DecisionTable({
  decisions,
  highlightDecisionId,
}: {
  decisions: Decision[];
  highlightDecisionId: string | null;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-left font-mono text-[11px] uppercase tracking-wide text-slate-500">
            <th className="px-3 py-2 font-normal">Container</th>
            <th className="px-3 py-2 font-normal">Action</th>
            <th className="px-3 py-2 font-normal">Status</th>
            <th className="px-3 py-2 font-normal">Rationale</th>
            <th className="px-3 py-2 font-normal">Recorded</th>
          </tr>
        </thead>
        <tbody>
          {decisions.map((decision) => {
            const highlighted = decision.id === highlightDecisionId;

            return (
              <tr
                key={decision.id}
                className={`border-b border-slate-900/80 ${
                  highlighted ? "bg-emerald-950/30" : ""
                }`}
              >
                <td className="px-3 py-3 font-mono text-slate-200">
                  {decision.container_id ?? "—"}
                </td>
                <td className="px-3 py-3 font-mono text-emerald-200">
                  {decision.action}
                </td>
                <td className="px-3 py-3 font-mono text-slate-300">
                  {decision.status}
                </td>
                <td className="max-w-xl px-3 py-3 text-slate-300">
                  {decision.rationale}
                </td>
                <td className="px-3 py-3 whitespace-nowrap text-slate-400">
                  {formatTimestamp(decision.created_at)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function CurrentDecision({
  decisions,
  highlightDecisionId,
  loading,
}: CurrentDecisionProps) {
  return (
    <section className="rounded border border-slate-800 bg-slate-950/60">
      <div className="border-b border-slate-800 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-100">
          Current recovery decisions
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Persisted backend policy output — not inferred by the UI.
        </p>
      </div>

      {loading && (
        <p className="px-4 py-6 font-mono text-sm text-slate-400">
          Loading decisions…
        </p>
      )}

      {!loading && decisions.length === 0 && (
        <p className="px-4 py-6 text-sm text-slate-500">
          No decisions recorded for this incident yet.
        </p>
      )}

      {!loading && decisions.length > 0 && (
        <DecisionTable
          decisions={decisions}
          highlightDecisionId={highlightDecisionId}
        />
      )}
    </section>
  );
}
