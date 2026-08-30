import { useState } from "react";

import type { CarrierRecoveryCase, CarrierRecoveryHistory, Decision } from "../../../api/types";
import { formatUtcClock } from "../../../lib/formatters";
import { DecisionLineage } from "../../carrier/DecisionLineage";
import { ChapterFrame } from "./ChapterFrame";

export function RespondChapter({
  carrierCase,
  history,
  decisions,
  loading,
  onSimulate,
  onApproveCounter,
  onRejectCounter,
  onEvaluateTimeout,
}: {
  carrierCase: CarrierRecoveryCase | null;
  history: CarrierRecoveryHistory | null;
  decisions: Decision[];
  loading: boolean;
  onSimulate(): void;
  onApproveCounter(): void;
  onRejectCounter(): void;
  onEvaluateTimeout(): void;
}) {
  const [showLineage, setShowLineage] = useState(false);
  const counter = history?.carrier_responses[0];

  return (
    <ChapterFrame
      label="Chapter 6 · Respond"
      title="External carrier response — second human approval"
    >
      <div className="rounded-[8px] border border-psa-amber/30 bg-psa-amber/5 px-4 py-4">
        <p className="psa-label text-psa-amber">External actor</p>
        <p className="mt-2 text-sm text-psa-chalk">
          Carrier responses arrive outside PSA control. The agent pauses for operator
          approval before recomputing recovery disposition.
        </p>
      </div>

      {carrierCase?.state === "AWAITING_CARRIER" ? (
        <div className="psa-surface-nested space-y-3 rounded-[8px] px-4 py-4">
          <p className="text-sm text-psa-chalk">Waiting for carrier response.</p>
          {history?.request_context?.sent_at ? (
            <p className="font-mono text-xs text-psa-steel">
              Sent {formatUtcClock(history.request_context.sent_at)}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={loading}
              onClick={onSimulate}
              className="psa-btn-secondary px-4 py-2 text-xs"
            >
              Simulate carrier response
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={onEvaluateTimeout}
              className="psa-btn-ghost px-4 py-2 text-xs"
            >
              Evaluate timeout
            </button>
          </div>
          <p className="text-xs text-psa-steel">
            SILENT outcomes leave no carrier response record; use explicit timeout
            evaluation after the deadline.
          </p>
        </div>
      ) : null}

      {carrierCase?.state === "AWAITING_COUNTER_APPROVAL" && history ? (
        <div className="psa-data-surface space-y-3 rounded-[10px] px-4 py-4">
          <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-psa-data-ink/60">
            Carrier counter proposal
          </p>
          <p className="text-sm text-psa-data-ink">
            Carrier counter received — waiting for operator approval.
          </p>
          {counter ? (
            <p className="font-mono text-xs text-psa-snow">
              Counter ETA{" "}
              {counter.counter_eta_pta ? formatUtcClock(counter.counter_eta_pta) : "—"}
              {counter.carrier_id ? ` · ${counter.carrier_id}` : ""}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={loading}
              onClick={onApproveCounter}
              className="psa-btn-primary px-4 py-2 text-xs"
            >
              Approve counter
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={onRejectCounter}
              className="psa-btn-secondary px-4 py-2 text-xs"
            >
              Reject counter
            </button>
          </div>
        </div>
      ) : null}

      {carrierCase?.state === "COMPLETED" && history ? (
        <div className="psa-surface-nested space-y-3 rounded-[8px] px-4 py-4">
          <p className="text-sm text-psa-fern">Carrier recovery completed.</p>
          {history.results.map((result) => (
            <div
              key={result.id}
              className="rounded border border-psa-graphite px-3 py-2 text-xs text-psa-chalk"
            >
              <p className="font-mono text-psa-snow">{result.container_id}</p>
              <p>{result.disposition.replaceAll("_", " ")}</p>
              <p className="text-psa-steel">{result.reconsideration_evidence_kind}</p>
            </div>
          ))}
          {history.results[0]?.replacement_decision_id ? (
            <>
              <button
                type="button"
                className="text-xs text-psa-signal underline-offset-2 hover:underline"
                onClick={() => setShowLineage((open) => !open)}
              >
                {showLineage ? "Hide" : "Show"} decision lineage
              </button>
              {showLineage ? (
                <DecisionLineage
                  decisionId={history.results[0].replacement_decision_id}
                  decisions={decisions}
                />
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}
    </ChapterFrame>
  );
}
