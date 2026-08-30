import type { Incident } from "../../api/types";
import type { CanonicalIncidentFixture } from "../../api/types";

export function IncidentCommandHeader({
  incident,
  fixture,
  loading,
}: {
  incident: Incident | null;
  fixture: CanonicalIncidentFixture | null;
  loading: boolean;
}) {
  if (!incident) {
    return null;
  }

  const vessel = fixture?.event.vessel_name ?? "Inbound vessel";
  const delay = fixture?.event.delay_minutes;

  return (
    <header className="psa-surface rounded-[12px] px-5 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="psa-label text-psa-signal">Active recovery</p>
          <h1 className="mt-2 text-2xl font-medium tracking-[-0.02em] text-psa-snow sm:text-[1.75rem]">
            {vessel} disruption
          </h1>
          <p className="mt-2 text-sm text-psa-chalk">
            {loading
              ? "Refreshing persisted recovery state…"
              : fixture?.event.estimated_arrival
                ? `ETA shift recorded · ${delay ?? "—"} min delay`
                : "Recovery analysis in progress"}
          </p>
        </div>
        <div className="text-right">
          <p className="psa-label">Event reference</p>
          <p className="mt-1 text-sm text-psa-chalk">{incident.source_event_id}</p>
          <p className="mt-1 text-xs text-psa-steel">{incident.state.replaceAll("_", " ")}</p>
        </div>
      </div>
    </header>
  );
}
