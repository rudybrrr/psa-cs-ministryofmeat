import { useState } from "react";

import type { CarrierRecoveryCase, CarrierRecoveryHistory } from "../../../api/types";
import type { ContainerRecoveryRow } from "../../../lib/recoverySelectors";
import { connectionShortLabel, formatUtcClock, truncateId } from "../../../lib/formatters";
import { ChapterFrame } from "./ChapterFrame";

export function CoordinateChapter({
  selectedContainer,
  carrierCase,
  history,
  approvalFingerprint,
  loading,
  agentRunActive,
  onApproveRequest,
  onRejectRequest,
}: {
  selectedContainer: ContainerRecoveryRow | null;
  carrierCase: CarrierRecoveryCase | null;
  history: CarrierRecoveryHistory | null;
  approvalFingerprint: string | null;
  loading: boolean;
  agentRunActive: boolean;
  onApproveRequest(): void;
  onRejectRequest(): void;
}) {
  const [showFingerprint, setShowFingerprint] = useState(false);
  const connectionId =
    selectedContainer?.connectionId ?? history?.case.connection_id ?? "—";
  const containerId =
    selectedContainer?.containerId ??
    history?.case.affected_container_ids[0] ??
    "—";
  const approved = history?.approvals.some((item) => item.status === "APPROVED");

  return (
    <ChapterFrame
      label="Chapter 5 · Coordinate"
      title="Agent-prepared recovery — human authority required"
    >
      <div className="rounded-[8px] border border-psa-signal/30 bg-psa-signal/5 px-4 py-4">
        <p className="psa-label text-psa-signal">Human authority boundary</p>
        <p className="mt-2 text-sm text-psa-chalk">
          The agent may prepare the JV2 recovery request and bind evidence. The agent
          may <strong className="text-psa-snow">not</strong> authorize outbound carrier
          communication.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <div className="psa-surface-nested space-y-3 rounded-[8px] px-4 py-4">
          <p className="psa-label">Agent-prepared recovery request</p>
          <p className="font-mono text-sm text-psa-snow">
            {connectionShortLabel(connectionId)}
          </p>
          <p className="text-xs text-psa-steel">{connectionId}</p>
          <p className="text-sm text-psa-chalk">
            Affected container: <span className="font-mono">{containerId}</span>
          </p>
          {history?.request_context?.response_deadline ? (
            <p className="font-mono text-xs text-psa-fog">
              Response deadline {formatUtcClock(history.request_context.response_deadline)}
            </p>
          ) : null}
          {carrierCase ? (
            <p className="text-xs text-psa-steel">
              Case {truncateId(carrierCase.id)} · {carrierCase.state.replaceAll("_", " ")}
            </p>
          ) : null}
        </div>

        <div className="psa-surface-nested rounded-[8px] px-4 py-4">
          <p className="psa-label">Operator action</p>
          {carrierCase?.state === "AWAITING_REQUEST_APPROVAL" ? (
            <div className="mt-3 space-y-3">
              <p className="text-sm text-psa-chalk">
                RTA proposal awaiting operator approval.
              </p>
              {approved && agentRunActive ? (
                <p className="text-xs text-psa-amber">
                  Approval persisted. Advance the agent explicitly to send the authorised
                  request.
                </p>
              ) : !approved ? (
                <div className="flex flex-col gap-2">
                  <button
                    type="button"
                    disabled={loading}
                    onClick={onApproveRequest}
                    className="psa-btn-primary w-full px-3 py-2.5 text-xs"
                  >
                    Approve request
                  </button>
                  <button
                    type="button"
                    disabled={loading}
                    onClick={onRejectRequest}
                    className="psa-btn-secondary w-full px-3 py-2 text-xs"
                  >
                    Reject request
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="mt-3 text-sm text-psa-steel">
              Awaiting agent preparation of carrier recovery case.
            </p>
          )}
        </div>
      </div>

      {approvalFingerprint ? (
        <div className="text-xs">
          <button
            type="button"
            className="text-psa-signal underline-offset-2 hover:underline"
            onClick={() => setShowFingerprint((open) => !open)}
          >
            {showFingerprint ? "Hide" : "Show"} authorization fingerprint
          </button>
          {showFingerprint ? (
            <p className="mt-2 break-all font-mono text-psa-fog">{approvalFingerprint}</p>
          ) : null}
        </div>
      ) : null}
    </ChapterFrame>
  );
}
