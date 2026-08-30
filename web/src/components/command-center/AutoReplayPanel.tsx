import { useState } from "react";

import { AUTO_REPLAY_DISCLOSURE, MAX_AUTO_ACTIONS } from "../../api/canonicalReplay";
import type { CanonicalReplayStageView } from "../../api/types";
import type { AutoReplayProgress } from "../../lib/autoReplayController";
import { guidedActionPresentation } from "../../lib/guidedActions";
import { chapterForStage, chapterMeta } from "../../lib/recoveryChapters";

export function AutoReplayPanel({
  stage,
  progress,
  canStart,
  loading,
  onStart,
  onStop,
}: {
  stage: CanonicalReplayStageView;
  progress: AutoReplayProgress;
  canStart: boolean;
  loading: boolean;
  onStart(): void;
  onStop(): void;
}) {
  const [showTechnical, setShowTechnical] = useState(false);
  const chapter = chapterMeta(chapterForStage(stage.stage));
  const currentPresentation = progress.currentAction
    ? guidedActionPresentation(progress.currentAction as never)
    : guidedActionPresentation(stage.next_allowed_action);

  const terminalSuccess = stage.stage === "SAFETY_BLOCKED" || progress.halt === "terminal-success";

  return (
    <section className="psa-surface overflow-hidden rounded-[12px]" aria-labelledby="auto-replay-heading">
      <div className="border-b border-white/10 px-5 py-5 sm:px-6">
        <p className="psa-meta">Presentation mode</p>
        <h2 id="auto-replay-heading" className="mt-1 text-xl font-medium tracking-[-0.02em] text-psa-snow">
          Auto replay
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-psa-chalk">
          Run the complete recovery scenario automatically. Operator approvals use the synthetic
          demo identity — a backup presentation path when live narration is not available.
        </p>
      </div>

      <div className="grid gap-0 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-4 border-b border-white/10 px-5 py-5 lg:border-b-0 lg:border-r lg:px-6">
          <div className="psa-surface-nested rounded-[10px] px-4 py-4">
            <p className="psa-meta">Current chapter</p>
            <p className="mt-2 text-lg font-medium text-psa-snow">{chapter.label}</p>
            <p className="mt-1 text-sm text-psa-chalk">{chapter.summary}</p>
          </div>

          <div className="psa-surface-nested rounded-[10px] px-4 py-4">
            <p className="psa-meta">Current action</p>
            <p className="mt-2 text-sm font-medium text-psa-snow">{currentPresentation.headline}</p>
            <p className="mt-1 text-xs text-psa-steel">{currentPresentation.detail}</p>
            {progress.running ? (
              <p className="mt-3 text-xs text-psa-signal">Running…</p>
            ) : null}
          </div>

          {terminalSuccess ? (
            <div className="rounded-[10px] border border-psa-fern/40 bg-psa-fern/10 px-4 py-4">
              <p className="text-sm font-medium text-psa-snow">ESCALATED / SAFETY_REVIEW_REQUIRED</p>
              <p className="mt-2 text-sm leading-relaxed text-psa-chalk">
                Safe escalation reached. Deterministic cargo-safety policy blocked automation — a
                controlled successful outcome, not an application failure.
              </p>
            </div>
          ) : null}
        </div>

        <div className="bg-psa-slate/50 px-5 py-5 lg:px-6">
          <p className="psa-meta">Playback controls</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {!progress.running ? (
              <button
                type="button"
                disabled={loading || !canStart}
                onClick={onStart}
                className="psa-btn psa-btn-primary"
              >
                Auto start
              </button>
            ) : (
              <button type="button" onClick={onStop} className="psa-btn psa-btn-destructive">
                Stop
              </button>
            )}
            <span className="text-xs text-psa-steel">
              {progress.actionsUsed} / {MAX_AUTO_ACTIONS} actions
            </span>
            {progress.halt ? (
              <span className="text-xs uppercase text-psa-chalk">halt: {progress.halt}</span>
            ) : null}
          </div>

          <p className="psa-mono mt-2 text-[10px] text-psa-steel">{stage.stage}</p>

          <ol className="mt-3 max-h-40 overflow-y-auto rounded-[8px] border border-white/10 bg-psa-void/70 px-3 py-2 font-mono text-[11px] text-psa-steel">
            {progress.log.length === 0 ? (
              <li>No auto replay actions in this session.</li>
            ) : null}
            {progress.log.map((entry, index) => (
              <li key={`${entry.ordinal}-${entry.action}-${index}`} className="whitespace-nowrap">
                <span>{`[${index + 1}] `}</span>
                <span className="text-psa-chalk">{entry.stage}</span>
                <span>{" -> "}</span>
                <span className="text-psa-signal">{entry.action}</span>
                <span>{` : ${entry.outcome}`}</span>
              </li>
            ))}
          </ol>

          <p className="mt-4 rounded-[8px] border border-psa-amber/25 bg-psa-amber/8 px-3 py-2 text-xs leading-relaxed text-psa-chalk">
            {AUTO_REPLAY_DISCLOSURE}
          </p>

          <button
            type="button"
            className="mt-4 text-xs text-psa-signal underline-offset-2 hover:underline"
            onClick={() => setShowTechnical((open) => !open)}
            aria-expanded={showTechnical}
          >
            {showTechnical ? "Hide" : "Show"} technical replay log
          </button>

          {showTechnical ? (
            <div className="mt-3 space-y-3">
              <div className="psa-surface-nested rounded-[8px] px-3 py-3 text-xs text-psa-chalk">
                <p>
                  <span className="text-psa-steel">Stage:</span>{" "}
                  <span className="font-mono">{stage.stage}</span>
                </p>
                <p className="mt-1">
                  <span className="text-psa-steel">Progress:</span> {stage.progress_label}
                </p>
                <p className="mt-1">
                  <span className="text-psa-steel">Status:</span> {stage.status}
                </p>
                {progress.currentAction ? (
                  <p className="mt-1">
                    <span className="text-psa-steel">Action:</span>{" "}
                    <span className="font-mono text-psa-signal">{progress.currentAction}</span>
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
