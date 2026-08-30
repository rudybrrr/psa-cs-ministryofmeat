import { useKpiCountUp } from "../../hooks/useChapterMotion";
import type { RecoverySummary } from "../../lib/recoverySelectors";

function AnimatedKpiValue({
  value,
  className,
}: {
  value: string;
  className?: string;
}) {
  const { ref, initialDisplay } = useKpiCountUp(value);

  return (
    <p ref={ref} className={className}>
      {initialDisplay}
    </p>
  );
}

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
    <div className="psa-surface rounded-[10px] px-4 py-4">
      <p className="psa-meta">{label}</p>
      <AnimatedKpiValue value={value} className={`psa-kpi mt-2 ${valueClass}`} />
      <p className="mt-1.5 text-xs text-psa-steel">{sublabel}</p>
    </div>
  );
}

function CompactKpi({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: "signal" | "warning";
}) {
  const valueClass =
    accent === "signal"
      ? "text-psa-signal"
      : accent === "warning"
        ? "text-psa-amber"
        : "text-psa-snow";

  return (
    <div className="min-w-0 px-3 py-3 sm:px-4">
      <p className="psa-meta truncate">{label}</p>
      <AnimatedKpiValue
        value={value}
        className={`psa-kpi mt-1 text-xl sm:text-2xl ${valueClass}`}
      />
    </div>
  );
}

export function RecoveryKpiStrip({
  summary,
  emptyPlaceholder = false,
  compact = false,
}: {
  summary: RecoverySummary | null;
  emptyPlaceholder?: boolean;
  compact?: boolean;
}) {
  if (emptyPlaceholder || !summary) {
    if (compact) {
      return (
        <section
          aria-label="Recovery KPIs"
          className="psa-surface grid grid-cols-2 divide-x divide-white/8 rounded-[12px] sm:grid-cols-4"
        >
          <CompactKpi label="At risk" value="24" />
          <CompactKpi label="Expedite slots" value="8" />
          <CompactKpi label="Preserved" value="—" accent="signal" />
          <CompactKpi label="Rollovers" value="—" />
        </section>
      );
    }

    return (
      <section aria-label="Recovery KPIs" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Containers at risk"
          value="24"
          sublabel="Synthetic scenario fixture"
        />
        <KpiCard
          label="Expedite capacity"
          value="8"
          sublabel="Slots available this window"
        />
        <KpiCard
          label="Expected preserved"
          value="—"
          sublabel="Awaiting optimization run"
          accent="signal"
        />
        <KpiCard
          label="Expected rollovers"
          value="—"
          sublabel="Awaiting evaluation"
        />
      </section>
    );
  }

  const preservedDelta =
    summary.scenarioAwareExpectedPreserved != null
      ? `+${(summary.scenarioAwareExpectedPreserved - summary.baselineExpectedPreserved).toFixed(1)} vs baseline`
      : "Scenario-aware pending";

  if (compact) {
    return (
      <section aria-label="Recovery KPIs" className="space-y-2">
        <p className="psa-meta">Live evaluation</p>
        <div className="psa-surface grid grid-cols-2 divide-x divide-white/8 rounded-[12px] sm:grid-cols-4">
          <CompactKpi label="At risk" value={String(summary.containersAtRisk)} />
          <CompactKpi label="Expedite slots" value={String(summary.selectedExpediteSlots)} />
          <CompactKpi
            label="Preserved"
            value={summary.scenarioAwareExpectedPreserved?.toFixed(1) ?? "—"}
            accent="signal"
          />
          <CompactKpi
            label="Rollovers"
            value={summary.expectedRollovers?.toFixed(1) ?? "—"}
            accent={
              summary.expectedRollovers != null && summary.expectedRollovers > 3
                ? "warning"
                : undefined
            }
          />
        </div>
        <p className="text-xs text-psa-steel">{preservedDelta}</p>
      </section>
    );
  }

  return (
    <section aria-label="Recovery KPIs" className="space-y-3">
      <p className="psa-meta">Live evaluation</p>
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
          accent={
            summary.expectedRollovers != null && summary.expectedRollovers > 3
              ? "warning"
              : "neutral"
          }
        />
      </div>
    </section>
  );
}
