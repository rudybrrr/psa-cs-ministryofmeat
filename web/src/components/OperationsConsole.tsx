import { useEffect, useRef, useState } from "react";

import { SyntheticBanner } from "./SyntheticBanner";
import { useRecoveryConsole } from "../hooks/useRecoveryConsole";
import {
  CANONICAL_COUNTER_EFFECTIVE_AT,
  CANONICAL_SAFETY_CONTAINER_ID,
  SYNTHETIC_DEMO_OPERATOR_ID,
  fetchCanonicalReplayStage,
  initialCanonicalStageView,
} from "../api/canonicalReplay";
import type { CanonicalReplayActionType } from "../api/types";
import { useAutoReplay } from "../hooks/useAutoReplay";
import type { AutoReplayCallbacks } from "../lib/autoReplayController";
import { canAdvanceAgent, canonicalApprovalFingerprint } from "../lib/recoverySelectors";
import { describeConsoleError } from "../lib/consoleErrors";
import {
  RECOVERY_CHAPTERS,
  chapterForStage,
  chapterIndex,
} from "../lib/recoveryChapters";
import { type ConsoleMode } from "./command-center/ModeSwitcher";
import { RecoveryKpiStrip } from "./command-center/RecoveryKpiStrip";
import { ChapterProgress } from "./command-center/ChapterProgress";
import { GuidedIntroSurface } from "./command-center/GuidedIntroSurface";
import { ResumePrompt } from "./command-center/ResumePrompt";
import { ChapterContextualRegion } from "./command-center/ChapterContextualRegion";
import { DashboardShell } from "./command-center/DashboardShell";
import {
  DashboardSidebar,
  type DashboardNavId,
} from "./command-center/DashboardSidebar";
import { DashboardContentHeader } from "./command-center/DashboardContentHeader";
import { StageActionCard } from "./command-center/StageActionCard";
import { AutoReplayPanel } from "./command-center/AutoReplayPanel";
import { ExploreAvailability } from "./command-center/ExploreAvailability";
import { ExploreWorkspaceEmpty } from "./command-center/ExploreWorkspaceEmpty";
import { LoadingIndicator } from "./command-center/LoadingIndicator";
import { EvidenceWorkspace } from "./command-center/workspaces/EvidenceWorkspace";
import { RecoveryWorkspace } from "./command-center/workspaces/RecoveryWorkspace";
import { ContainersWorkspace } from "./command-center/workspaces/ContainersWorkspace";
import { CarrierWorkspace } from "./command-center/workspaces/CarrierWorkspace";

export function OperationsConsole() {
  const console = useRecoveryConsole();
  const [mode, setMode] = useState<ConsoleMode>("guided");
  const [workspace, setWorkspace] = useState<DashboardNavId>("overview");
  const [reviewChapterIndex, setReviewChapterIndex] = useState<number | null>(null);
  const run = console.agentRuns.at(-1) ?? null;
  const agentEvidenceCanAdvance = canAdvanceAgent(run, {
    carrierHistory: console.agentWaitHistory,
    reconsiderations: console.reconsiderations,
    tradeoffReviews: console.tradeoffReviews,
  });
  const canonicalAdvanceAllowed =
    console.canonicalStage?.next_allowed_action === "ADVANCE_AGENT" &&
    console.canonicalStage.guided_can_execute;
  const canAdvance =
    mode === "guided" ? agentEvidenceCanAdvance && canonicalAdvanceAllowed : agentEvidenceCanAdvance;

  const consoleRef = useRef(console);
  consoleRef.current = console;

  const autoCallbacks: AutoReplayCallbacks = {
    fetchStage: async () => {
      const current = consoleRef.current;
      const live = current.readLatestState();
      if (!live.incident) {
        return initialCanonicalStageView();
      }
      return fetchCanonicalReplayStage(live.incident.id);
    },
    execute: async (action: CanonicalReplayActionType) => {
      const current = consoleRef.current;
      switch (action) {
        case "CREATE_CANONICAL_INCIDENT":
          return current.createCanonicalIncident();
        case "BOOTSTRAP_PRE_DISCHARGE":
          return current.bootstrapYard();
        case "START_DEMO_AGENT_RUN":
          return current.startDemoAgentRun();
        case "ADVANCE_AGENT":
          return current.advanceAgent();
        case "PUBLISH_DISCHARGE_ACTIVE":
          return current.publishActive();
        case "SIMULATE_CARRIER_RESPONSE":
          return current.simulateCarrierResponse(CANONICAL_COUNTER_EFFECTIVE_AT);
        case "APPROVE_REQUEST":
          return current.approveRequest(SYNTHETIC_DEMO_OPERATOR_ID);
        case "APPROVE_COUNTER":
          return current.approveCounter(SYNTHETIC_DEMO_OPERATOR_ID);
        case "PERSIST_SAFETY_REVIEW":
          return current.createSafetyReview(CANONICAL_SAFETY_CONTAINER_ID);
        default:
          return { ok: false, conflict: false };
      }
    },
  };
  const autoReplay = useAutoReplay(autoCallbacks);

  const fingerprint = canonicalApprovalFingerprint(
    console.canonicalStage,
    console.agentWaitHistory,
  );

  const executeGuidedAction = (action: CanonicalReplayActionType) => {
    switch (action) {
      case "CREATE_CANONICAL_INCIDENT":
        void console.createCanonicalIncident();
        break;
      case "BOOTSTRAP_PRE_DISCHARGE":
        void console.bootstrapYard();
        break;
      case "START_DEMO_AGENT_RUN":
        void console.startDemoAgentRun();
        break;
      case "ADVANCE_AGENT":
        void console.advanceAgent();
        break;
      case "PUBLISH_DISCHARGE_ACTIVE":
        void console.publishActive();
        break;
      case "SIMULATE_CARRIER_RESPONSE":
        void console.simulateCarrierResponse(CANONICAL_COUNTER_EFFECTIVE_AT);
        break;
      case "APPROVE_REQUEST":
        void console.approveRequest();
        break;
      case "APPROVE_COUNTER":
        void console.approveCounter();
        break;
      case "PERSIST_SAFETY_REVIEW":
        void console.createSafetyReview(CANONICAL_SAFETY_CONTAINER_ID);
        break;
      case "SELECT_TRADEOFF_OPTION":
        break;
      default:
        break;
    }
  };

  const showResume =
    !console.incident &&
    !console.loading &&
    Boolean(console.storedIncidentId) &&
    !console.resumeDismissed;

  const isGuidedEmpty =
    mode === "guided" &&
    !console.incident &&
    !console.loading &&
    !showResume;

  const showGuidedOverview =
    mode === "guided" &&
    workspace === "overview" &&
    (console.incident || isGuidedEmpty || showResume);

  const showExploreAvailability =
    mode === "explore" && !console.incident && !console.loading && !showResume;

  const handleModeChange = (nextMode: ConsoleMode) => {
    if (nextMode === "explore" && !console.incident && !console.storedIncidentId) {
      setMode("guided");
      setWorkspace("overview");
      return;
    }
    setMode(nextMode);
    if (nextMode === "explore" && console.incident) {
      setWorkspace("evidence");
    }
    if (nextMode === "guided") {
      setWorkspace("overview");
    }
  };

  const apiStatus = console.error ? "error" : console.loading ? "loading" : "ready";
  const incidentLoaded = Boolean(console.incident);
  const activeChapterIndex = incidentLoaded
    ? chapterIndex(chapterForStage(console.canonicalStage.stage))
    : 0;
  const focusChapterId =
    reviewChapterIndex != null ? RECOVERY_CHAPTERS[reviewChapterIndex]?.id : null;
  const errorPresentation = console.error ? describeConsoleError(console.error) : null;

  useEffect(() => {
    setReviewChapterIndex(null);
  }, [console.canonicalStage?.stage]);

  const handleReviewPrevious = () => {
    if (reviewChapterIndex !== null) {
      setReviewChapterIndex(null);
      return;
    }
    setReviewChapterIndex(Math.max(0, activeChapterIndex - 1));
  };

  const workspaceContent = incidentLoaded ? (
    <>
      {workspace === "recovery" ? (
        <RecoveryWorkspace
          summary={console.recoverySummary}
          yardForecasts={console.yardForecasts}
          allocationRevisions={console.allocationRevisions}
          expediteCommitments={console.expediteCommitments}
          tradeoffReviews={console.tradeoffReviews}
          tradeoffOptions={console.tradeoffOptions}
          run={run}
          agentHistory={console.selectedAgentHistory}
          canAdvance={canAdvance}
          loading={console.loading}
          onBootstrap={() => void console.bootstrapYard()}
          onPublishActive={() => void console.publishActive()}
          onAdvanceAgent={() => void console.advanceAgent()}
          onRefresh={() => void console.refresh()}
          onChooseTradeoff={(review, optionId) =>
            void console.chooseTradeoff(review, optionId)
          }
        />
      ) : null}

      {workspace === "containers" ? (
        <ContainersWorkspace
          rows={console.containerRows}
          selectedContainerId={console.selectedContainerId}
          selectedContainer={console.selectedContainer}
          loading={console.loading}
          onSelectContainer={(id) => void console.selectContainer(id)}
        />
      ) : null}

      {workspace === "carrier" ? (
        <CarrierWorkspace
          selectedContainer={console.selectedContainer}
          carrierCase={console.selectedCarrierCase ?? null}
          caseHistory={console.selectedCaseHistory}
          decisions={console.decisions}
          loading={console.loading}
          agentRunActive={Boolean(
            run && !["COMPLETED", "ESCALATED", "FAILED"].includes(run.state),
          )}
          onPrepare={(connectionId) => void console.prepareCarrierRecovery(connectionId)}
          onApproveRequest={() => void console.approveRequest()}
          onRejectRequest={() => void console.rejectRequest()}
          onSend={() => void console.sendRequest()}
          onSimulate={() => void console.simulateCarrierResponse()}
          onApproveCounter={() => void console.approveCounter()}
          onRejectCounter={() => void console.rejectCounter()}
          onEvaluateTimeout={() => void console.evaluateTimeout()}
        />
      ) : null}

      {workspace === "evidence" ? (
        <EvidenceWorkspace
          run={run}
          agentHistory={console.selectedAgentHistory}
          canAdvance={canAdvance}
          loading={console.loading}
          auditEvents={console.auditEvents}
          approvalFingerprint={fingerprint}
          cargoReviews={console.cargoSafetyReviews}
          safetyHistories={console.safetyHistories}
          onAdvanceAgent={() => void console.advanceAgent()}
          onRefresh={() => void console.refresh()}
          onStartAgent={() => void console.startAgent()}
          onEvaluateSafety={(id) => void console.evaluateSafety(id)}
          onCreateSafetyReview={() => void console.createSafetyReview("SYN-CNT-010")}
        />
      ) : null}
    </>
  ) : null;

  return (
    <>
      <SyntheticBanner />
      <DashboardShell
        sidebar={
          <DashboardSidebar
            workspace={workspace}
            onWorkspaceChange={setWorkspace}
            mode={mode}
            onModeChange={handleModeChange}
            apiStatus={apiStatus}
          />
        }
        header={
          <DashboardContentHeader
            mode={mode}
            workspace={workspace}
            incident={console.incident}
            fixture={console.fixture}
            loading={console.loading}
            showStartDemo={false}
            onStartDemo={() => executeGuidedAction("CREATE_CANONICAL_INCIDENT")}
            onStartFresh={() => void console.startFreshDemo()}
          />
        }
      >
        {showResume ? (
          <ResumePrompt
            incidentId={console.storedIncidentId!}
            loading={console.loading}
            onResume={() => void console.resumeStoredIncident()}
            onStartFresh={() => void console.startFreshDemo()}
            onDismiss={console.dismissStoredIncident}
          />
        ) : null}

        {console.loading ? (
          <LoadingIndicator label="Contacting backend and loading persisted incident state…" />
        ) : null}

        {errorPresentation ? (
          <div
            role="alert"
            className="rounded-[10px] border border-psa-coral/50 bg-psa-coral/10 px-4 py-4 text-sm text-psa-snow"
          >
            <p className="font-semibold">{errorPresentation.title}</p>
            <p className="mt-2 text-sm text-psa-chalk">{errorPresentation.detail}</p>
            <button
              type="button"
              disabled={console.loading}
              onClick={() => void console.refresh()}
              className="psa-btn-secondary mt-4 px-4 py-2 text-xs"
            >
              Try again
            </button>
          </div>
        ) : null}

        {showExploreAvailability ? (
          <ExploreAvailability
            loading={console.loading}
            storedIncidentId={console.storedIncidentId}
            onStartGuided={() => {
              setMode("guided");
              executeGuidedAction("CREATE_CANONICAL_INCIDENT");
            }}
            onResume={() => void console.resumeStoredIncident()}
          />
        ) : null}

        {mode === "auto" && workspace === "overview" ? (
          <>
            <ChapterProgress
              stage={console.canonicalStage?.stage}
              empty={!incidentLoaded}
            />
            <AutoReplayPanel
              stage={console.canonicalStage}
              progress={autoReplay.progress}
              canStart={!console.loading && console.canonicalStage.auto_replay_may_execute}
              loading={console.loading}
              onStart={autoReplay.start}
              onStop={autoReplay.stop}
            />
            {incidentLoaded ? (
              <ChapterContextualRegion
                mode={mode}
                stage={console.canonicalStage}
                incident={console.incident}
                fixture={console.fixture}
                summary={console.recoverySummary}
                scarcityEvaluation={console.scarcityEvaluation}
                containerRows={console.containerRows}
                selectedContainerId={console.selectedContainerId}
                onSelectContainer={(id) => void console.selectContainer(id)}
                selectedContainer={console.selectedContainer}
                yardForecasts={console.yardForecasts}
                allocationRevisions={console.allocationRevisions}
                expediteCommitments={console.expediteCommitments}
                run={run}
                agentHistory={console.selectedAgentHistory}
                canAdvance={canAdvance}
                loading={console.loading}
                carrierCase={console.selectedCarrierCase ?? null}
                caseHistory={console.selectedCaseHistory}
                decisions={console.decisions}
                approvalFingerprint={fingerprint}
                agentRunActive={Boolean(
                  run && !["COMPLETED", "ESCALATED", "FAILED"].includes(run.state),
                )}
                cargoReviews={console.cargoSafetyReviews}
                safetyHistories={console.safetyHistories}
                onBootstrap={() => void console.bootstrapYard()}
                onPublishActive={() => void console.publishActive()}
                onAdvanceAgent={() => void console.advanceAgent()}
                onRefresh={() => void console.refresh()}
                onApproveRequest={() => void console.approveRequest()}
                onRejectRequest={() => void console.rejectRequest()}
                onSimulate={() => void console.simulateCarrierResponse()}
                onApproveCounter={() => void console.approveCounter()}
                onRejectCounter={() => void console.rejectCounter()}
                onEvaluateTimeout={() => void console.evaluateTimeout()}
                onCreateSafetyReview={() => void console.createSafetyReview("SYN-CNT-010")}
              />
            ) : null}
          </>
        ) : null}

        {showGuidedOverview ? (
          <div className="space-y-5">
            <ChapterProgress
              stage={console.canonicalStage?.stage}
              empty={isGuidedEmpty}
              highlightIndex={reviewChapterIndex ?? undefined}
            />

            <StageActionCard
              stage={console.canonicalStage}
              incident={console.incident}
              loading={console.loading}
              approvalFingerprint={fingerprint}
              agentRun={run}
              onExecute={executeGuidedAction}
              onReviewPrevious={incidentLoaded ? handleReviewPrevious : undefined}
              reviewingPrior={reviewChapterIndex !== null}
              emptyState={
                isGuidedEmpty ? (
                  <GuidedIntroSurface
                    loading={console.loading}
                    summary={console.recoverySummary}
                    fixture={console.fixture}
                    onStart={() => executeGuidedAction("CREATE_CANONICAL_INCIDENT")}
                  />
                ) : undefined
              }
            />

            {incidentLoaded ? (
              <RecoveryKpiStrip summary={console.recoverySummary} compact />
            ) : (
              <RecoveryKpiStrip summary={null} emptyPlaceholder={isGuidedEmpty} compact />
            )}

            {incidentLoaded ? (
              <ChapterContextualRegion
                mode={mode}
                stage={console.canonicalStage}
                focusChapterOverride={focusChapterId}
                incident={console.incident}
                fixture={console.fixture}
                summary={console.recoverySummary}
                scarcityEvaluation={console.scarcityEvaluation}
                containerRows={console.containerRows}
                selectedContainerId={console.selectedContainerId}
                onSelectContainer={(id) => void console.selectContainer(id)}
                selectedContainer={console.selectedContainer}
                yardForecasts={console.yardForecasts}
                allocationRevisions={console.allocationRevisions}
                expediteCommitments={console.expediteCommitments}
                run={run}
                agentHistory={console.selectedAgentHistory}
                canAdvance={canAdvance}
                loading={console.loading}
                carrierCase={console.selectedCarrierCase ?? null}
                caseHistory={console.selectedCaseHistory}
                decisions={console.decisions}
                approvalFingerprint={fingerprint}
                agentRunActive={Boolean(
                  run && !["COMPLETED", "ESCALATED", "FAILED"].includes(run.state),
                )}
                cargoReviews={console.cargoSafetyReviews}
                safetyHistories={console.safetyHistories}
                onBootstrap={() => void console.bootstrapYard()}
                onPublishActive={() => void console.publishActive()}
                onAdvanceAgent={() => void console.advanceAgent()}
                onRefresh={() => void console.refresh()}
                onApproveRequest={() => void console.approveRequest()}
                onRejectRequest={() => void console.rejectRequest()}
                onSimulate={() => void console.simulateCarrierResponse()}
                onApproveCounter={() => void console.approveCounter()}
                onRejectCounter={() => void console.rejectCounter()}
                onEvaluateTimeout={() => void console.evaluateTimeout()}
                onCreateSafetyReview={() => void console.createSafetyReview("SYN-CNT-010")}
              />
            ) : null}
          </div>
        ) : null}

        {workspace !== "overview" ? workspaceContent : null}

        {mode === "explore" && !incidentLoaded && workspace !== "overview" ? (
          <ExploreWorkspaceEmpty
            tab={workspace}
            loading={console.loading}
            onStartGuided={() => {
              setMode("guided");
              setWorkspace("overview");
              executeGuidedAction("CREATE_CANONICAL_INCIDENT");
            }}
          />
        ) : null}

        {mode === "explore" && incidentLoaded && workspace === "overview" ? (
          <>
            <RecoveryKpiStrip summary={console.recoverySummary} />
            <ChapterProgress stage={console.canonicalStage?.stage} />
            <p className="psa-surface rounded-[10px] px-4 py-3 text-sm text-psa-chalk">
              Use the workspace navigation to inspect recovery planning, containers, carrier
              coordination, and evidence surfaces.
            </p>
          </>
        ) : null}

        {mode === "auto" && !incidentLoaded && workspace === "overview" ? (
          <p className="text-sm text-psa-steel">
            Auto replay will create the canonical incident on start, or resume an existing session.
          </p>
        ) : null}
      </DashboardShell>
    </>
  );
}
