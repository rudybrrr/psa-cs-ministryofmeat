import { useCallback, useState } from "react";

import {
  ApiError,
  loadIncidentSnapshot,
  triggerAndLoadIncidentSnapshot,
} from "../api/client";
import type { IncidentSnapshot, TriggerResponse } from "../api/types";
import { AuditTimeline } from "./AuditTimeline";
import { ActorLegend } from "./ActorBadge";
import { CurrentDecision } from "./CurrentDecision";
import { IncidentHeader } from "./IncidentHeader";
import { SyntheticBanner } from "./SyntheticBanner";

type ConsolePhase = "idle" | "triggering" | "ready" | "error";

export function OperationsConsole() {
  const [phase, setPhase] = useState<ConsolePhase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [triggerResult, setTriggerResult] = useState<TriggerResponse | null>(
    null,
  );
  const [snapshot, setSnapshot] = useState<IncidentSnapshot | null>(null);

  const runTrigger = useCallback(async () => {
    setPhase("triggering");
    setErrorMessage(null);

    try {
      const result = await triggerAndLoadIncidentSnapshot();
      setTriggerResult(result.trigger);
      setSnapshot(result.snapshot);
      setPhase("ready");
    } catch (error) {
      const message =
        error instanceof ApiError
          ? `${error.status}: ${error.detail}`
          : error instanceof Error
            ? error.message
            : "Unexpected error while triggering synthetic incident";

      setErrorMessage(message);
      setPhase("error");
    }
  }, []);

  const refreshSnapshot = useCallback(async () => {
    if (!snapshot?.incident.id) {
      return;
    }

    setPhase("triggering");
    setErrorMessage(null);

    try {
      const refreshed = await loadIncidentSnapshot(snapshot.incident.id);
      setSnapshot(refreshed);
      setPhase("ready");
    } catch (error) {
      const message =
        error instanceof ApiError
          ? `${error.status}: ${error.detail}`
          : error instanceof Error
            ? error.message
            : "Unexpected error while refreshing incident";

      setErrorMessage(message);
      setPhase("error");
    }
  }, [snapshot?.incident.id]);

  const loading = phase === "triggering";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <SyntheticBanner />
      <IncidentHeader incident={snapshot?.incident ?? null} loading={loading} />

      <main className="mx-auto max-w-7xl px-4 py-6">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded border border-slate-800 bg-slate-900/40 px-4 py-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">
              Synthetic scenario control
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-slate-400">
              Trigger the canonical one-container schedule-delay scenario. The
              console loads persisted incident, decision, and audit state from
              the FastAPI backend.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void runTrigger()}
              disabled={loading}
              className="rounded border border-emerald-500/60 bg-emerald-900/40 px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wide text-emerald-100 transition hover:bg-emerald-900/70 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Trigger synthetic incident
            </button>
            {snapshot && (
              <button
                type="button"
                onClick={() => void refreshSnapshot()}
                disabled={loading}
                className="rounded border border-slate-700 px-4 py-2 font-mono text-xs uppercase tracking-wide text-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Refresh persisted state
              </button>
            )}
          </div>
        </div>

        {phase === "idle" && (
          <div className="rounded border border-dashed border-slate-800 bg-slate-950/40 px-6 py-10 text-center">
            <p className="text-sm text-slate-400">
              No incident loaded. Trigger the synthetic schedule-delay scenario
              to begin the one-container recovery walkthrough.
            </p>
          </div>
        )}

        {loading && (
          <div className="mb-6 rounded border border-slate-800 bg-slate-900/30 px-4 py-3 font-mono text-sm text-slate-300">
            Contacting backend and loading persisted incident state…
          </div>
        )}

        {phase === "error" && errorMessage && (
          <div
            role="alert"
            className="mb-6 rounded border border-rose-500/50 bg-rose-950/40 px-4 py-3 text-sm text-rose-100"
          >
            <p className="font-semibold">Operations console error</p>
            <p className="mt-1 font-mono text-xs">{errorMessage}</p>
          </div>
        )}

        {snapshot && (
          <div className="space-y-6">
            <section className="rounded border border-slate-800 bg-slate-950/60 px-4 py-4">
              <h2 className="text-sm font-semibold text-slate-100">
                Current incident summary
              </h2>
              <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
                    Workflow state
                  </dt>
                  <dd className="mt-1 font-mono text-slate-200">
                    {snapshot.incident.state}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
                    Decisions recorded
                  </dt>
                  <dd className="mt-1 font-mono text-slate-200">
                    {snapshot.decisions.length}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
                    Audit events
                  </dt>
                  <dd className="mt-1 font-mono text-slate-200">
                    {snapshot.auditEvents.length}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[11px] uppercase tracking-wide text-slate-500">
                    Trigger decision ID
                  </dt>
                  <dd className="mt-1 font-mono text-slate-200">
                    {triggerResult?.decision_id ?? "—"}
                  </dd>
                </div>
              </dl>
            </section>

            <section className="rounded border border-slate-800 bg-slate-950/60 px-4 py-4">
              <h2 className="text-sm font-semibold text-slate-100">
                Audit actor legend
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Current synthetic scenario emits SYSTEM and POLICY actors only.
                Other badges are reserved for later workflow stages.
              </p>
              <div className="mt-3">
                <ActorLegend />
              </div>
            </section>

            <CurrentDecision
              decisions={snapshot.decisions}
              highlightDecisionId={triggerResult?.decision_id ?? null}
              loading={loading}
            />

            <AuditTimeline events={snapshot.auditEvents} loading={loading} />
          </div>
        )}
      </main>
    </div>
  );
}
