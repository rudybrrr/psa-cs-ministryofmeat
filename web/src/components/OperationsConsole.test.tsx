import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationsConsole } from "./OperationsConsole";
import { jsonResponse } from "../test/fixtures";

// Restored pre-Phase-6 OperationsConsole coverage (last published at f7e8385),
// adapted to the Phase 6 bundle APIs instead of deleting coverage.
//
// Superseded assertions (deliberate approved UI changes, not lost coverage):
// * "Run counter"/"Run silent"/demo-run autoplay buttons were removed by the
//   approved Phase 6 design (no autoplay/run-all/reset/replay). Their flows are
//   re-proven below against explicitly persisted state created through the
//   remaining eligible controls/mocked persistence.
// * Optional swallowing of missing Phase 5 endpoints is gone: the mocks now
//   serve every Phase 6 read route explicitly.

const INCIDENT_ID = "11111111-1111-4111-8111-111111111111";
const CASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const incidentId = INCIDENT_ID;
const fixture = { fixture_id: "SYN", event: { id: "event", vessel_call_id: "v", vessel_name: "v", terminal_id: "T", scheduled_arrival: "2026-08-25T00:00:00Z", estimated_arrival: "2026-08-25T01:00:00Z", delay_minutes: 60, occurred_at: "2026-08-25T01:00:00Z" }, services: [], profiles: [], capacity: { id: "cap", terminal_id: "T", window_start: "2026-08-25T00:00:00Z", window_end: "2026-08-25T01:00:00Z", overlap_service_ids: [], total_slots: 1, handling_group_limits: [], max_reefer_slots: 0, max_dg_slots: 0 } };
const report = { id: "eval", incident_id: incidentId, fixture_id: "SYN", seed: 1, scenario_count: 50, baseline: { allocation: { strategy: "P50_GREEDY", allocated_container_ids: [] }, world_count: 50, preserved_connection_total: 1, expected_preserved_connections: 1, rollover_total: 0, expected_rollovers: 0, p10_preserved_connections: 1, allocation_slot_count: 0, capacity_violations: 0, unsafe_allocations: 0, runtime_ms: 1, service_outcomes: [] }, scenario_aware_evaluations: [], pareto_evaluations: [], selected_allocation: null, reproducibility_key: "a".repeat(64), created_at: "2026-08-25T01:00:00Z" };

const incident = {
  id: INCIDENT_ID,
  source_event_id: "SYN-EVT-ASX17-20260822-001",
  state: "RECOVERY_ANALYSIS",
  created_at: "2026-08-22T08:00:00Z",
};

const scarcityEvaluation = {
  id: "eval-1",
  incident_id: INCIDENT_ID,
  fixture_id: "SYN-CANONICAL-24-V1",
  seed: 20260822,
  scenario_count: 50,
  baseline: {
    allocation: { strategy: "P50_GREEDY", allocated_container_ids: [] },
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
  scenario_aware_evaluations: [
    {
      allocation: { strategy: "SCENARIO_AWARE", allocated_container_ids: ["SYN-CNT-017"] },
      world_count: 50,
      preserved_connection_total: 12,
      expected_preserved_connections: 11.2,
      rollover_total: 3,
      expected_rollovers: 2.8,
      p10_preserved_connections: 10,
      allocation_slot_count: 1,
      capacity_violations: 0,
      unsafe_allocations: 0,
      runtime_ms: 2,
      service_outcomes: [],
    },
  ],
  pareto_evaluations: [],
  selected_allocation: { strategy: "SCENARIO_AWARE", allocated_container_ids: ["SYN-CNT-017"] },
  reproducibility_key: "a".repeat(64),
  created_at: "2026-08-22T08:00:00Z",
};

function minimalFixture() {
  return {
    fixture_id: "SYN-CANONICAL-24-V1",
    event: {
      id: "evt",
      vessel_call_id: "vc",
      vessel_name: "v",
      terminal_id: "SYN-TUAS-TERMINAL",
      scheduled_arrival: "2026-08-22T01:00:00Z",
      estimated_arrival: "2026-08-22T04:15:00Z",
      delay_minutes: 195,
      occurred_at: "2026-08-22T04:15:00Z",
    },
    services: [
      {
        service_id: "JV2",
        connection: {
          id: "SYN-CONN-JV2",
          outbound_vessel_name: "v",
          outbound_voyage: "v1",
          destination_port: "IDJKT",
          cutoff_at: "2026-08-22T05:00:00Z",
          departure_at: "2026-08-22T07:00:00Z",
          minimum_transfer_minutes: 90,
          expedited_transfer_minutes: 60,
        },
        planned_time_of_arrival: "2026-08-22T05:00:00Z",
        ready_boundary: "2026-08-22T05:35:00Z",
      },
      {
        service_id: "EC3",
        connection: {
          id: "SYN-CONN-EC3",
          outbound_vessel_name: "v2",
          outbound_voyage: "v2",
          destination_port: "CNSHA",
          cutoff_at: "2026-08-22T07:00:00Z",
          departure_at: "2026-08-22T09:00:00Z",
          minimum_transfer_minutes: 90,
          expedited_transfer_minutes: 60,
        },
        planned_time_of_arrival: "2026-08-22T07:00:00Z",
        ready_boundary: "2026-08-22T07:35:00Z",
      },
    ],
    profiles: [
      {
        container: {
          id: "SYN-CNT-017",
          origin_port: "NLRTM",
          destination_port: "IDJKT",
          cargo: { commodity: "x", gross_weight_kg: 1, dangerous_goods: false, un_number: null },
          inbound_vessel_call_id: "vc",
          onward_connection: {
            id: "SYN-CONN-JV2",
            outbound_vessel_name: "v",
            outbound_voyage: "v1",
            destination_port: "IDJKT",
            cutoff_at: "2026-08-22T05:00:00Z",
            departure_at: "2026-08-22T07:00:00Z",
            minimum_transfer_minutes: 90,
            expedited_transfer_minutes: 60,
          },
        },
        service_id: "JV2",
        handling_group_id: "HG",
        cargo_kind: "DRY",
        base_ready_at: "2026-08-22T05:10:00Z",
        expedite_minutes_saved: 30,
        reefer_continuity_available: true,
        dg_structurally_cleared: true,
      },
      {
        container: {
          id: "SYN-CNT-021",
          origin_port: "NLRTM",
          destination_port: "CNSHA",
          cargo: { commodity: "y", gross_weight_kg: 1, dangerous_goods: false, un_number: null },
          inbound_vessel_call_id: "vc",
          onward_connection: {
            id: "SYN-CONN-EC3",
            outbound_vessel_name: "v2",
            outbound_voyage: "v2",
            destination_port: "CNSHA",
            cutoff_at: "2026-08-22T07:00:00Z",
            departure_at: "2026-08-22T09:00:00Z",
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
      terminal_id: "SYN-TUAS-TERMINAL",
      window_start: "2026-08-22T05:00:00Z",
      window_end: "2026-08-22T06:00:00Z",
      overlap_service_ids: ["JV2", "EC3"],
      total_slots: 8,
      handling_group_limits: [],
      max_reefer_slots: 3,
      max_dg_slots: 1,
    },
  };
}

interface FetchMockHandlers {
  carrierCases?: unknown[];
  historyByCase?: Record<string, unknown>;
  agentRuns?: unknown[];
  yardForecasts?: unknown[];
  allocationRevisions?: unknown[];
  tradeoffReviews?: unknown[];
  tradeoffOptions?: unknown[];
  cargoSafetyReviews?: unknown[];
  canonicalStage?: Record<string, unknown>;
  onPost?: (url: string, body?: unknown) => void;
}

export const defaultStageView = (overrides: Record<string, unknown> = {}) => ({
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
  ...overrides,
});

function createFetchMock(handlers: FetchMockHandlers = {}) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;

    if (method === "POST") {
      handlers.onPost?.(url, body);
    }

    if (url.endsWith("/synthetic/scenarios/canonical-scarcity") && method === "POST") {
      return jsonResponse(
        {
          incident_id: INCIDENT_ID,
          evaluation_id: "eval-1",
          decision_ids: [],
          reproducibility_key: "a".repeat(64),
        },
        201,
      );
    }

    if (url.endsWith("/synthetic/scenarios/canonical-scarcity/fixture")) {
      return jsonResponse(minimalFixture());
    }

    if (url.includes("/canonical-replay/stage")) {
      return jsonResponse(handlers.canonicalStage ?? defaultStageView());
    }

    if (url.endsWith("/canonical-replay/agent-runs") && method === "POST") {
      return jsonResponse({ id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", incident_id: INCIDENT_ID, state: "CREATED", model_name: "canonical-replay-agent-v1", prompt_version: "incident-agent-v1", step_count: 0, max_steps: 16, wait_kind: null, wait_subject_id: null, escalation_reason: null, started_at: "2026-08-22T08:00:00Z", updated_at: "2026-08-22T08:00:00Z", completed_at: null }, 201);
    }

    if (url.endsWith(`/incidents/${INCIDENT_ID}/scarcity-evaluation`)) {
      return jsonResponse(scarcityEvaluation);
    }

    if (url.endsWith(`/incidents/${INCIDENT_ID}`)) {
      return jsonResponse(incident);
    }

    if (url.endsWith(`/incidents/${INCIDENT_ID}/decisions`)) {
      return jsonResponse([
        {
          id: "d-roll",
          incident_id: INCIDENT_ID,
          container_id: "SYN-CNT-017",
          action: "ROLL",
          status: "SUPERSEDED",
          rationale: "rolled",
          supersedes: null,
          supersession_reason: null,
          created_at: "2026-08-22T08:00:00Z",
        },
        {
          id: "d-preserve",
          incident_id: INCIDENT_ID,
          container_id: "SYN-CNT-017",
          action: "PRESERVE_VIA_RTA",
          status: "APPROVED",
          rationale: "rta",
          supersedes: "d-roll",
          supersession_reason: "carrier recovery",
          created_at: "2026-08-22T09:00:00Z",
        },
      ]);
    }

    if (url.endsWith(`/incidents/${INCIDENT_ID}/audit-events`)) {
      return jsonResponse([
        {
          id: "a1",
          actor: "POLICY",
          actor_id: "policy",
          incident_id: INCIDENT_ID,
          event_type: "decision.created",
          payload: {},
          timestamp: "2026-08-22T08:00:00Z",
        },
      ]);
    }

    if (url.endsWith(`/incidents/${INCIDENT_ID}/carrier-recovery-cases`) && method === "POST") {
      return jsonResponse(
        {
          id: CASE_ID,
          incident_id: INCIDENT_ID,
          connection_id: body.connection_id as string,
          source_evaluation_id: "eval-1",
          affected_container_ids:
            body.connection_id === "SYN-CONN-EC3" ? ["SYN-CNT-021"] : ["SYN-CNT-017"],
          state: "AWAITING_REQUEST_APPROVAL",
          created_at: "2026-08-22T07:00:00Z",
          updated_at: "2026-08-22T07:00:00Z",
        },
        201,
      );
    }

    if (url.endsWith(`/incidents/${INCIDENT_ID}/carrier-recovery-cases`)) {
      return jsonResponse(handlers.carrierCases ?? []);
    }

    if (url.endsWith(`/incidents/${INCIDENT_ID}/agent-runs`) && method === "POST") {
      return jsonResponse({
        id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        incident_id: INCIDENT_ID,
        state: "CREATED",
        model_name: "fake-model",
        prompt_version: "incident-agent-v1",
        step_count: 0,
        max_steps: 16,
        wait_kind: null,
        wait_subject_id: null,
        escalation_reason: null,
        started_at: "2026-08-22T08:00:00Z",
        updated_at: "2026-08-22T08:00:00Z",
        completed_at: null,
      }, 201);
    }

    if (url.includes("/carrier-recovery-cases/") && url.endsWith("/history")) {
      const caseId = url.split("/")[2];
      return jsonResponse(
        handlers.historyByCase?.[caseId] ?? {
          case: {
            id: caseId,
            incident_id: INCIDENT_ID,
            connection_id: "SYN-CONN-JV2",
            source_evaluation_id: "eval-1",
            affected_container_ids: ["SYN-CNT-017"],
            state: "AWAITING_REQUEST_APPROVAL",
            created_at: "2026-08-22T07:00:00Z",
            updated_at: "2026-08-22T07:00:00Z",
          },
          request: null,
          request_context: {
            case_id: caseId,
            request_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
            payload_fingerprint: "fp",
            prepared_at: "2026-08-22T07:00:00Z",
            response_deadline: "2026-08-22T09:00:00Z",
            sent_at: null,
            closed_at: null,
            close_reason: null,
            timeout_observed_at: null,
          },
          bindings: [
            {
              case_id: caseId,
              proposal_decision_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
              subject_kind: "OUTBOUND_REQUEST",
              subject_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
              payload_fingerprint: "fp",
              created_at: "2026-08-22T07:00:00Z",
            },
          ],
          approvals: [],
          carrier_responses: [],
          effective_timings: [],
          decision_links: [],
          decisions: [],
          results: [],
          audit_events: [],
        },
      );
    }

    if (url.endsWith("/request-approval") && method === "POST") {
      return jsonResponse(
        { id: "ap1", decision_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd", operator_id: "operator-console", status: "APPROVED", reason: null, created_at: "2026-08-22T08:00:00Z" },
        201,
      );
    }

    if (url.endsWith("/send") && method === "POST") {
      return jsonResponse(
        {
          case_id: CASE_ID,
          request_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
          payload_fingerprint: "fp",
          prepared_at: "2026-08-22T07:00:00Z",
          response_deadline: "2026-08-22T09:00:00Z",
          sent_at: "2026-08-22T08:00:00Z",
          closed_at: null,
          close_reason: null,
          timeout_observed_at: null,
        },
        201,
      );
    }

    if (url.endsWith("/simulate-carrier-response") && method === "POST") {
      return jsonResponse(
        { case_id: CASE_ID, carrier_response_id: "cr-counter", no_response_emitted: false },
        201,
      );
    }

    if (url.endsWith("/counter-approval") && method === "POST") {
      return jsonResponse(
        { id: "ap2", decision_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd", operator_id: "operator-console", status: "APPROVED", reason: null, created_at: "2026-08-22T08:30:00Z" },
        201,
      );
    }

    if (url.endsWith("/evaluate-timeout") && method === "POST") {
      return jsonResponse(
        {
          id: CASE_ID,
          incident_id: INCIDENT_ID,
          connection_id: "SYN-CONN-EC3",
          source_evaluation_id: "eval-1",
          affected_container_ids: ["SYN-CNT-021"],
          state: "COMPLETED",
          created_at: "2026-08-22T07:00:00Z",
          updated_at: "2026-08-22T09:05:00Z",
        },
        201,
      );
    }

    if (
      url.includes(`/incidents/${INCIDENT_ID}/`) &&
      [
        "yard-forecast-snapshots",
        "allocation-revisions",
        "expedite-commitments",
        "expedite-reconsiderations",
        "allocation-tradeoff-reviews",
        "allocation-tradeoff-options",
        "cargo-safety-reviews",
        "agent-runs",
      ].some((suffix) => url.endsWith(suffix))
    ) {
      const overrides: Partial<Record<string, unknown[]>> = {
        "yard-forecast-snapshots": handlers.yardForecasts,
        "allocation-revisions": handlers.allocationRevisions,
        "allocation-tradeoff-reviews": handlers.tradeoffReviews,
        "allocation-tradeoff-options": handlers.tradeoffOptions,
        "cargo-safety-reviews": handlers.cargoSafetyReviews,
        "agent-runs": handlers.agentRuns,
      };
      for (const [suffix, value] of Object.entries(overrides)) {
        if (url.endsWith(suffix) && value !== undefined) {
          return jsonResponse(value);
        }
      }
      return jsonResponse([]);
    }
    return jsonResponse({ detail: `Unexpected ${method} ${url}` }, 500);
  });
}

describe("OperationsConsole canonical scarcity", () => {
  afterEach(() => cleanup());
  beforeEach(() => vi.restoreAllMocks());

  it("creates canonical incident and renders live recovery summary", async () => {
    vi.stubGlobal("fetch", createFetchMock());

    const user = userEvent.setup();
    render(<OperationsConsole />);

    await user.click(
      screen.getByRole("button", { name: /^start recovery demo$/i }),
    );

    await waitFor(() => {
      expect(screen.getByText("SYN-EVT-ASX17-20260822-001")).toBeInTheDocument();
      expect(screen.getByText(/live evaluation/i)).toBeInTheDocument();
      expect(screen.getByText("11.2")).toBeInTheDocument();
      expect(screen.getByText("SYN-CNT-017")).toBeInTheDocument();
    });
  });
});

describe("OperationsConsole error state", () => {
  afterEach(() => cleanup());
  beforeEach(() => vi.restoreAllMocks());

  it("shows an alert when canonical incident creation fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Synthetic scenario unavailable" }, 503)),
    );

    const user = userEvent.setup();
    render(<OperationsConsole />);
    await user.click(
      screen.getByRole("button", { name: /^start recovery demo$/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("503");
    });
  });
});

describe("RecoveryConsole persisted-state carrier flows", () => {
  afterEach(() => cleanup());
  beforeEach(() => vi.restoreAllMocks());

  it("approves a persisted COUNTER through the fingerprint-bound operator endpoint", async () => {
    const posts: Array<{ url: string; body?: unknown }> = [];
    const counterCase = {
      id: CASE_ID,
      incident_id: INCIDENT_ID,
      connection_id: "SYN-CONN-JV2",
      source_evaluation_id: "eval-1",
      affected_container_ids: ["SYN-CNT-017"],
      state: "AWAITING_COUNTER_APPROVAL",
      created_at: "2026-08-22T07:00:00Z",
      updated_at: "2026-08-22T08:30:00Z",
    };
    const counterHistory = {
      case: counterCase,
      request: {
        id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        incident_id: INCIDENT_ID,
        connection_id: "SYN-CONN-JV2",
        requested_eta_pta: "2026-08-22T08:00:00Z",
        status: "SENT",
        created_at: "2026-08-22T07:00:00Z",
      },
      request_context: {
        case_id: CASE_ID,
        request_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        payload_fingerprint: "fp",
        prepared_at: "2026-08-22T07:00:00Z",
        response_deadline: "2026-08-22T09:00:00Z",
        sent_at: "2026-08-22T08:00:00Z",
        closed_at: null,
        close_reason: null,
        timeout_observed_at: null,
      },
      bindings: [
        {
          case_id: CASE_ID,
          proposal_decision_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
          subject_kind: "COUNTER_PROPOSAL",
          subject_id: "cr-counter",
          payload_fingerprint: "fp-counter",
          created_at: "2026-08-22T08:30:00Z",
        },
      ],
      approvals: [],
      carrier_responses: [
        {
          id: "cr-counter",
          request_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
          carrier_id: "SYN-CARRIER-RTA",
          response: "COUNTER",
          counter_eta_pta: "2026-08-22T06:45:00Z",
          message: null,
          received_at: "2026-08-22T08:30:00Z",
        },
      ],
      effective_timings: [],
      decision_links: [],
      decisions: [],
      results: [],
      audit_events: [],
    };
    vi.stubGlobal(
      "fetch",
      createFetchMock({
        carrierCases: [counterCase],
        historyByCase: { [CASE_ID]: counterHistory },
        onPost: (url, body) => posts.push({ url, body }),
      }),
    );

    const user = userEvent.setup();
    render(<OperationsConsole />);

    await user.click(
      screen.getByRole("button", { name: /^start recovery demo$/i }),
    );
    await waitFor(() => expect(screen.getByText("SYN-EVT-ASX17-20260822-001")).toBeInTheDocument());

    await user.click(await screen.findByRole("cell", { name: "SYN-CNT-017" }));

    await waitFor(() => {
      expect(screen.getByText(/carrier counter received — waiting for operator approval/i)).toBeInTheDocument();
      expect(screen.getByText(/06:45Z/)).toBeInTheDocument();
      expect(screen.getAllByRole("button", { name: /approve counter/i }).length).toBeGreaterThan(0);
    });

    await user.click(screen.getAllByRole("button", { name: /approve counter/i })[0]);

    await waitFor(() => {
      const approval = posts.find((post) => post.url.endsWith("/counter-approval"));
      expect(approval).toBeDefined();
      expect(approval?.body).toEqual({
        proposal_decision_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        carrier_response_id: "cr-counter",
        expected_payload_fingerprint: "fp-counter",
        operator_id: "operator-console",
        status: "APPROVED",
      });
    });
    expect(posts.some((post) => post.url.endsWith("/send"))).toBe(false);
    expect(posts.some((post) => post.url.includes("/agent-runs/") && post.url.endsWith("/advance"))).toBe(false);
  });

  it("surfaces persisted SILENT evidence and evaluates timeout only on explicit action", async () => {
    const posts: string[] = [];
    const silentCase = {
      id: CASE_ID,
      incident_id: INCIDENT_ID,
      connection_id: "SYN-CONN-EC3",
      source_evaluation_id: "eval-1",
      affected_container_ids: ["SYN-CNT-021"],
      state: "AWAITING_CARRIER",
      created_at: "2026-08-22T07:00:00Z",
      updated_at: "2026-08-22T08:00:00Z",
    };
    vi.stubGlobal(
      "fetch",
      createFetchMock({
        onPost: (url) => posts.push(url),
        carrierCases: [silentCase],
        historyByCase: {
          [CASE_ID]: {
            case: silentCase,
            request: {
              id: "req-ec3",
              incident_id: INCIDENT_ID,
              connection_id: "SYN-CONN-EC3",
              requested_eta_pta: "2026-08-22T08:00:00Z",
              status: "SENT",
              created_at: "2026-08-22T07:00:00Z",
            },
            request_context: {
              case_id: CASE_ID,
              request_id: "req-ec3",
              payload_fingerprint: "fp",
              prepared_at: "2026-08-22T07:00:00Z",
              response_deadline: "2026-08-22T09:00:00Z",
              sent_at: "2026-08-22T08:00:00Z",
              closed_at: null,
              close_reason: null,
              timeout_observed_at: null,
            },
            bindings: [],
            approvals: [],
            carrier_responses: [],
            effective_timings: [],
            decision_links: [],
            decisions: [],
            results: [],
            audit_events: [],
          },
        },
      }),
    );

    const user = userEvent.setup();
    render(<OperationsConsole />);

    await user.click(
      screen.getByRole("button", { name: /^start recovery demo$/i }),
    );
    await waitFor(() => expect(screen.getByText("SYN-EVT-ASX17-20260822-001")).toBeInTheDocument());

    await user.click(await screen.findByRole("cell", { name: "SYN-CNT-021" }));

    await waitFor(() => {
      expect(screen.getByText(/SILENT outcomes leave no carrier response record/i)).toBeInTheDocument();
    });
    expect(posts.some((post) => post.endsWith("/evaluate-timeout"))).toBe(false);

    await user.click(screen.getByRole("button", { name: /evaluate timeout/i }));

    await waitFor(() => {
      expect(posts.filter((post) => post.endsWith("/evaluate-timeout")).length).toBe(1);
    });
  });
});

describe("OperationsConsole guided Phase 6 entry flow", () => {
  afterEach(() => cleanup());

  it("creates an incident, bootstraps only on explicit click, and never auto-advances", async () => {
    const posts: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input); const method = init?.method ?? "GET";
      if (method === "POST") posts.push(url);
      if (url.endsWith("/synthetic/scenarios/canonical-scarcity")) return jsonResponse({ incident_id: incidentId, evaluation_id: "eval", decision_ids: [], reproducibility_key: "a".repeat(64) }, 201);
      if (url.endsWith("/fixture")) return jsonResponse(fixture);
      if (url.includes("/canonical-replay/stage")) return jsonResponse(defaultStageView());
      if (url.endsWith(`/incidents/${incidentId}/scarcity-evaluation`)) return jsonResponse(report);
      if (url.endsWith(`/incidents/${incidentId}`)) return jsonResponse({ id: incidentId, source_event_id: "SYN-EVENT", state: "RECOVERY_ANALYSIS", created_at: "2026-08-25T01:00:00Z" });
      if (url.includes(`/incidents/${incidentId}/`)) return jsonResponse([]);
      return jsonResponse({ detail: "unexpected" }, 404);
    }));
    const user = userEvent.setup(); render(<OperationsConsole />);
    expect(screen.getByText(/SYNTHETIC DATA/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^start recovery demo$/i }));
    await waitFor(() => expect(screen.getByText("SYN-EVENT")).toBeInTheDocument());
    expect(posts.filter((url) => url.endsWith("/agent-runs") && url.includes("/advance")).length).toBe(0);
    await user.click(screen.getAllByRole("button", { name: /publish yard forecast/i }).at(-1)!);
    await waitFor(() => expect(posts.filter((url) => url.endsWith("/bootstrap")).length).toBe(1));
    expect(posts.some((url) => url.includes("/agent-runs/") && url.endsWith("/advance"))).toBe(false);
    expect(posts.some((url) => url.includes("optimizer") || url.includes("allocation-tradeoff-options/") && !url.endsWith("/bootstrap"))).toBe(false);
  });
});

const R0_IDS = ["SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-005", "SYN-CNT-010", "SYN-CNT-011", "SYN-CNT-012", "SYN-CNT-014", "SYN-CNT-015"];
const R1_IDS = ["SYN-CNT-001", "SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-010", "SYN-CNT-011", "SYN-CNT-012", "SYN-CNT-014", "SYN-CNT-015"];
const RUN_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const COUNTER_ETA = "2026-08-22T06:45:00Z";

function guidedFixture() {
  const connection = {
    id: "SYN-CONN-JV2",
    outbound_vessel_name: "v",
    outbound_voyage: "v1",
    destination_port: "IDJKT",
    cutoff_at: "2026-08-22T05:00:00Z",
    departure_at: "2026-08-22T07:00:00Z",
    minimum_transfer_minutes: 90,
    expedited_transfer_minutes: 60,
  };
  return {
    fixture_id: "SYN-CANONICAL-24-V1",
    event: { id: "evt", vessel_call_id: "vc", vessel_name: "v", terminal_id: "SYN-TUAS-TERMINAL", scheduled_arrival: "2026-08-22T01:00:00Z", estimated_arrival: "2026-08-22T04:15:00Z", delay_minutes: 195, occurred_at: "2026-08-22T04:15:00Z" },
    services: [
      { service_id: "JV2", connection, planned_time_of_arrival: "2026-08-22T05:00:00Z", ready_boundary: "2026-08-22T05:35:00Z" },
    ],
    profiles: [
      {
        container: {
          id: "SYN-CNT-017",
          origin_port: "NLRTM",
          destination_port: "IDJKT",
          cargo: { commodity: "x", gross_weight_kg: 1, dangerous_goods: false, un_number: null },
          inbound_vessel_call_id: "vc",
          onward_connection: connection,
        },
        service_id: "JV2",
        handling_group_id: "HG",
        cargo_kind: "DRY",
        base_ready_at: "2026-08-22T05:10:00Z",
        expedite_minutes_saved: 30,
        reefer_continuity_available: true,
        dg_structurally_cleared: true,
      },
    ],
    capacity: {
      id: "cap",
      terminal_id: "SYN-TUAS-TERMINAL",
      window_start: "2026-08-22T05:00:00Z",
      window_end: "2026-08-22T06:00:00Z",
      overlap_service_ids: ["JV2"],
      total_slots: 8,
      handling_group_limits: [],
      max_reefer_slots: 3,
      max_dg_slots: 1,
    },
  };
}

function guidedReport() {
  return {
    id: "eval-1",
    incident_id: INCIDENT_ID,
    fixture_id: "SYN-CANONICAL-24-V1",
    seed: 20260822,
    scenario_count: 50,
    baseline: {
      allocation: { strategy: "P50_GREEDY", allocated_container_ids: ["SYN-CNT-001", "SYN-CNT-002", "SYN-CNT-003", "SYN-CNT-004", "SYN-CNT-005", "SYN-CNT-006", "SYN-CNT-007", "SYN-CNT-010"] },
      world_count: 50,
      preserved_connection_total: 584,
      expected_preserved_connections: 11.68,
      rollover_total: 616,
      expected_rollovers: 12.32,
      p10_preserved_connections: 5,
      allocation_slot_count: 8,
      capacity_violations: 0,
      unsafe_allocations: 0,
      runtime_ms: 1,
      service_outcomes: [],
    },
    scenario_aware_evaluations: [
      {
        allocation: { strategy: "SCENARIO_AWARE", allocated_container_ids: R0_IDS },
        world_count: 50,
        preserved_connection_total: 601,
        expected_preserved_connections: 12.02,
        rollover_total: 599,
        expected_rollovers: 11.98,
        p10_preserved_connections: 5,
        allocation_slot_count: 8,
        capacity_violations: 0,
        unsafe_allocations: 0,
        runtime_ms: 2,
        service_outcomes: [],
      },
    ],
    pareto_evaluations: [],
    selected_allocation: { strategy: "SCENARIO_AWARE", allocated_container_ids: R0_IDS },
    reproducibility_key: "a".repeat(64),
    created_at: "2026-08-22T08:00:00Z",
  };
}

function createGuidedBackend() {
  const posts: Array<{ url: string; body?: unknown }> = [];
  const at = (hh: number, mm: number) => `2026-08-22T${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}:00Z`;

  const state = {
    incident: { id: INCIDENT_ID, source_event_id: "SYN-EVT-GUIDED", state: "RECOVERY_ANALYSIS", created_at: at(8, 0) },
    snapshots: [] as unknown[],
    revisions: [] as Array<Record<string, unknown>>,
    commitments: [] as Array<{ id: string; container_id: string; status: string; origin_revision_id: string }>,
    assessments: [] as Array<Record<string, unknown>>,
    runs: [] as Array<Record<string, unknown>>,
    steps: [] as Array<Record<string, unknown>>,
    invocations: [] as Array<Record<string, unknown>>,
    caseState: null as string | null,
    history: null as null | Record<string, unknown>,
    safetyReviews: [] as Array<Record<string, unknown>>,
    safetyNotes: {} as Record<string, { text: string; source: string }>,
    safetyAssessments: {} as Record<string, Record<string, unknown> | undefined>,
    decisions: [] as Array<Record<string, unknown>>,
    audit: [] as Array<Record<string, unknown>>,
    stepCount: 0,
  };

  const run = () => state.runs[0];
  const counts = {
    bootstrap: 0, publishActive: 0, advance: 0, start: 0,
    requestApproval: 0, counterApproval: 0, simulate: 0, send: 0, prepare: 0,
    safetyCreate: 0, safetyEvaluate: 0, startDemoRun: 0,
  };

  function audit(actor: string, actorId: string, eventType: string, payload: Record<string, unknown>) {
    state.audit.push({ id: `audit-${state.audit.length + 1}`, actor, actor_id: actorId, incident_id: INCIDENT_ID, event_type: eventType, payload, timestamp: new Date().toISOString() });
  }

  function deriveStage() {
    const activeRun = state.runs.at(-1) as
      | { state?: string; wait_kind?: string | null }
      | undefined;
    const hasAny = state.snapshots.length > 0;
    const requestApproved = (
      (state.history?.approvals as Array<{ status: string }> | undefined) ?? []
    ).some((item) => item.status === "APPROVED");
    const counterApproved = (
      (state.history?.approvals as unknown[] | undefined) ?? []
    ).length >= 2;

    if (!activeRun) {
      if (hasAny) {
        return defaultStageView({
          stage: "READY_TO_START_AGENT",
          ordinal: 3,
          progress_label: "Stage 3 of 16",
          next_allowed_action: "START_DEMO_AGENT_RUN",
        });
      }
      return defaultStageView();
    }

    if (activeRun.state === "ESCALATED") {
      return defaultStageView({
        stage: "SAFETY_BLOCKED",
        ordinal: 16,
        progress_label: "Stage 16 of 16",
        status: "TERMINAL_SUCCESS",
        next_allowed_action: "NONE",
        guided_can_execute: false,
        auto_replay_may_execute: false,
      });
    }

    if (activeRun.state === "WAITING") {
      if (activeRun.wait_kind === "NEW_OPERATIONAL_EVIDENCE") {
        const unhandled = state.assessments.some((item) => item.handled_at === null);
        return unhandled
          ? defaultStageView({
              stage: "WAITING_FOR_ACTIVE_EVIDENCE",
              ordinal: 5,
              status: "PENDING_ACTION",
              next_allowed_action: "ADVANCE_AGENT",
            })
          : defaultStageView({
              stage: "WAITING_FOR_ACTIVE_EVIDENCE",
              ordinal: 5,
              status: "WAITING_EXTERNAL",
              next_allowed_action: "PUBLISH_DISCHARGE_ACTIVE",
            });
      }
      if (activeRun.wait_kind === "REQUEST_APPROVAL") {
        return requestApproved
          ? defaultStageView({
              stage: "REQUEST_APPROVED_READY_TO_SEND",
              ordinal: 9,
              next_allowed_action: "ADVANCE_AGENT",
            })
          : defaultStageView({
              stage: "REQUEST_APPROVAL_REQUIRED",
              ordinal: 8,
              status: "WAITING_HUMAN",
              next_allowed_action: "APPROVE_REQUEST",
              requires_human_authority: true,
            });
      }
      if (activeRun.wait_kind === "CARRIER_RESPONSE_OR_TIMEOUT") {
        if (state.caseState === "AWAITING_COUNTER_APPROVAL") {
          return defaultStageView({
            stage: "CARRIER_COUNTER_RECEIVED",
            ordinal: 11,
            next_allowed_action: "ADVANCE_AGENT",
          });
        }
        return defaultStageView({
          stage: "WAITING_FOR_CARRIER",
          ordinal: 10,
          status: "WAITING_EXTERNAL",
          next_allowed_action: "SIMULATE_CARRIER_RESPONSE",
        });
      }
      if (activeRun.wait_kind === "COUNTER_APPROVAL") {
        if (!counterApproved) {
          return defaultStageView({
            stage: "COUNTER_APPROVAL_REQUIRED",
            ordinal: 12,
            status: "WAITING_HUMAN",
            next_allowed_action: "APPROVE_COUNTER",
            requires_human_authority: true,
          });
        }
        return state.safetyReviews.length > 0
          ? defaultStageView({
              stage: "COUNTER_APPROVED_READY_TO_RESUME",
              ordinal: 13,
              next_allowed_action: "ADVANCE_AGENT",
            })
          : defaultStageView({
              stage: "COUNTER_APPROVED_READY_TO_RESUME",
              ordinal: 13,
              next_allowed_action: "PERSIST_SAFETY_REVIEW",
            });
      }
    }

    if (
      activeRun.state === "RUNNING" &&
      state.caseState === "COMPLETED" &&
      state.safetyReviews.length === 0
    ) {
      return defaultStageView({
        stage: "COUNTER_APPROVED_READY_TO_RESUME",
        ordinal: 13,
        next_allowed_action: "PERSIST_SAFETY_REVIEW",
      });
    }

    if (state.safetyReviews.length > 0 && activeRun.state === "RUNNING") {
      return defaultStageView({
        stage: "READY_FOR_SAFETY_EVIDENCE",
        ordinal: 14,
        next_allowed_action: "ADVANCE_AGENT",
      });
    }

    if (!state.invocations.some((invocation) => invocation.tool_name === "pause_agent_run")) {
      if (!hasAny) {
        return defaultStageView({
          stage: "READY_FOR_PRE_DISCHARGE",
          ordinal: 2,
          next_allowed_action: "BOOTSTRAP_PRE_DISCHARGE",
        });
      }
      return defaultStageView({
        stage: "READY_TO_ADVANCE_TO_EVIDENCE_WAIT",
        ordinal: 4,
        progress_label: "Stage 4 of 16",
        next_allowed_action: "ADVANCE_AGENT",
      });
    }

    return defaultStageView({
      stage: "READY_TO_ADVANCE_TO_EVIDENCE_WAIT",
      ordinal: 4,
      progress_label: "Stage 4 of 16",
      next_allowed_action: "ADVANCE_AGENT",
    });
  }

  function recordStep(runRecord: Record<string, unknown>, tool: string, summary: string) {
    state.stepCount += 1;
    runRecord.step_count = state.stepCount;
    runRecord.updated_at = new Date().toISOString();
    const stepId = `step-${state.stepCount}`;
    state.steps.push({ id: stepId, run_id: RUN_ID, step_number: state.stepCount, kind: "TOOL_CALL", action_summary: summary, model_name: runRecord.model_name, prompt_version: runRecord.prompt_version, latency_ms: null, input_tokens: null, output_tokens: null, created_at: new Date().toISOString() });
    state.invocations.push({ id: `inv-${state.stepCount}`, run_id: RUN_ID, step_id: stepId, tool_name: tool, arguments: {}, status: "SUCCEEDED", result_summary: summary, error_kind: null, started_at: new Date().toISOString(), completed_at: new Date().toISOString() });
  }

  function conflict(detail: string) {
    return jsonResponse({ detail }, 409);
  }

  function applyR1() {
    const assessment = state.assessments.find((item) => item.handled_at === null);
    if (!assessment) return false;
    state.revisions.push({
      id: "rev-r1", incident_id: INCIDENT_ID, source_phase2_evaluation_id: "eval-1",
      source_forecast_snapshot_id: "snap-active", parent_revision_id: "rev-r0",
      allocated_container_ids: R1_IDS, locked_container_ids: ["SYN-CNT-002", "SYN-CNT-004"],
      preserved_connection_total: 602, expected_preserved_connections: 12.04,
      reason: "feasible locked allocation strictly improves preserved connections",
      created_at: new Date().toISOString(),
    });
    for (const commitment of state.commitments) {
      if (commitment.container_id === "SYN-CNT-005" && commitment.status === "PLANNED") {
        commitment.status = "CANCELLED";
      }
    }
    state.commitments.push({ id: "commit-001", container_id: "SYN-CNT-001", status: "PLANNED", origin_revision_id: "rev-r1" });
    assessment.handled_at = new Date().toISOString();
    audit("POLICY", "allocation-dominance-policy", "allocation_revision.applied", { parent_revision_id: "rev-r0", child_revision_id: "rev-r1" });
    return true;
  }

  function prepareCase() {
    state.caseState = "AWAITING_REQUEST_APPROVAL";
    state.decisions.push(
      { id: "dec-roll-1", incident_id: INCIDENT_ID, container_id: "SYN-CNT-017", action: "ROLL", status: "APPROVED", rationale: "fallback roll", supersedes: null, supersession_reason: null, created_at: at(8, 20) },
      { id: "dec-prop-1", incident_id: INCIDENT_ID, container_id: "SYN-CNT-017", action: "REQUEST_RTA", status: "PROPOSED", rationale: "rta proposal", supersedes: "dec-roll-1", supersession_reason: "carrier recovery", created_at: at(8, 21) },
    );
    state.history = {
      case: { id: CASE_ID, incident_id: INCIDENT_ID, connection_id: "SYN-CONN-JV2", source_evaluation_id: "eval-1", affected_container_ids: ["SYN-CNT-017"], state: state.caseState, created_at: at(8, 20), updated_at: at(8, 20) },
      request: { id: "req-1", incident_id: INCIDENT_ID, connection_id: "SYN-CONN-JV2", requested_eta_pta: at(9, 0), status: "PENDING", created_at: at(8, 20) },
      request_context: { case_id: CASE_ID, request_id: "req-1", payload_fingerprint: "fp-request", prepared_at: at(8, 20), response_deadline: at(9, 30), sent_at: null, closed_at: null, close_reason: null, timeout_observed_at: null },
      bindings: [
        { case_id: CASE_ID, proposal_decision_id: "dec-prop-1", subject_kind: "OUTBOUND_REQUEST", subject_id: "req-1", payload_fingerprint: "fp-request", created_at: at(8, 20) },
      ],
      approvals: [],
      carrier_responses: [],
      effective_timings: [],
      decision_links: [{ case_id: CASE_ID, decision_id: "dec-roll-1", role: "FALLBACK_ROLL", created_at: at(8, 20) }],
      decisions: state.decisions,
      results: [],
      audit_events: [],
    };
    state.audit.push(...[
      { id: `audit-${state.audit.length + 1}`, actor: "AGENT", actor_id: "synthetic-agent", incident_id: INCIDENT_ID, event_type: "agent.tool_invoked", payload: { tool_name: "prepare_rta_request" }, timestamp: at(8, 20) },
      { id: `audit-${state.audit.length + 1}`, actor: "SYSTEM", actor_id: "carrier-recovery-workflow", incident_id: INCIDENT_ID, event_type: "carrier_recovery.case_prepared", payload: { recovery_case_id: CASE_ID }, timestamp: at(8, 20) },
    ]);
    const r = run();
    r.state = "WAITING"; r.wait_kind = "REQUEST_APPROVAL"; r.wait_subject_id = CASE_ID;
  }

  function sendRequestServerSide() {
    const context = (state.history!.request_context as Record<string, unknown>);
    context.sent_at = at(8, 40);
    const request = (state.history!.request as Record<string, unknown>);
    request.status = "SENT";
    state.caseState = "AWAITING_CARRIER";
    (state.history!.case as Record<string, unknown>).state = state.caseState;
    const r = run();
    r.state = "WAITING"; r.wait_kind = "CARRIER_RESPONSE_OR_TIMEOUT"; r.wait_subject_id = CASE_ID;
  }

  function evaluateSafetyServerSide(): boolean {
    const review = state.safetyReviews.find((item) => item.container_id === "SYN-CNT-010" && item.state === "PENDING_CHECK");
    if (!review) return false;
    review.state = "COMPLETED";
    state.safetyAssessments[String(review.id)] = {
      assessment: {
        id: "assessment-semantic-1", review_id: review.id, incident_id: INCIDENT_ID, container_id: "SYN-CNT-010",
        cargo_note_id: "note-syn-010", result: "CONTRADICTION_FOUND",
        explanation: "The trusted declaration says general cargo while the operator note identifies corrosive material.",
        evidence_excerpt: "corrosive material", failure_kind: null,
        structured_dangerous_goods: false, structured_un_number: null, structured_commodity: "general",
        checker_kind: "synthetic-checker", model_name: null, prompt_version: "cargo-safety-v1",
        latency_ms: null, input_tokens: null, output_tokens: null, created_at: at(9, 10),
      },
      policy_result: {
        id: "policy-1", review_id: review.id, assessment_id: "assessment-semantic-1", incident_id: INCIDENT_ID,
        container_id: "SYN-CNT-010", disposition: "ESCALATE", automation_blocked: true,
        reason: "deterministic policy requires human review before any automation proceeds",
        replacement_decision_id: null, created_at: at(9, 11),
      },
    };
    audit("AGENT", "synthetic-agent", "cargo_safety.review_evaluated", { container_id: "SYN-CNT-010" });
    return true;
  }

  function advanceRun(): Response {
    counts.advance += 1;
    const r = run();
    if (["COMPLETED", "ESCALATED", "FAILED"].includes(String(r.state))) {
      return jsonResponse(r);
    }
    if (r.state === "WAITING") {
      const unhandled = state.assessments.find((item) => item.handled_at === null);
      if (r.wait_kind === "NEW_OPERATIONAL_EVIDENCE") {
        if (!unhandled) return conflict("agent wait condition remains unresolved");
        r.state = "RUNNING"; r.wait_kind = null; r.wait_subject_id = null;
      } else if (r.wait_kind === "REQUEST_APPROVAL") {
        const approvals = (state.history?.approvals ?? []) as Array<{ status: string }>;
        if (state.caseState !== "AWAITING_REQUEST_APPROVAL" || !approvals.some((item) => item.status === "APPROVED")) {
          return conflict("agent wait condition remains unresolved");
        }
        r.state = "RUNNING"; r.wait_kind = null; r.wait_subject_id = null;
      } else if (r.wait_kind === "CARRIER_RESPONSE_OR_TIMEOUT") {
        if (state.caseState === "AWAITING_COUNTER_APPROVAL") {
          r.wait_kind = "COUNTER_APPROVAL";
          r.updated_at = new Date().toISOString();
          return conflict("agent wait condition remains unresolved");
        }
        if (!["COMPLETED", "ESCALATED", "RECOMPUTING"].includes(state.caseState ?? "")) {
          return conflict("agent wait condition remains unresolved");
        }
        r.state = "RUNNING"; r.wait_kind = null; r.wait_subject_id = null;
      } else if (r.wait_kind === "COUNTER_APPROVAL") {
        if (!["COMPLETED", "ESCALATED", "RECOMPUTING"].includes(state.caseState ?? "")) {
          return conflict("agent wait condition remains unresolved");
        }
        r.state = "RUNNING"; r.wait_kind = null; r.wait_subject_id = null;
      }
    }
    const unhandled = state.assessments.find((item) => item.handled_at === null);
    const hasActiveSnapshot = state.snapshots.some((snapshot) => (snapshot as { stage: string }).stage === "DISCHARGE_ACTIVE");
    if (!state.invocations.some((invocation) => invocation.tool_name === "pause_agent_run")) {
      if (!state.revisions.length || !state.snapshots.some((snapshot) => (snapshot as { stage: string }).stage === "PRE_DISCHARGE") || hasActiveSnapshot) {
        return conflict("pause requires pending dynamic-yard discharge evidence");
      }
      r.state = "WAITING"; r.wait_kind = "NEW_OPERATIONAL_EVIDENCE"; r.wait_subject_id = INCIDENT_ID;
      recordStep(r, "pause_agent_run", "Invoked pause_agent_run.");
      return jsonResponse(r);
    }
    if (unhandled && !state.revisions.some((item) => item.parent_revision_id === "rev-r0")) {
      if (applyR1()) {
        recordStep(r, "request_expedite_feasibility", "Invoked request_expedite_feasibility.");
        return jsonResponse(r);
      }
    }
    if (!state.history) {
      prepareCase();
      recordStep(r, "prepare_rta_request", "Invoked prepare_rta_request.");
      return jsonResponse(r);
    }
    if ((state.history.request_context as Record<string, unknown>).sent_at === null && state.caseState === "AWAITING_REQUEST_APPROVAL") {
      sendRequestServerSide();
      recordStep(r, "send_authorised_rta_request", "Invoked send_authorised_rta_request.");
      return jsonResponse(r);
    }
    if (evaluateSafetyServerSide()) {
      const escalated = run();
      escalated.state = "ESCALATED";
      escalated.escalation_reason = "SAFETY_REVIEW_REQUIRED";
      escalated.completed_at = new Date().toISOString();
      recordStep(escalated, "request_cargo_safety_review", "Invoked request_cargo_safety_review.");
      audit("SYSTEM", "agent-runtime", "agent_run.escalated", { reason: "SAFETY_REVIEW_REQUIRED" });
      return jsonResponse(escalated);
    }
    recordStep(r, "get_carrier_recovery_cases", "Invoked get_carrier_recovery_cases.");
    return jsonResponse(r);
  }

  function fetchMock(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    if (method === "POST") posts.push({ url, body });

    if (url.endsWith("/synthetic/scenarios/canonical-scarcity") && method === "POST") {
      return jsonResponse({ incident_id: INCIDENT_ID, evaluation_id: "eval-1", decision_ids: [], reproducibility_key: "a".repeat(64) }, 201);
    }
    if (url.endsWith("/canonical-scarcity/fixture")) return jsonResponse(guidedFixture());
    if (url.endsWith("/canonical-replay/stage")) {
      return jsonResponse(deriveStage());
    }
    if (url.endsWith("/canonical-replay/agent-runs") && method === "POST") {
      counts.startDemoRun += 1;
      state.runs.push({
        id: RUN_ID, incident_id: INCIDENT_ID, state: "CREATED", model_name: "canonical-replay-agent-v1",
        prompt_version: "incident-agent-v1", step_count: 0, max_steps: 16, wait_kind: null,
        wait_subject_id: null, escalation_reason: null, started_at: at(8, 10), updated_at: at(8, 10), completed_at: null,
      });
      return jsonResponse(state.runs[0], 201);
    }
    if (url.endsWith(`/incidents/${INCIDENT_ID}/scarcity-evaluation`)) return jsonResponse(guidedReport());
    if (url.endsWith(`/incidents/${INCIDENT_ID}`)) return jsonResponse(state.incident);
    if (url.endsWith(`/incidents/${INCIDENT_ID}/decisions`)) return jsonResponse(state.decisions);
    if (url.endsWith(`/incidents/${INCIDENT_ID}/audit-events`)) return jsonResponse(state.audit);

    if (url.endsWith("/dynamic-yard/bootstrap") && method === "POST") {
      counts.bootstrap += 1;
      state.snapshots.push({
        id: "snap-pre", incident_id: INCIDENT_ID, stage: "PRE_DISCHARGE", generated_at: at(7, 30), source: "canonical-harness",
        container_forecasts: R0_IDS.map((containerId) => ({ container_id: containerId, p10_ready_at: at(4, 40), p50_ready_at: at(5, 10), p90_ready_at: at(5, 40) })),
      });
      state.revisions.push({
        id: "rev-r0", incident_id: INCIDENT_ID, source_phase2_evaluation_id: "eval-1",
        source_forecast_snapshot_id: "snap-pre", parent_revision_id: null,
        allocated_container_ids: R0_IDS, locked_container_ids: ["SYN-CNT-002", "SYN-CNT-004"],
        preserved_connection_total: 601, expected_preserved_connections: 12.02,
        reason: "R0 derives from frozen Phase 2 selected allocation", created_at: at(7, 31),
      });
      R0_IDS.forEach((containerId, index) => {
        state.commitments.push({
          id: `commit-${index}`, container_id: containerId,
          status: containerId === "SYN-CNT-002" || containerId === "SYN-CNT-004" ? "COMMITTED" : "PLANNED",
          origin_revision_id: "rev-r0",
        });
      });
      audit("SYSTEM", "dynamic-yard-workflow", "yard_forecast.snapshot_ingested", { snapshot_id: "snap-pre", stage: "PRE_DISCHARGE" });
      return jsonResponse(state.revisions, 201);
    }

    if (url.endsWith("/dynamic-yard/discharge-active") && method === "POST") {
      counts.publishActive += 1;
      if (state.snapshots.some((snapshot) => (snapshot as { stage: string }).stage === "DISCHARGE_ACTIVE")) {
        return jsonResponse({ detail: "contradictory duplicate forecast stage" }, 409);
      }
      state.snapshots.push({
        id: "snap-active", incident_id: INCIDENT_ID, stage: "DISCHARGE_ACTIVE", generated_at: at(8, 5), source: "canonical-harness",
        container_forecasts: R0_IDS.map((containerId) => ({ container_id: containerId, p10_ready_at: at(4, 52), p50_ready_at: at(5, 10), p90_ready_at: at(5, 28) })),
      });
      state.assessments.push({
        id: "assessment-1", incident_id: INCIDENT_ID, source_snapshot_id: "snap-active", prior_allocation_revision_id: "rev-r0",
        locked_container_ids: ["SYN-CNT-002", "SYN-CNT-004"],
        candidate_options: [{ id: "cand-1", allocated_container_ids: R1_IDS, preserved_connection_total: 602, expected_preserved_connections: 12.04 }],
        preserved_connection_total_before: 601, preserved_connection_total_after: 602,
        expected_preserved_connections_before: 12.02, expected_preserved_connections_after: 12.04,
        disposition: "AUTO_SUPERSEDE", reason: "feasible locked allocation strictly improves preserved connections",
        handled_at: null, created_at: at(8, 6),
      });
      audit("SYSTEM", "dynamic-yard-workflow", "yard_forecast.snapshot_ingested", { snapshot_id: "snap-active", stage: "DISCHARGE_ACTIVE" });
      audit("POLICY", "allocation-dominance-policy", "expedite_reconsideration.assessed", { assessment_id: "assessment-1", disposition: "AUTO_SUPERSEDE" });
      return jsonResponse(state.assessments[0], 201);
    }

    if (url.endsWith(`/incidents/${INCIDENT_ID}/yard-forecast-snapshots`)) return jsonResponse(state.snapshots);
    if (url.endsWith(`/incidents/${INCIDENT_ID}/allocation-revisions`)) return jsonResponse(state.revisions);
    if (url.endsWith(`/incidents/${INCIDENT_ID}/expedite-commitments`)) return jsonResponse(state.commitments);
    if (url.endsWith(`/incidents/${INCIDENT_ID}/expedite-reconsiderations`)) return jsonResponse(state.assessments);
    if (url.endsWith(`/incidents/${INCIDENT_ID}/allocation-tradeoff-reviews`)) return jsonResponse([]);
    if (url.endsWith(`/incidents/${INCIDENT_ID}/allocation-tradeoff-options`)) return jsonResponse([]);

    if (url.endsWith(`/incidents/${INCIDENT_ID}/agent-runs`) && method === "POST") {
      counts.start += 1;
      state.runs.push({
        id: RUN_ID, incident_id: INCIDENT_ID, state: "CREATED", model_name: "synthetic-agent",
        prompt_version: "incident-agent-v1", step_count: 0, max_steps: 16, wait_kind: null,
        wait_subject_id: null, escalation_reason: null, started_at: at(8, 0), updated_at: at(8, 0), completed_at: null,
      });
      return jsonResponse(state.runs[0], 201);
    }
    if (url.endsWith(`/incidents/${INCIDENT_ID}/agent-runs`)) return jsonResponse(state.runs);
    if (url.endsWith(`/agent-runs/${RUN_ID}/advance`) && method === "POST") return advanceRun();
    if (url.endsWith(`/agent-runs/${RUN_ID}/history`)) {
      return jsonResponse({ run: run(), steps: state.steps, tool_invocations: state.invocations });
    }

    if (url.endsWith(`/incidents/${INCIDENT_ID}/cargo-safety-reviews`) && method === "POST") {
      counts.safetyCreate += 1;
      const note = (body as { note: { text: string; source: string } }).note;
      const review = { id: "review-syn-010", incident_id: INCIDENT_ID, container_id: "SYN-CNT-010", cargo_note_id: "note-syn-010", state: "PENDING_CHECK", created_at: at(9, 0), updated_at: at(9, 0) };
      state.safetyReviews.push(review);
      state.safetyNotes["review-syn-010"] = note;
      audit("OPERATOR", "operator-console", "cargo_safety.review_created", { container_id: "SYN-CNT-010" });
      return jsonResponse(review, 201);
    }
    if (url.endsWith("/cargo-safety-reviews/review-syn-010/history")) {
      const review = state.safetyReviews[0];
      const derived = state.safetyAssessments["review-syn-010"];
      return jsonResponse({
        review,
        note: { id: "note-syn-010", incident_id: INCIDENT_ID, container_id: "SYN-CNT-010", text: state.safetyNotes["review-syn-010"].text, source: state.safetyNotes["review-syn-010"].source, created_at: at(9, 0) },
        assessment: derived?.assessment ?? null,
        policy_result: derived?.policy_result ?? null,
        audit_events: [],
      });
    }
    if (url.endsWith("/cargo-safety-reviews/review-syn-010/evaluate") && method === "POST") {
      counts.safetyEvaluate += 1;
      return jsonResponse({ detail: "browser cannot evaluate safety reviews directly" }, 403);
    }
    if (url.endsWith(`/incidents/${INCIDENT_ID}/cargo-safety-reviews`)) return jsonResponse(state.safetyReviews);

    if (url.endsWith(`/carrier-recovery-cases/${CASE_ID}/history`)) return jsonResponse(state.history);
    if (url.endsWith("/request-approval") && method === "POST") {
      counts.requestApproval += 1;
      const approvalBody = body as { proposal_decision_id: string; request_id: string; expected_payload_fingerprint: string; operator_id: string; status: string };
      if (approvalBody.expected_payload_fingerprint !== "fp-request") return jsonResponse({ detail: "stale fingerprint" }, 409);
      (state.history!.approvals as unknown[]).push({ id: "ap-req-1", decision_id: approvalBody.proposal_decision_id, operator_id: approvalBody.operator_id, status: approvalBody.status, reason: null, created_at: at(8, 30) });
      audit("OPERATOR", approvalBody.operator_id, "carrier_recovery.request_approval_recorded", { status: approvalBody.status });
      return jsonResponse({ id: "ap-req-1", decision_id: approvalBody.proposal_decision_id, operator_id: approvalBody.operator_id, status: approvalBody.status, reason: null, created_at: at(8, 30) }, 201);
    }
    if (url.endsWith("/send") && method === "POST") {
      counts.send += 1;
      return jsonResponse({ detail: "browser cannot dispatch authorised RTA requests" }, 403);
    }
    if (url.endsWith("/simulate-carrier-response") && method === "POST") {
      counts.simulate += 1;
      state.caseState = "AWAITING_COUNTER_APPROVAL";
      (state.history!.case as Record<string, unknown>).state = state.caseState;
      (state.history!.request as Record<string, unknown>).status = "SENT";
      (state.history!.request_context as Record<string, unknown>).closed_at = at(8, 45);
      (state.history!.carrier_responses as unknown[]).push({ id: "cr-1", request_id: "req-1", carrier_id: "SYN-CARRIER-RTA", response: "COUNTER", counter_eta_pta: COUNTER_ETA, message: null, received_at: at(8, 45) });
      (state.history!.bindings as unknown[]).push({ case_id: CASE_ID, proposal_decision_id: "dec-prop-2", subject_kind: "COUNTER_PROPOSAL", subject_id: "cr-1", payload_fingerprint: "fp-counter", created_at: at(8, 45) });
      state.decisions.push({ id: "dec-prop-2", incident_id: INCIDENT_ID, container_id: "SYN-CNT-017", action: "REQUEST_RTA", status: "PROPOSED", rationale: "counter proposal", supersedes: "dec-prop-1", supersession_reason: "counter", created_at: at(8, 45) });
      audit("CARRIER", "SYN-CARRIER-RTA", "carrier.response_received", { response: "COUNTER" });
      return jsonResponse({ case_id: CASE_ID, carrier_response_id: "cr-1", no_response_emitted: false }, 201);
    }
    if (url.endsWith("/counter-approval") && method === "POST") {
      counts.counterApproval += 1;
      const approvalBody = body as { proposal_decision_id: string; carrier_response_id: string; expected_payload_fingerprint: string; operator_id: string; status: string };
      if (approvalBody.expected_payload_fingerprint !== "fp-counter") return jsonResponse({ detail: "stale fingerprint" }, 409);
      (state.history!.approvals as unknown[]).push({ id: "ap-counter-1", decision_id: approvalBody.proposal_decision_id, operator_id: approvalBody.operator_id, status: approvalBody.status, reason: null, created_at: at(8, 50) });
      (state.history!.effective_timings as unknown[]).push({ id: "timing-1", case_id: CASE_ID, request_id: "req-1", carrier_response_id: "cr-1", source_kind: "APPROVED_COUNTER", effective_eta_pta: COUNTER_ETA, created_at: at(8, 50) });
      state.decisions.push({ id: "dec-rta-2", incident_id: INCIDENT_ID, container_id: "SYN-CNT-017", action: "PRESERVE_VIA_RTA", status: "APPROVED", rationale: "frozen-evidence recomputation", supersedes: "dec-roll-1", supersession_reason: "approved counter", created_at: at(8, 51) });
      (state.history!.results as unknown[]).push({ id: "result-1", case_id: CASE_ID, container_id: "SYN-CNT-017", disposition: "PRESERVED_VIA_RTA", prior_decision_id: "dec-roll-1", replacement_decision_id: "dec-rta-2", preserved_world_count: 47, world_count: 50, hard_constraints_satisfied: true, reconsideration_evidence_kind: "EFFECTIVE_CONNECTION_TIMING", effective_connection_timing_id: "timing-1", rejected_approval_id: null, timeout_request_context_id: null, created_at: at(8, 51) });
      (state.history!.decision_links as unknown[]).push({ case_id: CASE_ID, decision_id: "dec-prop-2", role: "COUNTER_RTA_PROPOSAL", created_at: at(8, 50) });
      state.caseState = "COMPLETED";
      (state.history!.case as Record<string, unknown>).state = "COMPLETED";
      audit("OPERATOR", approvalBody.operator_id, "carrier_recovery.counter_approval_recorded", { status: approvalBody.status });
      return jsonResponse({ id: "ap-counter-1", decision_id: approvalBody.proposal_decision_id, operator_id: approvalBody.operator_id, status: approvalBody.status, reason: null, created_at: at(8, 50) }, 201);
    }
    if (url.endsWith("/evaluate-timeout") && method === "POST") return jsonResponse({ detail: "not exercised" }, 403);
    if (url.endsWith(`/incidents/${INCIDENT_ID}/carrier-recovery-cases`)) {
      return jsonResponse(state.history ? [state.history.case] : []);
    }
    return jsonResponse({ detail: `Unexpected ${method} ${url}` }, 500);
  }

  return { fetchMock: vi.fn(fetchMock), posts, counts };
}

describe("OperationsConsole full guided Phase 6 journey", () => {
  afterEach(() => cleanup());

  function advanceButton() {
    return screen.getByRole("button", { name: /advance agent once/i });
  }

  async function expectAdvanceDisabled() {
    await waitFor(() => expect(advanceButton()).toBeDisabled());
  }

  it("drives create, bootstrap, agent waits, evidence, approvals, counter, and safety escalation without authority bypass", async () => {
    const backend = createGuidedBackend();
    vi.stubGlobal("fetch", backend.fetchMock);
    const user = userEvent.setup();
    render(<OperationsConsole />);

    expect(screen.getByText(/SYNTHETIC DATA/)).toBeInTheDocument();
    expect(screen.getByText(/Recovery command center/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^start recovery demo$/i }));
    await waitFor(() => expect(screen.getByText("SYN-EVT-GUIDED")).toBeInTheDocument());
    expect(backend.counts.advance).toBe(0);

    await user.click(await screen.findByRole("cell", { name: "SYN-CNT-017" }));

    await user.click(screen.getAllByRole("button", { name: /publish yard forecast/i }).at(-1)!);
    await waitFor(() => {
      expect(screen.getByText(/wide uncertainty/)).toBeInTheDocument();
      expect(screen.getAllByText(/PRE_DISCHARGE/).length).toBeGreaterThan(0);
    });
    expect(backend.counts.bootstrap).toBe(1);

    await user.click(screen.getByRole("button", { name: /start recovery agent/i }));
    await waitFor(() => expect(screen.getByText("CREATED")).toBeInTheDocument());
    expect(backend.counts.startDemoRun).toBe(1);
    expect(backend.counts.start).toBe(0);
    expect(backend.counts.advance).toBe(0);

    await user.click(advanceButton());
    const waitBanner = await screen.findByText("NEW_OPERATIONAL_EVIDENCE");
    await waitFor(() => {
      expect(waitBanner).toBeInTheDocument();
      expect(screen.getByText(/waiting for updated yard forecast/i)).toBeInTheDocument();
    });
    expect(backend.counts.advance).toBe(1);
    await expectAdvanceDisabled();

    await user.click(screen.getAllByRole("button", { name: /publish discharge evidence/i })[0]);
    await waitFor(() => {
      expect(screen.getByText(/tighter forecast band/)).toBeInTheDocument();
      expect(screen.getAllByText(/DISCHARGE_ACTIVE/).length).toBeGreaterThan(0);
    });
    expect(backend.counts.publishActive).toBe(1);
    expect(backend.counts.advance).toBe(1);

    await user.click(advanceButton());
    await waitFor(() => {
      expect(screen.getAllByText(/R0 → R1/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/601 → 602/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/synthetic scenario-world total across 50 worlds/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/12\.02 → 12\.04/).length).toBeGreaterThan(0);
      expect(screen.getByText(/SYN-CNT-005 OUT CANCELLED/)).toBeInTheDocument();
      expect(screen.getByText(/SYN-CNT-001 IN PLANNED/)).toBeInTheDocument();
      expect(screen.getByText(/SYN-CNT-002 IN COMMITTED/)).toBeInTheDocument();
      expect(screen.getByText(/SYN-CNT-004 IN COMMITTED/)).toBeInTheDocument();
    });
    expect(backend.counts.advance).toBe(2);

    await user.click(advanceButton());
    await waitFor(() => {
      expect(screen.getByText("REQUEST_APPROVAL")).toBeInTheDocument();
      expect(screen.getByText(/RTA proposal awaiting operator approval/i)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /prepare carrier recovery/i })).not.toBeInTheDocument();
    });
    expect(backend.counts.advance).toBe(3);
    expect(backend.counts.prepare).toBe(0);

    await user.click(screen.getAllByRole("button", { name: /approve request/i })[0]);
    await waitFor(() => {
      const approval = backend.posts.find((post) => post.url.endsWith("/request-approval"));
      expect(approval?.body).toEqual({
        proposal_decision_id: "dec-prop-1",
        request_id: "req-1",
        expected_payload_fingerprint: "fp-request",
        operator_id: "operator-console",
        status: "APPROVED",
      });
      expect(screen.getByText(/approval persisted\. advance the agent explicitly to send the authorised request\./i)).toBeInTheDocument();
    });
    expect(backend.counts.advance).toBe(3);
    expect(backend.counts.send).toBe(0);

    await user.click(advanceButton());
    await waitFor(() => {
      expect(screen.getByText("CARRIER_RESPONSE_OR_TIMEOUT")).toBeInTheDocument();
      expect(screen.getAllByText(/waiting for carrier response/i).length).toBeGreaterThan(0);
    });
    expect(backend.counts.advance).toBe(4);
    expect(backend.counts.send).toBe(0);
    await expectAdvanceDisabled();

    await user.click(screen.getAllByRole("button", { name: /simulate carrier response/i })[0]);
    await waitFor(() => {
      expect(screen.getByText(/carrier counter received — waiting for operator approval/i)).toBeInTheDocument();
      expect(screen.getByText(/06:45Z/)).toBeInTheDocument();
    });
    expect(backend.counts.simulate).toBe(1);
    expect(backend.counts.advance).toBe(4);

    await user.click(advanceButton());
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("409");
      expect(screen.getByText("COUNTER_APPROVAL")).toBeInTheDocument();
      expect(screen.getByText(/operator approval required for carrier counter/i)).toBeInTheDocument();
    });
    expect(backend.counts.advance).toBe(5);
    await expectAdvanceDisabled();

    await user.click(screen.getAllByRole("button", { name: /approve counter/i })[0]);
    await waitFor(() => {
      const approval = backend.posts.find((post) => post.url.endsWith("/counter-approval"));
      expect(approval?.body).toEqual({
        proposal_decision_id: "dec-prop-2",
        carrier_response_id: "cr-1",
        expected_payload_fingerprint: "fp-counter",
        operator_id: "operator-console",
        status: "APPROVED",
      });
    });
    expect(backend.counts.counterApproval).toBe(1);
    expect(backend.counts.advance).toBe(5);

    await user.click(advanceButton());
    await waitFor(() => {
      expect(screen.getByText("RUNNING")).toBeInTheDocument();
      expect(screen.getByText(/preserved via rta/i)).toBeInTheDocument();
    });
    expect(backend.counts.advance).toBe(6);

    await user.click(screen.getByRole("button", { name: /record syn-cnt-010 safety evidence/i }));
    await waitFor(() => {
      const created = backend.posts.find((post) => post.url.endsWith("/cargo-safety-reviews") && post.url.includes(INCIDENT_ID));
      expect(created?.body).toEqual({
        container_id: "SYN-CNT-010",
        note: {
          text: "Manifest declares general cargo; free-text handling note identifies corrosive material and requires safety review.",
          source: "synthetic-canonical-cargo-note",
        },
      });
      expect(screen.getByText(/Review: PENDING_CHECK/)).toBeInTheDocument();
      expect(screen.getByText(/corrosive material and requires safety review/i)).toBeInTheDocument();
      expect(screen.getByText(/semantic result: pending/i)).toBeInTheDocument();
      expect(screen.getByText(/deterministic policy: pending/i)).toBeInTheDocument();
    });
    expect(backend.counts.safetyCreate).toBe(1);
    expect(backend.counts.safetyEvaluate).toBe(0);
    expect(backend.counts.advance).toBe(6);

    await user.click(advanceButton());
    await waitFor(() => {
      expect(screen.getByText("ESCALATED")).toBeInTheDocument();
      expect(screen.getByText(/escalated: SAFETY_REVIEW_REQUIRED/i)).toBeInTheDocument();
      expect(screen.getByText(/CONTRADICTION_FOUND/)).toBeInTheDocument();
      expect(screen.getByText(/automation blocked true/i)).toBeInTheDocument();
      expect(screen.getByText(/DG false · UN —/)).toBeInTheDocument();
    });
    expect(backend.counts.advance).toBe(7);
    expect(backend.counts.safetyEvaluate).toBe(0);
    expect(backend.counts.send).toBe(0);
    expect(backend.counts.prepare).toBe(0);

    await user.click(screen.getByRole("button", { name: /^explore$/i }));
    expect(screen.getByText("Audit / decision history")).toBeInTheDocument();
    expect(screen.getAllByText(/decision.created|agent_run.escalated|carrier.response_received/i).length).toBeGreaterThan(0);

    expect(screen.queryByText(/reasoning stream/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/arguments:/i)).not.toBeInTheDocument();

    for (const post of backend.posts) {
      expect(post.url).not.toMatch(/optimizer|allocation-candidate|schedule-change/);
      expect(post.url.endsWith("/send")).toBe(false);
      expect(post.url.endsWith("/evaluate")).toBe(false);
    }
    expect(backend.posts.filter((post) => post.url.endsWith("/request-approval"))).toHaveLength(1);
    expect(backend.posts.filter((post) => post.url.endsWith("/counter-approval"))).toHaveLength(1);

    const fetchCallsAfterSettle = backend.fetchMock.mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 150));
    expect(backend.fetchMock.mock.calls.length).toBe(fetchCallsAfterSettle);
  });
});

describe("OperationsConsole synthetic auto replay journey", () => {
  afterEach(() => cleanup());

  function createAutoBackend() {
    const counts = { bootstrap: 0, publishActive: 0, advance: 0, startDemoRun: 0, requestApproval: 0, counterApproval: 0, simulate: 0, safetyCreate: 0 };
    const posts: Array<{ url: string; body?: unknown }> = [];
    const st = {
      snapshots: [] as Array<{ stage: string }>,
      assessments: [] as Array<{ handled_at: string | null }>,
      runs: [] as Array<Record<string, unknown>>,
      caseState: null as string | null,
      requestApproved: false,
      counterApproved: false,
      waitKind: null as string | null,
      safetyReview: null as null | { state: string },
      safetyBlocked: false,
    };
    const runShape = () => ({
      id: RUN_ID, incident_id: INCIDENT_ID, state: "CREATED", model_name: "canonical-replay-agent-v1",
      prompt_version: "incident-agent-v1", step_count: 0, max_steps: 16, wait_kind: null,
      wait_subject_id: null, escalation_reason: null, started_at: "2026-08-22T08:00:00Z",
      updated_at: "2026-08-22T08:00:00Z", completed_at: null,
    });

    function deriveStage() {
      const run = st.runs.at(-1) as { state?: string } | undefined;
      if (!run) {
        if (st.snapshots.length > 0) return defaultStageView({ stage: "READY_TO_START_AGENT", ordinal: 3, progress_label: "Stage 3 of 16", next_allowed_action: "START_DEMO_AGENT_RUN" });
        return defaultStageView();
      }
      if (run.state === "ESCALATED") {
        return defaultStageView({ stage: "SAFETY_BLOCKED", ordinal: 16, progress_label: "Stage 16 of 16", status: "TERMINAL_SUCCESS", next_allowed_action: "NONE", guided_can_execute: false, auto_replay_may_execute: false });
      }
      if (run.state === "WAITING") {
        if (st.waitKind === "NEW_OPERATIONAL_EVIDENCE") {
          const unhandled = st.assessments.some((a) => a.handled_at === null);
          return unhandled
            ? defaultStageView({ stage: "WAITING_FOR_ACTIVE_EVIDENCE", ordinal: 5, status: "PENDING_ACTION", next_allowed_action: "ADVANCE_AGENT" })
            : defaultStageView({ stage: "WAITING_FOR_ACTIVE_EVIDENCE", ordinal: 5, status: "WAITING_EXTERNAL", next_allowed_action: "PUBLISH_DISCHARGE_ACTIVE" });
        }
        if (st.waitKind === "REQUEST_APPROVAL") {
          return st.requestApproved
            ? defaultStageView({ stage: "REQUEST_APPROVED_READY_TO_SEND", ordinal: 9, next_allowed_action: "ADVANCE_AGENT" })
            : defaultStageView({ stage: "REQUEST_APPROVAL_REQUIRED", ordinal: 8, status: "WAITING_HUMAN", next_allowed_action: "APPROVE_REQUEST", requires_human_authority: true });
        }
        if (st.waitKind === "CARRIER_RESPONSE_OR_TIMEOUT") {
          if (st.caseState === "AWAITING_COUNTER_APPROVAL") {
            return defaultStageView({ stage: "CARRIER_COUNTER_RECEIVED", ordinal: 11, next_allowed_action: "ADVANCE_AGENT" });
          }
          return defaultStageView({ stage: "WAITING_FOR_CARRIER", ordinal: 10, status: "WAITING_EXTERNAL", next_allowed_action: "SIMULATE_CARRIER_RESPONSE" });
        }
        if (st.waitKind === "COUNTER_APPROVAL") {
          if (!st.counterApproved) {
            return defaultStageView({ stage: "COUNTER_APPROVAL_REQUIRED", ordinal: 12, status: "WAITING_HUMAN", next_allowed_action: "APPROVE_COUNTER", requires_human_authority: true });
          }
          return st.safetyReview
            ? defaultStageView({ stage: "COUNTER_APPROVED_READY_TO_RESUME", ordinal: 13, next_allowed_action: "ADVANCE_AGENT" })
            : defaultStageView({ stage: "COUNTER_APPROVED_READY_TO_RESUME", ordinal: 13, next_allowed_action: "PERSIST_SAFETY_REVIEW" });
        }
      }
      return defaultStageView({ stage: "READY_TO_ADVANCE_TO_EVIDENCE_WAIT", ordinal: 4, progress_label: "Stage 4 of 16", next_allowed_action: "ADVANCE_AGENT" });
    }

    async function route(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;

      if (method === "POST") posts.push({ url, body });
      if (url.endsWith("/synthetic/scenarios/canonical-scarcity") && method === "POST") return jsonResponse({ incident_id: INCIDENT_ID, evaluation_id: "eval-1", decision_ids: [], reproducibility_key: "a".repeat(64) }, 201);
      if (url.endsWith("/canonical-scarcity/fixture")) return jsonResponse(minimalFixture());
      if (url.includes("/canonical-replay/stage")) return jsonResponse(deriveStage());
      if (url.endsWith("/canonical-replay/agent-runs") && method === "POST") {
        counts.startDemoRun += 1;
        const created = runShape();
        st.runs.push(created);
        return jsonResponse(created, 201);
      }
      if (url.endsWith(`/synthetic/scenarios/${INCIDENT_ID}/dynamic-yard/bootstrap`) && method === "POST") {
        counts.bootstrap += 1;
        st.snapshots.push({ stage: "PRE_DISCHARGE" });

        return jsonResponse([], 201);
      }
      if (url.endsWith(`/synthetic/scenarios/${INCIDENT_ID}/dynamic-yard/discharge-active`) && method === "POST") {
        counts.publishActive += 1;
        st.snapshots.push({ stage: "DISCHARGE_ACTIVE" });
        st.assessments.push({ handled_at: null });
        return jsonResponse({}, 201);
      }
      if (url.endsWith(`/agent-runs/${RUN_ID}/advance`) && method === "POST") {
        counts.advance += 1;
        const run = st.runs.at(-1) as Record<string, unknown>;
        const step = Number(run.step_count ?? 0);

        const bump = (patch: Record<string, unknown>) => {
          st.runs.pop();
          st.runs.push({ ...run, ...patch });
        };
        if (st.waitKind === "NEW_OPERATIONAL_EVIDENCE") {
          st.assessments.forEach((a) => { a.handled_at = "2026-08-22T09:00:00Z"; });
          st.waitKind = null;
          bump({ state: "RUNNING", step_count: step + 1, wait_kind: null, wait_subject_id: null });
        } else if (step === 0) {
          st.waitKind = "NEW_OPERATIONAL_EVIDENCE";
          bump({ state: "WAITING", step_count: step + 1, wait_kind: "NEW_OPERATIONAL_EVIDENCE", updated_at: "" });
        } else if (!st.caseState) {
          st.caseState = "AWAITING_REQUEST_APPROVAL";
          st.waitKind = "REQUEST_APPROVAL";
          bump({ state: "WAITING", step_count: step + 1, wait_kind: "REQUEST_APPROVAL" });
        } else if (st.waitKind === "REQUEST_APPROVAL" && st.requestApproved) {
          st.caseState = "AWAITING_CARRIER";
          st.waitKind = "CARRIER_RESPONSE_OR_TIMEOUT";
          bump({ state: "WAITING", step_count: step + 1, wait_kind: "CARRIER_RESPONSE_OR_TIMEOUT" });
        } else if (st.waitKind === "CARRIER_RESPONSE_OR_TIMEOUT" && st.caseState === "AWAITING_COUNTER_APPROVAL") {
          st.waitKind = "COUNTER_APPROVAL";
          bump({ state: "WAITING", wait_kind: "COUNTER_APPROVAL" });
          return jsonResponse({ detail: "carrier counter approval is required before resuming" }, 409);
        } else if (st.waitKind === "COUNTER_APPROVAL" && st.counterApproved) {
          if (!st.safetyReview) st.safetyReview = { state: "PENDING_CHECK" };
          st.safetyBlocked = true;
          st.waitKind = null;
          bump({ state: "ESCALATED", step_count: step + 1, wait_kind: null, escalation_reason: "SAFETY_REVIEW_REQUIRED", completed_at: "2026-08-22T10:00:00Z" });
        } else {
          return jsonResponse({ detail: "agent wait condition remains unresolved" }, 409);
        }
        return jsonResponse(st.runs.at(-1));
      }
      if (url.endsWith(`/incidents/${INCIDENT_ID}/agent-runs`) && method === "POST") throw new Error("production start must not be used by auto replay");
      if (url.includes("/agent-runs/") && url.endsWith("/history")) return jsonResponse({ run: st.runs.at(-1) ?? {}, steps: [], tool_invocations: [] });
      if (url.includes("/agent-runs/")) return jsonResponse(st.runs.at(-1) ?? {});
      if (url.includes("/agent-runs")) return jsonResponse(st.runs);
      if (url.includes("/carrier-recovery-cases/") && url.endsWith("/history")) {
        const bindings: Array<Record<string, unknown>> = [];
        if (st.caseState) bindings.push({ case_id: CASE_ID, proposal_decision_id: "dec-prop-1", subject_kind: "OUTBOUND_REQUEST", subject_id: "req-1", payload_fingerprint: "fp-request", created_at: "" });
        if (st.caseState === "AWAITING_COUNTER_APPROVAL" || st.counterApproved || st.caseState === "COMPLETED") bindings.push({ case_id: CASE_ID, proposal_decision_id: "dec-prop-2", subject_kind: "COUNTER_PROPOSAL", subject_id: "cr-1", payload_fingerprint: "fp-counter", created_at: "" });
        return jsonResponse({
          case: { id: CASE_ID, incident_id: INCIDENT_ID, connection_id: "SYN-CONN-JV2", source_evaluation_id: "eval-1", affected_container_ids: ["SYN-CNT-017"], state: st.caseState ?? "PREPARED", created_at: "", updated_at: "" },
          request: { id: "req-1", incident_id: INCIDENT_ID, connection_id: "SYN-CONN-JV2", requested_eta_pta: "", status: st.requestApproved ? "SENT" : "PENDING", created_at: "" },
          request_context: null,
          bindings,
          approvals: [],
          carrier_responses: [],
          effective_timings: [],
          decision_links: [],
          decisions: [],
          results: [],
          audit_events: [],
        });
      }
      if (url.includes("/request-approval") && method === "POST") {
        counts.requestApproval += 1;
        st.requestApproved = true;
        return jsonResponse({}, 201);
      }
      if (url.includes("/simulate-carrier-response") && method === "POST") {
        counts.simulate += 1;
        st.caseState = "AWAITING_COUNTER_APPROVAL";
        return jsonResponse({ case_id: CASE_ID, carrier_response_id: "cr-1", no_response_emitted: false }, 201);
      }
      if (url.includes("/counter-approval") && method === "POST") {
        counts.counterApproval += 1;
        st.counterApproved = true;
        st.caseState = "COMPLETED";
        return jsonResponse({}, 201);
      }
      if (url.includes("/cargo-safety-reviews") && method === "POST") {
        counts.safetyCreate += 1;
        st.safetyReview = { state: "PENDING_CHECK" };
        return jsonResponse({ id: "review-syn-010", incident_id: INCIDENT_ID, container_id: "SYN-CNT-010", cargo_note_id: "note-1", state: "PENDING_CHECK", created_at: "", updated_at: "" }, 201);
      }
      if (url.includes("/cargo-safety-reviews/") && url.endsWith("/history")) return jsonResponse({ review: { id: "review-syn-010", incident_id: INCIDENT_ID, container_id: "SYN-CNT-010", cargo_note_id: "note-1", state: st.safetyBlocked ? "COMPLETED" : "PENDING_CHECK", created_at: "", updated_at: "" }, note: { id: "note-1", incident_id: INCIDENT_ID, container_id: "SYN-CNT-010", text: "corrosive material note", source: "synthetic-canonical-cargo-note", created_at: "" }, assessment: st.safetyBlocked ? { result: "CONTRADICTION_FOUND", structured_dangerous_goods: false, structured_un_number: null, structured_commodity: "x", evidence_excerpt: "corrosive", explanation: "contradiction" } : null, policy_result: st.safetyBlocked ? { disposition: "ESCALATE", automation_blocked: true, reason: "blocked" } : null, audit_events: [] });
      if (url.includes("/cargo-safety-reviews")) return jsonResponse([]);
      if (url.includes("/carrier-recovery-cases")) {
        if (!st.caseState) return jsonResponse([]);
        return jsonResponse([{ id: CASE_ID, incident_id: INCIDENT_ID, connection_id: "SYN-CONN-JV2", source_evaluation_id: "eval-1", affected_container_ids: ["SYN-CNT-017"], state: st.caseState, created_at: "", updated_at: "" }]);
      }
      if (url.includes("/scarcity-evaluation")) return jsonResponse(report);
      if (url.endsWith(`/incidents/${INCIDENT_ID}`)) return jsonResponse({ id: INCIDENT_ID, source_event_id: "SYN-EVT-AUTO", state: "RECOVERY_ANALYSIS", created_at: "2026-08-22T08:00:00Z" });
      if (url.startsWith("/synthetic/scenarios/canonical-scarcity")) return jsonResponse({});

      return jsonResponse([]);
    }

    return { fetchMock: vi.fn(route), posts, counts };
  }

  it("auto replay drives the canonical hero and records synthetic-operator approvals only", async () => {
    const backend = createAutoBackend();
    vi.stubGlobal("fetch", backend.fetchMock);
    const user = userEvent.setup();
    render(<OperationsConsole />);

    await user.click(screen.getByRole("button", { name: /^start recovery demo$/i }));
    await waitFor(() => expect(screen.getByText("SYN-EVT-AUTO")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /^auto replay$/i }));
    await user.click(screen.getByRole("button", { name: /auto start/i }));

    await waitFor(() => expect(screen.getByText(/halt: terminal-success/i)).toBeInTheDocument(), { timeout: 3000 });
    expect(screen.getByText("ESCALATED / SAFETY_REVIEW_REQUIRED")).toBeInTheDocument();

    const requestApproval = backend.posts.find((post) => post.url.includes("/request-approval"));
    const counterApproval = backend.posts.find((post) => post.url.includes("/counter-approval"));
    expect((requestApproval?.body as Record<string, unknown>).operator_id).toBe("synthetic-demo-operator");
    expect((counterApproval?.body as Record<string, unknown>).operator_id).toBe("synthetic-demo-operator");
    expect(backend.counts.advance).toBeGreaterThanOrEqual(5);
    expect(backend.counts.startDemoRun).toBe(1);
    expect(backend.counts.bootstrap).toBe(1);
    expect(backend.counts.publishActive).toBe(1);
    expect(backend.counts.simulate).toBe(1);
    expect(backend.counts.safetyCreate).toBe(1);
    const productionStart = backend.posts.filter((post) => post.url.endsWith(`/incidents/${INCIDENT_ID}/agent-runs`));
    expect(productionStart).toHaveLength(0);
  }, 15000);

  it("auto start is enabled from the clean READY_TO_CREATE state and its first action creates the canonical incident", async () => {
    const backend = createAutoBackend();
    vi.stubGlobal("fetch", backend.fetchMock);
    const user = userEvent.setup();
    render(<OperationsConsole />);

    await user.click(screen.getByRole("button", { name: /^auto replay$/i }));
    const autoStart = screen.getByRole("button", { name: /auto start/i });
    expect(autoStart).toBeEnabled();
    await user.click(autoStart);

    await waitFor(() => expect(screen.getByText(/halt: terminal-success/i)).toBeInTheDocument(), { timeout: 3000 });
    expect(screen.getByText("READY_TO_CREATE")).toBeInTheDocument();
    const scarcityPosts = backend.posts.filter((post) => post.url.endsWith("/synthetic/scenarios/canonical-scarcity"));
    expect(scarcityPosts).toHaveLength(1);
    expect(backend.counts.startDemoRun).toBe(1);
    expect(screen.getByText("ESCALATED / SAFETY_REVIEW_REQUIRED")).toBeInTheDocument();
  }, 15000);

  it("auto replay resumes from an existing incident without minting a new one", async () => {
    const backend = createAutoBackend();
    vi.stubGlobal("fetch", backend.fetchMock);
    const first = userEvent.setup();
    render(<OperationsConsole />);
    await first.click(screen.getByRole("button", { name: /^start recovery demo$/i }));
    await waitFor(() => expect(screen.getByText("SYN-EVT-AUTO")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /^auto replay$/i }));
    expect(screen.getByRole("button", { name: /auto start/i })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: /auto start/i }));

    await waitFor(() => expect(screen.getByText(/halt: terminal-success/i)).toBeInTheDocument(), { timeout: 3000 });
    const scarcityPosts = backend.posts.filter((post) => post.url.endsWith("/synthetic/scenarios/canonical-scarcity"));
    expect(scarcityPosts).toHaveLength(1);
    expect(backend.counts.bootstrap).toBe(1);
    expect(screen.getByText("ESCALATED / SAFETY_REVIEW_REQUIRED")).toBeInTheDocument();
  }, 15000);

  it("halts with error when the projected stage fetch fails and never mints a fresh incident", async () => {
    let breakStage = false;
    const posts: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (method === "POST") posts.push(url);
      if (url.endsWith("/canonical-replay/stage")) {
        if (breakStage) return jsonResponse({ detail: "stage projection unavailable" }, 500);
        return jsonResponse(defaultStageView());
      }
      if (url.endsWith("/synthetic/scenarios/canonical-scarcity") && method === "POST") return jsonResponse({ incident_id: INCIDENT_ID, evaluation_id: "eval-1", decision_ids: [], reproducibility_key: "a".repeat(64) }, 201);
      if (url.endsWith("/canonical-scarcity/fixture")) return jsonResponse(minimalFixture());
      if (url.includes("/scarcity-evaluation")) return jsonResponse(report);
      if (url.endsWith(`/incidents/${INCIDENT_ID}`)) return jsonResponse({ id: INCIDENT_ID, source_event_id: "SYN-EVT-FIX1", state: "RECOVERY_ANALYSIS", created_at: "" });
      if (url.includes(`/incidents/${INCIDENT_ID}/`)) return jsonResponse([]);
      return jsonResponse([]);
    }));
    const user = userEvent.setup();
    render(<OperationsConsole />);

    await user.click(screen.getByRole("button", { name: /^start recovery demo$/i }));
    await waitFor(() => expect(screen.getByText("SYN-EVT-FIX1")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /^auto replay$/i }));
    breakStage = true;
    await user.click(screen.getByRole("button", { name: /auto start/i }));

    await waitFor(() => expect(screen.getByText(/halt: error/i)).toBeInTheDocument());
    const scarcityPosts = posts.filter((postUrl) => postUrl.endsWith("/canonical-scarcity"));
    expect(scarcityPosts).toHaveLength(1);
    expect(screen.getByText("SYN-EVT-FIX1")).toBeInTheDocument();
  });
});
