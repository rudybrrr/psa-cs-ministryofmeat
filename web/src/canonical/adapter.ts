/**
 * Typed view of shared/fixtures/canonical-24-container.json.
 *
 * Future API need: GET a CanonicalIncidentFixture (and later allocation
 * results) from the backend so the console does not load this JSON from disk.
 * Do not invent allocation results until that API exists.
 */
import canonicalFixtureJson from "../../../shared/fixtures/canonical-24-container.json";

export type CargoKind = "DRY" | "REEFER" | "DG";

export type Classification =
  | "expedition candidate"
  | "no expedition needed"
  | "expedition cannot preserve";

export interface CanonicalServiceCard {
  serviceId: string;
  containerCount: number;
  ptaUtc: string;
  boundaryUtc: string;
}

export interface CanonicalContainerRow {
  containerId: string;
  serviceId: string;
  cargoKind: CargoKind;
  handlingGroupId: string;
  baseReadyAt: string;
  boundaryOffsetMinutes: number;
  structurallyEligible: boolean;
  reeferContinuityAvailable: boolean;
  dgStructurallyCleared: boolean;
  classification: Classification;
}

export interface CanonicalIncidentViewModel {
  fixtureId: string;
  inboundService: string;
  delayMinutes: number;
  terminalId: string;
  affectedContainerCount: number;
  services: CanonicalServiceCard[];
  candidateCount: number;
  availableExpediteSlots: number;
  selectedAllocation: null;
  capacity: {
    totalSlots: number;
    handlingGroupLimits: { handlingGroupId: string; slots: number }[];
    maxReeferSlots: number;
    maxDgSlots: number;
    overlapServiceIds: string[];
  };
  containers: CanonicalContainerRow[];
}

const INBOUND_SERVICE_ID = "ASX-17";

function minutesBetween(laterIso: string, earlierIso: string): number {
  return (Date.parse(laterIso) - Date.parse(earlierIso)) / 60_000;
}

function isStructurallyEligible(profile: {
  cargo_kind: CargoKind;
  reefer_continuity_available: boolean;
  dg_structurally_cleared: boolean;
}): boolean {
  if (profile.cargo_kind === "REEFER" && !profile.reefer_continuity_available) {
    return false;
  }
  if (profile.cargo_kind === "DG" && !profile.dg_structurally_cleared) {
    return false;
  }
  return true;
}

function classifyProfile(
  offsetMinutes: number,
  expediteMinutesSaved: number,
  structurallyEligible: boolean,
): Classification {
  if (offsetMinutes <= 0) {
    return "no expedition needed";
  }
  if (offsetMinutes - expediteMinutesSaved <= 0 && structurallyEligible) {
    return "expedition candidate";
  }
  return "expedition cannot preserve";
}

function buildCanonicalIncident(): CanonicalIncidentViewModel {
  const fixture = canonicalFixtureJson;
  const servicesById = new Map(
    fixture.services.map((service) => [service.service_id, service]),
  );

  const containers: CanonicalContainerRow[] = fixture.profiles.map((profile) => {
    const service = servicesById.get(profile.service_id);
    if (!service) {
      throw new Error(`Unknown service ${profile.service_id}`);
    }

    const cargoKind = profile.cargo_kind as CargoKind;
    const structurallyEligible = isStructurallyEligible({
      cargo_kind: cargoKind,
      reefer_continuity_available: profile.reefer_continuity_available,
      dg_structurally_cleared: profile.dg_structurally_cleared,
    });
    const boundaryOffsetMinutes = minutesBetween(
      profile.base_ready_at,
      service.ready_boundary,
    );

    return {
      containerId: profile.container.id,
      serviceId: profile.service_id,
      cargoKind,
      handlingGroupId: profile.handling_group_id,
      baseReadyAt: profile.base_ready_at,
      boundaryOffsetMinutes,
      structurallyEligible,
      reeferContinuityAvailable: profile.reefer_continuity_available,
      dgStructurallyCleared: profile.dg_structurally_cleared,
      classification: classifyProfile(
        boundaryOffsetMinutes,
        profile.expedite_minutes_saved,
        structurallyEligible,
      ),
    };
  });

  const services: CanonicalServiceCard[] = fixture.services.map((service) => ({
    serviceId: service.service_id,
    containerCount: containers.filter((row) => row.serviceId === service.service_id)
      .length,
    ptaUtc: service.planned_time_of_arrival,
    boundaryUtc: service.ready_boundary,
  }));

  return {
    fixtureId: fixture.fixture_id,
    inboundService: INBOUND_SERVICE_ID,
    delayMinutes: fixture.event.delay_minutes,
    terminalId: fixture.event.terminal_id,
    affectedContainerCount: containers.length,
    services,
    candidateCount: containers.filter(
      (row) => row.classification === "expedition candidate",
    ).length,
    availableExpediteSlots: fixture.capacity.total_slots,
    selectedAllocation: null,
    capacity: {
      totalSlots: fixture.capacity.total_slots,
      handlingGroupLimits: fixture.capacity.handling_group_limits.map((limit) => ({
        handlingGroupId: limit.handling_group_id,
        slots: limit.slots,
      })),
      maxReeferSlots: fixture.capacity.max_reefer_slots,
      maxDgSlots: fixture.capacity.max_dg_slots,
      overlapServiceIds: [...fixture.capacity.overlap_service_ids],
    },
    containers,
  };
}

export const canonicalIncident = buildCanonicalIncident();
