import type {
  CanonicalIncidentFixture,
  CarrierRecoveryCase,
  CarrierRecoveryHistory,
  Decision,
  ScarcityEvaluationReport,
  StrategyEvaluation,
} from "../api/types";
import type { AgentRun, AllocationRevision, AllocationTradeoffReview, CargoSafetyHistory, ExpediteCommitment, ExpediteReconsiderationAssessment, YardForecastSnapshot } from "../api/types";

export const latestSnapshot = (snapshots: YardForecastSnapshot[], stage: YardForecastSnapshot["stage"]) => [...snapshots].filter((item) => item.stage === stage).at(-1) ?? null;
export const latestAllocationRevision = (revisions: AllocationRevision[]) => revisions.at(-1) ?? null;
export const previousAllocationRevision = (revisions: AllocationRevision[]) => revisions.length > 1 ? revisions.at(-2) ?? null : null;
export const allocationDelta = (revisions: AllocationRevision[]) => { const current = latestAllocationRevision(revisions); const prior = previousAllocationRevision(revisions); const before = new Set(prior?.allocated_container_ids ?? []); const after = new Set(current?.allocated_container_ids ?? []); return { added: [...after].filter((id) => !before.has(id)), removed: [...before].filter((id) => !after.has(id)) }; };
export const commitmentByContainer = (items: ExpediteCommitment[]) => new Map(items.map((item) => [item.container_id, item.status]));
export const forecastByContainer = (snapshot: YardForecastSnapshot | null) => new Map((snapshot?.container_forecasts ?? []).map((item) => [item.container_id, item]));
export const safetyByContainer = (histories: CargoSafetyHistory[]) => new Map(histories.map((item) => [item.review.container_id, item.policy_result?.automation_blocked ?? false]));
export interface AgentAdvanceEvidence { carrierHistory: CarrierRecoveryHistory | null; reconsiderations: ExpediteReconsiderationAssessment[]; tradeoffReviews: AllocationTradeoffReview[]; }
export function canAdvanceAgent(run: AgentRun | null, evidence: AgentAdvanceEvidence): boolean { if (!run || ["COMPLETED", "ESCALATED", "FAILED"].includes(run.state)) return false; if (run.state === "RUNNING" || run.state === "CREATED") return true; if (run.wait_kind === "NEW_OPERATIONAL_EVIDENCE") return evidence.reconsiderations.some((assessment) => assessment.handled_at === null); if (run.wait_kind === "HUMAN_TRADEOFF_DECISION") { const review = evidence.tradeoffReviews.find((item) => item.id === run.wait_subject_id); return Boolean(review && review.state === "RESOLVED" && evidence.reconsiderations.some((assessment) => assessment.id === review.reconsideration_assessment_id && assessment.handled_at !== null)); } const history = evidence.carrierHistory; if (!history || history.case.id !== run.wait_subject_id) return false; if (run.wait_kind === "REQUEST_APPROVAL") return history.case.state === "AWAITING_REQUEST_APPROVAL" && history.approvals.some((approval) => approval.status === "APPROVED"); if (run.wait_kind === "CARRIER_RESPONSE_OR_TIMEOUT") return ["COMPLETED", "ESCALATED", "RECOMPUTING", "AWAITING_COUNTER_APPROVAL"].includes(history.case.state); if (run.wait_kind === "COUNTER_APPROVAL") return ["COMPLETED", "ESCALATED", "RECOMPUTING"].includes(history.case.state); return false; }

export interface RecoverySummary {
  containersAtRisk: number;
  baselineExpectedPreserved: number;
  scenarioAwareExpectedPreserved: number | null;
  expectedRollovers: number | null;
  selectedExpediteSlots: number;
  scenarioCount: number;
  reproducibilityKey: string;
  selectedStrategy: string | null;
}

export interface ContainerRecoveryRow {
  containerId: string;
  serviceId: string;
  connectionId: string;
  cargoKind: string;
  expediteAllocated: boolean;
  decisionAction: string | null;
  decisionStatus: string | null;
  decisionId: string | null;
  carrierCaseState: string | null;
  displayDisposition: string;
  forecastBand: string | null;
  commitmentStatus: string | null;
  safetyWarning: string | null;
}

function findSelectedEvaluation(
  report: ScarcityEvaluationReport,
): StrategyEvaluation | null {
  if (!report.selected_allocation) {
    return null;
  }
  const selectedIds = report.selected_allocation.allocated_container_ids.join(",");
  const candidates = [
    report.baseline,
    ...report.scenario_aware_evaluations,
    ...report.pareto_evaluations,
  ];
  return (
    candidates.find(
      (evaluation) =>
        evaluation.allocation.strategy ===
          report.selected_allocation?.strategy &&
        evaluation.allocation.allocated_container_ids.join(",") === selectedIds,
    ) ?? null
  );
}

export function selectedAllocationSet(
  allocation: ScarcityEvaluationReport["selected_allocation"],
): Set<string> {
  if (!allocation) {
    return new Set();
  }
  return new Set(allocation.allocated_container_ids);
}

export function buildRecoverySummary(
  fixture: CanonicalIncidentFixture,
  report: ScarcityEvaluationReport,
): RecoverySummary {
  const selected = findSelectedEvaluation(report);
  return {
    containersAtRisk: fixture.profiles.length,
    baselineExpectedPreserved: report.baseline.expected_preserved_connections,
    scenarioAwareExpectedPreserved:
      selected?.expected_preserved_connections ?? null,
    expectedRollovers: selected?.expected_rollovers ?? null,
    selectedExpediteSlots:
      report.selected_allocation?.allocated_container_ids.length ?? 0,
    scenarioCount: report.scenario_count,
    reproducibilityKey: report.reproducibility_key,
    selectedStrategy: report.selected_allocation?.strategy ?? null,
  };
}

export function selectLatestDecisionByContainer(
  decisions: Decision[],
): Map<string, Decision> {
  const byContainer = new Map<string, Decision[]>();
  for (const decision of decisions) {
    if (!decision.container_id) {
      continue;
    }
    const list = byContainer.get(decision.container_id) ?? [];
    list.push(decision);
    byContainer.set(decision.container_id, list);
  }

  const latest = new Map<string, Decision>();
  for (const [containerId, list] of byContainer) {
    const sorted = [...list].sort((a, b) =>
      a.created_at.localeCompare(b.created_at),
    );
    const active =
      [...sorted].reverse().find((item) => item.status !== "SUPERSEDED") ??
      sorted[sorted.length - 1];
    latest.set(containerId, active);
  }
  return latest;
}

export function buildDecisionLineage(
  decisionId: string,
  decisions: Decision[],
): Decision[] {
  const byId = new Map(decisions.map((decision) => [decision.id, decision]));
  const chain: Decision[] = [];
  let current = byId.get(decisionId);
  while (current) {
    chain.unshift(current);
    current = current.supersedes ? byId.get(current.supersedes) : undefined;
  }
  return chain;
}

export function carrierCaseForConnection(
  cases: CarrierRecoveryCase[],
  connectionId: string,
): CarrierRecoveryCase | undefined {
  return cases.find((item) => item.connection_id === connectionId);
}

export function hasCarrierResponseEvidence(
  history: CarrierRecoveryHistory,
): boolean {
  return history.carrier_responses.length > 0;
}

export function buildContainerRows(
  fixture: CanonicalIncidentFixture,
  report: ScarcityEvaluationReport,
  decisions: Decision[],
  carrierCases: CarrierRecoveryCase[],
  activeSnapshot: YardForecastSnapshot | null = null,
  commitments: ExpediteCommitment[] = [],
  safetyHistories: CargoSafetyHistory[] = [],
  allocationRevision: AllocationRevision | null = null,
): ContainerRecoveryRow[] {
  const allocated = new Set(allocationRevision?.allocated_container_ids ?? report.selected_allocation?.allocated_container_ids ?? []);
  const latestDecisions = selectLatestDecisionByContainer(decisions);
  const forecasts = forecastByContainer(activeSnapshot);
  const commitmentStatus = commitmentByContainer(commitments);
  const safetyState = safetyByContainer(safetyHistories);

  return fixture.profiles.map((profile) => {
    const containerId = profile.container.id;
    const connectionId = profile.container.onward_connection.id;
    const carrierCase = carrierCaseForConnection(carrierCases, connectionId);
    const decision = latestDecisions.get(containerId);
    const forecast = forecasts.get(containerId);

    let displayDisposition = "pending policy";
    if (decision) {
      displayDisposition = decision.action.replaceAll("_", " ");
      if (carrierCase?.state === "COMPLETED") {
        displayDisposition = `${displayDisposition} · carrier recovery complete`;
      } else if (carrierCase) {
        displayDisposition = `${displayDisposition} · ${carrierCase.state.replaceAll("_", " ").toLowerCase()}`;
      }
    }

    return {
      containerId,
      serviceId: profile.service_id,
      connectionId,
      cargoKind: profile.cargo_kind,
      expediteAllocated: allocated.has(containerId),
      decisionAction: decision?.action ?? null,
      decisionStatus: decision?.status ?? null,
      decisionId: decision?.id ?? null,
      carrierCaseState: carrierCase?.state ?? null,
      displayDisposition,
      forecastBand: forecast ? `p50 ${forecast.p50_ready_at.slice(11, 16)} · p10–p90` : null,
      commitmentStatus: commitmentStatus.get(containerId) ?? null,
      safetyWarning: safetyState.get(containerId) ? "automation blocked" : null,
    };
  });
}
