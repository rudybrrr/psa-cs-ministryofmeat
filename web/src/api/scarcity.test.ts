import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jsonResponse } from "../test/fixtures";
import {
  getCanonicalFixture,
  getScarcityEvaluation,
  triggerCanonicalScarcity,
} from "./scarcity";
import { ApiError } from "./client";

const INCIDENT_ID = "11111111-1111-4111-8111-111111111111";
const EVALUATION_ID = "22222222-2222-4222-8222-222222222222";

describe("scarcity API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts canonical scarcity trigger", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(
        {
          incident_id: INCIDENT_ID,
          evaluation_id: EVALUATION_ID,
          decision_ids: ["dddddddd-dddd-4ddd-8ddd-dddddddddddd"],
          reproducibility_key: "a".repeat(64),
        },
        201,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await triggerCanonicalScarcity();

    expect(fetchMock).toHaveBeenCalledWith(
      "/synthetic/scenarios/canonical-scarcity",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.incident_id).toBe(INCIDENT_ID);
    expect(result.evaluation_id).toBe(EVALUATION_ID);
  });

  it("gets canonical fixture", async () => {
    const fixture = { fixture_id: "SYN-CANONICAL-24-V1", event: {}, services: [], profiles: [], capacity: {} };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        expect(String(input)).toBe(
          "/synthetic/scenarios/canonical-scarcity/fixture",
        );
        return jsonResponse(fixture);
      }),
    );

    const result = await getCanonicalFixture();
    expect(result.fixture_id).toBe("SYN-CANONICAL-24-V1");
  });

  it("gets scarcity evaluation for incident", async () => {
    const report = {
      id: EVALUATION_ID,
      incident_id: INCIDENT_ID,
      fixture_id: "SYN-CANONICAL-24-V1",
      seed: 20260822,
      scenario_count: 50,
      baseline: { allocation: { strategy: "P50_GREEDY", allocated_container_ids: [] } },
      scenario_aware_evaluations: [],
      pareto_evaluations: [],
      selected_allocation: null,
      reproducibility_key: "b".repeat(64),
      created_at: "2026-08-22T08:00:00Z",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        expect(String(input)).toBe(
          `/incidents/${INCIDENT_ID}/scarcity-evaluation`,
        );
        return jsonResponse(report);
      }),
    );

    const result = await getScarcityEvaluation(INCIDENT_ID);
    expect(result.id).toBe(EVALUATION_ID);
  });

  it("maps 404 scarcity evaluation to ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Scarcity evaluation not found" }, 404)),
    );

    await expect(getScarcityEvaluation(INCIDENT_ID)).rejects.toBeInstanceOf(
      ApiError,
    );
    await expect(getScarcityEvaluation(INCIDENT_ID)).rejects.toMatchObject({
      status: 404,
      detail: "Scarcity evaluation not found",
    });
  });
});
