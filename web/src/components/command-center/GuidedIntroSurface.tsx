const PROOF_POINTS = [
  "Scarce-capacity optimization under uncertainty",
  "Human authorization at carrier boundaries",
  "Deterministic cargo safety enforcement",
] as const;

export function GuidedIntroSurface({
  loading,
  onStart,
}: {
  loading: boolean;
  onStart(): void;
}) {
  return (
    <div className="px-5 py-6 sm:px-8 sm:py-8">
      <p className="psa-label text-psa-signal">Stage action</p>
      <h2
        id="guided-intro-heading"
        className="mt-2 text-xl font-medium tracking-[-0.02em] text-psa-snow sm:text-2xl"
      >
        A delayed inbound vessel has put 24 transshipment containers at risk — but recovery
        capacity is limited.
      </h2>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-psa-chalk">
        Begin the guided recovery walkthrough to see how the system allocates scarce expedite
        slots, pauses at evidence boundaries, and stops at human authority and safety policy.
      </p>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <div className="psa-surface-nested rounded-[8px] px-3 py-3">
          <p className="psa-label">Synthetic scenario</p>
          <p className="mt-1 text-sm font-medium text-psa-snow">Late inbound vessel</p>
        </div>
        <div className="psa-surface-nested rounded-[8px] px-3 py-3">
          <p className="psa-label">Containers at risk</p>
          <p className="mt-1 text-sm font-medium text-psa-snow">24</p>
        </div>
        <div className="psa-surface-nested rounded-[8px] px-3 py-3">
          <p className="psa-label">Expedite slots</p>
          <p className="mt-1 text-sm font-medium text-psa-snow">8</p>
        </div>
      </div>

      <button
        type="button"
        disabled={loading}
        onClick={onStart}
        className="psa-btn psa-btn-primary mt-6"
      >
        Start recovery demo
      </button>

      <ul className="mt-6 flex flex-wrap gap-x-6 gap-y-2 border-t border-white/10 pt-4">
        {PROOF_POINTS.map((point) => (
          <li key={point} className="flex items-center gap-2 text-xs text-psa-steel">
            <span className="h-1 w-1 shrink-0 rounded-full bg-psa-signal/70" aria-hidden />
            {point}
          </li>
        ))}
      </ul>
    </div>
  );
}
