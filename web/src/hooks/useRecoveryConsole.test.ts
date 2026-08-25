import { renderHook, act, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as carrierApi from "../api/carrierRecovery";
import * as clientApi from "../api/client";
import * as scarcityApi from "../api/scarcity";
import { ApiError } from "../api/client";
import { useRecoveryConsole } from "./useRecoveryConsole";

vi.mock("../api/agentRuntime", () => ({ createAgentRun: vi.fn(), advanceAgentRun: vi.fn(), listAgentRuns: vi.fn().mockResolvedValue([]), getAgentRunHistory: vi.fn() }));
vi.mock("../api/dynamicYard", () => ({ bootstrapDynamicYard: vi.fn(), publishDischargeActive: vi.fn(), selectTradeoff: vi.fn(), listYardForecasts: vi.fn().mockResolvedValue([]), listAllocationRevisions: vi.fn().mockResolvedValue([]), listExpediteCommitments: vi.fn().mockResolvedValue([]), listReconsiderations: vi.fn().mockResolvedValue([]), listTradeoffReviews: vi.fn().mockResolvedValue([]), listTradeoffOptions: vi.fn().mockResolvedValue([]) }));
vi.mock("../api/cargoSafety", () => ({ createCargoSafetyReview: vi.fn(), evaluateCargoSafetyReview: vi.fn(), listCargoSafetyReviews: vi.fn().mockResolvedValue([]), getCargoSafetyHistory: vi.fn() }));

const INCIDENT_ID = "11111111-1111-4111-8111-111111111111";
const CASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

const incident = {
  id: INCIDENT_ID,
  source_event_id: "SYN-EVT",
  state: "RECOVERY_ANALYSIS" as const,
  created_at: "2026-08-22T08:00:00Z",
};

const fixture = {
  fixture_id: "SYN-CANONICAL-24-V1",
  event: {
    id: "e",
    vessel_call_id: "vc",
    vessel_name: "v",
    terminal_id: "T",
    scheduled_arrival: "2026-08-22T01:00:00Z",
    estimated_arrival: "2026-08-22T04:15:00Z",
    delay_minutes: 195,
    occurred_at: "2026-08-22T04:15:00Z",
  },
  services: [],
  profiles: [
    {
      container: {
        id: "SYN-CNT-017",
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
      handling_group_id: "HG",
      cargo_kind: "DRY" as const,
      base_ready_at: "2026-08-22T05:10:00Z",
      expedite_minutes_saved: 30,
      reefer_continuity_available: true,
      dg_structurally_cleared: true,
    },
  ],
  capacity: {
    id: "cap",
    terminal_id: "T",
    window_start: "2026-08-22T05:00:00Z",
    window_end: "2026-08-22T06:00:00Z",
    overlap_service_ids: ["JV2"],
    total_slots: 8,
    handling_group_limits: [],
    max_reefer_slots: 3,
    max_dg_slots: 1,
  },
};

const scarcityEvaluation = {
  id: "eval-1",
  incident_id: INCIDENT_ID,
  fixture_id: "SYN-CANONICAL-24-V1",
  seed: 20260822,
  scenario_count: 50,
  baseline: {
    allocation: { strategy: "P50_GREEDY" as const, allocated_container_ids: [] },
    world_count: 50,
    preserved_connection_total: 10,
    expected_preserved_connections: 9.5,
    rollover_total: 5,
    expected_rollovers: 4.2,
    p10_preserved_connections: 8,
    allocation_slot_count: 0,
    capacity_violations: 0,
    unsafe_allocations: 0,
    runtime_ms: 1,
    service_outcomes: [],
  },
  scenario_aware_evaluations: [],
  pareto_evaluations: [],
  selected_allocation: { strategy: "SCENARIO_AWARE" as const, allocated_container_ids: ["SYN-CNT-017"] },
  reproducibility_key: "a".repeat(64),
  created_at: "2026-08-22T08:00:00Z",
};

describe("useRecoveryConsole", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates canonical incident and loads persisted state", async () => {
    vi.spyOn(scarcityApi, "triggerCanonicalScarcity").mockResolvedValue({
      incident_id: INCIDENT_ID,
      evaluation_id: "eval-1",
      decision_ids: [],
      reproducibility_key: "a".repeat(64),
    });
    vi.spyOn(scarcityApi, "getCanonicalFixture").mockResolvedValue(fixture);
    vi.spyOn(scarcityApi, "getScarcityEvaluation").mockResolvedValue(scarcityEvaluation);
    vi.spyOn(clientApi, "getIncident").mockResolvedValue(incident);
    vi.spyOn(clientApi, "getDecisions").mockResolvedValue([]);
    vi.spyOn(clientApi, "getAuditEvents").mockResolvedValue([]);
    vi.spyOn(carrierApi, "listCarrierCases").mockResolvedValue([]);

    const { result } = renderHook(() => useRecoveryConsole());

    await act(async () => {
      await result.current.createCanonicalIncident();
    });

    await waitFor(() => {
      expect(result.current.incident?.id).toBe(INCIDENT_ID);
      expect(result.current.scarcityEvaluation?.id).toBe("eval-1");
      expect(result.current.fixture?.fixture_id).toBe("SYN-CANONICAL-24-V1");
    });
  });

  it("prepareCarrierRecovery refreshes carrier cases after mutation", async () => {
    const carrierCase = {
      id: CASE_ID,
      incident_id: INCIDENT_ID,
      connection_id: "SYN-CONN-JV2",
      source_evaluation_id: "eval-1",
      affected_container_ids: ["SYN-CNT-017"],
      state: "AWAITING_REQUEST_APPROVAL" as const,
      created_at: "2026-08-22T07:00:00Z",
      updated_at: "2026-08-22T07:00:00Z",
    };

    vi.spyOn(scarcityApi, "triggerCanonicalScarcity").mockResolvedValue({
      incident_id: INCIDENT_ID,
      evaluation_id: "eval-1",
      decision_ids: [],
      reproducibility_key: "a".repeat(64),
    });
    vi.spyOn(carrierApi, "prepareCarrierRecovery").mockResolvedValue(carrierCase);
    vi.spyOn(scarcityApi, "getCanonicalFixture").mockResolvedValue(fixture);
    vi.spyOn(scarcityApi, "getScarcityEvaluation").mockResolvedValue(scarcityEvaluation);
    vi.spyOn(clientApi, "getIncident").mockResolvedValue(incident);
    vi.spyOn(clientApi, "getDecisions").mockResolvedValue([]);
    vi.spyOn(clientApi, "getAuditEvents").mockResolvedValue([]);
    const listSpy = vi
      .spyOn(carrierApi, "listCarrierCases")
      .mockResolvedValue([carrierCase]);
    vi.spyOn(carrierApi, "getCarrierCaseHistory").mockResolvedValue({
      case: carrierCase,
      request: null,
      request_context: null,
      bindings: [],
      approvals: [],
      carrier_responses: [],
      effective_timings: [],
      decision_links: [],
      decisions: [],
      results: [],
      audit_events: [],
    });

    const { result } = renderHook(() => useRecoveryConsole());

    await act(async () => {
      await result.current.createCanonicalIncident();
    });

    await act(async () => {
      await result.current.prepareCarrierRecovery("SYN-CONN-JV2");
    });

    expect(carrierApi.prepareCarrierRecovery).toHaveBeenCalled();
    expect(listSpy).toHaveBeenCalledWith(INCIDENT_ID);
    expect(result.current.carrierCases[0]?.id).toBe(CASE_ID);
  });

  it("refreshes on 409 conflict", async () => {
    vi.spyOn(scarcityApi, "triggerCanonicalScarcity").mockResolvedValue({
      incident_id: INCIDENT_ID,
      evaluation_id: "eval-1",
      decision_ids: [],
      reproducibility_key: "a".repeat(64),
    });
    vi.spyOn(scarcityApi, "getCanonicalFixture").mockResolvedValue(fixture);
    vi.spyOn(scarcityApi, "getScarcityEvaluation").mockResolvedValue(scarcityEvaluation);
    vi.spyOn(clientApi, "getIncident").mockResolvedValue(incident);
    vi.spyOn(clientApi, "getDecisions").mockResolvedValue([]);
    vi.spyOn(clientApi, "getAuditEvents").mockResolvedValue([]);
    vi.spyOn(carrierApi, "listCarrierCases").mockResolvedValue([
      {
        id: CASE_ID,
        incident_id: INCIDENT_ID,
        connection_id: "SYN-CONN-JV2",
        source_evaluation_id: "eval-1",
        affected_container_ids: ["SYN-CNT-017"],
        state: "AWAITING_CARRIER" as const,
        created_at: "2026-08-22T07:00:00Z",
        updated_at: "2026-08-22T07:00:00Z",
      },
    ]);
    vi.spyOn(carrierApi, "getCarrierCaseHistory").mockResolvedValue({
      case: {
        id: CASE_ID,
        incident_id: INCIDENT_ID,
        connection_id: "SYN-CONN-JV2",
        source_evaluation_id: "eval-1",
        affected_container_ids: ["SYN-CNT-017"],
        state: "AWAITING_CARRIER",
        created_at: "2026-08-22T07:00:00Z",
        updated_at: "2026-08-22T07:00:00Z",
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
      audit_events: [],
    });
    vi.spyOn(carrierApi, "sendCarrierRequest").mockRejectedValue(
      new ApiError(409, "carrier send is not valid"),
    );

    const { result } = renderHook(() => useRecoveryConsole());

    await act(async () => {
      await result.current.createCanonicalIncident();
      result.current.setSelectedCarrierCaseId(CASE_ID);
    });

    await act(async () => {
      await result.current.sendRequest();
    });

    expect(scarcityApi.getScarcityEvaluation).toHaveBeenCalled();
    expect(result.current.error?.status).toBe(409);
  });
});
