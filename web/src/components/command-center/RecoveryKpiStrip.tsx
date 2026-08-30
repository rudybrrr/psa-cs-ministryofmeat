import type { RecoverySummary } from "../../lib/recoverySelectors";

function KpiCard({
  label,
  value,
  sublabel,
  accent,
}: {
  label: string;
  value: string;
  sublabel: string;
  accent?: "signal" | "neutral" | "warning";
}) {
  const valueClass =
    accent === "signal"
      ? "text-psa-signal"
      : accent === "warning"
        ? "text-psa-amber"
        : "text-psa-snow";

  return (
    <div className="psa-surface rounded-[10px] px-4 py-3.5">
      <p className="psa-label">{label}</p>
      <p className={`psa-kpi mt-1.5 ${valueClass}`}>{value}</p>
      <p className="mt-1.5 text-xs text-psa-steel">{sublabel}</p>
    </div>
  );
}

export function RecoveryKpiStrip({
  summary,
  emptyPlaceholder = false,
}: {
  summary: RecoverySummary | null;
  emptyPlaceholder?: boolean;
}) {
  if (emptyPlaceholder || !summary) {
    return (
      <section aria-label="Recovery KPIs" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Containers at risk" value="24" sublabel="Synthetic scenario fixture" />
        <KpiCard label="Expedite capacity" value="8" sublabel="Slots available this window" />
        <KpiCard
          label="Expected preserved"
          value="—"
          sublabel="Awaiting optimization run"
          accent="signal"
        />
        <KpiCard label="Expected rollovers" value="—" sublabel="Awaiting evaluation" />
      </section>
    );
  }

  const preservedDelta =
    summary.scenarioAwareExpectedPreserved != null
      ? `+${(summary.scenarioAwareExpectedPreserved - summary.baselineExpectedPreserved).toFixed(1)} vs baseline`
      : "Scenario-aware pending";

  return (
    <section aria-label="Recovery KPIs" className="space-y-3">
      <p className="psa-label text-psa-signal">Live evaluation</p>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard
        label="Containers at risk"
        value={String(summary.containersAtRisk)}
        sublabel={`${summary.scenarioCount} scenario worlds`}
      />
      <KpiCard
        label="Expedite capacity"
        value={String(summary.selectedExpediteSlots)}
        sublabel={summary.selectedStrategy ?? "allocation pending"}
      />
      <KpiCard
        label="Expected preserved"
        value={summary.scenarioAwareExpectedPreserved?.toFixed(1) ?? "—"}
        sublabel={preservedDelta}
        accent="signal"
      />
      <KpiCard
        label="Expected rollovers"
        value={summary.expectedRollovers?.toFixed(1) ?? "—"}
        sublabel="Post-allocation forecast"
        accent={summary.expectedRollovers != null && summary.expectedRollovers > 3 ? "warning" : "neutral"}
      />
    </div>
    </section>
  );
}
