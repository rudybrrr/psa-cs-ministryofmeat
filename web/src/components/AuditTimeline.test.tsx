import { describe, expect, it } from "vitest";

import { sortAuditEvents } from "../components/AuditTimeline";
import { sampleAuditEvents } from "../test/fixtures";

describe("sortAuditEvents", () => {
  it("orders events chronologically regardless of API response order", () => {
    const shuffled = [
      sampleAuditEvents[2],
      sampleAuditEvents[0],
      sampleAuditEvents[1],
    ];

    const ordered = sortAuditEvents(shuffled);

    expect(ordered.map((event) => event.event_type)).toEqual([
      "schedule.delay_ingested",
      "connection.feasibility_evaluated",
      "decision.created",
    ]);
  });
});
