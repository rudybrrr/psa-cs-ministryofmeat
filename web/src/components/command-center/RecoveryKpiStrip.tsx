import type { RecoverySummary } from "../../lib/recoverySelectors";

export function RecoveryKpiStrip({
  summary,
}: {
  summary: RecoverySummary | null;
  loading?: boolean;
}) {
  if (!summary) {
    return null;
  }

  return (
    <section
      aria-labelledby="recovery-kpi-heading"
      className="psa-surface rounded-[12px] px-5 py-4 sm:px-6"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="psa-label text-psa-signal">Live evaluation</p>
          <h2
            id="recovery-kpi-heading"
            className="mt-1 text-sm font-medium text-psa-snow"
          >
            Recovery capacity snapshot
          </h2>
        </div>
        <p className="text-xs text-psa-steel">
          {summary.selectedStrategy ?? "scenario-aware"} · {summary.scenarioCount} worlds
        </p>
      </div>

      <dl className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="psa-surface-nested rounded-[8px] px-3 py-3">
          <dt className="psa-label">Containers at risk</dt>
          <dd className="psa-kpi mt-1 text-psa-snow">{summary.containersAtRisk}</dd>
        </div>
        <div className="psa-surface-nested rounded-[8px] px-3 py-3">
          <dt className="psa-label">Expedite slots</dt>
          <dd className="psa-kpi mt-1 text-psa-snow">{summary.selectedExpediteSlots}</dd>
        </div>
        <div className="psa-surface-nested rounded-[8px] px-3 py-3">
          <dt className="psa-label">Expected preserved</dt>
          <dd className="psa-kpi mt-1 text-psa-signal">
            {summary.scenarioAwareExpectedPreserved?.toFixed(1) ?? "—"}
          </dd>
        </div>
        <div className="psa-surface-nested rounded-[8px] px-3 py-3">
          <dt className="psa-label">Expected rollovers</dt>
          <dd className="psa-kpi mt-1 text-psa-chalk">
            {summary.expectedRollovers?.toFixed(1) ?? "—"}
          </dd>
        </div>
      </dl>
    </section>
  );
}
