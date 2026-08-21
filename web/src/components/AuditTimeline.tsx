import type { AuditEvent } from "../api/types";
import { formatTimestamp } from "../lib/format";
import { ActorBadge } from "./ActorBadge";

interface AuditTimelineProps {
  events: AuditEvent[];
  loading: boolean;
}

function sortAuditEvents(events: AuditEvent[]): AuditEvent[] {
  return [...events].sort(
    (left, right) =>
      new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime(),
  );
}

function formatPayload(payload: Record<string, unknown>): string {
  return JSON.stringify(payload, null, 2);
}

export function AuditTimeline({ events, loading }: AuditTimelineProps) {
  const orderedEvents = sortAuditEvents(events);

  return (
    <section className="rounded border border-slate-800 bg-slate-950/60">
      <div className="border-b border-slate-800 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-100">Audit timeline</h2>
        <p className="mt-1 text-xs text-slate-500">
          Append-only evidence trail from persisted audit events.
        </p>
      </div>

      {loading && (
        <p className="px-4 py-6 font-mono text-sm text-slate-400">
          Loading audit events…
        </p>
      )}

      {!loading && orderedEvents.length === 0 && (
        <p className="px-4 py-6 text-sm text-slate-500">
          No audit events recorded for this incident yet.
        </p>
      )}

      {!loading && orderedEvents.length > 0 && (
        <ol className="divide-y divide-slate-900">
          {orderedEvents.map((event, index) => (
            <li key={event.id} className="px-4 py-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[11px] text-slate-500">
                  #{String(index + 1).padStart(2, "0")}
                </span>
                <ActorBadge actor={event.actor} />
                <span className="font-mono text-xs text-slate-300">
                  {event.event_type}
                </span>
                <span className="text-xs text-slate-500">
                  {formatTimestamp(event.timestamp)}
                </span>
              </div>

              {event.actor_id && (
                <p className="mt-2 font-mono text-[11px] text-slate-500">
                  actor_id: {event.actor_id}
                </p>
              )}

              <pre className="mt-3 overflow-x-auto rounded border border-slate-900 bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-slate-300">
                {formatPayload(event.payload)}
              </pre>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export { sortAuditEvents };
