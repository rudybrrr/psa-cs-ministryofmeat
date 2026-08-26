import { renderHook, act, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as agentApi from "../api/agentRuntime";
import * as carrierApi from "../api/carrierRecovery";
import * as clientApi from "../api/client";
import * as scarcityApi from "../api/scarcity";
import * as dynamicYardApi from "../api/dynamicYard";
import * as cargoSafetyApi from "../api/cargoSafety";
import * as canonicalReplayApi from "../api/canonicalReplay";
import { ApiError } from "../api/client";
import type { AgentRun, CargoSafetyReview } from "../api/types";
import { useRecoveryConsole } from "./useRecoveryConsole";

vi.mock("../api/agentRuntime", () => ({ createAgentRun: vi.fn(), advanceAgentRun: vi.fn(), listAgentRuns: vi.fn().mockResolvedValue([]), getAgentRunHistory: vi.fn() }));
vi.mock("../api/dynamicYard", () => ({ bootstrapDynamicYard: vi.fn(), publishDischargeActive: vi.fn(), selectTradeoff: vi.fn(), listYardForecasts: vi.fn().mockResolvedValue([]), listAllocationRevisions: vi.fn().mockResolvedValue([]), listExpediteCommitments: vi.fn().mockResolvedValue([]), listReconsiderations: vi.fn().mockResolvedValue([]), listTradeoffReviews: vi.fn().mockResolvedValue([]), listTradeoffOptions: vi.fn().mockResolvedValue([]) }));
vi.mock("../api/cargoSafety", () => ({ createCargoSafetyReview: vi.fn(), evaluateCargoSafetyReview: vi.fn(), listCargoSafetyReviews: vi.fn().mockResolvedValue([]), getCargoSafetyHistory: vi.fn() }));
vi.mock("../api/canonicalReplay", () => ({
  fetchCanonicalReplayStage: vi.fn().mockResolvedValue(null),
  createCanonicalDemoAgentRun: vi.fn(),
  initialCanonicalStageView: vi.fn(() => ({
    stage: "READY_TO_CREATE",
    ordinal: 1,
    progress_label: "Stage 1 of 16",
    status: "PENDING_ACTION",
    explanation: "No incident is loaded yet.",
    next_allowed_action: "CREATE_CANONICAL_INCIDENT",
    guided_can_execute: true,
    auto_replay_may_execute: true,
    requires_human_authority: false,
    deviation_reason: null,
  })),
}));

const INCIDENT_ID = "11111111-1111-4111-8111-111111111111";
const CASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const RUN_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const REVIEW_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const NOTE_TEXT =
  "Manifest declares general cargo; free-text handling note identifies corrosive material and requires safety review.";

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

const emptyCarrierHistory = {
  case: {
    id: CASE_ID,
    incident_id: INCIDENT_ID,
    connection_id: "SYN-CONN-JV2",
    source_evaluation_id: "eval-1",
    affected_container_ids: ["SYN-CNT-017"],
    state: "AWAITING_REQUEST_APPROVAL" as const,
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
};

const agentRun = (overrides: Partial<AgentRun> = {}): AgentRun => ({
  id: RUN_ID,
  incident_id: INCIDENT_ID,
  state: "RUNNING",
  model_name: "fake-model",
  prompt_version: "incident-agent-v1",
  step_count: 1,
  max_steps: 16,
  wait_kind: null,
  wait_subject_id: null,
  escalation_reason: null,
  started_at: "2026-08-22T08:00:00Z",
  updated_at: "2026-08-22T08:01:00Z",
  completed_at: null,
  ...overrides,
});

const agentHistoryFor = (run: AgentRun) => ({ run, steps: [], tool_invocations: [] });

const safetyReview = (overrides: Partial<CargoSafetyReview> = {}): CargoSafetyReview => ({
  id: REVIEW_ID,
  incident_id: INCIDENT_ID,
  container_id: "SYN-CNT-010",
  cargo_note_id: "note-1",
  state: "PENDING_CHECK",
  created_at: "2026-08-22T09:00:00Z",
  updated_at: "2026-08-22T09:00:00Z",
  ...overrides,
});

const safetyHistoryFor = (review: CargoSafetyReview) => ({
  review,
  note: {
    id: review.cargo_note_id,
    incident_id: INCIDENT_ID,
    container_id: review.container_id,
    text: NOTE_TEXT,
    source: "synthetic-canonical-cargo-note",
    created_at: review.created_at,
  },
  assessment: null,
  policy_result: null,
  audit_events: [],
});

const yardSnapshot = {
  id: "snap-pre",
  incident_id: INCIDENT_ID,
  stage: "PRE_DISCHARGE" as const,
  generated_at: "2026-08-22T07:30:00Z",
  source: "canonical-harness",
  container_forecasts: [
    { container_id: "SYN-CNT-017", p10_ready_at: "2026-08-22T04:40:00Z", p50_ready_at: "2026-08-22T05:10:00Z", p90_ready_at: "2026-08-22T05:40:00Z" },
  ],
};

function mockBaseReads(overrides: {
  incident?: typeof incident;
  agentRuns?: AgentRun[];
  safetyReviews?: CargoSafetyReview[];
  carrierCasesOverride?: unknown[];
} = {}) {
  vi.spyOn(scarcityApi, "triggerCanonicalScarcity").mockResolvedValue({
    incident_id: INCIDENT_ID,
    evaluation_id: "eval-1",
    decision_ids: [],
    reproducibility_key: "a".repeat(64),
  });
  vi.spyOn(scarcityApi, "getCanonicalFixture").mockResolvedValue(fixture);
  vi.spyOn(scarcityApi, "getScarcityEvaluation").mockResolvedValue(scarcityEvaluation);
  vi.spyOn(clientApi, "getIncident").mockResolvedValue(overrides.incident ?? incident);
  vi.spyOn(clientApi, "getDecisions").mockResolvedValue([]);
  vi.spyOn(clientApi, "getAuditEvents").mockResolvedValue([]);
  vi.spyOn(carrierApi, "listCarrierCases").mockResolvedValue(overrides.carrierCasesOverride ?? []);
  vi.mocked(dynamicYardApi.listYardForecasts).mockResolvedValue([]);
  vi.mocked(dynamicYardApi.listAllocationRevisions).mockResolvedValue([]);
  vi.mocked(dynamicYardApi.listExpediteCommitments).mockResolvedValue([]);
  vi.mocked(dynamicYardApi.listReconsiderations).mockResolvedValue([]);
  vi.mocked(dynamicYardApi.listTradeoffReviews).mockResolvedValue([]);
  vi.mocked(dynamicYardApi.listTradeoffOptions).mockResolvedValue([]);
  vi.mocked(cargoSafetyApi.listCargoSafetyReviews).mockResolvedValue(overrides.safetyReviews ?? []);
  vi.mocked(agentApi.listAgentRuns).mockResolvedValue(overrides.agentRuns ?? []);
  vi.mocked(canonicalReplayApi.fetchCanonicalReplayStage).mockResolvedValue({
    stage: "READY_FOR_PRE_DISCHARGE",
    ordinal: 2,
    progress_label: "Stage 2 of 16",
    status: "PENDING_ACTION",
    explanation: "bootstrap",
    next_allowed_action: "BOOTSTRAP_PRE_DISCHARGE",
    guided_can_execute: true,
    auto_replay_may_execute: true,
    requires_human_authority: false,
    deviation_reason: null,
  });
}

describe("useRecoveryConsole", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    vi.mocked(dynamicYardApi.listYardForecasts).mockResolvedValue([]);
    vi.mocked(dynamicYardApi.listAllocationRevisions).mockResolvedValue([]);
    vi.mocked(dynamicYardApi.listExpediteCommitments).mockResolvedValue([]);
    vi.mocked(dynamicYardApi.listReconsiderations).mockResolvedValue([]);
    vi.mocked(dynamicYardApi.listTradeoffReviews).mockResolvedValue([]);
    vi.mocked(dynamicYardApi.listTradeoffOptions).mockResolvedValue([]);
    vi.mocked(cargoSafetyApi.listCargoSafetyReviews).mockResolvedValue([]);
    vi.mocked(agentApi.listAgentRuns).mockResolvedValue([]);
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

  it("loads the complete phase 5/6 bundle including agent, wait, and safety histories", async () => {
    const run = agentRun({
      state: "WAITING",
      wait_kind: "REQUEST_APPROVAL",
      wait_subject_id: CASE_ID,
    });
    const review = safetyReview();
    mockBaseReads({ agentRuns: [run], safetyReviews: [review] });
    vi.mocked(agentApi.getAgentRunHistory).mockResolvedValue(agentHistoryFor(run));
    vi.spyOn(carrierApi, "getCarrierCaseHistory").mockResolvedValue(emptyCarrierHistory);
    vi.mocked(cargoSafetyApi.getCargoSafetyHistory).mockResolvedValue(safetyHistoryFor(review));

    const { result } = renderHook(() => useRecoveryConsole());

    await act(async () => {
      await result.current.createCanonicalIncident();
    });

    await waitFor(() => {
      expect(result.current.incident?.id).toBe(INCIDENT_ID);
      expect(result.current.fixture?.fixture_id).toBe("SYN-CANONICAL-24-V1");
      expect(result.current.scarcityEvaluation?.id).toBe("eval-1");
      expect(result.current.decisions).toEqual([]);
      expect(result.current.auditEvents).toEqual([]);
      expect(result.current.carrierCases).toEqual([]);
      expect(result.current.yardForecasts).toEqual([]);
      expect(result.current.allocationRevisions).toEqual([]);
      expect(result.current.expediteCommitments).toEqual([]);
      expect(result.current.reconsiderations).toEqual([]);
      expect(result.current.tradeoffReviews).toEqual([]);
      expect(result.current.tradeoffOptions).toEqual([]);
      expect(result.current.agentRuns.at(-1)?.id).toBe(RUN_ID);
      expect(result.current.cargoSafetyReviews.at(-1)?.id).toBe(REVIEW_ID);
      expect(result.current.selectedAgentHistory?.run.id).toBe(RUN_ID);
      expect(result.current.agentWaitHistory?.case.id).toBe(CASE_ID);
      expect(result.current.safetyHistories.at(-1)?.review.id).toBe(REVIEW_ID);
    });
    expect(agentApi.getAgentRunHistory).toHaveBeenCalledWith(RUN_ID);
    expect(carrierApi.getCarrierCaseHistory).toHaveBeenCalledWith(CASE_ID);
    expect(cargoSafetyApi.getCargoSafetyHistory).toHaveBeenCalledWith(REVIEW_ID);
  });

  it("surfaces phase 5/6 read failures as user-visible errors instead of silent empty lists", async () => {
    mockBaseReads();
    vi.mocked(dynamicYardApi.listTradeoffOptions).mockRejectedValue(
      new ApiError(503, "allocation tradeoff options unavailable"),
    );

    const { result } = renderHook(() => useRecoveryConsole());

    await act(async () => {
      await result.current.createCanonicalIncident();
    });

    await waitFor(() => {
      expect(result.current.error?.status).toBe(503);
      expect(result.current.error?.detail).toContain("allocation tradeoff options unavailable");
      expect(result.current.incident).toBeNull();
    });
  });

  it("clears stale phase 5/6 state when a new canonical incident is created", async () => {
    const run = agentRun();
    const review = safetyReview();
    mockBaseReads({ agentRuns: [run], safetyReviews: [review] });
    vi.mocked(agentApi.getAgentRunHistory).mockResolvedValue(agentHistoryFor(run));
    vi.mocked(cargoSafetyApi.getCargoSafetyHistory).mockResolvedValue(safetyHistoryFor(review));
    vi.mocked(dynamicYardApi.listYardForecasts).mockResolvedValue([yardSnapshot]);
    vi.mocked(dynamicYardApi.listTradeoffReviews).mockResolvedValue([
      {
        id: "review-open",
        incident_id: INCIDENT_ID,
        reconsideration_assessment_id: "assessment-1",
        option_ids: ["option-1"],
        options_fingerprint: "fp",
        state: "OPEN" as const,
        created_at: "2026-08-22T08:30:00Z",
      },
    ]);

    const { result } = renderHook(() => useRecoveryConsole());

    await act(async () => {
      await result.current.createCanonicalIncident();
    });
    await waitFor(() => expect(result.current.yardForecasts.length).toBe(1));

    const secondIncident = { ...incident, id: "22222222-2222-4222-8222-222222222222" };
    vi.spyOn(scarcityApi, "triggerCanonicalScarcity").mockResolvedValue({
      incident_id: secondIncident.id,
      evaluation_id: "eval-2",
      decision_ids: [],
      reproducibility_key: "b".repeat(64),
    });
    vi.spyOn(clientApi, "getIncident").mockResolvedValue(secondIncident);
    vi.mocked(dynamicYardApi.listYardForecasts).mockResolvedValue([]);
    vi.mocked(dynamicYardApi.listTradeoffReviews).mockResolvedValue([]);
    vi.mocked(agentApi.listAgentRuns).mockResolvedValue([]);
    vi.mocked(cargoSafetyApi.listCargoSafetyReviews).mockResolvedValue([]);

    await act(async () => {
      await result.current.createCanonicalIncident();
    });

    await waitFor(() => {
      expect(result.current.incident?.id).toBe(secondIncident.id);
      expect(result.current.yardForecasts).toEqual([]);
      expect(result.current.tradeoffReviews).toEqual([]);
      expect(result.current.agentRuns).toEqual([]);
      expect(result.current.cargoSafetyReviews).toEqual([]);
      expect(result.current.safetyHistories).toEqual([]);
      expect(result.current.selectedAgentHistory).toBeNull();
      expect(result.current.agentWaitHistory).toBeNull();
      expect(result.current.selectedContainerId).toBeNull();
      expect(result.current.selectedCarrierCaseId).toBeNull();
      expect(result.current.selectedCaseHistory).toBeNull();
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

  it("bootstrapYard posts exactly once and refreshes persisted forecasts afterwards", async () => {
    mockBaseReads();
    const { result } = renderHook(() => useRecoveryConsole());
    await act(async () => {
      await result.current.createCanonicalIncident();
    });
    const forecastReadsAfterCreate = vi.mocked(dynamicYardApi.listYardForecasts).mock.calls.length;
    vi.mocked(dynamicYardApi.bootstrapDynamicYard).mockResolvedValue([]);

    await act(async () => {
      await result.current.bootstrapYard();
    });

    expect(dynamicYardApi.bootstrapDynamicYard).toHaveBeenCalledTimes(1);
    expect(dynamicYardApi.bootstrapDynamicYard).toHaveBeenCalledWith(INCIDENT_ID);
    expect(vi.mocked(dynamicYardApi.listYardForecasts).mock.calls.length).toBe(
      forecastReadsAfterCreate + 1,
    );
    expect(result.current.error).toBeNull();
  });

  it("startAgent creates exactly one run and refreshes agent runs afterwards", async () => {
    mockBaseReads();
    const { result } = renderHook(() => useRecoveryConsole());
    await act(async () => {
      await result.current.createCanonicalIncident();
    });
    const agentListReadsAfterCreate = vi.mocked(agentApi.listAgentRuns).mock.calls.length;
    vi.mocked(agentApi.createAgentRun).mockResolvedValue(agentRun({ state: "CREATED", step_count: 0 }));

    await act(async () => {
      await result.current.startAgent();
    });

    expect(agentApi.createAgentRun).toHaveBeenCalledTimes(1);
    expect(agentApi.createAgentRun).toHaveBeenCalledWith(INCIDENT_ID);
    expect(vi.mocked(agentApi.listAgentRuns).mock.calls.length).toBe(
      agentListReadsAfterCreate + 1,
    );
  });

  it("advanceAgent advances exactly once, never loops, and refreshes afterwards", async () => {
    const run = agentRun();
    mockBaseReads({ agentRuns: [run] });
    vi.mocked(agentApi.getAgentRunHistory).mockResolvedValue(agentHistoryFor(run));
    const { result } = renderHook(() => useRecoveryConsole());
    await act(async () => {
      await result.current.createCanonicalIncident();
    });
    const advanceCallsAfterCreate = vi.mocked(agentApi.advanceAgentRun).mock.calls.length;
    const agentListReadsAfterCreate = vi.mocked(agentApi.listAgentRuns).mock.calls.length;
    vi.mocked(agentApi.advanceAgentRun).mockResolvedValue(agentRun({ state: "RUNNING", step_count: 2 }));

    await act(async () => {
      await result.current.advanceAgent();
    });

    expect(vi.mocked(agentApi.advanceAgentRun).mock.calls.length).toBe(advanceCallsAfterCreate + 1);
    expect(agentApi.advanceAgentRun).toHaveBeenLastCalledWith(RUN_ID);
    expect(vi.mocked(agentApi.listAgentRuns).mock.calls.length).toBe(
      agentListReadsAfterCreate + 1,
    );
  });

  it("publishActive publishes evidence once and never advances the agent", async () => {
    mockBaseReads();
    const { result } = renderHook(() => useRecoveryConsole());
    await act(async () => {
      await result.current.createCanonicalIncident();
    });
    const reconsiderationReadsAfterCreate = vi.mocked(dynamicYardApi.listReconsiderations).mock.calls.length;
    vi.mocked(dynamicYardApi.publishDischargeActive).mockResolvedValue({
      id: "assessment-1",
      incident_id: INCIDENT_ID,
      source_snapshot_id: "snap-active",
      prior_allocation_revision_id: "revision-r0",
      locked_container_ids: ["SYN-CNT-002", "SYN-CNT-004"],
      candidate_options: [],
      preserved_connection_total_before: 601,
      preserved_connection_total_after: 602,
      expected_preserved_connections_before: 12.02,
      expected_preserved_connections_after: 12.04,
      disposition: "AUTO_SUPERSEDE",
      reason: "feasible locked allocation strictly improves preserved connections",
      handled_at: null,
      created_at: "2026-08-22T08:30:00Z",
    });

    await act(async () => {
      await result.current.publishActive();
    });

    expect(dynamicYardApi.publishDischargeActive).toHaveBeenCalledTimes(1);
    expect(dynamicYardApi.publishDischargeActive).toHaveBeenCalledWith(INCIDENT_ID);
    expect(agentApi.advanceAgentRun).not.toHaveBeenCalled();
    expect(vi.mocked(dynamicYardApi.listReconsiderations).mock.calls.length).toBe(
      reconsiderationReadsAfterCreate + 1,
    );
  });

  it("chooseTradeoff submits exactly the persisted option id, fingerprint, and console operator", async () => {
    mockBaseReads();
    const review = {
      id: "review-open",
      incident_id: INCIDENT_ID,
      reconsideration_assessment_id: "assessment-1",
      option_ids: ["option-1", "option-2"] as const,
      options_fingerprint: "fingerprint-64",
      state: "OPEN" as const,
      created_at: "2026-08-22T08:30:00Z",
    };
    const { result } = renderHook(() => useRecoveryConsole());
    await act(async () => {
      await result.current.createCanonicalIncident();
    });
    vi.mocked(dynamicYardApi.selectTradeoff).mockResolvedValue([]);

    await act(async () => {
      await result.current.chooseTradeoff(
        review as unknown as Parameters<typeof result.current.chooseTradeoff>[0],
        "option-2",
      );
    });

    expect(dynamicYardApi.selectTradeoff).toHaveBeenCalledExactlyOnceWith("review-open", {
      selected_option_id: "option-2",
      expected_options_fingerprint: "fingerprint-64",
      operator_id: "operator-console",
    });
  });

  it("persists the canonical SYN-CNT-010 contradiction once without evaluating or advancing", async () => {
    const review = safetyReview();
    mockBaseReads({ safetyReviews: [review] });
    vi.mocked(cargoSafetyApi.getCargoSafetyHistory).mockResolvedValue(safetyHistoryFor(review));
    const { result } = renderHook(() => useRecoveryConsole());
    await act(async () => {
      await result.current.createCanonicalIncident();
    });
    const safetyListReadsAfterCreate = vi.mocked(cargoSafetyApi.listCargoSafetyReviews).mock.calls.length;
    vi.mocked(cargoSafetyApi.createCargoSafetyReview).mockResolvedValue(review);

    await act(async () => {
      await result.current.createSafetyReview("SYN-CNT-010");
    });

    expect(cargoSafetyApi.createCargoSafetyReview).toHaveBeenCalledTimes(1);
    expect(cargoSafetyApi.createCargoSafetyReview).toHaveBeenCalledWith(
      INCIDENT_ID,
      "SYN-CNT-010",
      NOTE_TEXT,
      "synthetic-canonical-cargo-note",
    );
    expect(cargoSafetyApi.evaluateCargoSafetyReview).not.toHaveBeenCalled();
    expect(agentApi.advanceAgentRun).not.toHaveBeenCalled();
    expect(vi.mocked(cargoSafetyApi.listCargoSafetyReviews).mock.calls.length).toBe(
      safetyListReadsAfterCreate + 1,
    );
  });

  it("evaluateSafety evaluates exactly one existing review and refreshes afterwards", async () => {
    const review = safetyReview();
    mockBaseReads({ safetyReviews: [review] });
    vi.mocked(cargoSafetyApi.getCargoSafetyHistory).mockResolvedValue(safetyHistoryFor(review));
    const { result } = renderHook(() => useRecoveryConsole());
    await act(async () => {
      await result.current.createCanonicalIncident();
    });
    const safetyHistoryReadsAfterCreate = vi.mocked(cargoSafetyApi.getCargoSafetyHistory).mock.calls.length;
    vi.mocked(cargoSafetyApi.evaluateCargoSafetyReview).mockResolvedValue({
      review: safetyReview({ state: "COMPLETED" }),
      assessment: {
        id: "assessment-semantic",
        review_id: REVIEW_ID,
        incident_id: INCIDENT_ID,
        container_id: "SYN-CNT-010",
        cargo_note_id: "note-1",
        result: "CONTRADICTION_FOUND",
        explanation: "Declaration contradicts the handling note.",
        evidence_excerpt: "corrosive material",
        failure_kind: null,
        structured_dangerous_goods: false,
        structured_un_number: null,
        structured_commodity: "x",
        checker_kind: "fake-checker",
        model_name: null,
        prompt_version: "cargo-safety-v1",
        latency_ms: null,
        input_tokens: null,
        output_tokens: null,
        created_at: "2026-08-22T09:05:00Z",
      },
      policy_result: {
        id: "policy-result-1",
        review_id: REVIEW_ID,
        assessment_id: "assessment-semantic",
        incident_id: INCIDENT_ID,
        container_id: "SYN-CNT-010",
        disposition: "ESCALATE",
        automation_blocked: true,
        reason: "deterministic policy blocks automation",
        replacement_decision_id: null,
        created_at: "2026-08-22T09:05:01Z",
      },
      decision: null,
    });

    await act(async () => {
      await result.current.evaluateSafety(REVIEW_ID);
    });

    expect(cargoSafetyApi.evaluateCargoSafetyReview).toHaveBeenCalledTimes(1);
    expect(cargoSafetyApi.evaluateCargoSafetyReview).toHaveBeenCalledWith(REVIEW_ID);
    expect(vi.mocked(cargoSafetyApi.getCargoSafetyHistory).mock.calls.length).toBe(
      safetyHistoryReadsAfterCreate + 1,
    );
  });

  it("loads the projected canonical replay stage with the incident bundle", async () => {
    mockBaseReads();
    const { result } = renderHook(() => useRecoveryConsole());
    expect(result.current.canonicalStage.stage).toBe("READY_TO_CREATE");
    await act(async () => {
      await result.current.createCanonicalIncident();
    });
    expect(canonicalReplayApi.fetchCanonicalReplayStage).toHaveBeenCalledWith(INCIDENT_ID);
    expect(result.current.canonicalStage.stage).toBe("READY_FOR_PRE_DISCHARGE");
  });

  it("startDemoAgentRun posts once to the synthetic demo route and refreshes", async () => {
    mockBaseReads();
    const { result } = renderHook(() => useRecoveryConsole());
    await act(async () => {
      await result.current.createCanonicalIncident();
    });
    const agentListReadsAfterCreate = vi.mocked(agentApi.listAgentRuns).mock.calls.length;
    vi.mocked(canonicalReplayApi.createCanonicalDemoAgentRun).mockResolvedValue(
      agentRun({ model_name: "canonical-replay-agent-v1", state: "CREATED", step_count: 0 }),
    );

    await act(async () => {
      await result.current.startDemoAgentRun();
    });

    expect(canonicalReplayApi.createCanonicalDemoAgentRun).toHaveBeenCalledTimes(1);
    expect(canonicalReplayApi.createCanonicalDemoAgentRun).toHaveBeenCalledWith(INCIDENT_ID);
    expect(agentApi.createAgentRun).not.toHaveBeenCalled();
    expect(vi.mocked(agentApi.listAgentRuns).mock.calls.length).toBe(agentListReadsAfterCreate + 1);
  });

  it("approvals accept an explicit synthetic operator identity", async () => {
    const run = agentRun({ wait_kind: "REQUEST_APPROVAL", wait_subject_id: CASE_ID });
    mockBaseReads({
      agentRuns: [run],
      carrierCasesOverride: [
        {
          id: CASE_ID,
          incident_id: INCIDENT_ID,
          connection_id: "SYN-CONN-JV2",
          source_evaluation_id: "eval-1",
          affected_container_ids: ["SYN-CNT-017"],
          state: "AWAITING_REQUEST_APPROVAL" as const,
          created_at: "2026-08-22T07:00:00Z",
          updated_at: "2026-08-22T07:00:00Z",
        },
      ],
    });
    vi.mocked(agentApi.getAgentRunHistory).mockResolvedValue(agentHistoryFor(run));
    vi.spyOn(carrierApi, "getCarrierCaseHistory").mockResolvedValue({
      ...emptyCarrierHistory,
      bindings: [
        {
          case_id: CASE_ID,
          proposal_decision_id: "decision-1",
          subject_kind: "OUTBOUND_REQUEST" as const,
          subject_id: "request-1",
          payload_fingerprint: "fingerprint-abc",
          created_at: "2026-08-22T07:00:00Z",
        },
      ],
      request: { id: "request-1", incident_id: INCIDENT_ID, connection_id: "SYN-CONN-JV2", requested_eta_pta: "2026-08-22T08:00:00Z", status: "PENDING" as const, created_at: "2026-08-22T07:00:00Z" },
    });
    const { result } = renderHook(() => useRecoveryConsole());
    await act(async () => {
      await result.current.createCanonicalIncident();
      result.current.setSelectedCarrierCaseId(CASE_ID);
    });
    vi.spyOn(carrierApi, "approveRequest").mockResolvedValue({ id: "approval", decision_id: "decision-1", operator_id: "synthetic-demo-operator", status: "APPROVED" as const, reason: null, created_at: "2026-08-22T09:00:00Z" });

    await act(async () => {
      await result.current.approveRequest("synthetic-demo-operator");
    });

    expect(carrierApi.approveRequest).toHaveBeenCalledWith(
      CASE_ID,
      expect.objectContaining({ operator_id: "synthetic-demo-operator", expected_payload_fingerprint: "fingerprint-abc" }),
    );
  });

  it("simulateCarrierResponse override sends the canonical effective_at and default keeps legacy timing", async () => {
    const run = agentRun({ wait_kind: "CARRIER_RESPONSE_OR_TIMEOUT", wait_subject_id: CASE_ID });
    mockBaseReads({
      agentRuns: [run],
      carrierCasesOverride: [
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
      ],
    });
    vi.mocked(agentApi.getAgentRunHistory).mockResolvedValue(agentHistoryFor(run));
    vi.spyOn(carrierApi, "getCarrierCaseHistory").mockResolvedValue(emptyCarrierHistory);
    const { result } = renderHook(() => useRecoveryConsole());
    await act(async () => {
      await result.current.createCanonicalIncident();
      result.current.setSelectedCarrierCaseId(CASE_ID);
    });
    vi.spyOn(carrierApi, "simulateCarrierResponse").mockResolvedValue({ case_id: CASE_ID, carrier_response_id: null, no_response_emitted: true });

    await act(async () => {
      await result.current.simulateCarrierResponse("2026-08-23T05:00:00Z");
    });
    expect(carrierApi.simulateCarrierResponse).toHaveBeenLastCalledWith(CASE_ID, { effective_at: "2026-08-23T05:00:00Z" });

    await act(async () => {
      await result.current.simulateCarrierResponse();
    });
    expect(carrierApi.simulateCarrierResponse).toHaveBeenLastCalledWith(CASE_ID, { effective_at: "2026-08-22T08:30:00Z" });
  });

  it("mutation outcomes expose ok and conflict flags without breaking refresh semantics", async () => {
    const run = agentRun();
    mockBaseReads({ agentRuns: [run] });
    vi.mocked(agentApi.getAgentRunHistory).mockResolvedValue(agentHistoryFor(run));
    const { result } = renderHook(() => useRecoveryConsole());
    await act(async () => {
      await result.current.createCanonicalIncident();
    });
    vi.mocked(agentApi.advanceAgentRun).mockRejectedValue(new ApiError(409, "wait upgrade"));

    let outcome: { ok: boolean; conflict: boolean } | undefined;
    await act(async () => {
      outcome = await result.current.advanceAgent();
    });
    expect(outcome?.ok).toBe(false);
    expect(outcome?.conflict).toBe(true);
    expect(result.current.error?.status).toBe(409);

    vi.mocked(agentApi.advanceAgentRun).mockResolvedValue(run);
    await act(async () => {
      outcome = await result.current.advanceAgent();
    });
    expect(outcome?.ok).toBe(true);
    expect(outcome?.conflict).toBe(false);
  });
});
