import { SyntheticBanner } from "./SyntheticBanner";
import { IncidentHeader } from "./IncidentHeader";
import { AuditTimeline } from "./AuditTimeline";
import { ActorLegend } from "./ActorBadge";
import { RecoverySummaryPanel } from "./incident/RecoverySummary";
import { ContainerRecoveryTable } from "./recovery/ContainerRecoveryTable";
import { CarrierRecoveryPanel } from "./carrier/CarrierRecoveryPanel";
import { SyntheticDemoControl } from "./demo/SyntheticDemoControl";
import { AgentRunPanel } from "./agent/AgentRunPanel";
import { DynamicYardPanel } from "./dynamic/DynamicYardPanel";
import { TradeoffReviewPanel } from "./dynamic/TradeoffReviewPanel";
import { CargoSafetyPanel } from "./safety/CargoSafetyPanel";
import { useRecoveryConsole } from "../hooks/useRecoveryConsole";
import { canAdvanceAgent, latestSnapshot } from "../lib/recoverySelectors";

export function OperationsConsole() {
  const console = useRecoveryConsole();
  const run = console.agentRuns.at(-1) ?? null;
  const activeSnapshot = latestSnapshot(console.yardForecasts, "DISCHARGE_ACTIVE");
  const canAdvance = canAdvanceAgent(run, { carrierHistory: console.agentWaitHistory, reconsiderations: console.reconsiderations, tradeoffReviews: console.tradeoffReviews });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <SyntheticBanner />
      <IncidentHeader incident={console.incident} loading={console.loading} />

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6">
        <RecoverySummaryPanel
          summary={console.recoverySummary}
          fixtureId={console.fixture?.fixture_id ?? null}
          loading={console.loading}
        />

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <AgentRunPanel run={run} history={console.selectedAgentHistory} loading={console.loading} canAdvance={canAdvance} onStart={() => void console.startAgent()} onAdvance={() => void console.advanceAgent()} onRefresh={() => void console.refresh()} />
          <DynamicYardPanel snapshots={console.yardForecasts} revisions={console.allocationRevisions} commitments={console.expediteCommitments} loading={console.loading} onBootstrap={() => void console.bootstrapYard()} onActive={() => void console.publishActive()} />
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <ContainerRecoveryTable
            rows={console.containerRows}
            selectedContainerId={console.selectedContainerId}
            onSelect={(containerId) => void console.selectContainer(containerId)}
            loading={console.loading}
          />
          <CarrierRecoveryPanel
            selectedContainer={console.selectedContainer}
            carrierCase={console.selectedCarrierCase ?? null}
            history={console.selectedCaseHistory}
            decisions={console.selectedCaseHistory?.decisions ?? console.decisions}
            loading={console.loading}
            onPrepare={(connectionId) =>
              void console.prepareCarrierRecovery(connectionId)
            }
            onApproveRequest={() => void console.approveRequest()}
            onRejectRequest={() => void console.rejectRequest()}
            onSend={() => void console.sendRequest()}
            onSimulate={() => void console.simulateCarrierResponse()}
            onApproveCounter={() => void console.approveCounter()}
            onRejectCounter={() => void console.rejectCounter()}
            onEvaluateTimeout={() => void console.evaluateTimeout()}
            agentRunActive={Boolean(console.agentRuns.at(-1) && !["COMPLETED", "ESCALATED", "FAILED"].includes(console.agentRuns.at(-1)!.state))}
          />
        </div>

        <TradeoffReviewPanel reviews={console.tradeoffReviews} options={console.tradeoffOptions} loading={console.loading} onSelect={(review, optionId) => void console.chooseTradeoff(review, optionId)} />
        <CargoSafetyPanel reviews={console.cargoSafetyReviews} histories={console.safetyHistories} loading={console.loading} onEvaluate={(id) => void console.evaluateSafety(id)} onCreateCanonical={() => void console.createSafetyReview("SYN-CNT-010")} />

        {!console.incident && !console.loading && (
          <div className="rounded border border-dashed border-slate-800 bg-slate-950/40 px-6 py-10 text-center">
            <p className="text-sm text-slate-400">
              No incident loaded. Create a canonical scarcity incident or start a
              canonical carrier demo run.
            </p>
          </div>
        )}

        {console.loading && (
          <div className="rounded border border-slate-800 bg-slate-900/30 px-4 py-3 font-mono text-sm text-slate-300">
            Contacting backend and loading persisted incident state…
          </div>
        )}

        {console.error && (
          <div
            role="alert"
            className="rounded border border-rose-500/50 bg-rose-950/40 px-4 py-3 text-sm text-rose-100"
          >
            <p className="font-semibold">Operations console error</p>
            <p className="mt-1 font-mono text-xs">
              {console.error.status}: {console.error.detail}
            </p>
          </div>
        )}

        {console.incident && (
          <section className="space-y-4 rounded border border-slate-800 bg-slate-950/60 px-4 py-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-100">
                Audit / decision history
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Persisted audit trail for the active incident. Human approvals and
                carrier evidence remain visible in workflow order.
              </p>
            </div>
            <ActorLegend />
            <AuditTimeline events={console.auditEvents} loading={console.loading} />
          </section>
        )}

        <SyntheticDemoControl
          incidentId={console.incident?.id ?? null}
          loading={console.loading}
          onCreateIncident={() => void console.createCanonicalIncident()}
          onRefresh={() => void console.refresh()}
          onBootstrap={() => void console.bootstrapYard()}
          onStartAgent={() => void console.startAgent()}
          onAdvanceAgent={() => void console.advanceAgent()}
          onPublishActive={() => void console.publishActive()}
          onCreateSafetyReview={() => void console.createSafetyReview("SYN-CNT-010")}
          canBootstrap={Boolean(console.incident && console.yardForecasts.length === 0)}
          canStartAgent={Boolean(console.incident && !run)}
          canAdvanceAgent={canAdvance}
          canPublishActive={Boolean(console.incident && console.yardForecasts.length > 0 && !activeSnapshot)}
          canCreateSafetyReview={Boolean(console.incident && !console.cargoSafetyReviews.some((review) => review.container_id === "SYN-CNT-010"))}
        />
      </main>
    </div>
  );
}
