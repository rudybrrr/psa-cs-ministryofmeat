import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationsConsole } from "../components/OperationsConsole";
import {
  jsonResponse,
  sampleAuditEvents,
  sampleDecision,
  sampleIncident,
} from "../test/fixtures";

describe("OperationsConsole trigger behavior", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls trigger and follow-up GET endpoints when the scenario is started", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.endsWith("/synthetic/scenarios/schedule-delay") && method === "POST") {
        return jsonResponse(
          {
            incident_id: sampleIncident.id,
            decision_id: sampleDecision.id,
          },
          201,
        );
      }

      if (url.endsWith(`/incidents/${sampleIncident.id}`)) {
        return jsonResponse(sampleIncident);
      }

      if (url.endsWith(`/incidents/${sampleIncident.id}/decisions`)) {
        return jsonResponse([sampleDecision]);
      }

      if (url.endsWith(`/incidents/${sampleIncident.id}/audit-events`)) {
        return jsonResponse(sampleAuditEvents);
      }

      return jsonResponse({ detail: "Unexpected request" }, 500);
    });

    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<OperationsConsole />);

    await user.click(
      screen.getByRole("button", { name: /trigger synthetic incident/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(sampleIncident.source_event_id)).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/synthetic/scenarios/schedule-delay",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(`/incidents/${sampleIncident.id}`, expect.any(Object));
    expect(fetchMock).toHaveBeenCalledWith(
      `/incidents/${sampleIncident.id}/decisions`,
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `/incidents/${sampleIncident.id}/audit-events`,
      expect.any(Object),
    );
  });
});

describe("OperationsConsole API rendering", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders persisted incident, decision, and audit data from the backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url.endsWith("/synthetic/scenarios/schedule-delay") && method === "POST") {
          return jsonResponse(
            {
              incident_id: sampleIncident.id,
              decision_id: sampleDecision.id,
            },
            201,
          );
        }

        if (url.endsWith(`/incidents/${sampleIncident.id}`)) {
          return jsonResponse(sampleIncident);
        }

        if (url.endsWith(`/incidents/${sampleIncident.id}/decisions`)) {
          return jsonResponse([sampleDecision]);
        }

        if (url.endsWith(`/incidents/${sampleIncident.id}/audit-events`)) {
          return jsonResponse(sampleAuditEvents);
        }

        return jsonResponse({ detail: "Unexpected request" }, 500);
      }),
    );

    const user = userEvent.setup();
    render(<OperationsConsole />);
    await user.click(
      screen.getByRole("button", { name: /trigger synthetic incident/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(sampleIncident.source_event_id)).toBeInTheDocument();
      expect(screen.getByText("PSAU1234567")).toBeInTheDocument();
      expect(screen.getByText(/Normal transfer misses the synthetic cutoff/i)).toBeInTheDocument();
      expect(screen.getByText("schedule.delay_ingested")).toBeInTheDocument();
      expect(screen.getByText("decision.created")).toBeInTheDocument();
    });
  });
});

describe("OperationsConsole error state", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows an alert when the trigger endpoint fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Synthetic scenario unavailable" }, 503)),
    );

    const user = userEvent.setup();
    render(<OperationsConsole />);
    await user.click(
      screen.getByRole("button", { name: /trigger synthetic incident/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("503");
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Synthetic scenario unavailable",
      );
    });
  });
});

describe("AuditTimeline ordering", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders audit events in timestamp order with actor badges", async () => {
    const shuffledEvents = [
      sampleAuditEvents[2],
      sampleAuditEvents[0],
      sampleAuditEvents[1],
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url.endsWith("/synthetic/scenarios/schedule-delay") && method === "POST") {
          return jsonResponse(
            {
              incident_id: sampleIncident.id,
              decision_id: sampleDecision.id,
            },
            201,
          );
        }

        if (url.endsWith(`/incidents/${sampleIncident.id}`)) {
          return jsonResponse(sampleIncident);
        }

        if (url.endsWith(`/incidents/${sampleIncident.id}/decisions`)) {
          return jsonResponse([sampleDecision]);
        }

        if (url.endsWith(`/incidents/${sampleIncident.id}/audit-events`)) {
          return jsonResponse(shuffledEvents);
        }

        return jsonResponse({ detail: "Unexpected request" }, 500);
      }),
    );

    const user = userEvent.setup();
    render(<OperationsConsole />);
    await user.click(
      screen.getByRole("button", { name: /trigger synthetic incident/i }),
    );

    await waitFor(() => {
      const eventTypes = screen
        .getAllByText(/schedule\.delay_ingested|connection\.feasibility_evaluated|decision\.created/)
        .map((node) => node.textContent);

      expect(eventTypes).toEqual([
        "schedule.delay_ingested",
        "connection.feasibility_evaluated",
        "decision.created",
      ]);
    });

    expect(screen.getAllByText("SYSTEM").length).toBeGreaterThan(0);
    expect(screen.getAllByText("POLICY").length).toBeGreaterThan(0);
  });
});
