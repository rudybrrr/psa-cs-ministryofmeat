import type {
  AllocationRevision,
  ExpediteCommitment,
  YardForecastSnapshot,
} from "../../../api/types";
import { useEffect, useRef } from "react";
import gsap from "gsap";

import { buildAllocationComparison } from "../../../lib/chapterContext";
import { latestSnapshot } from "../../../lib/recoverySelectors";
import { motionEnabled } from "../../../lib/useReducedMotion";
import { ChapterFrame, ComparisonColumn, MetricCard, EvidencePanel } from "./ChapterFrame";

export function AdaptChapter({
  snapshots,
  revisions,
  commitments,
  quiet = false,
}: {
  snapshots: YardForecastSnapshot[];
  revisions: AllocationRevision[];
  commitments: ExpediteCommitment[];
  quiet?: boolean;
}) {
  const comparison = buildAllocationComparison(revisions, commitments);
  const preDischarge = latestSnapshot(snapshots, "PRE_DISCHARGE");
  const active = latestSnapshot(snapshots, "DISCHARGE_ACTIVE");

  const changedSwaps = comparison.swaps.filter(
    (swap) => swap.before !== swap.after && !swap.before.includes("LOCKED"),
  );

  const swapListRef = useRef<HTMLDivElement>(null);
  const revisionKey = comparison.current?.id ?? "none";
  useEffect(() => {
    if (!motionEnabled() || !swapListRef.current || changedSwaps.length === 0) return;
    gsap.fromTo(
      swapListRef.current.querySelectorAll("[data-swap-chip]"),
      { opacity: 0, scale: 0.92 },
      { opacity: 1, scale: 1, duration: 0.28, stagger: 0.06, ease: "power2.out" },
    );
  }, [changedSwaps.length, revisionKey]);

  return (
    <ChapterFrame
      label="Chapter 4 · Adapt"
      title="Evidence arrives — allocation revises under locked commitments"
      quiet={quiet}
    >
      <div className="grid gap-3 lg:grid-cols-3 !pt-0">
        <MetricCard
          label="Forecast transition"
          value={
            preDischarge && active
              ? "PRE_DISCHARGE → DISCHARGE_ACTIVE"
              : "Awaiting discharge evidence"
          }
          accent
        />
        <MetricCard
          label="Expected preserved"
          value={
            comparison.expectedBefore != null && comparison.expectedAfter != null
              ? `${comparison.expectedBefore.toFixed(2)} → ${comparison.expectedAfter.toFixed(2)}`
              : "—"
          }
        />
        <MetricCard
          label="Scenario-world total"
          value={
            comparison.totalBefore != null && comparison.totalAfter != null
              ? `${comparison.totalBefore} → ${comparison.totalAfter}`
              : "—"
          }
        />
      </div>

      {comparison.prior && comparison.current ? (
        <div className="grid gap-3 lg:grid-cols-2">
          <ComparisonColumn heading={`${comparison.label} · prior (R0)`} tone="adapt">
            <p className="font-mono text-sm font-medium">
              {comparison.totalBefore} scenario-world total
            </p>
            <p className="text-xs opacity-80">
              Expected preserved {comparison.expectedBefore?.toFixed(2)}
            </p>
          </ComparisonColumn>
          <ComparisonColumn heading={`${comparison.label} · current (R1)`} tone="adapt">
            <p className="font-mono text-sm font-medium">
              {comparison.totalAfter} scenario-world total
            </p>
            <p className="text-xs opacity-80">
              Expected preserved {comparison.expectedAfter?.toFixed(2)}
            </p>
          </ComparisonColumn>
          <p className="text-xs text-psa-steel lg:col-span-2">
            {comparison.totalBefore} → {comparison.totalAfter} synthetic scenario-world total
            across 50 worlds · expected {comparison.expectedBefore?.toFixed(2)} →{" "}
            {comparison.expectedAfter?.toFixed(2)}
          </p>
        </div>
      ) : null}

      {changedSwaps.length > 0 ? (
        <EvidencePanel title="Allocation changes (R0 → R1)" tone="adapt">
          <div ref={swapListRef} className="flex flex-wrap gap-2">
            {changedSwaps.map((swap) => (
              <span
                key={swap.containerId}
                data-swap-chip
                className="psa-mono rounded-[6px] border border-black/10 bg-white px-2.5 py-1.5 text-xs font-medium text-psa-data-ink"
              >
                {swap.containerId} {swap.before} → {swap.after}
              </span>
            ))}
          </div>
          {comparison.locked.length > 0 ? (
            <p className="text-xs text-psa-data-ink/70">
              Locked commitments remain stable: {comparison.locked.join(", ")}
            </p>
          ) : null}
        </EvidencePanel>
      ) : null}

      {comparison.commitmentLines.length > 0 ? (
        <div>
          <p className="psa-meta">Commitment disposition</p>
          <p className="psa-mono mt-2 text-xs leading-relaxed text-psa-chalk">
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
