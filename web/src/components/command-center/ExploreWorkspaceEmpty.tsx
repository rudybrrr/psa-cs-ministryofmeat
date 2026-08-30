import type { DashboardNavId } from "./DashboardSidebar";

const TAB_COPY: Record<
  Exclude<DashboardNavId, "overview">,
  { title: string; body: string }
> = {
  recovery: {
    title: "Recovery planning",
    body: "Yard forecasts, allocation revisions, expedite commitments, and tradeoff reviews appear here once the guided demo creates an incident.",
  },
  containers: {
    title: "Container dispositions",
    body: "Per-container allocation, carrier case state, and safety warnings populate after scarce-capacity optimization runs.",
  },
  carrier: {
    title: "Carrier coordination",
    body: "RTA proposals, approvals, carrier responses, and counter-approval gates surface when a connection enters carrier recovery.",
  },
  evidence: {
    title: "Evidence and audit",
    body: "Agent tool traces, authorization fingerprints, cargo safety reviews, and audit events accumulate as the recovery sequence advances.",
  },
};

export function ExploreWorkspaceEmpty({
  tab,
  onStartGuided,
  loading,
}: {
  tab: Exclude<DashboardNavId, "overview">;
  onStartGuided(): void;
  loading: boolean;
}) {
  const copy = TAB_COPY[tab];

  return (
    <section className="psa-surface max-w-2xl rounded-[12px] px-6 py-8">
      <p className="psa-meta">Explore · {copy.title}</p>
      <h2 className="mt-2 text-lg font-medium tracking-[-0.02em] text-psa-snow">
        No recovery session yet
      </h2>
      <p className="mt-3 text-sm leading-relaxed text-psa-chalk">{copy.body}</p>
      <button
        type="button"
        disabled={loading}
        onClick={onStartGuided}
        className="psa-btn psa-btn-primary mt-6"
      >
        Start guided demo
      </button>
    </section>
  );
}
