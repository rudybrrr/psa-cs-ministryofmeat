import { describe, expect, it } from "vitest";

import { canonicalIncident } from "./adapter";

describe("canonical incident adapter", () => {
  it("loads exactly 24 unique containers from the frozen fixture", () => {
    const ids = canonicalIncident.containers.map((row) => row.containerId);

    expect(ids).toHaveLength(24);
    expect(new Set(ids).size).toBe(24);
    expect(ids[0]).toBe("SYN-CNT-001");
    expect(ids[23]).toBe("SYN-CNT-024");
  });

  it("counts 9 SF1, 8 JV2, and 7 EC3 containers", () => {
    const counts = Object.fromEntries(
      canonicalIncident.services.map((service) => [
        service.serviceId,
        service.containerCount,
      ]),
    );

    expect(counts).toEqual({ SF1: 9, JV2: 8, EC3: 7 });
  });

  it("derives 13 p50 expedition candidates against 8 available slots", () => {
    expect(canonicalIncident.candidateCount).toBe(13);
    expect(canonicalIncident.availableExpediteSlots).toBe(8);
    expect(canonicalIncident.selectedAllocation).toBeNull();
  });

  it("classifies frozen fixture rows without inventing allocations", () => {
    const byId = Object.fromEntries(
      canonicalIncident.containers.map((row) => [row.containerId, row]),
    );

    expect(byId["SYN-CNT-001"]?.classification).toBe("expedition candidate");
    expect(byId["SYN-CNT-008"]?.classification).toBe("no expedition needed");
    expect(byId["SYN-CNT-009"]?.classification).toBe(
      "expedition cannot preserve",
    );
    expect(byId["SYN-CNT-016"]?.classification).toBe("no expedition needed");
    expect(byId["SYN-CNT-017"]?.classification).toBe(
      "expedition cannot preserve",
    );

    const classified = canonicalIncident.containers.reduce<Record<string, number>>(
      (counts, row) => {
        counts[row.classification] = (counts[row.classification] ?? 0) + 1;
        return counts;
      },
      {},
    );

    expect(classified).toEqual({
      "expedition candidate": 13,
      "no expedition needed": 5,
      "expedition cannot preserve": 6,
    });
  });

  it("exposes structural DG and reefer constraints from the fixture", () => {
    const byId = Object.fromEntries(
      canonicalIncident.containers.map((row) => [row.containerId, row]),
    );

    expect(byId["SYN-CNT-004"]).toMatchObject({
      cargoKind: "DG",
      dgStructurallyCleared: true,
      structurallyEligible: true,
      classification: "expedition candidate",
    });
    expect(byId["SYN-CNT-009"]).toMatchObject({
      cargoKind: "DG",
      dgStructurallyCleared: false,
      structurallyEligible: false,
    });
    expect(byId["SYN-CNT-022"]).toMatchObject({
      cargoKind: "DG",
      dgStructurallyCleared: false,
      structurallyEligible: false,
    });
    expect(byId["SYN-CNT-023"]).toMatchObject({
      cargoKind: "REEFER",
      reeferContinuityAvailable: false,
      structurallyEligible: false,
    });
    expect(byId["SYN-CNT-002"]).toMatchObject({
      cargoKind: "REEFER",
      reeferContinuityAvailable: true,
      structurallyEligible: true,
    });
  });
});
