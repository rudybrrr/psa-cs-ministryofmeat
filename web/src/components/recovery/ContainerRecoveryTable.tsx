import type { ContainerRecoveryRow } from "../../lib/recoverySelectors";
import { connectionShortLabel } from "../../lib/formatters";
import { RecoveryStatusBadge } from "./RecoveryStatusBadge";

interface ContainerRecoveryTableProps {
  rows: ContainerRecoveryRow[];
  selectedContainerId: string | null;
  onSelect: (containerId: string) => void;
  loading?: boolean;
}

function badgeToneForRow(row: ContainerRecoveryRow) {
  if (row.carrierCaseState === "AWAITING_COUNTER_APPROVAL") {
    return "warning" as const;
  }
  if (row.carrierCaseState === "COMPLETED") {
    return "success" as const;
  }
  if (row.carrierCaseState === "ESCALATED") {
    return "danger" as const;
  }
  if (row.expediteAllocated) {
    return "info" as const;
  }
  return "neutral" as const;
}

export function ContainerRecoveryTable({
  rows,
  selectedContainerId,
  onSelect,
  loading = false,
}: ContainerRecoveryTableProps) {
  return (
    <section className="rounded border border-slate-800 bg-slate-950/60">
      <div className="border-b border-slate-800 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-100">
          Container recovery workspace
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Live join of canonical fixture, persisted scarcity allocation, decisions,
          and carrier recovery state. Select a row to open connection-scoped
          recovery controls.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table
          aria-label="Container recovery table"
          className="min-w-full border-collapse text-sm"
        >
          <thead>
            <tr className="border-b border-slate-800 text-left font-mono text-[11px] uppercase tracking-wide text-slate-500">
              <th className="px-3 py-2 font-normal">Container</th>
              <th className="px-3 py-2 font-normal">Service</th>
              <th className="px-3 py-2 font-normal">Connection</th>
              <th className="px-3 py-2 font-normal">Cargo</th>
              <th className="px-3 py-2 font-normal">Expedite</th>
              <th className="px-3 py-2 font-normal">Forecast</th>
              <th className="px-3 py-2 font-normal">Commitment</th>
              <th className="px-3 py-2 font-normal">Decision</th>
              <th className="px-3 py-2 font-normal">Carrier case</th>
              <th className="px-3 py-2 font-normal">Safety</th>
              <th className="px-3 py-2 font-normal">Disposition</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const selected = row.containerId === selectedContainerId;
              return (
                <tr
                  key={row.containerId}
                  className={`cursor-pointer border-b border-slate-900/80 ${selected ? "bg-slate-800/60" : "hover:bg-slate-900/40"}`}
                  onClick={() => onSelect(row.containerId)}
                >
                  <td className="px-3 py-3 font-mono text-slate-200">
                    {row.containerId}
                  </td>
                  <td className="px-3 py-3 font-mono text-slate-300">
                    {row.serviceId}
                  </td>
                  <td className="px-3 py-3 font-mono text-slate-300">
                    {connectionShortLabel(row.connectionId)}
                  </td>
                  <td className="px-3 py-3 font-mono text-slate-300">
                    {row.cargoKind}
                  </td>
                  <td className="px-3 py-3">
                    <RecoveryStatusBadge
                      label={row.expediteAllocated ? "allocated" : "not allocated"}
                      tone={row.expediteAllocated ? "success" : "neutral"}
                    />
                  </td>
                  <td className="px-3 py-3 text-xs text-slate-300">{row.forecastBand ?? "—"}</td>
                  <td className="px-3 py-3 text-xs text-slate-300">{row.commitmentStatus ?? "—"}</td>
                  <td className="px-3 py-3 font-mono text-xs text-slate-300">
                    {row.decisionAction ?? "—"}
                    {row.decisionStatus ? ` · ${row.decisionStatus}` : ""}
                  </td>
                  <td className="px-3 py-3">
                    {row.carrierCaseState ? (
                      <RecoveryStatusBadge
                        label={row.carrierCaseState.replaceAll("_", " ")}
                        tone={badgeToneForRow(row)}
                      />
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-xs text-rose-200">{row.safetyWarning ?? "—"}</td>
                  <td className="px-3 py-3 text-slate-300">{row.displayDisposition}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {rows.length === 0 && (
        <p className="px-4 py-6 text-sm text-slate-500">
          {loading ? "Loading container recovery rows…" : "No container rows available."}
        </p>
      )}
    </section>
  );
}
