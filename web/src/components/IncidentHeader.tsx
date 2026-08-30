import type { Incident, IncidentState } from "../api/types";
import { formatTimestamp, truncateId } from "../lib/format";

const STATE_STYLES: Record<
  IncidentState,
  { label: string; className: string }
> = {
  INCIDENT_RECEIVED: {
    label: "Incident received",
    className: "border-sky-500/50 bg-sky-950 text-sky-100",
  },
  COLLECTING_STATE: {
    label: "Collecting state",
    className: "border-blue-500/50 bg-blue-950 text-blue-100",
  },
  CONSTRAINT_VALIDATION: {
    label: "Constraint validation",
    className: "border-orange-500/50 bg-orange-950 text-orange-100",
  },
  RECOVERY_ANALYSIS: {
    label: "Recovery analysis",
    className: "border-yellow-500/50 bg-yellow-950 text-yellow-100",
  },
  RESOLVED: {
    label: "Resolved",
    className: "border-emerald-500/50 bg-emerald-950 text-emerald-100",
  },
  ESCALATED: {
    label: "Escalated",
    className: "border-rose-500/50 bg-rose-950 text-rose-100",
  },
};

interface IncidentHeaderProps {
  incident: Incident | null;
  loading: boolean;
}

export function IncidentHeader({ incident, loading }: IncidentHeaderProps) {
  const stateStyle = incident ? STATE_STYLES[incident.state] : null;

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 px-4 py-4">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <img src="/reroute-icon-white.png" alt="" className="h-10 w-10 shrink-0" />
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-slate-500">
              ReRoute
            </p>
            <h1 className="mt-1 text-xl font-semibold text-slate-100">
              Incident operations status
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {loading && (
            <span className="font-mono text-xs text-slate-400">Refreshing…</span>
          )}
          {stateStyle && (
            <span
              className={`rounded border px-3 py-1 font-mono text-xs font-semibold uppercase tracking-wide ${stateStyle.className}`}
            >
              {stateStyle.label}
            </span>
          )}
          {!incident && !loading && (
            <span className="rounded border border-slate-700 px-3 py-1 font-mono text-xs text-slate-400">
              No active incident
            </span>
          )}
        </div>
      </div>

      {incident && (
        <dl className="mx-auto mt-4 grid max-w-7xl gap-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
              Incident ID
            </dt>
            <dd
              className="mt-1 font-mono text-slate-200"
              title={incident.id}
            >
              {truncateId(incident.id)}
            </dd>
          </div>
          <div>
            <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
              Source event
            </dt>
            <dd className="mt-1 font-mono text-slate-200">
              {incident.source_event_id}
            </dd>
          </div>
          <div>
            <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
              Opened
            </dt>
            <dd className="mt-1 text-slate-200">
              {formatTimestamp(incident.created_at)}
            </dd>
          </div>
        </dl>
      )}
    </header>
  );
}
