import type { YardForecastSnapshot } from "../../../api/types";
import { latestSnapshot } from "../../../lib/recoverySelectors";
import { ChapterFrame, ComparisonColumn } from "./ChapterFrame";

export function ObserveChapter({
  snapshots,
  loading,
  onPublishActive,
}: {
  snapshots: YardForecastSnapshot[];
  loading: boolean;
  onPublishActive(): void;
}) {
  const preDischarge = latestSnapshot(snapshots, "PRE_DISCHARGE");
  const active = latestSnapshot(snapshots, "DISCHARGE_ACTIVE");

  return (
    <ChapterFrame
      label="Chapter 3 · Observe"
      title="Agent pauses — waiting for operational evidence"
    >
      <p className="max-w-2xl text-sm leading-relaxed text-psa-chalk">
        The agent does not guess through missing yard evidence. While forecasts remain
        in PRE_DISCHARGE, authority stays bounded until discharge-active operational
        signals arrive.
      </p>

      <div className="rounded-[8px] border border-psa-amber/40 bg-psa-amber/5 px-4 py-4">
        <p className="psa-label text-psa-amber">Status</p>
        <p className="mt-2 text-lg font-medium text-psa-snow">
          WAITING FOR OPERATIONAL EVIDENCE
        </p>
        <p className="mt-1 text-sm text-psa-chalk">
          Agent waits at NEW_OPERATIONAL_EVIDENCE rather than advancing on stale
          forecasts.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <ComparisonColumn heading="PRE_DISCHARGE forecast">
          {preDischarge ? (
            <>
              <p className="font-mono text-xs text-psa-snow">
                {preDischarge.stage} — wide uncertainty
              </p>
              <p className="text-xs text-psa-steel">
                Wide p10–p90 bands reflect discharge timing uncertainty before active
                operations.
              </p>
            </>
          ) : (
            <p className="text-psa-steel">Bootstrap yard forecasts to begin observation.</p>
          )}
        </ComparisonColumn>
        <ComparisonColumn heading="Authority boundary">
          <p>Evidence class: yard forecast snapshot</p>
          <p>Agent may read persisted forecasts</p>
          <p>Agent may not authorize carrier recovery or safety overrides</p>
          <p className="text-psa-amber">Human authority required for outbound actions</p>
        </ComparisonColumn>
      </div>

      {active ? (
        <div className="psa-surface-nested rounded-[8px] px-4 py-3">
          <p className="font-mono text-xs text-psa-snow">
            {active.stage} — tighter forecast band
          </p>
        </div>
      ) : (
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
      )}
    </ChapterFrame>
  );
}
