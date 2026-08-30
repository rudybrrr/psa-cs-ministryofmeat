import type { Incident } from "../../api/types";
import type { CanonicalIncidentFixture } from "../../api/types";
import type { ConsoleMode } from "./ModeSwitcher";
import type { DashboardNavId } from "./DashboardSidebar";

const MODE_LABELS: Record<ConsoleMode, string> = {
  guided: "Guided demo",
  auto: "Auto replay",
  explore: "Explore workspace",
};

const WORKSPACE_LABELS: Record<DashboardNavId, string> = {
  overview: "Overview",
  recovery: "Recovery",
  containers: "Containers",
  carrier: "Carrier",
  evidence: "Evidence / Audit",
};

export function DashboardContentHeader({
  mode,
  workspace,
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
    ? `${vessel} · ${incident.state.replaceAll("_", " ").toLowerCase()}`
    : "No active incident · synthetic scenario ready";

  return (
    <header className="border-b border-white/10 bg-psa-graphite px-5 py-4 lg:px-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          {incident ? (
            <p className="psa-label text-psa-signal">Recovery command center</p>
          ) : null}
          <h1 className={`font-medium tracking-[-0.02em] text-psa-snow sm:text-2xl ${incident ? "mt-1 text-xl" : "text-xl"}`}>
            {incident ? `${vessel} disruption` : "Recovery Command Center"}
          </h1>
          <p className="mt-1.5 text-sm text-psa-chalk">
            {loading ? "Refreshing persisted recovery state…" : context}
          </p>
          <p className="mt-1 text-xs text-psa-steel">
            Workspace: <span className="text-psa-chalk">{WORKSPACE_LABELS[workspace]}</span>
            {" · "}
            Mode: <span className="text-psa-chalk">{MODE_LABELS[mode]}</span>
            {incident ? (
              <>
                {" · "}
                <span className="font-mono text-psa-fog">{incident.source_event_id}</span>
              </>
            ) : null}
          </p>
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
