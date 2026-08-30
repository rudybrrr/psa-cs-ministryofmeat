import type {
  AllocationRevision,
  CanonicalIncidentFixture,
  ExpediteCommitment,
  ScarcityEvaluationReport,
  YardForecastSnapshot,
} from "../api/types";
import {
  latestAllocationRevision,
  previousAllocationRevision,
} from "./recoverySelectors";

export interface AllocationComparison {
  prior: AllocationRevision | null;
  current: AllocationRevision | null;
  label: string;
  expectedBefore: number | null;
  expectedAfter: number | null;
  totalBefore: number | null;
  totalAfter: number | null;
  swaps: Array<{ containerId: string; before: string; after: string }>;
  locked: string[];
  commitmentLines: string[];
}

export function buildAllocationComparison(
  revisions: AllocationRevision[],
  commitments: ExpediteCommitment[],
): AllocationComparison {
  const current = latestAllocationRevision(revisions);
  const prior = previousAllocationRevision(revisions);
  const beforeSet = new Set(prior?.allocated_container_ids ?? []);
  const afterSet = new Set(current?.allocated_container_ids ?? []);
  const ids = new Set([...beforeSet, ...afterSet, ...commitments.map((c) => c.container_id)]);

  const swaps: AllocationComparison["swaps"] = [];
  for (const containerId of ids) {
    const beforeIn = beforeSet.has(containerId);
    const afterIn = afterSet.has(containerId);
    if (beforeIn === afterIn) {
      if (beforeIn && current?.locked_container_ids.includes(containerId)) {
        swaps.push({ containerId, before: "IN LOCKED", after: "IN LOCKED" });
      }
      continue;
    }
    swaps.push({
      containerId,
      before: beforeIn ? "IN" : "OUT",
      after: afterIn ? "IN" : "OUT",
    });
  }

  const commitmentLines = commitments.map((item) => {
    const inAlloc = current?.allocated_container_ids.includes(item.container_id);
    return `${item.container_id} ${inAlloc ? "IN" : "OUT"} ${item.status}`;
  });

  const rIndex = revisions.length;

  return {
    prior,
    current,
    label: prior ? `R${rIndex - 2} → R${rIndex - 1}` : current ? `R${rIndex - 1}` : "R0",
    expectedBefore: prior?.expected_preserved_connections ?? null,
    expectedAfter: current?.expected_preserved_connections ?? null,
    totalBefore: prior?.preserved_connection_total ?? null,
    totalAfter: current?.preserved_connection_total ?? null,
    swaps,
    locked: current?.locked_container_ids ?? [],
    commitmentLines,
  };
}

export function serviceSummaries(fixture: CanonicalIncidentFixture | null) {
  if (!fixture) return [];
  return fixture.services.map((service) => ({
    id: service.service_id,
    connectionId: service.connection.id,
    destination: service.connection.destination_port,
    cutoff: service.connection.cutoff_at,
  }));
}

export function forecastStageLabel(snapshot: YardForecastSnapshot | null) {
  if (!snapshot) return null;
  return snapshot.stage === "PRE_DISCHARGE" ? "wide uncertainty" : "tighter forecast band";
}

export function scarcityBaselines(report: ScarcityEvaluationReport | null) {
  if (!report) {
    return { baselineExpected: null, scenarioExpected: null, baselineRollovers: null, scenarioRollovers: null };
  }
  const selected = report.scenario_aware_evaluations[0] ?? null;
  return {
    baselineExpected: report.baseline.expected_preserved_connections,
    scenarioExpected: selected?.expected_preserved_connections ?? null,
    baselineRollovers: report.baseline.expected_rollovers,
    scenarioRollovers: selected?.expected_rollovers ?? null,
  };
}

export function formatMetricDelta(before: number | null, after: number | null, digits = 2) {
  if (before === null || after === null) return "—";
  return `${before.toFixed(digits)} → ${after.toFixed(digits)}`;
}

export function formatTotalDelta(before: number | null, after: number | null) {
  if (before === null || after === null) return "—";
  return `${before} → ${after}`;
}
