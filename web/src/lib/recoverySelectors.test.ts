import { describe, expect, it } from "vitest";

import type {
  AllocationPlan,
  CanonicalIncidentFixture,
  CarrierRecoveryCase,
  CarrierRecoveryHistory,
  Decision,
  ScarcityEvaluationReport,
  StrategyEvaluation,
} from "../api/types";
import {
  allocationDelta,
  buildContainerRows,
  buildDecisionLineage,
  buildRecoverySummary,
  carrierCaseForConnection,
  hasCarrierResponseEvidence,
  selectLatestDecisionByContainer,
  selectedAllocationSet,
  canAdvanceAgent,
  commitmentByContainer,
  forecastByContainer,
  latestAllocationRevision,
  latestSnapshot,
  previousAllocationRevision,
  safetyByContainer,
} from "./recoverySelectors";

const baselineEval: StrategyEvaluation = {
  allocation: { strategy: "P50_GREEDY", allocated_container_ids: ["C1", "C2"] },
  world_count: 50,
  preserved_connection_total: 10,
  expected_preserved_connections: 9.5,
  rollover_total: 5,
  expected_rollovers: 4.2,
  p10_preserved_connections: 8,
  allocation_slot_count: 2,
  capacity_violations: 0,
  unsafe_allocations: 0,
  runtime_ms: 12,
  service_outcomes: [],
};

const scenarioEval: StrategyEvaluation = {
  allocation: {
    strategy: "SCENARIO_AWARE",
    allocated_container_ids: ["C1", "C3"],
  },
  world_count: 50,
  preserved_connection_total: 12,
  expected_preserved_connections: 11.2,
  rollover_total: 3,
  expected_rollovers: 2.8,
  p10_preserved_connections: 10,
  allocation_slot_count: 2,
  capacity_violations: 0,
  unsafe_allocations: 0,
  runtime_ms: 20,
  service_outcomes: [],
};

const report: ScarcityEvaluationReport = {
  id: "eval-1",
  incident_id: "inc-1",
  fixture_id: "SYN-CANONICAL-24-V1",
  seed: 20260822,
  scenario_count: 50,
  baseline: baselineEval,
  scenario_aware_evaluations: [scenarioEval],
  pareto_evaluations: [],
  selected_allocation: scenarioEval.allocation,
  reproducibility_key: "a".repeat(64),
  created_at: "2026-08-22T08:00:00Z",
};

const fixture: CanonicalIncidentFixture = {
  fixture_id: "SYN-CANONICAL-24-V1",
  event: {
    id: "evt",
    vessel_call_id: "vc",
    vessel_name: "v",
    terminal_id: "T1",
    scheduled_arrival: "2026-08-22T01:00:00Z",
    estimated_arrival: "2026-08-22T04:15:00Z",
    delay_minutes: 195,
    occurred_at: "2026-08-22T04:15:00Z",
  },
  services: [],
  profiles: [
    {
      container: {
        id: "C1",
        origin_port: "A",
        destination_port: "B",
        cargo: { commodity: "x", gross_weight_kg: 1, dangerous_goods: false, un_number: null },
        inbound_vessel_call_id: "vc",
        onward_connection: {
          id: "SYN-CONN-JV2",
          outbound_vessel_name: "v",
          outbound_voyage: "v1",
          destination_port: "B",
          cutoff_at: "2026-08-22T05:00:00Z",
          departure_at: "2026-08-22T06:00:00Z",
          minimum_transfer_minutes: 90,
          expedited_transfer_minutes: 60,
        },
      },
      service_id: "JV2",
      handling_group_id: "HG1",
      cargo_kind: "DRY",
      base_ready_at: "2026-08-22T05:10:00Z",
      expedite_minutes_saved: 30,
      reefer_continuity_available: true,
      dg_structurally_cleared: true,
    },
    {
      container: {
        id: "C3",
        origin_port: "A",
        destination_port: "C",
        cargo: { commodity: "y", gross_weight_kg: 1, dangerous_goods: false, un_number: null },
        inbound_vessel_call_id: "vc",
        onward_connection: {
          id: "SYN-CONN-EC3",
          outbound_vessel_name: "v2",
          outbound_voyage: "v2",
          destination_port: "C",
          cutoff_at: "2026-08-22T07:00:00Z",
          departure_at: "2026-08-22T08:00:00Z",
          minimum_transfer_minutes: 90,
          expedited_transfer_minutes: 60,
        },
      },
      service_id: "EC3",
      handling_group_id: "HG2",
      cargo_kind: "DRY",
      base_ready_at: "2026-08-22T06:00:00Z",
      expedite_minutes_saved: 30,
      reefer_continuity_available: true,
      dg_structurally_cleared: true,
    },
  ],
  capacity: {
    id: "cap",
    terminal_id: "T1",
    window_start: "2026-08-22T05:00:00Z",
    window_end: "2026-08-22T06:00:00Z",
    overlap_service_ids: ["JV2"],
    total_slots: 8,
    handling_group_limits: [],
    max_reefer_slots: 3,
    max_dg_slots: 1,
  },
};

describe("recoverySelectors", () => {
  it("builds recovery summary from report without hard-coded counts", () => {
    const summary = buildRecoverySummary(fixture, report);
    expect(summary.containersAtRisk).toBe(2);
    expect(summary.baselineExpectedPreserved).toBe(9.5);
    expect(summary.scenarioAwareExpectedPreserved).toBe(11.2);
    expect(summary.expectedRollovers).toBe(2.8);
    expect(summary.selectedExpediteSlots).toBe(2);
    expect(summary.scenarioCount).toBe(50);
    expect(summary.reproducibilityKey).toBe("a".repeat(64));
  });

  it("maps selected allocation to container rows", () => {
    const rows = buildContainerRows(fixture, report, [], []);
    const c1 = rows.find((row) => row.containerId === "C1");
    const c3 = rows.find((row) => row.containerId === "C3");
    expect(c1?.expediteAllocated).toBe(true);
    expect(c3?.expediteAllocated).toBe(true);
  });

  it("selectedAllocationSet reflects allocation plan", () => {
    const plan: AllocationPlan = {
      strategy: "SCENARIO_AWARE",
      allocated_container_ids: ["X"],
    };
    expect(selectedAllocationSet(plan)).toEqual(new Set(["X"]));
    expect(selectedAllocationSet(null)).toEqual(new Set());
  });

  it("selectLatestDecisionByContainer ignores superseded", () => {
    const decisions: Decision[] = [
      {
        id: "d1",
        incident_id: "i",
        container_id: "C1",
        action: "ROLL",
        status: "SUPERSEDED",
        rationale: "old",
        supersedes: null,
        supersession_reason: null,
        created_at: "2026-08-22T08:00:00Z",
      },
      {
        id: "d2",
        incident_id: "i",
        container_id: "C1",
        action: "PRESERVE_VIA_RTA",
        status: "APPROVED",
        rationale: "new",
        supersedes: "d1",
        supersession_reason: "carrier recovery",
        created_at: "2026-08-22T09:00:00Z",
      },
    ];
    const map = selectLatestDecisionByContainer(decisions);
    expect(map.get("C1")?.action).toBe("PRESERVE_VIA_RTA");
  });

  it("buildDecisionLineage follows supersedes chain", () => {
    const decisions: Decision[] = [
      {
        id: "d1",
        incident_id: "i",
        container_id: "C1",
        action: "ROLL",
        status: "SUPERSEDED",
        rationale: "roll",
        supersedes: null,
        supersession_reason: null,
        created_at: "2026-08-22T08:00:00Z",
      },
      {
        id: "d2",
        incident_id: "i",
        container_id: "C1",
        action: "PRESERVE_VIA_RTA",
        status: "APPROVED",
        rationale: "rta",
        supersedes: "d1",
        supersession_reason: "carrier accept",
        created_at: "2026-08-22T09:00:00Z",
      },
    ];
    const lineage = buildDecisionLineage("d2", decisions);
    expect(lineage.map((item) => item.action)).toEqual([
      "ROLL",
      "PRESERVE_VIA_RTA",
    ]);
  });

  it("carrierCaseForConnection finds case by connection id", () => {
    const cases: CarrierRecoveryCase[] = [
      {
        id: "case-1",
        incident_id: "i",
        connection_id: "SYN-CONN-JV2",
        source_evaluation_id: "e",
        affected_container_ids: ["C1"],
        state: "AWAITING_CARRIER",
        created_at: "2026-08-22T08:00:00Z",
        updated_at: "2026-08-22T08:00:00Z",
      },
    ];
    expect(carrierCaseForConnection(cases, "SYN-CONN-JV2")?.id).toBe("case-1");
  });

  it("SILENT history has no carrier response evidence", () => {
    const history: CarrierRecoveryHistory = {
      case: {
        id: "case-1",
        incident_id: "i",
        connection_id: "SYN-CONN-EC3",
        source_evaluation_id: "e",
        affected_container_ids: ["C3"],
        state: "COMPLETED",
        created_at: "2026-08-22T08:00:00Z",
        updated_at: "2026-08-22T09:00:00Z",
      },
      request: null,
      request_context: null,
      bindings: [],
      approvals: [],
      carrier_responses: [],
      effective_timings: [],
      decision_links: [],
      decisions: [],
      results: [],
      audit_events: [
        {
          id: "a1",
          actor: "SYSTEM",
          actor_id: "timeout",
          incident_id: "i",
          event_type: "carrier.response_timed_out",
          payload: {},
          timestamp: "2026-08-22T09:00:00Z",
        },
      ],
    };
    expect(hasCarrierResponseEvidence(history)).toBe(false);
  });

  it("selects persisted snapshots, revisions, and their membership delta", () => {
    const snapshots = [
      { id: "pre", incident_id: "i", stage: "PRE_DISCHARGE" as const, generated_at: "2026-08-25T01:00:00Z", source: "seed", container_forecasts: [] },
      { id: "active", incident_id: "i", stage: "DISCHARGE_ACTIVE" as const, generated_at: "2026-08-25T02:00:00Z", source: "sensor", container_forecasts: [] },
    ];
    const revisions = [
      { id: "r0", incident_id: "i", source_phase2_evaluation_id: "e", source_forecast_snapshot_id: "pre", parent_revision_id: null, allocated_container_ids: ["OUT"], locked_container_ids: [], preserved_connection_total: 601, expected_preserved_connections: 12.02, reason: "pre", created_at: "2026-08-25T01:00:00Z" },
      { id: "r1", incident_id: "i", source_phase2_evaluation_id: "e", source_forecast_snapshot_id: "active", parent_revision_id: "r0", allocated_container_ids: ["IN"], locked_container_ids: [], preserved_connection_total: 602, expected_preserved_connections: 12.04, reason: "active", created_at: "2026-08-25T02:00:00Z" },
    ];
    expect(latestSnapshot(snapshots, "PRE_DISCHARGE")?.id).toBe("pre");
    expect(latestSnapshot(snapshots, "DISCHARGE_ACTIVE")?.id).toBe("active");
    expect(latestAllocationRevision(revisions)?.id).toBe("r1");
    expect(previousAllocationRevision(revisions)?.id).toBe("r0");
    expect(allocationDelta(revisions)).toEqual({ added: ["IN"], removed: ["OUT"] });
  });

  it("indexes persisted commitment, forecast, and safety evidence by container", () => {
    expect(commitmentByContainer([{ id: "c", incident_id: "i", origin_revision_id: "r", container_id: "C1", status: "COMMITTED", created_at: "", updated_at: "" }]).get("C1")).toBe("COMMITTED");
    expect(forecastByContainer({ id: "s", incident_id: "i", stage: "DISCHARGE_ACTIVE", generated_at: "", source: "", container_forecasts: [{ container_id: "C1", p10_ready_at: "a", p50_ready_at: "b", p90_ready_at: "c" }] }).get("C1")?.p50_ready_at).toBe("b");
    expect(safetyByContainer([{ review: { id: "r", incident_id: "i", container_id: "C1", cargo_note_id: "n", state: "COMPLETED", created_at: "", updated_at: "" }, note: { id: "n", incident_id: "i", container_id: "C1", text: "", source: "", created_at: "" }, assessment: null, policy_result: { id: "p", review_id: "r", assessment_id: "a", incident_id: "i", container_id: "C1", disposition: "BLOCK", automation_blocked: true, reason: "x", replacement_decision_id: null, created_at: "" }, audit_events: [] }]).get("C1")).toBe(true);
  });

  it("enables agent advance only from the exact persisted wait subject", () => {
    const run = (state: any, wait_kind: any = null, wait_subject_id: string | null = null) => ({ id: "run", incident_id: "i", state, model_name: "m", prompt_version: "v", step_count: 1, max_steps: 4, wait_kind, wait_subject_id, escalation_reason: null, started_at: "", updated_at: "", completed_at: null });
    const empty = { carrierHistory: null, reconsiderations: [], tradeoffReviews: [] };
    const history: any = { case: { id: "case", state: "AWAITING_REQUEST_APPROVAL" }, approvals: [{ status: "APPROVED" }] };
    expect(canAdvanceAgent(run("RUNNING"), empty)).toBe(true);
    expect(canAdvanceAgent(run("WAITING", "NEW_OPERATIONAL_EVIDENCE"), empty)).toBe(false);
    expect(canAdvanceAgent(run("WAITING", "NEW_OPERATIONAL_EVIDENCE"), { ...empty, reconsiderations: [{ id: "a", handled_at: null }] })).toBe(true);
    expect(canAdvanceAgent(run("WAITING", "REQUEST_APPROVAL", "case"), empty)).toBe(false);
    expect(canAdvanceAgent(run("WAITING", "REQUEST_APPROVAL", "case"), { ...empty, carrierHistory: history })).toBe(true);
    expect(canAdvanceAgent(run("WAITING", "REQUEST_APPROVAL", "other"), { ...empty, carrierHistory: history })).toBe(false);
    expect(canAdvanceAgent(run("WAITING", "COUNTER_APPROVAL", "case"), { ...empty, carrierHistory: { ...history, case: { id: "case", state: "COMPLETED" } } })).toBe(true);
    expect(canAdvanceAgent(run("WAITING", "HUMAN_TRADEOFF_DECISION", "review"), { ...empty, reconsiderations: [{ id: "a", handled_at: "now" }], tradeoffReviews: [{ id: "review", reconsideration_assessment_id: "a", state: "RESOLVED" }] })).toBe(true);
    expect(canAdvanceAgent(run("COMPLETED"), empty)).toBe(false);
  });
});
