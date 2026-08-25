import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OperationsConsole } from "./OperationsConsole";
import { jsonResponse } from "../test/fixtures";

const incidentId = "11111111-1111-4111-8111-111111111111";
const fixture = { fixture_id: "SYN", event: { id: "event", vessel_call_id: "v", vessel_name: "v", terminal_id: "T", scheduled_arrival: "2026-08-25T00:00:00Z", estimated_arrival: "2026-08-25T01:00:00Z", delay_minutes: 60, occurred_at: "2026-08-25T01:00:00Z" }, services: [], profiles: [], capacity: { id: "cap", terminal_id: "T", window_start: "2026-08-25T00:00:00Z", window_end: "2026-08-25T01:00:00Z", overlap_service_ids: [], total_slots: 1, handling_group_limits: [], max_reefer_slots: 0, max_dg_slots: 0 } };
const report = { id: "eval", incident_id: incidentId, fixture_id: "SYN", seed: 1, scenario_count: 50, baseline: { allocation: { strategy: "P50_GREEDY", allocated_container_ids: [] }, world_count: 50, preserved_connection_total: 1, expected_preserved_connections: 1, rollover_total: 0, expected_rollovers: 0, p10_preserved_connections: 1, allocation_slot_count: 0, capacity_violations: 0, unsafe_allocations: 0, runtime_ms: 1, service_outcomes: [] }, scenario_aware_evaluations: [], pareto_evaluations: [], selected_allocation: null, reproducibility_key: "a".repeat(64), created_at: "2026-08-25T01:00:00Z" };

describe("OperationsConsole guided flow", () => {
  afterEach(() => cleanup());
  it("creates an incident, bootstraps only on explicit click, and never auto-advances", async () => {
    const posts: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input); const method = init?.method ?? "GET";
      if (method === "POST") posts.push(url);
      if (url.endsWith("/synthetic/scenarios/canonical-scarcity")) return jsonResponse({ incident_id: incidentId, evaluation_id: "eval", decision_ids: [], reproducibility_key: "a".repeat(64) }, 201);
      if (url.endsWith("/fixture")) return jsonResponse(fixture);
      if (url.endsWith(`/incidents/${incidentId}/scarcity-evaluation`)) return jsonResponse(report);
      if (url.endsWith(`/incidents/${incidentId}`)) return jsonResponse({ id: incidentId, source_event_id: "SYN-EVENT", state: "RECOVERY_ANALYSIS", created_at: "2026-08-25T01:00:00Z" });
      if (url.includes(`/incidents/${incidentId}/`)) return jsonResponse([]);
      return jsonResponse({ detail: "unexpected" }, 404);
    }));
    const user = userEvent.setup(); render(<OperationsConsole />);
    expect(screen.getByText(/SYNTHETIC DATA/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^create canonical incident$/i }));
    await waitFor(() => expect(screen.getByText("SYN-EVENT")).toBeInTheDocument());
    expect(posts.filter((url) => url.endsWith("/agent-runs") && url.includes("/advance")).length).toBe(0);
    await user.click(screen.getAllByRole("button", { name: /bootstrap pre_discharge/i }).at(-1)!);
    await waitFor(() => expect(posts.filter((url) => url.endsWith("/bootstrap")).length).toBe(1));
    expect(posts.some((url) => url.includes("/agent-runs/") && url.endsWith("/advance"))).toBe(false);
    expect(posts.some((url) => url.includes("optimizer") || url.includes("allocation-tradeoff-options/") && !url.endsWith("/bootstrap"))).toBe(false);
  });
});
