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

const MODE_ITEMS: Array<{ id: ConsoleMode; label: string }> = [
  { id: "guided", label: "Guided" },
  { id: "auto", label: "Auto" },
  { id: "explore", label: "Explore" },
];

const MODE_ARIA: Record<ConsoleMode, string> = {
  guided: "Guided demo",
  auto: "Auto replay",
  explore: "Explore",
};

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
    <aside className="psa-surface-chrome sticky top-0 flex h-screen w-[236px] shrink-0 flex-col overflow-hidden border-r border-white/10">
      <div className="border-b border-white/8 px-4 py-4">
        <img
          src="/reroute-logo-white.png"
          alt="ReRoute"
          className="h-7 w-auto max-w-full"
        />
        <p className="mt-2 text-[11px] text-psa-steel">Tuas terminal · synthetic demo</p>
      </div>

      <nav aria-label="Workspace" className="flex-1 overflow-y-auto px-2 py-3">
        <p className="px-2 pb-2 psa-meta">Workspace</p>
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
                  className={`flex w-full items-center gap-2 rounded-[6px] px-2.5 py-2 text-left text-[13px] transition-colors ${
                    active
                      ? "bg-psa-slate font-medium text-psa-snow"
                      : "text-psa-fog hover:bg-psa-charcoal/90 hover:text-psa-chalk"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5 shrink-0 opacity-80" />
                  <span>{item.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-white/10 px-3 py-4">
        <p className="px-1 pb-2 text-[10px] font-medium uppercase tracking-[0.12em] text-psa-steel">
          Presentation mode
        </p>
        <div className="psa-segment" role="group" aria-label="Presentation mode">
          {MODE_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={mode === item.id}
              aria-label={MODE_ARIA[item.id]}
              onClick={() => onModeChange(item.id)}
              className="psa-segment__btn"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-white/8 px-4 py-3">
        <div className="flex items-center gap-2 text-[11px] text-psa-steel">
          <span
            className={`h-1.5 w-1.5 shrink-0 rounded-full ${
              apiStatus === "ready"
                ? "bg-psa-fern"
                : apiStatus === "loading"
                  ? "bg-psa-amber"
                  : "bg-psa-coral"
            }`}
            aria-hidden
          />
          <span>
            {apiStatus === "ready"
              ? "Backend connected"
              : apiStatus === "loading"
                ? "Syncing…"
                : "Connection error"}
          </span>
        </div>
      </div>
    </aside>
  );
}
