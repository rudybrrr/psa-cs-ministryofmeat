import { useMemo, useState } from "react";

import { ContainerRecoveryTable } from "../../recovery/ContainerRecoveryTable";
import type { ContainerRecoveryRow } from "../../../lib/recoverySelectors";

export function ContainersWorkspace({
  rows,
  selectedContainerId,
  selectedContainer,
  loading,
  onSelectContainer,
}: {
  rows: ContainerRecoveryRow[];
  selectedContainerId: string | null;
  selectedContainer: ContainerRecoveryRow | null;
  loading: boolean;
  onSelectContainer(containerId: string): void;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter(
      (row) =>
        row.containerId.toLowerCase().includes(needle) ||
        row.connectionId.toLowerCase().includes(needle) ||
        row.serviceId.toLowerCase().includes(needle),
    );
  }, [query, rows]);

  return (
    <div className="space-y-4">
      <header className="psa-surface rounded-[12px] px-5 py-4">
        <p className="psa-label text-psa-signal">Containers workspace</p>
        <h2 className="mt-1 text-lg font-medium text-psa-snow">Container recovery</h2>
        <p className="mt-2 text-sm text-psa-chalk">
          {rows.length} containers under recovery analysis. Select a row for allocation, forecast,
          commitment, and safety disposition detail.
        </p>
        <label className="mt-4 block max-w-md">
          <span className="sr-only">Search containers</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter by container, connection, or service…"
            className="w-full rounded-[8px] border border-white/12 bg-psa-slate px-3 py-2.5 text-sm text-psa-snow placeholder:text-psa-steel focus:border-psa-signal/50 focus:outline-none focus:ring-2 focus:ring-psa-signal/25"
          />
        </label>
      </header>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.8fr)]">
        <ContainerRecoveryTable
          rows={filtered}
          selectedContainerId={selectedContainerId}
          onSelect={onSelectContainer}
          loading={loading}
        />

        <aside className="psa-surface rounded-[12px] px-4 py-4">
          <p className="psa-label">Selected container</p>
          {selectedContainer ? (
            <dl className="mt-3 space-y-3 text-sm">
              <div>
                <dt className="psa-label">Container</dt>
                <dd className="mt-1 font-mono text-psa-snow">{selectedContainer.containerId}</dd>
              </div>
              <div>
                <dt className="psa-label">Connection</dt>
                <dd className="mt-1 font-mono text-psa-chalk">{selectedContainer.connectionId}</dd>
              </div>
              <div>
                <dt className="psa-label">Service</dt>
                <dd className="mt-1 text-psa-chalk">{selectedContainer.serviceId}</dd>
              </div>
              <div>
                <dt className="psa-label">Allocation</dt>
                <dd className="mt-1 text-psa-chalk">
                  {selectedContainer.expediteAllocated ? "IN" : "OUT"}
                </dd>
              </div>
              <div>
                <dt className="psa-label">Forecast</dt>
                <dd className="mt-1 text-psa-chalk">{selectedContainer.forecastBand ?? "—"}</dd>
              </div>
              <div>
                <dt className="psa-label">Commitment</dt>
                <dd className="mt-1 text-psa-chalk">{selectedContainer.commitmentStatus ?? "—"}</dd>
              </div>
              <div>
                <dt className="psa-label">Decision</dt>
                <dd className="mt-1 text-psa-chalk">
                  {selectedContainer.decisionAction
                    ? `${selectedContainer.decisionAction} (${selectedContainer.decisionStatus ?? "—"})`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="psa-label">Carrier state</dt>
                <dd className="mt-1 text-psa-chalk">{selectedContainer.carrierCaseState ?? "—"}</dd>
              </div>
              <div>
                <dt className="psa-label">Safety</dt>
                <dd className="mt-1 text-psa-chalk">{selectedContainer.safetyWarning ?? "—"}</dd>
              </div>
              <div>
                <dt className="psa-label">Disposition</dt>
                <dd className="mt-1 text-psa-chalk">{selectedContainer.displayDisposition}</dd>
              </div>
            </dl>
          ) : (
            <p className="mt-3 text-sm text-psa-steel">Select a container from the table.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
