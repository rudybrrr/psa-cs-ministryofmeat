import { IconCarrier, IconContainers, IconEvidence, IconRecovery } from "./icons";

const CAPABILITIES = [
  {
    icon: IconContainers,
    title: "Containers",
    detail: "Allocation, forecast, commitment, and safety disposition per container.",
  },
  {
    icon: IconCarrier,
    title: "Carrier recovery",
    detail: "RTA requests, authorization state, carrier responses, and decision lineage.",
  },
  {
    icon: IconRecovery,
    title: "Agent trace",
    detail: "Durable AgentRun steps, tool invocations, and wait boundaries.",
  },
  {
    icon: IconEvidence,
    title: "Evidence / audit",
    detail: "Audit timeline, approval bindings, and expandable raw payloads.",
  },
] as const;

export function ExploreAvailability({
  loading,
  storedIncidentId,
  onStartGuided,
  onResume,
}: {
  loading: boolean;
  storedIncidentId: string | null;
  onStartGuided(): void;
  onResume(): void;
}) {
  return (
    <section className="psa-surface overflow-hidden rounded-[12px]">
      <div className="border-b border-white/10 px-6 py-8 sm:px-8">
        <p className="psa-label text-psa-signal">Explore workspace</p>
        <h2 className="mt-2 text-2xl font-medium tracking-[-0.02em] text-psa-snow">
          Inspect recovery operations in depth
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-psa-chalk">
          Start or resume a recovery session to inspect containers, carrier coordination, agent
          trace, and evidence surfaces. Explore mode exposes technical detail without changing
          backend semantics.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            disabled={loading}
            onClick={onStartGuided}
            className="psa-btn psa-btn-primary"
          >
            Start guided demo
          </button>
          {storedIncidentId ? (
            <button
              type="button"
              disabled={loading}
              onClick={onResume}
              className="psa-btn psa-btn-secondary"
            >
              Resume saved incident
            </button>
          ) : null}
        </div>
      </div>

      <div className="grid gap-px bg-white/10 sm:grid-cols-2">
        {CAPABILITIES.map(({ icon: Icon, title, detail }) => (
          <div key={title} className="bg-psa-charcoal px-5 py-5">
            <div className="flex items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-psa-slate text-psa-chalk">
                <Icon className="h-4 w-4" />
              </span>
              <div>
                <p className="text-sm font-medium text-psa-snow">{title}</p>
                <p className="mt-1 text-xs leading-relaxed text-psa-steel">{detail}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
