import {
  RECOVERY_CHAPTERS,
  chapterForStage,
  chapterIndex,
} from "../../lib/recoveryChapters";
import type { CanonicalReplayStage } from "../../api/types";

export function ChapterProgress({
  stage,
  empty = false,
}: {
  stage?: CanonicalReplayStage;
  empty?: boolean;
}) {
  const activeId = empty ? "INCIDENT" : chapterForStage(stage ?? "READY_TO_CREATE");
  const activeIndex = chapterIndex(activeId);

  return (
    <nav
      aria-label="Recovery sequence"
      className="psa-surface rounded-[12px] px-4 py-4 sm:px-5"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="psa-label">Recovery progress</p>
        <p className="text-[11px] text-psa-steel">
          Step {activeIndex + 1} of {RECOVERY_CHAPTERS.length}
        </p>
      </div>

      <ol className="flex min-w-0 items-start gap-0 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:thin]">
        {RECOVERY_CHAPTERS.map((chapter, index) => {
          const state =
            index < activeIndex
              ? "complete"
              : index === activeIndex
                ? "current"
                : "upcoming";
          const isLast = index === RECOVERY_CHAPTERS.length - 1;

          return (
            <li
              key={chapter.id}
              className="flex min-w-[4.75rem] shrink-0 flex-1 flex-col"
              aria-current={state === "current" ? "step" : undefined}
            >
              <div className="flex items-center">
                {index > 0 ? (
                  <TrackSegment filled={index <= activeIndex} />
                ) : null}
                <ChapterNode state={state} />
                {!isLast ? <TrackSegment filled={index < activeIndex} /> : null}
              </div>

              <div className="mt-2 px-0.5 text-center">
                <p
                  className={`text-[10px] font-medium leading-tight sm:text-[11px] ${
                    state === "current"
                      ? "text-psa-signal"
                      : state === "complete"
                        ? "text-psa-chalk"
                        : "text-psa-steel"
                  }`}
                >
                  {chapter.label}
                </p>
                {state === "current" ? (
                  <p className="mt-1 hidden text-[10px] leading-snug text-psa-fog sm:block">
                    {chapter.summary}
                  </p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function TrackSegment({ filled }: { filled: boolean }) {
  return (
    <span
      className={`mx-0.5 h-[2px] min-w-[0.5rem] flex-1 rounded-full ${
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
        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-psa-fern/15 ring-1 ring-psa-fern/50"
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
        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-psa-signal/20 ring-2 ring-psa-signal"
        aria-hidden
      >
        <span className="h-2.5 w-2.5 rounded-full bg-psa-signal" />
      </span>
    );
  }

  return (
    <span
      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-psa-charcoal ring-1 ring-white/14"
      aria-hidden
    >
      <span className="h-2 w-2 rounded-full bg-psa-smoke" />
    </span>
  );
}
