import {
  RECOVERY_CHAPTERS,
  chapterForStage,
  chapterIndex,
} from "../../lib/recoveryChapters";
import type { CanonicalReplayStage } from "../../api/types";

export function ChapterProgress({ stage }: { stage: CanonicalReplayStage }) {
  const activeId = chapterForStage(stage);
  const activeIndex = chapterIndex(activeId);

  return (
    <nav
      aria-label="Recovery sequence"
      className="psa-surface rounded-[12px] px-4 py-5 sm:px-6"
    >
      <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
        <p className="psa-label">Recovery sequence</p>
        <p className="text-xs text-psa-steel">Incident → Protect</p>
      </div>

      <ol className="flex min-w-0 gap-0 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:thin]">
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
              className="flex min-w-[5.25rem] shrink-0 flex-1 flex-col"
              aria-current={state === "current" ? "step" : undefined}
            >
              <div className="flex min-h-[1.25rem] items-center">
                {index > 0 ? (
                  <TrackSegment filled={index <= activeIndex} side="left" />
                ) : (
                  <span className="w-2 shrink-0" aria-hidden />
                )}
                <ChapterNode state={state} label={chapter.label} />
                {!isLast ? (
                  <TrackSegment filled={index < activeIndex} side="right" />
                ) : (
                  <span className="w-2 shrink-0" aria-hidden />
                )}
              </div>

              <div className="mt-2 px-0.5 text-center">
                <p
                  className={`text-[11px] font-medium leading-tight sm:text-xs ${
                    state === "current"
                      ? "text-psa-snow"
                      : state === "complete"
                        ? "text-psa-chalk"
                        : "text-psa-steel"
                  }`}
                >
                  {chapter.label}
                </p>
                {state === "current" ? (
                  <p className="mt-1.5 hidden text-[11px] leading-snug text-psa-fog sm:block">
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

function TrackSegment({
  filled,
  side,
}: {
  filled: boolean;
  side: "left" | "right";
}) {
  return (
    <span
      className={`h-px min-w-[0.35rem] flex-1 ${
        filled ? "bg-psa-signal/50" : "bg-white/10"
      } ${side === "left" ? "mr-0.5" : "ml-0.5"}`}
      aria-hidden
    />
  );
}

function ChapterNode({
  state,
  label,
}: {
  state: "complete" | "current" | "upcoming";
  label: string;
}) {
  if (state === "complete") {
    return (
      <span
        className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-psa-fern/20 ring-1 ring-psa-fern/50"
        title={`${label} complete`}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-psa-fern" />
      </span>
    );
  }

  if (state === "current") {
    return (
      <span
        className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-psa-signal/15 ring-2 ring-psa-signal/40"
        title={`${label} current`}
      >
        <span className="h-2 w-2 rounded-full bg-psa-signal" />
      </span>
    );
  }

  return (
    <span
      className="h-2.5 w-2.5 shrink-0 rounded-full bg-psa-smoke ring-1 ring-white/10"
      title={`${label} upcoming`}
    />
  );
}