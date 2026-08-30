import { useState } from "react";

import type { CarrierRecoveryCase, CarrierRecoveryHistory } from "../../../api/types";
import type { ContainerRecoveryRow } from "../../../lib/recoverySelectors";
import { connectionShortLabel, formatUtcClock, truncateId } from "../../../lib/formatters";
import { useAuthorityGatePulse } from "../../../hooks/useChapterMotion";
import { ChapterFrame, EvidencePanel } from "./ChapterFrame";

export function CoordinateChapter({
  selectedContainer,
  carrierCase,
  history,
  approvalFingerprint,
  loading,
  agentRunActive,
  onApproveRequest,
  onRejectRequest,
  evidenceOnly = false,
  quiet = false,
}: {
  selectedContainer: ContainerRecoveryRow | null;
  carrierCase: CarrierRecoveryCase | null;
  history: CarrierRecoveryHistory | null;
  approvalFingerprint: string | null;
  loading: boolean;
  agentRunActive: boolean;
  onApproveRequest(): void;
  onRejectRequest(): void;
  evidenceOnly?: boolean;
  quiet?: boolean;
}) {
  const [showFingerprint, setShowFingerprint] = useState(false);
  const connectionId =
    selectedContainer?.connectionId ?? history?.case.connection_id ?? "—";
  const containerId =
    selectedContainer?.containerId ??
    history?.case.affected_container_ids[0] ??
    "—";
  const approved = history?.approvals.some((item) => item.status === "APPROVED");
  const authorityRef = useAuthorityGatePulse(
    carrierCase?.state === "AWAITING_REQUEST_APPROVAL" && !approved,
  );

  return (
    <ChapterFrame
      label="Chapter 5 · Coordinate"
      title="Agent-prepared recovery — human authority required"
      quiet={quiet}
    >
        <div
          ref={authorityRef}
          className="border-l-2 border-psa-amber/60 pl-4"
        >
          <p className="psa-meta text-psa-amber">Human authority required</p>
        <p className="mt-2 text-sm text-psa-chalk">
          The agent may prepare the JV2 recovery request and bind evidence. The agent
          may <strong className="text-psa-snow">not</strong> authorize outbound carrier
          communication.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <EvidencePanel title="Agent-prepared recovery request" tone="coordinate">
          <p className="psa-mono text-sm font-medium">
            {connectionShortLabel(connectionId)}
          </p>
          <p className="text-xs text-psa-data-ink/70">{connectionId}</p>
          <p>
            Affected container: <span className="psa-mono">{containerId}</span>
          </p>
          {history?.request_context?.response_deadline ? (
            <p className="psa-mono text-xs text-psa-data-ink/70">
              Response deadline {formatUtcClock(history.request_context.response_deadline)}
            </p>
          ) : null}
          {carrierCase ? (
            <p className="text-xs text-psa-data-ink/70">
              Case {truncateId(carrierCase.id)} · {carrierCase.state.replaceAll("_", " ")}
            </p>
          ) : null}
        </EvidencePanel>

        <div className="space-y-3 lg:col-span-1">
          <p className="psa-meta text-psa-amber">Operator action</p>
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
              ) : !approved && !evidenceOnly ? (
                <div className="flex flex-col gap-2">
                  <button
                    type="button"
                    disabled={loading}
                    onClick={onApproveRequest}
                    className="psa-btn psa-btn-authority w-full text-xs"
                  >
                    Approve request
                  </button>
                  <button
                    type="button"
                    disabled={loading}
                    onClick={onRejectRequest}
                    className="psa-btn psa-btn-destructive w-full text-xs"
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
