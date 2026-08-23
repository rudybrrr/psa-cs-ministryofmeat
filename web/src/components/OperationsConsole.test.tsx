import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationsConsole } from "./OperationsConsole";
import { jsonResponse } from "../test/fixtures";

const INCIDENT_ID = "11111111-1111-4111-8111-111111111111";
const CASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

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

function createFetchMock(handlers: {
  carrierCases?: unknown[];
  historyByCase?: Record<string, unknown>;
  onPost?: (url: string, body?: unknown) => void;
}) {
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

    return jsonResponse({ detail: `Unexpected ${method} ${url}` }, 500);
  });
}

describe("OperationsConsole canonical scarcity", () => {
  afterEach(() => cleanup());
  beforeEach(() => vi.restoreAllMocks());

  it("creates canonical incident and renders live recovery summary", async () => {
    vi.stubGlobal("fetch", createFetchMock({}));

    const user = userEvent.setup();
    render(<OperationsConsole />);

    await user.click(
      screen.getByRole("button", { name: /create canonical scarcity incident/i }),
    );

    await waitFor(() => {
      expect(screen.getByText("SYN-EVT-ASX17-20260822-001")).toBeInTheDocument();
      expect(screen.getByText("LIVE EVALUATION")).toBeInTheDocument();
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
      screen.getByRole("button", { name: /create canonical scarcity incident/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("503");
    });
  });
});

describe("RecoveryConsole integration demo flows", () => {
  afterEach(() => cleanup());
  beforeEach(() => vi.restoreAllMocks());

  it("represents COUNTER flow with second human approval", async () => {
    const posts: string[] = [];
    const dynamicCases: unknown[] = [];
    const fetchMock = createFetchMock({
      carrierCases: dynamicCases,
      onPost: (url) => posts.push(url),
      historyByCase: {
        [CASE_ID]: {
          case: {
            id: CASE_ID,
            incident_id: INCIDENT_ID,
            connection_id: "SYN-CONN-JV2",
            source_evaluation_id: "eval-1",
            affected_container_ids: ["SYN-CNT-017"],
            state: "AWAITING_COUNTER_APPROVAL",
            created_at: "2026-08-22T07:00:00Z",
            updated_at: "2026-08-22T08:30:00Z",
          },
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
        },
      },
    });

    vi.stubGlobal("fetch", fetchMock);
    dynamicCases.push({
      id: CASE_ID,
      incident_id: INCIDENT_ID,
      connection_id: "SYN-CONN-JV2",
      source_evaluation_id: "eval-1",
      affected_container_ids: ["SYN-CNT-017"],
      state: "AWAITING_COUNTER_APPROVAL",
      created_at: "2026-08-22T07:00:00Z",
      updated_at: "2026-08-22T08:30:00Z",
    });

    const user = userEvent.setup();
    render(<OperationsConsole />);

    await user.click(screen.getByRole("button", { name: /run counter/i }));
    await waitFor(() => {
      expect(screen.getAllByText("SYN-CNT-017").length).toBeGreaterThan(0);
    });

    await user.click(screen.getByRole("cell", { name: "SYN-CNT-017" }));

    await waitFor(() => {
      expect(screen.getByText(/waiting for operator approval/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /approve counter/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /approve counter/i }));

    await waitFor(() => {
      expect(posts.some((url) => url.endsWith("/counter-approval"))).toBe(true);
    });
  });

  it("represents SILENT flow via explicit timeout without carrier response", async () => {
    const posts: string[] = [];
    vi.stubGlobal(
      "fetch",
      createFetchMock({
        onPost: (url) => posts.push(url),
        carrierCases: [
          {
            id: CASE_ID,
            incident_id: INCIDENT_ID,
            connection_id: "SYN-CONN-EC3",
            source_evaluation_id: "eval-1",
            affected_container_ids: ["SYN-CNT-021"],
            state: "AWAITING_CARRIER",
            created_at: "2026-08-22T07:00:00Z",
            updated_at: "2026-08-22T08:00:00Z",
          },
        ],
        historyByCase: {
          [CASE_ID]: {
            case: {
              id: CASE_ID,
              incident_id: INCIDENT_ID,
              connection_id: "SYN-CONN-EC3",
              source_evaluation_id: "eval-1",
              affected_container_ids: ["SYN-CNT-021"],
              state: "AWAITING_CARRIER",
              created_at: "2026-08-22T07:00:00Z",
              updated_at: "2026-08-22T08:00:00Z",
            },
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

    await user.click(screen.getByRole("button", { name: /run silent/i }));
    await waitFor(() => {
      expect(screen.getAllByText("SYN-CNT-021").length).toBeGreaterThan(0);
    });
    await user.click(screen.getByRole("cell", { name: "SYN-CNT-021" }));

    await waitFor(() => {
      expect(screen.getByText(/no carrier response record/i)).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /evaluate timeout/i }));

    await waitFor(() => {
      expect(posts.some((url) => url.endsWith("/evaluate-timeout"))).toBe(true);
    });
  });
});
