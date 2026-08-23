import type { Decision } from "../../api/types";
import { buildDecisionLineage } from "../../lib/recoverySelectors";
import { formatActionLabel } from "../../lib/formatters";

interface DecisionLineageProps {
  decisionId: string | null;
  decisions: Decision[];
}

export function DecisionLineage({ decisionId, decisions }: DecisionLineageProps) {
  if (!decisionId) {
    return null;
  }

  const lineage = buildDecisionLineage(decisionId, decisions);
  if (lineage.length <= 1) {
    return null;
  }

  return (
    <div className="rounded border border-slate-800 bg-slate-950/70 px-3 py-3">
      <h4 className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
        Decision lineage
      </h4>
      <ol className="mt-2 space-y-2">
        {lineage.map((decision, index) => (
          <li key={decision.id} className="font-mono text-xs text-slate-200">
            {index > 0 && (
              <span className="mb-1 block text-[10px] uppercase tracking-wide text-slate-500">
                ↓ superseded
              </span>
            )}
            <span>{formatActionLabel(decision.action)}</span>
            <span className="ml-2 text-slate-500">{decision.status}</span>
            {decision.supersession_reason && (
              <span className="mt-1 block text-slate-400">
                {decision.supersession_reason}
              </span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
