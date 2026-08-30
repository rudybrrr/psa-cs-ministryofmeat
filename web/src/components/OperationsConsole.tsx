import { useRef, useState } from "react";

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
import { type ConsoleMode } from "./command-center/ModeSwitcher";
import { RecoveryKpiStrip } from "./command-center/RecoveryKpiStrip";
import { ChapterProgress } from "./command-center/ChapterProgress";
import { GuidedIntroSurface } from "./command-center/GuidedIntroSurface";
import { ResumePrompt } from "./command-center/ResumePrompt";
import { ExploreWorkspace } from "./command-center/ExploreWorkspace";
import { ChapterContextualRegion } from "./command-center/ChapterContextualRegion";
import { DashboardShell } from "./command-center/DashboardShell";
import { DashboardSidebar } from "./command-center/DashboardSidebar";
import { DashboardContentHeader } from "./command-center/DashboardContentHeader";
import { StageActionCard } from "./command-center/StageActionCard";

export function OperationsConsole() {
  const console = useRecoveryConsole();
  const [mode, setMode] = useState<ConsoleMode>("guided");
  const run = console.agentRuns.at(-1) ?? null;
  const canAdvance = canAdvanceAgent(run, {
    carrierHistory: console.agentWaitHistory,
    reconsiderations: console.reconsiderations,
    tradeoffReviews: console.tradeoffReviews,
  });

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
    console.storedIncidentId &&
    !console.resumeDismissed;

  const isGuidedEmpty =
    mode === "guided" &&
    !console.incident &&
    !console.loading &&
    !showResume;

  const showGuidedShell =
    mode === "guided" && (console.incident || isGuidedEmpty || showResume);

  const apiStatus = console.error ? "error" : console.loading ? "loading" : "ready";

  return (
    <>
      <SyntheticBanner />
      <DashboardShell
        sidebar={
          <DashboardSidebar
            mode={mode}
            onModeChange={setMode}
            apiStatus={apiStatus}
            incidentLoaded={Boolean(console.incident)}
          />
        }
        header={
          <DashboardContentHeader
            mode={mode}
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

        {showGuidedShell ? (
          <>
            <RecoveryKpiStrip
              summary={console.recoverySummary}
              emptyPlaceholder={isGuidedEmpty}
            />

            <ChapterProgress
              stage={console.canonicalStage?.stage}
              empty={isGuidedEmpty}
            />

            {mode === "guided" ? (
              <StageActionCard
                stage={console.canonicalStage}
                incident={console.incident}
                fixture={console.fixture}
                loading={console.loading}
                approvalFingerprint={fingerprint}
                onExecute={executeGuidedAction}
                emptyState={
                  isGuidedEmpty ? (
                    <GuidedIntroSurface
                      loading={console.loading}
                      onStart={() => executeGuidedAction("CREATE_CANONICAL_INCIDENT")}
                    />
                  ) : undefined
                }
              />
            ) : null}
          </>
        ) : null}

        {console.loading ? (
          <div className="psa-surface rounded-[10px] px-4 py-3 text-sm text-psa-chalk">
            Contacting backend and loading persisted incident state…
          </div>
        ) : null}

        {console.error ? (
          <div
            role="alert"
            className="rounded-[10px] border border-psa-coral/50 bg-psa-coral/10 px-4 py-3 text-sm text-psa-snow"
          >
            <p className="font-semibold">Operations console error</p>
            <p className="mt-1 font-mono text-xs">
              {console.error.status}: {console.error.detail}
            </p>
          </div>
        ) : null}

        {console.incident && (mode === "guided" || mode === "auto") ? (
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

        <ExploreWorkspace
          mode={mode}
          incidentLoaded={Boolean(console.incident)}
          loading={console.loading}
          error={
            console.error
              ? { status: console.error.status, detail: console.error.detail }
              : null
          }
          containerRows={console.containerRows}
          selectedContainerId={console.selectedContainerId}
          onSelectContainer={(id) => void console.selectContainer(id)}
          run={run}
          agentHistory={console.selectedAgentHistory}
          canAdvance={canAdvance}
          onStartAgent={() => void console.startAgent()}
          onAdvanceAgent={() => void console.advanceAgent()}
          onRefresh={() => void console.refresh()}
          yardForecasts={console.yardForecasts}
          allocationRevisions={console.allocationRevisions}
          expediteCommitments={console.expediteCommitments}
          onBootstrap={() => void console.bootstrapYard()}
          onPublishActive={() => void console.publishActive()}
          selectedContainer={console.selectedContainer}
          carrierCase={console.selectedCarrierCase ?? null}
          caseHistory={console.selectedCaseHistory}
          decisions={console.decisions}
          onPrepare={(connectionId) => void console.prepareCarrierRecovery(connectionId)}
          onApproveRequest={() => void console.approveRequest()}
          onRejectRequest={() => void console.rejectRequest()}
          onSend={() => void console.sendRequest()}
          onSimulate={() => void console.simulateCarrierResponse()}
          onApproveCounter={() => void console.approveCounter()}
          onRejectCounter={() => void console.rejectCounter()}
          onEvaluateTimeout={() => void console.evaluateTimeout()}
          agentRunActive={Boolean(
            run && !["COMPLETED", "ESCALATED", "FAILED"].includes(run.state),
          )}
          tradeoffReviews={console.tradeoffReviews}
          tradeoffOptions={console.tradeoffOptions}
          onChooseTradeoff={(review, optionId) =>
            void console.chooseTradeoff(review, optionId)
          }
          cargoReviews={console.cargoSafetyReviews}
          safetyHistories={console.safetyHistories}
          onEvaluateSafety={(id) => void console.evaluateSafety(id)}
          onCreateSafetyReview={() => void console.createSafetyReview("SYN-CNT-010")}
          auditEvents={console.auditEvents}
          incidentId={console.incident?.id ?? null}
          stage={console.canonicalStage}
          approvalFingerprint={fingerprint}
          onCreateIncident={() => void console.createCanonicalIncident()}
          onStartDemoAgentRun={() => void console.startDemoAgentRun()}
          onSimulateCarrierResponse={() =>
            void console.simulateCarrierResponse(CANONICAL_COUNTER_EFFECTIVE_AT)
          }
          autoReplay={{
            progress: autoReplay.progress,
            canStart: !console.loading && console.canonicalStage.auto_replay_may_execute,
            onStart: autoReplay.start,
            onStop: autoReplay.stop,
          }}
          recoverySummary={console.recoverySummary}
        />

        {mode === "auto" && !console.incident ? (
          <p className="text-sm text-psa-steel">
            Auto replay backup mode · create an incident in Explore or start guided demo
          </p>
        ) : null}
      </DashboardShell>
    </>
  );
}
