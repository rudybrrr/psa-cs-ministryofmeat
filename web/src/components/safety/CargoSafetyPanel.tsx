import type { CargoSafetyHistory, CargoSafetyReview } from "../../api/types";

export function CargoSafetyPanel({
  reviews,
  histories,
  loading,
  onEvaluate,
  onCreateCanonical,
}: {
  reviews: CargoSafetyReview[];
  histories: CargoSafetyHistory[];
  loading: boolean;
  onEvaluate(id: string): void;
  onCreateCanonical(): void;
}) {
  return (
    <section className="psa-surface rounded-[10px] p-4">
      <h2 className="text-sm font-semibold text-psa-snow">Cargo safety review</h2>
      <p className="mt-1 text-xs text-psa-steel">
        Semantic AI detects inconsistency. Deterministic policy decides whether automation
        may proceed.
      </p>
      {reviews.length === 0 ? (
        <button
          type="button"
          disabled={loading}
          onClick={onCreateCanonical}
          className="psa-btn-secondary mt-3 px-3 py-2 text-xs"
        >
          Persist SYN-CNT-010 canonical contradiction
        </button>
      ) : null}
      {reviews.map((review) => {
        const history = histories.find((h) => h.review.id === review.id);
        const a = history?.assessment;
        const p = history?.policy_result;
        return (
          <div
            className="psa-surface-nested mt-3 rounded-[6px] p-3 text-xs text-psa-chalk"
            key={review.id}
          >
            <b className="text-psa-snow">{review.container_id}</b>
            <p>Review: {review.state}</p>
            <p>
              Trusted declaration: DG {a ? String(a.structured_dangerous_goods) : "pending"} · UN{" "}
              {a?.structured_un_number ?? "—"} · commodity {a?.structured_commodity ?? "—"}
            </p>
            <p>
              Untrusted note: {history?.note.text ?? "pending"} ({history?.note.source ?? "—"})
            </p>
            <p>Semantic result: {a?.result ?? "pending"}</p>
            {a ? (
              <>
                <p>Evidence: {a.evidence_excerpt ?? "—"}</p>
                <p>Explanation: {a.explanation}</p>
              </>
            ) : null}
            <p>
              Deterministic policy:{" "}
              {p ? `${p.disposition} · automation blocked ${String(p.automation_blocked)}` : "pending"}
            </p>
            {p ? <p className="text-psa-steel">Policy reason: {p.reason}</p> : null}
            {review.state === "PENDING_CHECK" ? (
              <button
                type="button"
                disabled={loading}
                onClick={() => onEvaluate(review.id)}
                className="psa-btn-secondary mt-2 px-3 py-2 text-xs"
              >
                Evaluate review
              </button>
            ) : null}
          </div>
        );
      })}
    </section>
  );
}
