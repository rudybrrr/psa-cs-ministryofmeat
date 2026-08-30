import type {
  AllocationRevision,
  ExpediteCommitment,
  YardForecastSnapshot,
} from "../../../api/types";
import { buildAllocationComparison } from "../../../lib/chapterContext";
import { latestSnapshot } from "../../../lib/recoverySelectors";
import { ChapterFrame, MetricCard } from "./ChapterFrame";

export function AdaptChapter({
  snapshots,
  revisions,
  commitments,
}: {
  snapshots: YardForecastSnapshot[];
  revisions: AllocationRevision[];
  commitments: ExpediteCommitment[];
}) {
  const comparison = buildAllocationComparison(revisions, commitments);
  const preDischarge = latestSnapshot(snapshots, "PRE_DISCHARGE");
  const active = latestSnapshot(snapshots, "DISCHARGE_ACTIVE");

  const changedSwaps = comparison.swaps.filter(
    (swap) => swap.before !== swap.after && !swap.before.includes("LOCKED"),
  );

  return (
    <ChapterFrame
      label="Chapter 4 · Adapt"
      title="Evidence arrives — allocation revises under locked commitments"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <MetricCard
          label="Forecast transition"
          value={
            preDischarge && active
              ? "PRE_DISCHARGE → DISCHARGE_ACTIVE"
              : "Awaiting discharge evidence"
          }
          accent
        />
      </div>

      {comparison.prior && comparison.current ? (
        <p className="font-mono text-xs text-psa-chalk">
          <b>{comparison.label}</b>
          {" · "}
          {comparison.totalBefore} → {comparison.totalAfter} synthetic scenario-world total
          across 50 worlds · expected {comparison.expectedBefore?.toFixed(2)} →{" "}
          {comparison.expectedAfter?.toFixed(2)}
        </p>
      ) : null}

      {changedSwaps.length > 0 ? (
        <div className="psa-surface-nested rounded-[8px] px-4 py-4">
          <p className="psa-label">Changed allocation</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {changedSwaps.map((swap) => (
              <span
                key={swap.containerId}
                className="rounded border border-psa-graphite bg-psa-void px-2 py-1 font-mono text-xs text-psa-snow"
              >
                {swap.containerId} {swap.before} → {swap.after}
              </span>
            ))}
          </div>
          {comparison.locked.length > 0 ? (
            <p className="mt-3 text-xs text-psa-steel">
              Locked commitments remain stable: {comparison.locked.join(", ")}
            </p>
          ) : null}
        </div>
      ) : null}

      {comparison.commitmentLines.length > 0 ? (
        <div className="psa-surface-nested rounded-[8px] px-4 py-4">
          <p className="psa-label">Commitment disposition</p>
          <p className="mt-2 font-mono text-xs leading-relaxed text-psa-chalk">
            {comparison.commitmentLines.join(" · ")}
          </p>
        </div>
      ) : null}

      {comparison.current ? (
        <p className="text-xs text-psa-steel">{comparison.current.reason}</p>
      ) : null}
    </ChapterFrame>
  );
}
