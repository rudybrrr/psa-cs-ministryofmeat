import { useState } from "react";

import { AgentRunPanel } from "../../agent/AgentRunPanel";
import { AuditTimeline } from "../../AuditTimeline";
import { ActorLegend } from "../../ActorBadge";
import { CargoSafetyPanel } from "../../safety/CargoSafetyPanel";
import type {
  AgentHistory,
  AgentRun,
  AuditEvent,
  CargoSafetyHistory,
  CargoSafetyReview,
} from "../../../api/types";

export function EvidenceWorkspace({
  run,
  agentHistory,
  canAdvance,
  loading,
  auditEvents,
  approvalFingerprint,
  cargoReviews,
  safetyHistories,
  onAdvanceAgent,
  onRefresh,
  onStartAgent,
  onEvaluateSafety,
  onCreateSafetyReview,
}: {
  run: AgentRun | null;
  agentHistory: AgentHistory | null;
  canAdvance: boolean;
  loading: boolean;
  auditEvents: AuditEvent[];
  approvalFingerprint: string | null;
  cargoReviews: CargoSafetyReview[];
  safetyHistories: CargoSafetyHistory[];
  onAdvanceAgent(): void;
  onRefresh(): void;
  onStartAgent(): void;
  onEvaluateSafety(id: string): void;
  onCreateSafetyReview(): void;
}) {
  const [showFingerprint, setShowFingerprint] = useState(false);

  return (
    <div className="space-y-4">
      <header className="psa-surface rounded-[12px] px-5 py-4">
        <p className="psa-label text-psa-signal">Evidence / audit workspace</p>
        <h2 className="mt-1 text-lg font-medium text-psa-snow">Technical proof surface</h2>
        <p className="mt-2 text-sm text-psa-chalk">
          AgentRun steps, tool invocations, approval bindings, semantic safety evidence, and the
          append-only audit timeline. Raw payloads stay behind progressive disclosure.
        </p>
        {approvalFingerprint ? (
          <button
            type="button"
            className="mt-3 text-xs text-psa-signal underline-offset-2 hover:underline"
            onClick={() => setShowFingerprint((open) => !open)}
          >
            {showFingerprint ? "Hide" : "Show"} approval fingerprint
          </button>
        ) : null}
        {showFingerprint && approvalFingerprint ? (
          <p className="mt-2 break-all rounded-[8px] border border-white/10 bg-psa-slate px-3 py-2 font-mono text-[11px] text-psa-chalk">
            {approvalFingerprint}
          </p>
        ) : null}
      </header>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <AgentRunPanel
          run={run}
          history={agentHistory}
          loading={loading}
          canAdvance={canAdvance}
          onStart={onStartAgent}
          onAdvance={onAdvanceAgent}
          onRefresh={onRefresh}
        />
        <CargoSafetyPanel
          reviews={cargoReviews}
          histories={safetyHistories}
          loading={loading}
          onEvaluate={onEvaluateSafety}
          onCreateCanonical={onCreateSafetyReview}
        />
      </div>

      <section className="psa-surface space-y-4 rounded-[12px] px-4 py-4">
        <div>
          <h3 className="text-sm font-semibold text-psa-snow">Audit / decision history</h3>
          <p className="mt-1 text-xs text-psa-steel">
            Persisted audit trail for the active incident.
          </p>
        </div>
        <ActorLegend />
        <AuditTimeline events={auditEvents} loading={loading} />
      </section>
    </div>
  );
}
