import type { ConsoleMode } from "./ModeSwitcher";
import {
  IconCarrier,
  IconContainers,
  IconEvidence,
  IconOverview,
  IconRecovery,
} from "./icons";

export type DashboardNavId =
  | "overview"
  | "recovery"
  | "containers"
  | "carrier"
  | "evidence";

const NAV_ITEMS: Array<{
  id: DashboardNavId;
  label: string;
  icon: typeof IconOverview;
}> = [
  { id: "overview", label: "Overview", icon: IconOverview },
  { id: "recovery", label: "Recovery", icon: IconRecovery },
  { id: "containers", label: "Containers", icon: IconContainers },
  { id: "carrier", label: "Carrier", icon: IconCarrier },
  { id: "evidence", label: "Evidence / Audit", icon: IconEvidence },
];

const MODE_ITEMS: Array<{ id: ConsoleMode; label: string; description: string }> = [
  { id: "guided", label: "Guided demo", description: "Judge-facing narrative" },
  { id: "auto", label: "Auto replay", description: "Automatic playback" },
  { id: "explore", label: "Explore", description: "Technical inspection" },
];

export function DashboardSidebar({
  workspace,
  onWorkspaceChange,
  mode,
  onModeChange,
  apiStatus,
}: {
  workspace: DashboardNavId;
  onWorkspaceChange(workspace: DashboardNavId): void;
  mode: ConsoleMode;
  onModeChange(mode: ConsoleMode): void;
  apiStatus: "ready" | "loading" | "error";
}) {
  return (
    <aside className="psa-surface-chrome sticky top-0 flex h-screen w-[240px] shrink-0 flex-col overflow-hidden border-r border-white/12 shadow-[inset_-1px_0_0_rgba(255,255,255,0.04)]">
      <div className="border-b border-white/10 px-4 py-4">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-psa-slate text-psa-signal ring-1 ring-white/10">
            <IconRecovery className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium text-psa-snow">PSA Recovery</p>
            <p className="truncate text-[11px] text-psa-steel">Tuas · synthetic demo</p>
          </div>
        </div>
      </div>

      <nav aria-label="Workspace" className="flex-1 overflow-y-auto px-2 py-3">
        <p className="px-2 pb-2 psa-label">Workspace</p>
        <ul className="space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = item.id === workspace;
            const Icon = item.icon;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => onWorkspaceChange(item.id)}
                  aria-current={active ? "page" : undefined}
                  className={`flex w-full items-center gap-2.5 rounded-[8px] px-3 py-2.5 text-left text-sm transition-colors ${
                    active
                      ? "bg-psa-slate font-medium text-psa-snow ring-1 ring-white/12"
                      : "text-psa-fog hover:bg-psa-charcoal/80 hover:text-psa-chalk"
                  }`}
                >
                  <Icon className={`h-4 w-4 shrink-0 ${active ? "text-psa-chalk" : ""}`} />
                  <span>{item.label}</span>
                </button>
              </li>
            );
          })}
        </ul>

        <p className="mt-6 px-2 pb-2 psa-label">Presentation mode</p>
        <div
          className="mx-1 flex flex-col gap-1 rounded-[10px] border border-dashed border-white/14 bg-psa-charcoal/60 p-1"
          role="group"
          aria-label="Presentation mode"
        >
          {MODE_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={mode === item.id}
              onClick={() => onModeChange(item.id)}
              className={`rounded-[8px] px-3 py-2.5 text-left transition-colors ${
                mode === item.id
                  ? "bg-psa-graphite text-psa-snow ring-1 ring-psa-signal/35"
                  : "text-psa-fog hover:bg-psa-slate/50 hover:text-psa-chalk"
              }`}
              aria-label={item.label}
            >
              <span className="block text-xs font-medium">{item.label}</span>
              <span className="mt-0.5 block text-[10px] text-psa-steel">{item.description}</span>
            </button>
          ))}
        </div>
      </nav>

      <div className="border-t border-white/10 px-4 py-3">
        <p className="psa-label">API status</p>
        <div className="mt-2 flex items-center gap-2">
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${
              apiStatus === "ready"
                ? "bg-psa-fern"
                : apiStatus === "loading"
                  ? "bg-psa-amber"
                  : "bg-psa-coral"
            }`}
            aria-hidden
          />
          <p className="text-xs text-psa-chalk">
            {apiStatus === "ready"
              ? "Backend connected"
              : apiStatus === "loading"
                ? "Syncing state…"
                : "Connection error"}
          </p>
        </div>
        <p className="mt-1 text-[11px] text-psa-steel">Synthetic fixtures only</p>
      </div>
    </aside>
  );
}
