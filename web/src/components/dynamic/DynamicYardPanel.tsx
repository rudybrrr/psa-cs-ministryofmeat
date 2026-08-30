import type {
  AllocationRevision,
  ExpediteCommitment,
  YardForecastSnapshot,
} from "../../api/types";

export function DynamicYardPanel({
  snapshots,
  revisions,
  commitments,
  loading,
  onBootstrap,
  onActive,
}: {
  snapshots: YardForecastSnapshot[];
  revisions: AllocationRevision[];
  commitments: ExpediteCommitment[];
  loading: boolean;
  onBootstrap(): void;
  onActive(): void;
}) {
  const active = revisions.at(-1);
  const prior = revisions.at(-2);
  const relevant = new Set([
    ...(active?.allocated_container_ids ?? []),
    ...(prior?.allocated_container_ids ?? []),
    ...commitments.map((item) => item.container_id),
  ]);

  return (
    <section className="psa-surface rounded-[10px] p-4">
      <p className="psa-label">Dynamic yard / uncertainty</p>
      <h2 className="mt-1 text-sm font-semibold text-psa-snow">
        Forecast and allocation revision
      </h2>
      {snapshots.map((snapshot) => (
        <div key={snapshot.id} className="mt-3">
          <p className="font-mono text-xs text-psa-chalk">
            {snapshot.stage} —{" "}
            {snapshot.stage === "PRE_DISCHARGE" ? "wide uncertainty" : "tighter forecast band"}
          </p>
          <div className="mt-1 grid gap-1 text-xs text-psa-steel">
            {snapshot.container_forecasts
              .filter((f) => relevant.size === 0 || relevant.has(f.container_id))
              .map((f) => (
                <span key={f.container_id}>
                  {f.container_id}: p10 {f.p10_ready_at.slice(11, 16)} · p50{" "}
                  {f.p50_ready_at.slice(11, 16)} · p90 {f.p90_ready_at.slice(11, 16)}
                </span>
              ))}
          </div>
        </div>
      ))}
      {active ? (
        <div className="psa-surface-nested mt-3 rounded-[6px] p-3 text-xs text-psa-chalk">
          <b className="text-psa-snow">
            {prior ? `R${revisions.length - 2} → R${revisions.length - 1}` : `R${revisions.length - 1}`}
          </b>
          {prior ? (
            <>
              {" "}
              · {prior.preserved_connection_total} → {active.preserved_connection_total}{" "}
              synthetic scenario-world total across 50 worlds · expected{" "}
              {prior.expected_preserved_connections.toFixed(2)} →{" "}
              {active.expected_preserved_connections.toFixed(2)}
            </>
          ) : null}
          <p className="mt-1">Allocated: {active.allocated_container_ids.join(", ")}</p>
          <p>Locked: {active.locked_container_ids.join(", ") || "—"}</p>
          <p className="text-psa-steel">{active.reason}</p>
        </div>
      ) : null}
      <p className="mt-3 text-xs text-psa-steel">
        Commitments:{" "}
        {commitments
          .map(
            (item) =>
              `${item.container_id} ${active?.allocated_container_ids.includes(item.container_id) ? "IN" : "OUT"} ${item.status}`,
          )
          .join(" · ") || "—"}
      </p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={onBootstrap}
          className="psa-btn-secondary px-3 py-2 text-xs"
        >
          Bootstrap PRE_DISCHARGE
        </button>
        <button
          type="button"
          disabled={loading || !snapshots.length}
          onClick={onActive}
          className="psa-btn-secondary px-3 py-2 text-xs disabled:opacity-50"
        >
          Publish DISCHARGE_ACTIVE
        </button>
      </div>
    </section>
  );
}
