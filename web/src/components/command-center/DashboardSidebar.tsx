import type { ConsoleMode } from "./ModeSwitcher";

export type DashboardNavId =
  | "overview"
  | "recovery"
  | "containers"
  | "carrier"
  | "evidence";

const NAV_ITEMS: Array<{ id: DashboardNavId; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "recovery", label: "Recovery" },
  { id: "containers", label: "Containers" },
  { id: "carrier", label: "Carrier" },
  { id: "evidence", label: "Evidence / Audit" },
];

const MODE_ITEMS: Array<{ id: ConsoleMode; label: string }> = [
  { id: "guided", label: "Guided demo" },
  { id: "auto", label: "Auto replay" },
  { id: "explore", label: "Explore" },
];

export function DashboardSidebar({
  mode,
  onModeChange,
  apiStatus,
  incidentLoaded,
}: {
  mode: ConsoleMode;
  onModeChange(mode: ConsoleMode): void;
  apiStatus: "ready" | "loading" | "error";
  incidentLoaded: boolean;
}) {
  const activeNav: DashboardNavId = incidentLoaded ? "recovery" : "overview";

  return (
    <aside className="flex h-full w-[240px] shrink-0 flex-col border-r border-white/10 bg-psa-graphite">
      <div className="border-b border-white/10 px-4 py-4">
        <p className="psa-label text-psa-signal">PSA Recovery</p>
        <p className="mt-1 text-sm font-medium text-psa-snow">Ministry of Meat</p>
        <p className="mt-1 text-xs text-psa-steel">Tuas terminal · synthetic demo</p>
      </div>

      <nav aria-label="Primary" className="flex-1 px-2 py-3">
        <p className="px-2 pb-2 psa-label">Workspace</p>
        <ul className="space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = item.id === activeNav;
            return (
              <li key={item.id}>
                <span
                  className={`flex w-full items-center rounded-[8px] px-3 py-2 text-sm ${
                    active
                      ? "bg-psa-charcoal font-medium text-psa-snow ring-1 ring-white/10"
                      : "text-psa-fog"
                  }`}
                  aria-current={active ? "page" : undefined}
                >
                  {item.label}
                </span>
              </li>
            );
          })}
        </ul>

        <p className="mt-6 px-2 pb-2 psa-label">Presentation mode</p>
        <div
          className="mx-1 flex flex-col gap-1 rounded-[10px] border border-white/10 bg-psa-charcoal p-1"
          role="group"
          aria-label="Console mode"
        >
          {MODE_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={mode === item.id}
              onClick={() => onModeChange(item.id)}
              className={`rounded-[8px] px-3 py-2 text-left text-xs font-medium transition-colors ${
                mode === item.id
                  ? "bg-psa-slate text-psa-snow ring-1 ring-white/12"
                  : "text-psa-fog hover:bg-psa-slate/60 hover:text-psa-chalk"
              }`}
            >
              {item.label}
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
