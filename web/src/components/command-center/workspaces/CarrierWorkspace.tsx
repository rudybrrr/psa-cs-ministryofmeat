import { CarrierRecoveryPanel } from "../../carrier/CarrierRecoveryPanel";
import type {
  CarrierRecoveryCase,
  CarrierRecoveryHistory,
  Decision,
} from "../../../api/types";
import type { ContainerRecoveryRow } from "../../../lib/recoverySelectors";

export function CarrierWorkspace({
  selectedContainer,
  carrierCase,
  caseHistory,
  decisions,
  loading,
  agentRunActive,
  onPrepare,
  onApproveRequest,
  onRejectRequest,
  onSend,
  onSimulate,
  onApproveCounter,
  onRejectCounter,
  onEvaluateTimeout,
}: {
  selectedContainer: ContainerRecoveryRow | null;
  carrierCase: CarrierRecoveryCase | null;
  caseHistory: CarrierRecoveryHistory | null;
  decisions: Decision[];
  loading: boolean;
  agentRunActive: boolean;
  onPrepare(connectionId: string): void;
  onApproveRequest(): void;
  onRejectRequest(): void;
  onSend(): void;
  onSimulate(): void;
  onApproveCounter(): void;
  onRejectCounter(): void;
  onEvaluateTimeout(): void;
}) {
  return (
    <div className="space-y-4">
      <header className="psa-surface rounded-[12px] px-5 py-4">
        <p className="psa-label text-psa-signal">Carrier workspace</p>
        <h2 className="mt-1 text-lg font-medium text-psa-snow">Carrier coordination</h2>
        <p className="mt-2 text-sm text-psa-chalk">
          JV2 recovery requests, authorization boundaries, carrier responses, counter proposals,
          and final recovery disposition.
        </p>
        {carrierCase ? (
          <p className="mt-3 font-mono text-xs text-psa-steel">
            Case {carrierCase.id.slice(0, 8)}… · {carrierCase.state.replaceAll("_", " ")}
          </p>
        ) : (
          <p className="mt-3 text-xs text-psa-steel">
            Select a container with an outbound connection to inspect carrier recovery.
          </p>
        )}
      </header>

      <CarrierRecoveryPanel
        selectedContainer={selectedContainer}
        carrierCase={carrierCase}
        history={caseHistory}
        decisions={caseHistory?.decisions ?? decisions}
        loading={loading}
        onPrepare={onPrepare}
        onApproveRequest={onApproveRequest}
        onRejectRequest={onRejectRequest}
        onSend={onSend}
        onSimulate={onSimulate}
        onApproveCounter={onApproveCounter}
        onRejectCounter={onRejectCounter}
        onEvaluateTimeout={onEvaluateTimeout}
        agentRunActive={agentRunActive}
      />
    </div>
  );
}
