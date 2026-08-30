import type { CanonicalIncidentFixture } from "../../api/types";
import type { RecoverySummary } from "../../lib/recoverySelectors";

const PROOF_POINTS = [
  "Scarce-capacity optimization under uncertainty",
  "Human authorization at carrier boundaries",
  "Deterministic cargo safety enforcement",
] as const;

export function GuidedIntroSurface({
  loading,
  onStart,
  summary,
  fixture,
}: {
  loading: boolean;
  onStart(): void;
  summary?: RecoverySummary | null;
  fixture?: CanonicalIncidentFixture | null;
}) {
  const containersAtRisk =
    summary?.containersAtRisk ?? fixture?.profiles.length ?? 24;
  const expediteSlots =
    summary?.selectedExpediteSlots ?? fixture?.capacity.total_slots ?? 8;

  return (
    <div className="px-5 py-6 sm:px-8 sm:py-7">
      <h2
        id="guided-intro-heading"
        className="max-w-2xl text-xl font-medium tracking-[-0.02em] text-psa-snow sm:text-2xl"
      >
        {containersAtRisk} transshipment containers at risk — {expediteSlots} expedite
        slots available.
      </h2>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-psa-chalk">
        Walk through a synthetic late-vessel disruption: allocation under uncertainty, evidence
        boundaries, human authority, and deterministic cargo safety.
      </p>

      <button
        type="button"
        disabled={loading}
        onClick={onStart}
        className="psa-btn psa-btn-primary mt-6"
      >
        Start recovery demo
      </button>

      <ul className="mt-6 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:gap-x-5">
        {PROOF_POINTS.map((point) => (
          <li key={point} className="text-xs text-psa-steel">
            {point}
          </li>
        ))}
      </ul>
    </div>
  );
}
