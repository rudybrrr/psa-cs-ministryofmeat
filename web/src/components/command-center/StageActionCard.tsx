import type { CanonicalReplayActionType, CanonicalReplayStageView } from "../../api/types";
import type { CanonicalIncidentFixture } from "../../api/types";
import type { Incident } from "../../api/types";
import { guidedActionPresentation } from "../../lib/guidedActions";
import { chapterMeta, chapterForStage } from "../../lib/recoveryChapters";

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
  fixture,
  loading,
  approvalFingerprint,
  onExecute,
  emptyState,
}: {
  stage: CanonicalReplayStageView | null;
  incident: Incident | null;
  fixture: CanonicalIncidentFixture | null;
  loading: boolean;
  approvalFingerprint: string | null;
  onExecute(action: CanonicalReplayActionType): void;
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
  const isTerminal =
    stage.stage === "SAFETY_BLOCKED" || stage.stage === "COMPLETE";
  const vessel = fixture?.event.vessel_name ?? "Inbound vessel";

  return (
    <section className="psa-surface overflow-hidden rounded-[12px]">
      <div className="grid lg:grid-cols-[1.2fr_0.8fr]">
        <div className="border-b border-white/10 px-5 py-5 lg:border-b-0 lg:border-r lg:px-6 lg:py-6">
          <p className="psa-label text-psa-signal">Current stage · {chapter.label}</p>
          <h2 className="mt-2 text-lg font-medium tracking-[-0.02em] text-psa-snow sm:text-xl">
            {presentation.headline}
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-psa-chalk">
            {presentation.detail}
          </p>
          <dl className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="psa-surface-nested rounded-[8px] px-3 py-2.5">
              <dt className="psa-label">Event</dt>
              <dd className="mt-1 text-sm text-psa-snow">{vessel}</dd>
            </div>
            <div className="psa-surface-nested rounded-[8px] px-3 py-2.5">
              <dt className="psa-label">Operational state</dt>
              <dd className="mt-1 text-sm text-psa-chalk">
                {stage.stage.replaceAll("_", " ").toLowerCase()}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-xs leading-relaxed text-psa-steel">{chapter.summary}</p>
        </div>

        <div className="bg-psa-slate/80 px-5 py-5 lg:px-6 lg:py-6">
          <p className="psa-label">Action boundary</p>
          <p className="mt-2 text-sm font-medium text-psa-snow">{presentation.actor}</p>
          {stage.requires_human_authority ? (
            <p className="mt-2 rounded-[8px] border border-psa-amber/40 bg-psa-amber/10 px-3 py-2 text-xs text-psa-chalk">
              Human authority required before this action can proceed.
            </p>
          ) : null}

          {!isTerminal && stage.next_allowed_action !== "NONE" ? (
            <button
              type="button"
              disabled={!enabled}
              onClick={() => onExecute(stage.next_allowed_action)}
              className={`mt-5 ${buttonClassForVariant(presentation.variant)}`}
            >
              {presentation.buttonLabel}
            </button>
          ) : null}

          {stage.requires_human_authority && approvalFingerprint ? (
            <details className="mt-4 rounded-[8px] border border-white/10 bg-psa-charcoal/80 px-3 py-2">
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
                Deterministic cargo-safety policy blocked automation. Controlled successful
                outcome — not an application failure.
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
