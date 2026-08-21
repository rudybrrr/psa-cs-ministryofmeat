import type { AuditActor } from "../api/types";

const ACTOR_STYLES: Record<
  AuditActor,
  { label: string; className: string; description: string }
> = {
  SYSTEM: {
    label: "SYSTEM",
    className: "border-slate-500/60 bg-slate-800 text-slate-100",
    description: "Deterministic workflow and integrations",
  },
  POLICY: {
    label: "POLICY",
    className: "border-violet-500/60 bg-violet-950 text-violet-100",
    description: "Policy engine evaluations",
  },
  OPERATOR: {
    label: "OPERATOR",
    className: "border-emerald-500/60 bg-emerald-950 text-emerald-100",
    description: "Human approvals and overrides",
  },
  CARRIER: {
    label: "CARRIER",
    className: "border-amber-500/60 bg-amber-950 text-amber-100",
    description: "External carrier responses",
  },
  AGENT: {
    label: "AGENT",
    className: "border-cyan-500/60 bg-cyan-950 text-cyan-100",
    description: "LLM agent reasoning actions",
  },
  SOLVER: {
    label: "SOLVER",
    className: "border-indigo-500/60 bg-indigo-950 text-indigo-100",
    description: "Optimization solver outputs",
  },
};

interface ActorBadgeProps {
  actor: AuditActor;
  compact?: boolean;
}

export function ActorBadge({ actor, compact = false }: ActorBadgeProps) {
  const style = ACTOR_STYLES[actor];

  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wide ${style.className}`}
      title={style.description}
    >
      {compact ? style.label.slice(0, 3) : style.label}
    </span>
  );
}

export function ActorLegend() {
  const legendActors: AuditActor[] = [
    "SYSTEM",
    "POLICY",
    "OPERATOR",
    "CARRIER",
    "AGENT",
  ];

  return (
    <div className="flex flex-wrap gap-2">
      {legendActors.map((actor) => (
        <ActorBadge key={actor} actor={actor} />
      ))}
    </div>
  );
}
