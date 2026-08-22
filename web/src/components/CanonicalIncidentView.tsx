import { useMemo, useState } from "react";

import {
  canonicalIncident,
  type CanonicalContainerRow,
  type CargoKind,
  type Classification,
} from "../canonical/adapter";
import { formatSgClock, formatUtcClock } from "../lib/format";

type ServiceFilter = "all" | "SF1" | "JV2" | "EC3";
type CargoFilter = "all" | CargoKind;
type ClassificationFilter = "all" | Classification;

function formatOffset(minutes: number): string {
  if (minutes === 0) {
    return "0 min";
  }
  const sign = minutes > 0 ? "+" : "";
  return `${sign}${minutes} min`;
}

function eligibilityLabel(row: CanonicalContainerRow): string {
  if (row.cargoKind === "DG") {
    return row.dgStructurallyCleared
      ? "Eligible — DG structurally cleared"
      : "Ineligible — DG not structurally cleared";
  }
  if (row.cargoKind === "REEFER") {
    return row.reeferContinuityAvailable
      ? "Eligible — reefer continuity available"
      : "Ineligible — reefer continuity unavailable";
  }
  return "Eligible";
}

export function CanonicalIncidentView() {
  const [serviceFilter, setServiceFilter] = useState<ServiceFilter>("all");
  const [cargoFilter, setCargoFilter] = useState<CargoFilter>("all");
  const [classificationFilter, setClassificationFilter] =
    useState<ClassificationFilter>("all");

  const rows = useMemo(
    () =>
      canonicalIncident.containers.filter((row) => {
        if (serviceFilter !== "all" && row.serviceId !== serviceFilter) {
          return false;
        }
        if (cargoFilter !== "all" && row.cargoKind !== cargoFilter) {
          return false;
        }
        if (
          classificationFilter !== "all" &&
          row.classification !== classificationFilter
        ) {
          return false;
        }
        return true;
      }),
    [serviceFilter, cargoFilter, classificationFilter],
  );

  return (
    <div className="space-y-6">
      <section
        aria-labelledby="canonical-overview-heading"
        className="rounded border border-slate-800 bg-slate-950/60 px-4 py-4"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-amber-300">
              SYNTHETIC DATA
            </p>
            <h2
              id="canonical-overview-heading"
              className="mt-1 text-sm font-semibold text-slate-100"
            >
              Canonical incident overview
            </h2>
          </div>
          <p className="font-mono text-[11px] text-slate-500">
            {canonicalIncident.fixtureId} · local fixture · no allocation API
          </p>
        </div>

        <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
              Inbound service
            </dt>
            <dd className="mt-1 font-mono text-lg text-slate-100">
              {canonicalIncident.inboundService}
            </dd>
          </div>
          <div>
            <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
              Delay
            </dt>
            <dd className="mt-1 font-mono text-lg text-slate-100">
              {canonicalIncident.delayMinutes}-minute delay
            </dd>
          </div>
          <div>
            <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
              Terminal
            </dt>
            <dd className="mt-1 font-mono text-lg text-slate-100">
              {canonicalIncident.terminalId}
            </dd>
          </div>
          <div>
            <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
              Affected boxes
            </dt>
            <dd className="mt-1 font-mono text-lg text-slate-100">
              {canonicalIncident.affectedContainerCount} affected containers
            </dd>
          </div>
          <div>
            <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
              Onward services
            </dt>
            <dd className="mt-1 font-mono text-lg text-slate-100">
              {canonicalIncident.services
                .map((service) => service.serviceId)
                .join(" / ")}
            </dd>
          </div>
        </dl>
      </section>

      <section
        aria-labelledby="scarcity-heading"
        className="rounded border border-amber-500/30 bg-amber-950/20 px-4 py-4"
      >
        <h2 id="scarcity-heading" className="text-sm font-semibold text-slate-100">
          Scarcity summary
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div className="rounded border border-slate-800 bg-slate-950/70 px-4 py-4">
            <p className="font-mono text-4xl font-semibold text-amber-100">
              {canonicalIncident.candidateCount}
            </p>
            <p className="mt-1 text-sm text-slate-300">
              p50 expedition candidates
            </p>
          </div>
          <div className="rounded border border-slate-800 bg-slate-950/70 px-4 py-4">
            <p className="font-mono text-4xl font-semibold text-emerald-100">
              {canonicalIncident.availableExpediteSlots}
            </p>
            <p className="mt-1 text-sm text-slate-300">
              available expedite slots
            </p>
          </div>
        </div>
        <p className="mt-4 text-sm text-slate-300">
          {canonicalIncident.candidateCount} p50 expedition candidates compete
          for {canonicalIncident.availableExpediteSlots} available expedite
          slots. Phase 2 has not selected allocations yet.
        </p>
      </section>

      <section aria-labelledby="service-cards-heading" className="space-y-3">
        <h2 id="service-cards-heading" className="text-sm font-semibold text-slate-100">
          Onward services
        </h2>
        <div className="grid gap-4 lg:grid-cols-3">
          {canonicalIncident.services.map((service) => (
            <article
              key={service.serviceId}
              aria-labelledby={`service-${service.serviceId}`}
              className="rounded border border-slate-800 bg-slate-950/60 px-4 py-4"
            >
              <h3
                id={`service-${service.serviceId}`}
                className="font-mono text-lg font-semibold text-slate-100"
              >
                {service.serviceId}
              </h3>
              <p className="mt-2 font-mono text-sm text-slate-200">
                {service.containerCount} containers
              </p>
              <dl className="mt-3 space-y-1 text-sm text-slate-300">
                <div>
                  <dt className="sr-only">Planned time of arrival</dt>
                  <dd className="font-mono">
                    PTA {formatUtcClock(service.ptaUtc)}
                    <span className="ml-2 text-slate-500">
                      {formatSgClock(service.ptaUtc)}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt className="sr-only">Ready boundary</dt>
                  <dd className="font-mono">
                    boundary {formatUtcClock(service.boundaryUtc)}
                    <span className="ml-2 text-slate-500">
                      {formatSgClock(service.boundaryUtc)}
                    </span>
                  </dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section
        aria-labelledby="capacity-heading"
        className="rounded border border-slate-800 bg-slate-950/60 px-4 py-4"
      >
        <h2 id="capacity-heading" className="text-sm font-semibold text-slate-100">
          Expedite capacity
        </h2>
        <p className="mt-1 text-sm text-slate-400">
          Total critical-overlap slots: {canonicalIncident.capacity.totalSlots}
        </p>
        <p className="mt-3 font-mono text-[11px] uppercase tracking-wide text-slate-500">
          Handling groups
        </p>
        <ul className="mt-1 grid gap-1 font-mono text-sm text-slate-200 sm:grid-cols-3">
          {canonicalIncident.capacity.handlingGroupLimits.map((limit) => (
            <li key={limit.handlingGroupId}>
              {limit.handlingGroupId}: {limit.slots}
            </li>
          ))}
        </ul>
        <p className="mt-3 font-mono text-[11px] uppercase tracking-wide text-slate-500">
          Additional hard limits
        </p>
        <ul className="mt-1 space-y-1 font-mono text-sm text-slate-200">
          <li>reefer: {canonicalIncident.capacity.maxReeferSlots}</li>
          <li>
            structurally cleared DG: {canonicalIncident.capacity.maxDgSlots}
          </li>
        </ul>
        <p className="mt-3 text-sm text-slate-400">
          These are simultaneous hard constraints, not independent quotas to
          sum. Overlap services:{" "}
          {canonicalIncident.capacity.overlapServiceIds.join(" / ")}.
        </p>
      </section>

      <section
        aria-labelledby="container-table-heading"
        className="rounded border border-slate-800 bg-slate-950/60"
      >
        <div className="border-b border-slate-800 px-4 py-3">
          <h2
            id="container-table-heading"
            className="text-sm font-semibold text-slate-100"
          >
            Affected containers
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Classifications are derived from ready time, the service boundary,
            the 30-minute expedite saving, and structural eligibility. DG flags
            are structural fixture data only.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <label className="block text-xs text-slate-400">
              Filter by service
              <select
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 font-mono text-sm text-slate-100"
                value={serviceFilter}
                onChange={(event) =>
                  setServiceFilter(event.target.value as ServiceFilter)
                }
              >
                <option value="all">All services</option>
                <option value="SF1">SF1</option>
                <option value="JV2">JV2</option>
                <option value="EC3">EC3</option>
              </select>
            </label>
            <label className="block text-xs text-slate-400">
              Filter by cargo type
              <select
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 font-mono text-sm text-slate-100"
                value={cargoFilter}
                onChange={(event) =>
                  setCargoFilter(event.target.value as CargoFilter)
                }
              >
                <option value="all">All cargo types</option>
                <option value="DRY">DRY</option>
                <option value="REEFER">REEFER</option>
                <option value="DG">DG</option>
              </select>
            </label>
            <label className="block text-xs text-slate-400">
              Filter by classification
              <select
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 font-mono text-sm text-slate-100"
                value={classificationFilter}
                onChange={(event) =>
                  setClassificationFilter(
                    event.target.value as ClassificationFilter,
                  )
                }
              >
                <option value="all">All classifications</option>
                <option value="expedition candidate">
                  expedition candidate
                </option>
                <option value="no expedition needed">
                  no expedition needed
                </option>
                <option value="expedition cannot preserve">
                  expedition cannot preserve
                </option>
              </select>
            </label>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table
            aria-label="Affected containers"
            className="min-w-full border-collapse text-sm"
          >
            <thead>
              <tr className="border-b border-slate-800 text-left font-mono text-[11px] uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2 font-normal">Container</th>
                <th className="px-3 py-2 font-normal">Service</th>
                <th className="px-3 py-2 font-normal">Cargo type</th>
                <th className="px-3 py-2 font-normal">Handling group</th>
                <th className="px-3 py-2 font-normal">
                  Base ready / boundary offset
                </th>
                <th className="px-3 py-2 font-normal">Structural eligibility</th>
                <th className="px-3 py-2 font-normal">Current classification</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.containerId} className="border-b border-slate-900/80">
                  <td className="px-3 py-3 font-mono text-slate-200">
                    {row.containerId}
                  </td>
                  <td className="px-3 py-3 font-mono text-slate-300">
                    {row.serviceId}
                  </td>
                  <td className="px-3 py-3 font-mono text-slate-300">
                    {row.cargoKind}
                  </td>
                  <td className="px-3 py-3 font-mono text-slate-300">
                    {row.handlingGroupId}
                  </td>
                  <td className="px-3 py-3 font-mono text-slate-300">
                    {formatUtcClock(row.baseReadyAt)} /{" "}
                    {formatOffset(row.boundaryOffsetMinutes)}
                  </td>
                  <td className="px-3 py-3 text-slate-300">
                    {eligibilityLabel(row)}
                  </td>
                  <td className="px-3 py-3 text-slate-200">{row.classification}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {rows.length === 0 && (
          <p className="px-4 py-6 text-sm text-slate-500">
            No containers match the current filters.
          </p>
        )}
      </section>
    </div>
  );
}
