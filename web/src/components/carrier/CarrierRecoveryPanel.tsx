import type { CarrierRecoveryCase, CarrierRecoveryHistory } from "../../api/types";
import type { ContainerRecoveryRow } from "../../lib/recoverySelectors";
import { connectionShortLabel, formatUtcClock } from "../../lib/formatters";
import { hasCarrierResponseEvidence } from "../../lib/recoverySelectors";
import { RecoveryStatusBadge } from "../recovery/RecoveryStatusBadge";
import { DecisionLineage } from "./DecisionLineage";

interface CarrierRecoveryPanelProps {
  selectedContainer: ContainerRecoveryRow | null;
  carrierCase: CarrierRecoveryCase | null;
  history: CarrierRecoveryHistory | null;
  decisions: CarrierRecoveryHistory["decisions"];
  loading: boolean;
  onPrepare: (connectionId: string) => void;
  onApproveRequest: () => void;
  onRejectRequest: () => void;
  onSend: () => void;
  onSimulate: () => void;
  onApproveCounter: () => void;
  onRejectCounter: () => void;
  onEvaluateTimeout: () => void;
  agentRunActive?: boolean;
}

function actionButtonClass(variant: "primary" | "danger" | "neutral" = "primary") {
  const base =
    "rounded border px-3 py-2 font-mono text-[11px] uppercase tracking-wide disabled:cursor-not-allowed disabled:opacity-50";
  if (variant === "danger") {
    return `${base} border-rose-500/50 bg-rose-950/40 text-rose-100 hover:bg-rose-900/50`;
  }
  if (variant === "neutral") {
    return `${base} border-slate-700 text-slate-300 hover:bg-slate-800`;
  }
  return `${base} border-emerald-500/50 bg-emerald-950/40 text-emerald-100 hover:bg-emerald-900/50`;
}

export function CarrierRecoveryPanel({
  selectedContainer,
  carrierCase,
  history,
  decisions,
  loading,
  onPrepare,
  onApproveRequest,
  onRejectRequest,
  onSend,
  onSimulate,
  onApproveCounter,
  onRejectCounter,
  onEvaluateTimeout,
  agentRunActive = false,
}: CarrierRecoveryPanelProps) {
  if (!selectedContainer) {
    return (
      <aside className="rounded border border-slate-800 bg-slate-950/60 px-4 py-4">
        <h2 className="text-sm font-semibold text-slate-100">Carrier recovery</h2>
        <p className="mt-2 text-sm text-slate-500">
          Select a container to inspect connection-scoped carrier recovery evidence
          and operator controls.
        </p>
      </aside>
    );
  }

  const affectedCount =
    carrierCase?.affected_container_ids.length ??
    history?.case.affected_container_ids.length ??
    0;

  return (
    <aside className="space-y-4 rounded border border-slate-800 bg-slate-950/60 px-4 py-4">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-sky-300">
          OPERATOR CONTROLS
        </p>
        <h2 className="mt-1 text-sm font-semibold text-slate-100">Carrier recovery</h2>
        <p className="mt-2 text-sm text-slate-300">
          Connection:{" "}
          <span className="font-mono text-slate-100">
            {connectionShortLabel(selectedContainer.connectionId)}
          </span>
        </p>
        <p className="text-xs text-slate-500">
          {selectedContainer.connectionId} · affected snapshot {affectedCount}{" "}
          containers
        </p>
      </div>

      <div className="rounded border border-slate-800 bg-slate-900/40 px-3 py-3 text-sm text-slate-300">
        <p className="font-mono text-xs text-slate-400">Container evidence</p>
        <p className="mt-1 font-mono text-slate-100">{selectedContainer.containerId}</p>
        <p className="mt-1">
          Decision: {selectedContainer.decisionAction ?? "—"}
          {selectedContainer.decisionStatus
            ? ` · ${selectedContainer.decisionStatus}`
            : ""}
        </p>
      </div>

      {!carrierCase && (
        <div className="space-y-3">
          <p className="text-sm text-slate-400">
            No carrier recovery case prepared for this connection.
          </p>
          {!agentRunActive && <button
            type="button"
            disabled={loading}
            className={actionButtonClass()}
            onClick={() => onPrepare(selectedContainer.connectionId)}
          >
            Prepare carrier recovery
          </button>}
          {agentRunActive && <p className="text-xs text-amber-200">AgentRun is active. The agent prepares carrier recovery on the next explicit advance.</p>}
        </div>
      )}

      {carrierCase && (
        <div className="space-y-3">
          <RecoveryStatusBadge
            label={carrierCase.state.replaceAll("_", " ")}
            tone={
              carrierCase.state === "AWAITING_COUNTER_APPROVAL"
                ? "warning"
                : carrierCase.state === "COMPLETED"
                  ? "success"
                  : "info"
            }
          />

          {carrierCase.state === "AWAITING_REQUEST_APPROVAL" && history && (
            <div className="space-y-2">
              <p className="text-sm text-slate-300">RTA proposal awaiting operator approval.</p>
              {history.request_context && (
                <p className="font-mono text-xs text-slate-400">
                  Deadline {formatUtcClock(history.request_context.response_deadline)}
                </p>
              )}
              {history.approvals.some((approval) => approval.status === "APPROVED") && !agentRunActive ? (
                <button type="button" disabled={loading} className={actionButtonClass()} onClick={onSend}>
                  Send authorised request
                </button>
              ) : !history.approvals.some((approval) => approval.status === "APPROVED") ? (
                <div className="flex flex-wrap gap-2">
                  <button type="button" disabled={loading} className={actionButtonClass()} onClick={onApproveRequest}>
                    Approve request
                  </button>
                  <button type="button" disabled={loading} className={actionButtonClass("danger")} onClick={onRejectRequest}>
                    Reject request
                  </button>
                </div>
              ) : <p className="text-xs text-amber-200">Approval persisted. Advance the agent explicitly to send the authorised request.</p>}
            </div>
          )}

          {carrierCase.state === "AWAITING_CARRIER" && (
            <div className="space-y-2">
              <p className="text-sm text-amber-100">Waiting for carrier response.</p>
              {history?.request_context?.sent_at && (
                <p className="font-mono text-xs text-slate-400">
                  Sent {formatUtcClock(history.request_context.sent_at)}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={loading} className={actionButtonClass()} onClick={onSimulate}>
                  Simulate carrier response
                </button>
                <button type="button" disabled={loading} className={actionButtonClass("neutral")} onClick={onEvaluateTimeout}>
                  Evaluate timeout
                </button>
              </div>
              {history && !hasCarrierResponseEvidence(history) && (
                <p className="text-xs text-slate-500">
                  SILENT outcomes leave no carrier response record; use explicit timeout
                  evaluation after the deadline.
                </p>
              )}
            </div>
          )}

          {carrierCase.state === "AWAITING_COUNTER_APPROVAL" && history && (
            <div className="space-y-2">
              <p className="text-sm text-amber-100">
                Carrier counter received — waiting for operator approval.
              </p>
              {history.carrier_responses[0] && (
                <p className="font-mono text-xs text-slate-300">
                  Counter ETA{" "}
                  {history.carrier_responses[0].counter_eta_pta
                    ? formatUtcClock(history.carrier_responses[0].counter_eta_pta)
                    : "—"}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={loading} className={actionButtonClass()} onClick={onApproveCounter}>
                  Approve counter
                </button>
                <button type="button" disabled={loading} className={actionButtonClass("danger")} onClick={onRejectCounter}>
                  Reject counter
                </button>
              </div>
            </div>
          )}

          {carrierCase.state === "COMPLETED" && history && (
            <div className="space-y-3">
              <p className="text-sm text-emerald-100">Carrier recovery completed.</p>
              {history.results.map((result) => (
                <div key={result.id} className="rounded border border-slate-800 px-3 py-2 text-xs text-slate-300">
                  <p className="font-mono text-slate-100">{result.container_id}</p>
                  <p>{result.disposition.replaceAll("_", " ")}</p>
                  <p className="text-slate-500">{result.reconsideration_evidence_kind}</p>
                </div>
              ))}
              {history.results[0]?.replacement_decision_id && (
                <DecisionLineage
                  decisionId={history.results[0].replacement_decision_id}
                  decisions={decisions}
                />
              )}
            </div>
          )}

          {carrierCase.state === "ESCALATED" && (
            <p className="text-sm text-rose-100">
              Case escalated after carrier recovery reconsideration.
            </p>
          )}
        </div>
      )}
    </aside>
  );
}
