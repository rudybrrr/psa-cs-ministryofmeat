const PROOF_POINTS = [
  {
    title: "Scarce-capacity optimization",
    detail:
      "Eight expedite slots must be allocated across affected connections while forecasts remain uncertain.",
  },
  {
    title: "Human authorization boundaries",
    detail:
      "The agent prepares carrier recovery actions; operators must explicitly approve transmission.",
  },
  {
    title: "Deterministic safety enforcement",
    detail:
      "Semantic inconsistency detection and cargo policy own automation — escalation is a controlled outcome.",
  },
] as const;

export function GuidedIntroSurface({
  loading,
  onStart,
}: {
  loading: boolean;
  onStart(): void;
}) {
  return (
    <section
      className="psa-surface overflow-hidden rounded-[12px]"
      aria-labelledby="guided-intro-heading"
    >
      <div className="border-b border-white/[0.08] px-6 py-8 sm:px-8 sm:py-10">
        <div className="flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center rounded-full border border-psa-signal/35 bg-psa-signal/10 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.12em] text-psa-signal">
            Guided demo
          </span>
          <span className="text-xs text-psa-steel">7-stage recovery scenario</span>
        </div>

        <h1
          id="guided-intro-heading"
          className="mt-6 max-w-3xl text-3xl font-medium tracking-[-0.03em] text-psa-snow sm:text-[2.125rem] sm:leading-tight"
        >
          Recovery command center
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-psa-chalk">
          A delayed inbound vessel compresses transshipment recovery at Tuas terminal.
          Walk through one connected scenario — from disruption and scarce expedite
          allocation to carrier coordination and cargo safety enforcement.
        </p>

        <div className="mt-8 flex flex-wrap items-center gap-4">
          <button
            type="button"
            disabled={loading}
            onClick={onStart}
            className="rounded-[10px] border border-transparent bg-psa-bone px-6 py-3.5 text-sm font-medium text-psa-ink transition-colors hover:bg-white disabled:opacity-40"
          >
            Start recovery demo
          </button>
          <p className="text-xs text-psa-steel">Synthetic fixtures · no live operations data</p>
        </div>
      </div>

      <div className="grid gap-px bg-white/[0.08] sm:grid-cols-3">
        {PROOF_POINTS.map((point) => (
          <div
            key={point.title}
            className="bg-psa-graphite px-5 py-5 sm:px-6 sm:py-6"
          >
            <p className="text-sm font-medium text-psa-snow">{point.title}</p>
            <p className="mt-2 text-sm leading-relaxed text-psa-fog">{point.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
