import { DynamicYardPanel } from "../../dynamic/DynamicYardPanel";
import { TradeoffReviewPanel } from "../../dynamic/TradeoffReviewPanel";
import { AgentRunPanel } from "../../agent/AgentRunPanel";
import type {
  AgentHistory,
  AgentRun,
  AllocationRevision,
  AllocationTradeoffOption,
  AllocationTradeoffReview,
  ExpediteCommitment,
  YardForecastSnapshot,
} from "../../../api/types";
import type { RecoverySummary } from "../../../lib/recoverySelectors";

export function RecoveryWorkspace({
  summary,
  yardForecasts,
  allocationRevisions,
  expediteCommitments,
  tradeoffReviews,
  tradeoffOptions,
  run,
  agentHistory,
  canAdvance,
  loading,
  onBootstrap,
  onPublishActive,
  onAdvanceAgent,
  onRefresh,
  onChooseTradeoff,
}: {
  summary: RecoverySummary | null;
  yardForecasts: YardForecastSnapshot[];
  allocationRevisions: AllocationRevision[];
  expediteCommitments: ExpediteCommitment[];
  tradeoffReviews: AllocationTradeoffReview[];
  tradeoffOptions: AllocationTradeoffOption[];
  run: AgentRun | null;
  agentHistory: AgentHistory | null;
  canAdvance: boolean;
  loading: boolean;
  onBootstrap(): void;
  onPublishActive(): void;
  onAdvanceAgent(): void;
  onRefresh(): void;
  onChooseTradeoff(review: AllocationTradeoffReview, optionId: string): void;
}) {
  return (
    <div className="space-y-4">
      <header className="psa-surface rounded-[12px] px-5 py-4">
        <p className="psa-label text-psa-signal">Recovery workspace</p>
        <h2 className="mt-1 text-lg font-medium text-psa-snow">Operations planning</h2>
        <p className="mt-2 text-sm text-psa-chalk">
          Scarcity allocation, yard forecasts, allocation revisions, expedite commitments, and
          active agent orchestration.
        </p>
        {summary ? (
          <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="psa-surface-nested rounded-[8px] px-3 py-2.5">
              <dt className="psa-label">Strategy</dt>
              <dd className="mt-1 text-sm text-psa-snow">{summary.selectedStrategy ?? "—"}</dd>
            </div>
            <div className="psa-surface-nested rounded-[8px] px-3 py-2.5">
              <dt className="psa-label">Expedite slots</dt>
              <dd className="psa-kpi mt-1 text-xl text-psa-snow">{summary.selectedExpediteSlots}</dd>
            </div>
            <div className="psa-surface-nested rounded-[8px] px-3 py-2.5">
              <dt className="psa-label">Expected preserved</dt>
              <dd className="psa-kpi mt-1 text-xl text-psa-signal">
                {summary.scenarioAwareExpectedPreserved?.toFixed(1) ?? "—"}
              </dd>
            </div>
            <div className="psa-surface-nested rounded-[8px] px-3 py-2.5">
              <dt className="psa-label">Revisions</dt>
              <dd className="psa-kpi mt-1 text-xl text-psa-snow">{allocationRevisions.length}</dd>
            </div>
          </dl>
        ) : null}
      </header>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <DynamicYardPanel
          snapshots={yardForecasts}
          revisions={allocationRevisions}
          commitments={expediteCommitments}
          loading={loading}
          onBootstrap={onBootstrap}
          onActive={onPublishActive}
        />
        <AgentRunPanel
          run={run}
          history={agentHistory}
          loading={loading}
          canAdvance={canAdvance}
          onStart={onAdvanceAgent}
          onAdvance={onAdvanceAgent}
          onRefresh={onRefresh}
        />
      </div>

      <TradeoffReviewPanel
        reviews={tradeoffReviews}
        options={tradeoffOptions}
        loading={loading}
        onSelect={onChooseTradeoff}
      />
    </div>
  );
}
