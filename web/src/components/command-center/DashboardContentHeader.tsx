import type { Incident } from "../../api/types";
import type { CanonicalIncidentFixture } from "../../api/types";
import type { ConsoleMode } from "./ModeSwitcher";
import type { DashboardNavId } from "./DashboardSidebar";

export function DashboardContentHeader({
  incident,
  fixture,
  loading,
  onStartDemo,
  onStartFresh,
  showStartDemo,
}: {
  mode: ConsoleMode;
  workspace: DashboardNavId;
  incident: Incident | null;
  fixture: CanonicalIncidentFixture | null;
  loading: boolean;
  onStartDemo(): void;
  onStartFresh(): void;
  showStartDemo: boolean;
}) {
  const vessel = fixture?.event.vessel_name ?? "Late inbound vessel";
  const context = incident
    ? `${incident.state.replaceAll("_", " ").toLowerCase()}`
    : "Synthetic scenario ready — no active incident";

  return (
    <header className="border-b border-white/10 bg-psa-graphite px-5 py-3.5 lg:px-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-lg font-medium tracking-[-0.02em] text-psa-snow sm:text-xl">
            {incident ? `${vessel} disruption` : "Recovery Command Center"}
          </h1>
          <p className="mt-1 text-sm text-psa-chalk">
            {loading ? "Refreshing persisted recovery state…" : context}
          </p>
          {incident ? (
            <p className="psa-mono mt-1 text-[11px] text-psa-steel">{incident.source_event_id}</p>
          ) : null}
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {showStartDemo ? (
            <button
              type="button"
              disabled={loading}
              onClick={onStartDemo}
              className="psa-btn psa-btn-primary"
            >
              Start recovery demo
            </button>
          ) : null}
          {incident ? (
            <button
              type="button"
              disabled={loading}
              onClick={onStartFresh}
              className="psa-btn psa-btn-secondary"
            >
              Start fresh
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
