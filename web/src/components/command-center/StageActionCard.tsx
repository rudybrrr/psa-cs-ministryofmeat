import type { CanonicalReplayActionType, CanonicalReplayStageView } from "../../api/types";
import type { Incident } from "../../api/types";
import type { AgentRun } from "../../api/types";
import { agentStateLabel } from "../../lib/agentRunPresentation";
import { guidedActionPresentation } from "../../lib/guidedActions";
import { chapterMeta, chapterForStage } from "../../lib/recoveryChapters";
import { waitKindPresentation } from "../../lib/waitKindCopy";

function buttonClassForVariant(
  variant: ReturnType<typeof guidedActionPresentation>["variant"],
): string {
  switch (variant) {
    case "authority":
      return "psa-btn psa-btn-authority w-full sm:w-auto";
    case "safety":
      return "psa-btn psa-btn-destructive w-full sm:w-auto";
    default:
      return "psa-btn psa-btn-primary w-full sm:w-auto";
  }
}

export function StageActionCard({
  stage,
  incident,
  loading,
  approvalFingerprint,
  agentRun,
  onExecute,
  onReviewPrevious,
  reviewingPrior = false,
  emptyState,
}: {
  stage: CanonicalReplayStageView | null;
  incident: Incident | null;
  loading: boolean;
  approvalFingerprint: string | null;
  agentRun?: AgentRun | null;
  onExecute(action: CanonicalReplayActionType): void;
  onReviewPrevious?(): void;
  reviewingPrior?: boolean;
  emptyState?: React.ReactNode;
}) {
  if (!incident && emptyState) {
    return (
      <section className="psa-surface overflow-hidden rounded-[12px]">{emptyState}</section>
    );
  }

  if (!stage || !incident) {
    return null;
  }

  const chapter = chapterMeta(chapterForStage(stage.stage));
  const presentation = guidedActionPresentation(stage.next_allowed_action);
  const enabled =
    !loading && stage.guided_can_execute && stage.next_allowed_action !== "NONE";
  const isSafetyFinale = stage.stage === "SAFETY_BLOCKED";
  const isTerminal = isSafetyFinale || stage.stage === "COMPLETE";
  const waiting = waitKindPresentation(agentRun?.wait_kind);
  const canReviewPrevious =
    Boolean(onReviewPrevious) &&
    chapterForStage(stage.stage) !== "INCIDENT";

  return (
    <section
      className="psa-surface rounded-[12px] px-5 py-5 sm:px-6 sm:py-6"
      aria-labelledby="stage-action-heading"
    >
      <div className="max-w-3xl">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-psa-signal">
          Next action · {chapter.label} · {presentation.actor}
        </p>
        <h2
          id="stage-action-heading"
          className="mt-1.5 text-xl font-medium tracking-[-0.02em] text-psa-snow sm:text-2xl"
        >
          {presentation.headline}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-psa-chalk sm:text-[15px]">
          {presentation.detail}
        </p>
      </div>

      {agentRun?.state === "WAITING" && waiting ? (
        <div className="mt-4 max-w-3xl rounded-[10px] border border-psa-amber/35 bg-psa-amber/8 px-4 py-3">
          <p className="text-xs font-medium text-psa-amber">{waiting.label}</p>
          <p className="mt-1 text-sm text-psa-chalk">{waiting.detail}</p>
        </div>
      ) : null}

      {stage.requires_human_authority ? (
        <p className="mt-4 max-w-3xl text-sm text-psa-chalk">
          Human authority is required — the agent may prepare evidence but cannot authorize
          this step.
        </p>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        {!isTerminal && stage.next_allowed_action !== "NONE" ? (
          <button
            type="button"
            disabled={!enabled}
            onClick={() => onExecute(stage.next_allowed_action)}
            className={buttonClassForVariant(presentation.variant)}
          >
            {presentation.buttonLabel}
          </button>
        ) : null}

        {canReviewPrevious ? (
          <button
            type="button"
            onClick={onReviewPrevious}
            className="psa-btn-ghost text-xs"
          >
            {reviewingPrior ? "Return to current step" : "Review previous step"}
          </button>
        ) : null}

        {isSafetyFinale ? (
          <div
            className="w-full max-w-3xl rounded-[10px] border border-psa-fern/45 bg-psa-fern/10 px-5 py-5 motion-safe:animate-[psa-finale-in_0.45s_ease-out]"
            role="status"
          >
            <p className="text-lg font-medium tracking-[-0.02em] text-psa-fern sm:text-xl">
              Safety policy enforced
            </p>
            <p className="mt-2 text-sm leading-relaxed text-psa-chalk">
              Controlled escalation — automation blocked until human DG review completes.
              This is the intended successful outcome for the demo finale.
            </p>
          </div>
        ) : null}
      </div>

      {agentRun ? (
        <p className="mt-4 text-xs text-psa-steel">
          Agent run · {agentStateLabel(agentRun.state)}
          {waiting ? ` · ${waiting.label}` : ""}
        </p>
      ) : null}

      {stage.requires_human_authority && approvalFingerprint ? (
        <details className="mt-4 max-w-3xl rounded-[8px] bg-psa-charcoal/50 px-3 py-2">
          <summary className="cursor-pointer text-xs text-psa-amber">
            Authorization evidence
          </summary>
          <p className="psa-mono mt-2 break-all text-[11px] text-psa-chalk">
            {approvalFingerprint}
          </p>
        </details>
      ) : null}
    </section>
  );
}
