import type {
  AgentHistory,
  AgentRun,
  AllocationRevision,
  CanonicalIncidentFixture,
  CanonicalReplayStageView,
  CarrierRecoveryCase,
  CarrierRecoveryHistory,
  CargoSafetyHistory,
  CargoSafetyReview,
  Decision,
  ExpediteCommitment,
  Incident,
  ScarcityEvaluationReport,
  YardForecastSnapshot,
} from "../../api/types";
import type { RecoveryChapterId } from "../../lib/recoveryChapters";
import { chapterForStage } from "../../lib/recoveryChapters";
import type { ContainerRecoveryRow, RecoverySummary } from "../../lib/recoverySelectors";
import type { ConsoleMode } from "./ModeSwitcher";
import { AdaptChapter } from "./chapters/AdaptChapter";
import { CoordinateChapter } from "./chapters/CoordinateChapter";
import { GuidedAgentStrip } from "./chapters/GuidedAgentStrip";
import { GuidedContainerOverview } from "./chapters/GuidedContainerOverview";
import { IncidentChapter } from "./chapters/IncidentChapter";
import { ObserveChapter } from "./chapters/ObserveChapter";
import { OptimizeChapter } from "./chapters/OptimizeChapter";
import { ProtectChapter } from "./chapters/ProtectChapter";
import { RespondChapter } from "./chapters/RespondChapter";

export interface ChapterContextualRegionProps {
  mode: ConsoleMode;
  stage: CanonicalReplayStageView;
  incident: Incident | null;
  fixture: CanonicalIncidentFixture | null;
  summary: RecoverySummary | null;
  scarcityEvaluation: ScarcityEvaluationReport | null;
  containerRows: ContainerRecoveryRow[];
  selectedContainerId: string | null;
  onSelectContainer(containerId: string): void;
  selectedContainer: ContainerRecoveryRow | null;
  yardForecasts: YardForecastSnapshot[];
  allocationRevisions: AllocationRevision[];
  expediteCommitments: ExpediteCommitment[];
  run: AgentRun | null;
  agentHistory: AgentHistory | null;
  canAdvance: boolean;
  loading: boolean;
  carrierCase: CarrierRecoveryCase | null;
  caseHistory: CarrierRecoveryHistory | null;
  decisions: Decision[];
  approvalFingerprint: string | null;
  agentRunActive: boolean;
  cargoReviews: CargoSafetyReview[];
  safetyHistories: CargoSafetyHistory[];
  onBootstrap(): void;
  onPublishActive(): void;
  onAdvanceAgent(): void;
  onRefresh(): void;
  onApproveRequest(): void;
  onRejectRequest(): void;
  onSimulate(): void;
  onApproveCounter(): void;
  onRejectCounter(): void;
  onEvaluateTimeout(): void;
  onCreateSafetyReview(): void;
}

function resolveActiveChapter(
  stage: CanonicalReplayStageView,
  carrierCase: CarrierRecoveryCase | null,
): RecoveryChapterId {
  const fromStage = chapterForStage(stage.stage);

  if (
    fromStage === "PROTECT" ||
    stage.stage === "READY_FOR_SAFETY_EVIDENCE" ||
    stage.stage === "SAFETY_REVIEW_PENDING" ||
    stage.stage === "SAFETY_BLOCKED"
  ) {
    return "PROTECT";
  }

  if (carrierCase?.state === "AWAITING_REQUEST_APPROVAL") {
    return "COORDINATE";
  }
  if (
    carrierCase?.state === "AWAITING_CARRIER" ||
    carrierCase?.state === "AWAITING_COUNTER_APPROVAL" ||
    carrierCase?.state === "COMPLETED"
  ) {
    return "RESPOND";
  }

  return fromStage;
}

export function ChapterContextualRegion(props: ChapterContextualRegionProps) {
  if (props.mode === "explore") {
    return null;
  }

  const chapter = resolveActiveChapter(props.stage, props.carrierCase);
  const showAdaptEvidence =
    props.allocationRevisions.length >= 2;
  const showAgent =
    Boolean(props.run) &&
    !["INCIDENT", "OPTIMIZE"].includes(chapter) &&
    !["ESCALATED", "COMPLETED", "FAILED"].includes(props.run?.state ?? "");

  const yardActions =
    chapter === "OBSERVE" && !props.yardForecasts.some((s) => s.stage === "DISCHARGE_ACTIVE") ? (
      <button
        type="button"
        disabled={props.loading || !props.yardForecasts.some((s) => s.stage === "PRE_DISCHARGE")}
        onClick={props.onPublishActive}
        className="psa-btn-secondary px-3 py-2 text-xs disabled:opacity-50"
      >
        Publish discharge evidence
      </button>
    ) : null;

  return (
    <div className="space-y-4" data-guided-context>
      {chapter === "INCIDENT" ? (
        <IncidentChapter
          incident={props.incident}
          fixture={props.fixture}
          summary={props.summary}
        />
      ) : null}
      {chapter === "OPTIMIZE" ? (
        <OptimizeChapter
          summary={props.summary}
          scarcityEvaluation={props.scarcityEvaluation}
          loading={props.loading}
          onBootstrap={props.onBootstrap}
        />
      ) : null}
      {chapter === "OBSERVE" && !showAdaptEvidence ? (
        <ObserveChapter
          snapshots={props.yardForecasts}
          loading={props.loading}
          onPublishActive={props.onPublishActive}
        />
      ) : null}
      {showAdaptEvidence || chapter === "ADAPT" ? (
        <AdaptChapter
          snapshots={props.yardForecasts}
          revisions={props.allocationRevisions}
          commitments={props.expediteCommitments}
        />
      ) : null}
      {chapter === "COORDINATE" ? (
        <CoordinateChapter
          selectedContainer={props.selectedContainer}
          carrierCase={props.carrierCase}
          history={props.caseHistory}
          approvalFingerprint={props.approvalFingerprint}
          loading={props.loading}
          agentRunActive={props.agentRunActive}
          onApproveRequest={props.onApproveRequest}
          onRejectRequest={props.onRejectRequest}
        />
      ) : null}
      {chapter === "RESPOND" ? (
        <RespondChapter
          carrierCase={props.carrierCase}
          history={props.caseHistory}
          decisions={props.decisions}
          loading={props.loading}
          onSimulate={props.onSimulate}
          onApproveCounter={props.onApproveCounter}
          onRejectCounter={props.onRejectCounter}
          onEvaluateTimeout={props.onEvaluateTimeout}
        />
      ) : null}
      {chapter === "PROTECT" || props.cargoReviews.length > 0 ? (
        <ProtectChapter
          run={props.run}
          reviews={props.cargoReviews}
          histories={props.safetyHistories}
          loading={props.loading}
          onCreateCanonical={props.onCreateSafetyReview}
        />
      ) : null}

      {showAgent ? (
        <GuidedAgentStrip
          run={props.run}
          history={props.agentHistory}
          loading={props.loading}
          canAdvance={props.canAdvance}
          onAdvance={props.onAdvanceAgent}
          onRefresh={props.onRefresh}
          yardActions={yardActions}
        />
      ) : null}

      {props.containerRows.length > 0 ? (
        <GuidedContainerOverview
          rows={props.containerRows}
          selectedContainerId={props.selectedContainerId}
          onSelect={props.onSelectContainer}
        />
      ) : null}
    </div>
  );
}
