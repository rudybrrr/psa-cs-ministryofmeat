import type {
  CanonicalIncidentFixture,
  CarrierRecoveryCase,
  CarrierRecoveryHistory,
  Decision,
  ScarcityEvaluationReport,
  StrategyEvaluation,
} from "../api/types";

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
): ContainerRecoveryRow[] {
  const allocated = selectedAllocationSet(report.selected_allocation);
  const latestDecisions = selectLatestDecisionByContainer(decisions);

  return fixture.profiles.map((profile) => {
    const containerId = profile.container.id;
    const connectionId = profile.container.onward_connection.id;
    const carrierCase = carrierCaseForConnection(carrierCases, connectionId);
    const decision = latestDecisions.get(containerId);

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
    };
  });
}
