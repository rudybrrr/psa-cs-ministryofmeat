import type { YardForecastSnapshot } from "../../../api/types";
import { latestSnapshot } from "../../../lib/recoverySelectors";
import { ChapterFrame, ComparisonColumn } from "./ChapterFrame";

export function ObserveChapter({
  snapshots,
  loading,
  onPublishActive,
  evidenceOnly = false,
  quiet = false,
}: {
  snapshots: YardForecastSnapshot[];
  loading: boolean;
  onPublishActive(): void;
  evidenceOnly?: boolean;
  quiet?: boolean;
}) {
  const preDischarge = latestSnapshot(snapshots, "PRE_DISCHARGE");
  const active = latestSnapshot(snapshots, "DISCHARGE_ACTIVE");

  return (
    <ChapterFrame
      label="Chapter 3 · Observe"
      title="Agent pauses — waiting for operational evidence"
      quiet={quiet}
    >
      <p className="max-w-2xl !pt-0 text-sm leading-relaxed text-psa-chalk">
        The agent does not guess through missing yard evidence. While forecasts remain
        in PRE_DISCHARGE, authority stays bounded until discharge-active operational
        signals arrive.
      </p>

      <div className="border-l-2 border-psa-amber/60 pl-4">
        <p className="psa-label text-psa-amber">Status</p>
        <p className="mt-2 text-lg font-medium text-psa-snow">
          Waiting for operational evidence
        </p>
        <p className="mt-1 text-sm text-psa-chalk">
          The agent pauses until discharge-active yard forecasts are published rather
          than advancing on stale PRE_DISCHARGE bands.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <ComparisonColumn heading="PRE_DISCHARGE forecast" tone="adapt">
          {preDischarge ? (
            <>
              <p className="font-mono text-xs">
                {preDischarge.stage} — wide uncertainty
              </p>
              <p className="text-xs opacity-80">
                Wide p10–p90 bands reflect discharge timing uncertainty before active
                operations.
              </p>
            </>
          ) : (
            <p>Bootstrap yard forecasts to begin observation.</p>
          )}
        </ComparisonColumn>
        <ComparisonColumn heading="Authority boundary" tone="adapt">
          <p>Evidence class: yard forecast snapshot</p>
          <p>Agent may read persisted forecasts</p>
          <p>Agent may not authorize carrier recovery or safety overrides</p>
          <p className="font-medium text-psa-data-ink">Human authority required for outbound actions</p>
        </ComparisonColumn>
      </div>

      {active ? (
        <div>
          <p className="psa-meta">Discharge-active signal</p>
          <p className="psa-mono mt-2 text-xs text-psa-snow">
            {active.stage} — tighter forecast band
          </p>
        </div>
      ) : !evidenceOnly ? (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={loading || !preDischarge}
            onClick={onPublishActive}
            className="psa-btn-secondary px-4 py-2 text-xs disabled:opacity-50"
          >
            Publish discharge evidence
          </button>
          <p className="text-xs text-psa-steel">
            Simulates operational discharge signal tightening forecast bands.
          </p>
        </div>
      ) : null}
    </ChapterFrame>
  );
}
