import {
  CANONICAL_DEMO_RUNS,
  CANONICAL_DEMO_SUITE_ID,
  type CanonicalDemoRunId,
} from "../../lib/canonicalDemo";
import { connectionShortLabel, truncateId } from "../../lib/formatters";

interface SyntheticDemoControlProps {
  activeRunId: CanonicalDemoRunId | null;
  incidentId: string | null;
  loading: boolean;
  onRunDemo: (runId: CanonicalDemoRunId) => void;
  onCreateIncident: () => void;
  onRefresh: () => void;
}

export function SyntheticDemoControl({
  activeRunId,
  incidentId,
  loading,
  onRunDemo,
  onCreateIncident,
  onRefresh,
}: SyntheticDemoControlProps) {
  const activeRun = CANONICAL_DEMO_RUNS.find((run) => run.runId === activeRunId);

  return (
    <section
      aria-labelledby="demo-control-heading"
      className="rounded border border-fuchsia-500/40 bg-fuchsia-950/20 px-4 py-4"
    >
      <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-fuchsia-300">
        DEMO CONTROL
      </p>
      <h2 id="demo-control-heading" className="mt-1 text-sm font-semibold text-slate-100">
        Synthetic counterparty behavior
      </h2>
      <p className="mt-1 text-sm text-slate-400">
        Canonical carrier demo suite ({CANONICAL_DEMO_SUITE_ID}). Each run creates
        an independent canonical scarcity incident. Workflow state always comes from
        persisted backend APIs.
      </p>

      <div className="mt-4">
        <p className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
          Canonical carrier demo suite
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {CANONICAL_DEMO_RUNS.map((run) => (
            <button
              key={run.runId}
              type="button"
              disabled={loading}
              className={`rounded border px-3 py-2 font-mono text-[11px] uppercase tracking-wide disabled:opacity-50 ${
                activeRunId === run.runId
                  ? "border-fuchsia-400 bg-fuchsia-900/50 text-fuchsia-100"
                  : "border-fuchsia-500/40 text-fuchsia-100 hover:bg-fuchsia-900/30"
              }`}
              onClick={() => onRunDemo(run.runId)}
            >
              Run {run.outcome}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={onCreateIncident}
          className="rounded border border-emerald-500/60 bg-emerald-900/40 px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wide text-emerald-100 hover:bg-emerald-900/70 disabled:opacity-50"
        >
          Create canonical scarcity incident
        </button>
        {incidentId && (
          <button
            type="button"
            disabled={loading}
            onClick={onRefresh}
            className="rounded border border-slate-700 px-4 py-2 font-mono text-xs uppercase tracking-wide text-slate-300 hover:bg-slate-800 disabled:opacity-50"
          >
            Refresh persisted state
          </button>
        )}
      </div>

      {activeRun && (
        <dl className="mt-4 grid gap-2 font-mono text-xs text-slate-300 sm:grid-cols-3">
          <div>
            <dt className="text-slate-500">Active run</dt>
            <dd>{activeRun.runId}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Connection</dt>
            <dd>
              {connectionShortLabel(activeRun.connectionId)} ({activeRun.outcome})
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">Incident</dt>
            <dd>{incidentId ? truncateId(incidentId) : "—"}</dd>
          </div>
        </dl>
      )}
    </section>
  );
}
