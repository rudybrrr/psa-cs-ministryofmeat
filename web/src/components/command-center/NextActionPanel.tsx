import type { CanonicalReplayActionType, CanonicalReplayStageView } from "../../api/types";
import { guidedActionPresentation } from "../../lib/guidedActions";
import { chapterMeta, chapterForStage } from "../../lib/recoveryChapters";

export function NextActionPanel({
  stage,
  loading,
  approvalFingerprint,
  onExecute,
}: {
  stage: CanonicalReplayStageView;
  loading: boolean;
  approvalFingerprint: string | null;
  onExecute(action: CanonicalReplayActionType): void;
}) {
  const chapter = chapterMeta(chapterForStage(stage.stage));
  const presentation = guidedActionPresentation(stage.next_allowed_action);
  const enabled =
    !loading && stage.guided_can_execute && stage.next_allowed_action !== "NONE";
  const isTerminal =
    stage.stage === "SAFETY_BLOCKED" || stage.stage === "COMPLETE";

  const buttonClass =
    presentation.variant === "authority"
      ? "border-psa-amber/50 bg-psa-amber/10 text-psa-snow hover:bg-psa-amber/15"
      : presentation.variant === "safety"
        ? "border-psa-coral/40 bg-psa-coral/10 text-psa-snow"
        : "border-transparent bg-psa-bone text-psa-ink hover:bg-white";

  return (
    <section className="psa-surface rounded-[12px] px-5 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="max-w-2xl">
          <p className="psa-label text-psa-signal">Next action · {chapter.label}</p>
          <p className="mt-2 text-xs font-medium text-psa-steel">{presentation.actor}</p>
          <h2 className="mt-2 text-xl font-medium tracking-[-0.02em] text-psa-snow sm:text-2xl">
            {presentation.headline}
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-psa-chalk">
            {presentation.detail}
          </p>
        </div>
        {!isTerminal && stage.next_allowed_action !== "NONE" ? (
          <button
            type="button"
            disabled={!enabled}
            onClick={() => onExecute(stage.next_allowed_action)}
            className={`shrink-0 rounded-[10px] border px-5 py-3 text-sm font-medium disabled:opacity-40 ${buttonClass}`}
          >
            {presentation.buttonLabel}
          </button>
        ) : null}
      </div>

      {stage.requires_human_authority && approvalFingerprint ? (
        <details className="mt-5 psa-surface-nested rounded-[8px] px-3 py-2">
          <summary className="cursor-pointer text-xs text-psa-amber">
            View authorization evidence
          </summary>
          <p className="mt-2 break-all font-mono text-[11px] text-psa-chalk">
            {approvalFingerprint}
          </p>
        </details>
      ) : null}

      {stage.stage === "SAFETY_BLOCKED" ? (
        <div className="mt-5 rounded-[10px] border border-psa-fern/40 bg-psa-fern/10 px-4 py-4">
          <p className="text-sm font-medium text-psa-snow">
            Escalated · safety review required
          </p>
          <p className="mt-2 text-sm leading-relaxed text-psa-chalk">
            Deterministic cargo-safety policy blocked automation. This is a controlled
            successful outcome — not an application failure.
          </p>
        </div>
      ) : null}
    </section>
  );
}
