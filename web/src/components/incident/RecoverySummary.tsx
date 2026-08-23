import type { RecoverySummary } from "../../lib/recoverySelectors";
import { truncateId } from "../../lib/formatters";

interface RecoverySummaryProps {
  summary: RecoverySummary | null;
  fixtureId: string | null;
  loading?: boolean;
}

export function RecoverySummaryPanel({
  summary,
  fixtureId,
  loading = false,
}: RecoverySummaryProps) {
  if (!summary) {
    return (
      <section className="rounded border border-slate-800 bg-slate-950/60 px-4 py-4">
        <h2 className="text-sm font-semibold text-slate-100">Recovery summary</h2>
        <p className="mt-2 text-sm text-slate-500">
          {loading
            ? "Loading persisted scarcity evaluation…"
            : "Create a canonical scarcity incident to load live recovery evidence."}
        </p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="recovery-summary-heading"
      className="rounded border border-emerald-500/20 bg-slate-950/60 px-4 py-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-emerald-300">
            LIVE EVALUATION
          </p>
          <h2 id="recovery-summary-heading" className="mt-1 text-sm font-semibold text-slate-100">
            Recovery summary
          </h2>
        </div>
        <p className="font-mono text-[11px] text-slate-500">
          {fixtureId} · {summary.selectedStrategy ?? "no selection"}
        </p>
      </div>

      <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
            Containers at risk
          </dt>
          <dd className="mt-1 font-mono text-lg text-slate-100">
            {summary.containersAtRisk}
          </dd>
        </div>
        <div>
          <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
            Baseline expected preserved
          </dt>
          <dd className="mt-1 font-mono text-lg text-slate-100">
            {summary.baselineExpectedPreserved.toFixed(1)}
          </dd>
        </div>
        <div>
          <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
            Scenario-aware expected preserved
          </dt>
          <dd className="mt-1 font-mono text-lg text-emerald-100">
            {summary.scenarioAwareExpectedPreserved?.toFixed(1) ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
            Expected rollovers
          </dt>
          <dd className="mt-1 font-mono text-lg text-amber-100">
            {summary.expectedRollovers?.toFixed(1) ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
            Selected expedite slots
          </dt>
          <dd className="mt-1 font-mono text-lg text-slate-100">
            {summary.selectedExpediteSlots}
          </dd>
        </div>
        <div>
          <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
            Scenario count
          </dt>
          <dd className="mt-1 font-mono text-lg text-slate-100">
            {summary.scenarioCount}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
            Reproducibility key
          </dt>
          <dd className="mt-1 font-mono text-xs text-slate-300">
            {truncateId(summary.reproducibilityKey, 12)}
          </dd>
        </div>
      </dl>
    </section>
  );
}
