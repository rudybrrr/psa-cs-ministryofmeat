import type { ContainerRecoveryRow } from "../../../lib/recoverySelectors";
import { connectionShortLabel } from "../../../lib/formatters";

export function GuidedContainerOverview({
  rows,
  selectedContainerId,
  onSelect,
  defaultOpen = false,
}: {
  rows: ContainerRecoveryRow[];
  selectedContainerId: string | null;
  onSelect: (containerId: string) => void;
  defaultOpen?: boolean;
}) {
  if (rows.length === 0) return null;

  return (
    <details className="rounded-[10px] border border-white/8 bg-psa-charcoal/30 px-4 py-3" open={defaultOpen}>
      <summary className="cursor-pointer text-sm font-medium text-psa-snow">
        Affected containers ({rows.length})
      </summary>
      <div className="mt-3 overflow-x-auto">
        <table
          aria-label="Affected containers"
          className="min-w-full border-collapse text-xs"
        >
          <thead>
            <tr className="border-b border-psa-graphite text-left font-mono text-[10px] uppercase tracking-wide text-psa-steel">
              <th className="px-2 py-1.5 font-normal">Container</th>
              <th className="px-2 py-1.5 font-normal">Connection</th>
              <th className="px-2 py-1.5 font-normal">Expedite</th>
              <th className="px-2 py-1.5 font-normal">Carrier</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.containerId}
                className={`cursor-pointer border-b border-psa-graphite/60 ${
                  row.containerId === selectedContainerId ? "bg-psa-graphite/40" : ""
                }`}
                onClick={() => onSelect(row.containerId)}
              >
                <td className="px-2 py-2 font-mono text-psa-chalk">{row.containerId}</td>
                <td className="px-2 py-2 font-mono text-psa-fog">
                  {connectionShortLabel(row.connectionId)}
                </td>
                <td className="px-2 py-2 text-psa-fog">
                  {row.expediteAllocated ? "allocated" : "—"}
                </td>
                <td className="px-2 py-2 text-psa-fog">
                  {row.carrierCaseState?.replaceAll("_", " ") ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
