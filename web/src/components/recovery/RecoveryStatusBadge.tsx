interface RecoveryStatusBadgeProps {
  label: string;
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
}

const toneClasses: Record<NonNullable<RecoveryStatusBadgeProps["tone"]>, string> = {
  neutral: "border-slate-600 bg-slate-900 text-slate-200",
  success: "border-emerald-500/50 bg-emerald-950/50 text-emerald-100",
  warning: "border-amber-500/50 bg-amber-950/40 text-amber-100",
  danger: "border-rose-500/50 bg-rose-950/40 text-rose-100",
  info: "border-sky-500/50 bg-sky-950/40 text-sky-100",
};

export function RecoveryStatusBadge({
  label,
  tone = "neutral",
}: RecoveryStatusBadgeProps) {
  return (
    <span
      className={`inline-flex rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${toneClasses[tone]}`}
    >
      {label}
    </span>
  );
}
