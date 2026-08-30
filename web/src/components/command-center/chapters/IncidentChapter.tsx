import type { CanonicalIncidentFixture, Incident } from "../../../api/types";
import type { RecoverySummary } from "../../../lib/recoverySelectors";
import { serviceSummaries } from "../../../lib/chapterContext";
import { connectionShortLabel } from "../../../lib/formatters";
import { ChapterFrame, MetricCard } from "./ChapterFrame";

export function IncidentChapter({
  fixture,
  summary,
}: {
  incident: Incident | null;
  fixture: CanonicalIncidentFixture | null;
  summary: RecoverySummary | null;
}) {
  const services = serviceSummaries(fixture);

  return (
    <ChapterFrame
      label="Chapter 1 · Incident"
      title="Inbound disruption creates a constrained recovery problem"
    >
      <p className="max-w-2xl text-sm leading-relaxed text-psa-chalk">
        A delayed vessel arrival compresses the recovery window. PSA must preserve
        outbound connections for affected containers using scarce expedite capacity —
        without guessing before operational evidence arrives.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Schedule event"
          value={fixture?.event.id ?? "—"}
          accent
        />
        <MetricCard
          label="Delay"
          value={fixture ? `${fixture.event.delay_minutes} min` : "—"}
        />
        <MetricCard
          label="Containers at risk"
          value={summary ? String(summary.containersAtRisk) : "—"}
        />
        <MetricCard
          label="Expedite capacity"
          value={fixture ? String(fixture.capacity.total_slots) : "—"}
        />
      </div>

      {fixture ? (
        <div className="psa-surface-nested rounded-[8px] px-4 py-4">
          <p className="psa-label">Disruption context</p>
          <p className="mt-2 text-sm text-psa-chalk">
            <span className="font-mono text-psa-snow">{fixture.event.vessel_name}</span>{" "}
            at terminal {fixture.event.terminal_id} — estimated arrival shifted from
            scheduled inbound timing by {fixture.event.delay_minutes} minutes.
          </p>
        </div>
      ) : null}

      {services.length > 0 ? (
        <div className="psa-surface-nested rounded-[8px] px-4 py-4">
          <p className="psa-label">Affected connections</p>
          <ul className="mt-3 space-y-2 text-sm text-psa-chalk">
            {services.map((service) => (
              <li key={service.id} className="flex flex-wrap gap-x-3 gap-y-1">
                <span className="font-mono text-psa-snow">{service.id}</span>
                <span>{connectionShortLabel(service.connectionId)}</span>
                <span className="text-psa-steel">→ {service.destination}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </ChapterFrame>
  );
}
