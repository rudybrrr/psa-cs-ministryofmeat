import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jsonResponse } from "../test/fixtures";
import { ApiError } from "./client";
import {
  approveCounter,
  approveRequest,
  evaluateTimeout,
  getCarrierCase,
  getCarrierCaseHistory,
  listCarrierCases,
  prepareCarrierRecovery,
  rejectCounter,
  rejectRequest,
  sendCarrierRequest,
  simulateCarrierResponse,
} from "./carrierRecovery";

const INCIDENT_ID = "11111111-1111-4111-8111-111111111111";
const CASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const PREPARED_AT = "2026-08-22T07:00:00Z";
const PREPARE_TIME = "2026-08-22T08:00:00Z";
const DEADLINE = "2026-08-22T09:00:00Z";
const RESPONSE_TIME = "2026-08-22T08:30:00Z";

const sampleCase = {
  id: CASE_ID,
  incident_id: INCIDENT_ID,
  connection_id: "SYN-CONN-JV2",
  source_evaluation_id: "22222222-2222-4222-8222-222222222222",
  affected_container_ids: ["SYN-CNT-017"],
  state: "AWAITING_REQUEST_APPROVAL",
  created_at: PREPARED_AT,
  updated_at: PREPARED_AT,
};

describe("carrier recovery API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("prepares carrier recovery case", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(sampleCase, 201));
    vi.stubGlobal("fetch", fetchMock);

    const result = await prepareCarrierRecovery(INCIDENT_ID, {
      connection_id: "SYN-CONN-JV2",
      prepared_at: PREPARED_AT,
      requested_eta_pta: PREPARE_TIME,
      response_deadline: DEADLINE,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `/incidents/${INCIDENT_ID}/carrier-recovery-cases`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          connection_id: "SYN-CONN-JV2",
          prepared_at: PREPARED_AT,
          requested_eta_pta: PREPARE_TIME,
          response_deadline: DEADLINE,
        }),
      }),
    );
    expect(result.connection_id).toBe("SYN-CONN-JV2");
  });

  it("lists and gets carrier cases", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith(`/incidents/${INCIDENT_ID}/carrier-recovery-cases`)) {
          return jsonResponse([sampleCase]);
        }
        if (url.endsWith(`/carrier-recovery-cases/${CASE_ID}`)) {
          return jsonResponse(sampleCase);
        }
        return jsonResponse({ detail: "missing" }, 404);
      }),
    );

    const cases = await listCarrierCases(INCIDENT_ID);
    expect(cases).toHaveLength(1);

    const single = await getCarrierCase(CASE_ID);
    expect(single.id).toBe(CASE_ID);
  });

  it("posts request approval, send, simulate, counter approval, timeout", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.endsWith("/request-approval") && method === "POST") {
        return jsonResponse({ id: "ap1", decision_id: "d1", operator_id: "op", status: "APPROVED", reason: null, created_at: PREPARED_AT }, 201);
      }
      if (url.endsWith("/send") && method === "POST") {
        return jsonResponse({ case_id: CASE_ID, request_id: "r1", payload_fingerprint: "fp", prepared_at: PREPARED_AT, response_deadline: DEADLINE, sent_at: PREPARE_TIME, closed_at: null, close_reason: null, timeout_observed_at: null }, 201);
      }
      if (url.endsWith("/simulate-carrier-response") && method === "POST") {
        return jsonResponse({ case_id: CASE_ID, carrier_response_id: "cr1", no_response_emitted: false }, 201);
      }
      if (url.endsWith("/counter-approval") && method === "POST") {
        return jsonResponse({ id: "ap2", decision_id: "d2", operator_id: "op", status: "APPROVED", reason: null, created_at: PREPARED_AT }, 201);
      }
      if (url.endsWith("/evaluate-timeout") && method === "POST") {
        return jsonResponse({ ...sampleCase, state: "COMPLETED" }, 201);
      }
      if (url.endsWith("/history")) {
        return jsonResponse({ case: sampleCase, bindings: [], approvals: [], carrier_responses: [], effective_timings: [], decision_links: [], decisions: [], results: [], audit_events: [] });
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    const approvalBody = {
      proposal_decision_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      request_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      expected_payload_fingerprint: "abc",
      operator_id: "operator-ui",
      status: "APPROVED" as const,
    };

    await approveRequest(CASE_ID, approvalBody);
    await sendCarrierRequest(CASE_ID);
    await simulateCarrierResponse(CASE_ID, { effective_at: RESPONSE_TIME });
    await approveCounter(CASE_ID, {
      ...approvalBody,
      carrier_response_id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
    });
    await evaluateTimeout(CASE_ID, { effective_at: DEADLINE });

    expect(fetchMock).toHaveBeenCalledWith(
      `/carrier-recovery-cases/${CASE_ID}/request-approval`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `/carrier-recovery-cases/${CASE_ID}/send`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `/carrier-recovery-cases/${CASE_ID}/simulate-carrier-response`,
      expect.objectContaining({
        body: JSON.stringify({ effective_at: RESPONSE_TIME }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `/carrier-recovery-cases/${CASE_ID}/counter-approval`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `/carrier-recovery-cases/${CASE_ID}/evaluate-timeout`,
      expect.objectContaining({ method: "POST" }),
    );

    const history = await getCarrierCaseHistory(CASE_ID);
    expect(history.case.id).toBe(CASE_ID);
  });

  it("reject helpers send rejected status", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ id: "ap1", decision_id: "d1", operator_id: "op", status: "REJECTED", reason: null, created_at: PREPARED_AT }, 201),
    );
    vi.stubGlobal("fetch", fetchMock);

    const body = {
      proposal_decision_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      request_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      expected_payload_fingerprint: "abc",
      operator_id: "operator-ui",
    };

    await rejectRequest(CASE_ID, body);
    await rejectCounter(CASE_ID, {
      ...body,
      carrier_response_id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
    });

    const bodies = fetchMock.mock.calls.map(([, init]) =>
      JSON.parse(String(init?.body)),
    );
    expect(bodies.every((item) => item.status === "REJECTED")).toBe(true);
  });

  it("maps 409 conflicts to ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "carrier simulation is not valid" }, 409)),
    );

    await expect(
      simulateCarrierResponse(CASE_ID, { effective_at: RESPONSE_TIME }),
    ).rejects.toMatchObject({ status: 409 });
    await expect(
      simulateCarrierResponse(CASE_ID, { effective_at: RESPONSE_TIME }),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
