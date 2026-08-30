import { AgentRunPanel } from "../agent/AgentRunPanel";
import { AuditTimeline } from "../AuditTimeline";
import { ActorLegend } from "../ActorBadge";
import { CarrierRecoveryPanel } from "../carrier/CarrierRecoveryPanel";
import { SyntheticDemoControl } from "../demo/SyntheticDemoControl";
import { DynamicYardPanel } from "../dynamic/DynamicYardPanel";
import { TradeoffReviewPanel } from "../dynamic/TradeoffReviewPanel";
import { ContainerRecoveryTable } from "../recovery/ContainerRecoveryTable";
import { CargoSafetyPanel } from "../safety/CargoSafetyPanel";
import type { ConsoleMode } from "./ModeSwitcher";
import type { AutoReplayProgress } from "../../lib/autoReplayController";
import type {
  AgentHistory,
  AgentRun,
  AllocationRevision,
  AllocationTradeoffOption,
  AllocationTradeoffReview,
  AuditEvent,
  CanonicalReplayStageView,
  CarrierRecoveryCase,
  CarrierRecoveryHistory,
  CargoSafetyHistory,
  CargoSafetyReview,
  Decision,
  ExpediteCommitment,
  YardForecastSnapshot,
} from "../../api/types";
import type { ContainerRecoveryRow, RecoverySummary } from "../../lib/recoverySelectors";

export interface ExploreWorkspaceProps {
  mode: ConsoleMode;
  incidentLoaded: boolean;
  loading: boolean;
  error: { status: number; detail: string } | null;
  containerRows: ContainerRecoveryRow[];
  selectedContainerId: string | null;
  onSelectContainer(containerId: string): void;
  run: AgentRun | null;
  agentHistory: AgentHistory | null;
  canAdvance: boolean;
  onStartAgent(): void;
  onAdvanceAgent(): void;
  onRefresh(): void;
  yardForecasts: YardForecastSnapshot[];
  allocationRevisions: AllocationRevision[];
  expediteCommitments: ExpediteCommitment[];
  onBootstrap(): void;
  onPublishActive(): void;
  selectedContainer: ContainerRecoveryRow | null;
  carrierCase: CarrierRecoveryCase | null;
  caseHistory: CarrierRecoveryHistory | null;
  decisions: Decision[];
  onPrepare(connectionId: string): void;
  onApproveRequest(): void;
  onRejectRequest(): void;
  onSend(): void;
  onSimulate(): void;
  onApproveCounter(): void;
  onRejectCounter(): void;
  onEvaluateTimeout(): void;
  agentRunActive: boolean;
  tradeoffReviews: AllocationTradeoffReview[];
  tradeoffOptions: AllocationTradeoffOption[];
  onChooseTradeoff(review: AllocationTradeoffReview, optionId: string): void;
  cargoReviews: CargoSafetyReview[];
  safetyHistories: CargoSafetyHistory[];
  onEvaluateSafety(id: string): void;
  onCreateSafetyReview(): void;
  auditEvents: AuditEvent[];
  incidentId: string | null;
  stage: CanonicalReplayStageView;
  approvalFingerprint: string | null;
  onCreateIncident(): void;
  onStartDemoAgentRun(): void;
  onSimulateCarrierResponse(): void;
  autoReplay?: {
    progress: AutoReplayProgress;
    canStart: boolean;
    onStart(): void;
    onStop(): void;
  };
  recoverySummary: RecoverySummary | null;
}

export function ExploreWorkspace(props: ExploreWorkspaceProps) {
  const showHarness = props.mode === "auto";
  const showTechnical = props.mode === "explore";

  if (!props.incidentLoaded && props.mode === "explore") {
    return (
      <div className="psa-surface rounded-[10px] px-6 py-10 text-center text-sm text-psa-fog">
        No active recovery session. Switch to Guided demo and start the recovery
        scenario, or resume a saved incident.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {showTechnical ? (
        <>
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
            <AgentRunPanel
              run={props.run}
              history={props.agentHistory}
              loading={props.loading}
              canAdvance={props.canAdvance}
              onStart={props.onStartAgent}
              onAdvance={props.onAdvanceAgent}
              onRefresh={props.onRefresh}
            />
            <DynamicYardPanel
              snapshots={props.yardForecasts}
              revisions={props.allocationRevisions}
              commitments={props.expediteCommitments}
              loading={props.loading}
              onBootstrap={props.onBootstrap}
              onActive={props.onPublishActive}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
            <ContainerRecoveryTable
              rows={props.containerRows}
              selectedContainerId={props.selectedContainerId}
              onSelect={props.onSelectContainer}
              loading={props.loading}
            />
            <CarrierRecoveryPanel
              selectedContainer={props.selectedContainer}
              carrierCase={props.carrierCase}
              history={props.caseHistory}
              decisions={props.caseHistory?.decisions ?? props.decisions}
              loading={props.loading}
              onPrepare={props.onPrepare}
              onApproveRequest={props.onApproveRequest}
              onRejectRequest={props.onRejectRequest}
              onSend={props.onSend}
              onSimulate={props.onSimulate}
              onApproveCounter={props.onApproveCounter}
              onRejectCounter={props.onRejectCounter}
              onEvaluateTimeout={props.onEvaluateTimeout}
              agentRunActive={props.agentRunActive}
            />
          </div>

          <TradeoffReviewPanel
            reviews={props.tradeoffReviews}
            options={props.tradeoffOptions}
            loading={props.loading}
            onSelect={props.onChooseTradeoff}
          />
          <CargoSafetyPanel
            reviews={props.cargoReviews}
            histories={props.safetyHistories}
            loading={props.loading}
            onEvaluate={props.onEvaluateSafety}
            onCreateCanonical={props.onCreateSafetyReview}
          />
        </>
      ) : null}

      {props.incidentLoaded && props.mode === "explore" ? (
        <section className="psa-surface space-y-4 rounded-[10px] px-4 py-4">
          <div>
            <h2 className="text-sm font-semibold text-psa-snow">Audit / decision history</h2>
            <p className="mt-1 text-xs text-psa-steel">
              Persisted audit trail for the active incident.
            </p>
          </div>
          <ActorLegend />
          <AuditTimeline events={props.auditEvents} loading={props.loading} />
        </section>
      ) : null}

      {showHarness ? (
        <SyntheticDemoControl
          incidentId={props.incidentId}
          loading={props.loading}
          stage={props.stage}
          error={props.error}
          approvalFingerprint={props.approvalFingerprint}
          mode={props.mode}
          hideModeTabs
          compact={props.mode === "guided" || props.mode === "auto"}
          onCreateIncident={props.onCreateIncident}
          onRefresh={props.onRefresh}
          onBootstrap={props.onBootstrap}
          onStartDemoAgentRun={props.onStartDemoAgentRun}
          onAdvanceAgent={props.onAdvanceAgent}
          onPublishActive={props.onPublishActive}
          onSimulateCarrierResponse={props.onSimulateCarrierResponse}
          onApproveRequest={props.onApproveRequest}
          onRejectRequest={props.onRejectRequest}
          onApproveCounter={props.onApproveCounter}
          onRejectCounter={props.onRejectCounter}
          onCreateSafetyReview={props.onCreateSafetyReview}
          autoReplay={props.autoReplay}
        />
      ) : null}
    </div>
  );
}
