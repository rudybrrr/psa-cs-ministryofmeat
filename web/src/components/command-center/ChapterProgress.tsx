import {
  RECOVERY_CHAPTERS,
  chapterForStage,
  chapterIndex,
} from "../../lib/recoveryChapters";
import type { CanonicalReplayStage } from "../../api/types";

export function ChapterProgress({
  stage,
  empty = false,
  highlightIndex,
}: {
  stage?: CanonicalReplayStage;
  empty?: boolean;
  highlightIndex?: number;
}) {
  const activeId = empty ? "INCIDENT" : chapterForStage(stage ?? "READY_TO_CREATE");
  const activeIndex = chapterIndex(activeId);
  const displayIndex = highlightIndex ?? activeIndex;
  const reviewingPrior = highlightIndex != null && highlightIndex < activeIndex;

  return (
    <nav
      aria-label="Recovery sequence"
      className="psa-surface w-full rounded-[12px] px-4 py-4 sm:px-5"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="psa-meta">Recovery progress</p>
        <p className="text-[11px] text-psa-steel">
          {reviewingPrior ? (
            <>
              Reviewing step {displayIndex + 1} · current step {activeIndex + 1}
            </>
          ) : (
            <>Step {displayIndex + 1} of {RECOVERY_CHAPTERS.length}</>
          )}
        </p>
      </div>

      {/* Scroll on very narrow viewports; steps distribute evenly at full width */}
      <div className="w-full overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:thin]">
        <ol className="flex w-full min-w-[34rem] items-start px-1 py-1 sm:min-w-0">
          {RECOVERY_CHAPTERS.map((chapter, index) => {
            const state =
              index < displayIndex
                ? "complete"
                : index === displayIndex
                  ? "current"
                  : "upcoming";
            const isLast = index === RECOVERY_CHAPTERS.length - 1;

            return (
              <li
                key={chapter.id}
                className="flex min-w-0 flex-1 flex-col"
                aria-current={state === "current" ? "step" : undefined}
              >
                <div className="flex w-full items-center">
                  {index > 0 ? (
                    <TrackSegment filled={index <= displayIndex} />
                  ) : (
                    <span className="min-w-0 flex-1" aria-hidden />
                  )}
                  <ChapterNode state={state} />
                  {!isLast ? (
                    <TrackSegment filled={index < displayIndex} />
                  ) : (
                    <span className="min-w-0 flex-1" aria-hidden />
                  )}
                </div>

                <div className="mt-2 w-full px-0.5 text-center">
                  {state === "current" ? (
                    <>
                      <p className="text-[10px] font-medium leading-tight text-psa-signal sm:text-[11px]">
                        {chapter.label}
                      </p>
                      <p className="mt-1 hidden text-[10px] leading-snug text-psa-steel sm:block">
                        {chapter.summary}
                      </p>
                    </>
                  ) : (
                    <p
                      className={`text-[10px] font-medium leading-tight sm:text-[11px] ${
                        state === "complete" ? "text-psa-chalk" : "text-psa-steel"
                      }`}
                    >
                      {chapter.label}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </nav>
  );
}

function TrackSegment({ filled }: { filled: boolean }) {
  return (
    <span
      className={`mx-0.5 h-[2px] min-w-[0.25rem] flex-1 rounded-full ${
        filled ? "bg-psa-signal/60" : "bg-white/12"
      }`}
      aria-hidden
    />
  );
}

function ChapterNode({ state }: { state: "complete" | "current" | "upcoming" }) {
  if (state === "complete") {
    return (
      <span
        className="box-border flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-psa-fern/50 bg-psa-fern/15"
        aria-hidden
      >
        <svg viewBox="0 0 12 12" className="h-3 w-3 text-psa-fern" fill="none">
          <path
            d="M2.5 6.2 5 8.7 9.5 3.8"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    );
  }

  if (state === "current") {
    return (
      <span
        className="box-border flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 border-psa-signal bg-psa-signal/20"
        aria-hidden
      >
        <span className="h-2.5 w-2.5 rounded-full bg-psa-signal" />
      </span>
    );
  }

  return (
    <span
      className="box-border flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/14 bg-psa-charcoal"
      aria-hidden
    >
      <span className="h-2 w-2 rounded-full bg-psa-smoke" />
    </span>
  );
}
