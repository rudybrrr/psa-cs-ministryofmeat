import type { ScarcityEvaluationReport } from "../../../api/types";
import type { RecoverySummary } from "../../../lib/recoverySelectors";
import { scarcityBaselines } from "../../../lib/chapterContext";
import { ChapterFrame, MetricCard } from "./ChapterFrame";

export function OptimizeChapter({
  summary,
  scarcityEvaluation,
  loading,
  onBootstrap,
}: {
  summary: RecoverySummary | null;
  scarcityEvaluation: ScarcityEvaluationReport | null;
  loading: boolean;
  onBootstrap(): void;
}) {
  const baselines = scarcityBaselines(scarcityEvaluation);
  const allocated = scarcityEvaluation?.selected_allocation?.allocated_container_ids ?? [];

  return (
    <ChapterFrame
      label="Chapter 2 · Optimize"
      title="Scarce capacity allocation under uncertainty"
    >
      <p className="max-w-2xl text-sm leading-relaxed text-psa-chalk">
        Eight expedite slots must cover more containers than capacity allows. The
        optimizer selects an allocation that maximizes expected preserved connections
        across scenario worlds — before yard discharge evidence arrives.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Expedite slots"
          value={summary ? String(summary.selectedExpediteSlots) : "8"}
          accent
        />
        <MetricCard
          label="Baseline expected preserved"
          value={
            baselines.baselineExpected !== null
              ? baselines.baselineExpected.toFixed(2)
              : "—"
          }
        />
        <MetricCard
          label="Selected expected preserved"
          value={
            baselines.scenarioExpected !== null
              ? baselines.scenarioExpected.toFixed(2)
              : "—"
          }
        />
        <MetricCard
          label="Expected rollovers"
          value={
            baselines.scenarioRollovers !== null
              ? String(baselines.scenarioRollovers)
              : "—"
          }
        />
      </div>

      {allocated.length > 0 ? (
        <div className="psa-data-surface rounded-[10px] px-4 py-4">
          <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-psa-data-ink/60">
            Selected allocation evidence
          </p>
          <p className="mt-2 text-sm text-psa-data-ink">
            {allocated.length} containers committed to expedite under{" "}
            {summary?.selectedStrategy ?? "scenario-aware"} strategy across{" "}
            {summary?.scenarioCount ?? 50} scenario worlds.
          </p>
          <p className="mt-2 text-xs text-psa-data-ink/70">
            Open the Containers workspace for per-container allocation and disposition detail.
          </p>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={loading}
          onClick={onBootstrap}
          className="psa-btn-secondary px-4 py-2 text-xs"
        >
          Publish yard forecast
        </button>
        <p className="text-xs text-psa-steel">
          Seeds wide forecast uncertainty before the agent observes discharge.
        </p>
      </div>
    </ChapterFrame>
  );
}
