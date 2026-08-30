export function LoadingIndicator({
  label,
  className = "",
}: {
  label: string;
  className?: string;
}) {
  return (
    <div
      className={`psa-surface flex items-center gap-3 rounded-[10px] px-4 py-3 ${className}`}
      role="status"
      aria-live="polite"
    >
      <span
        className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-psa-steel/40 border-t-psa-signal"
        aria-hidden
      />
      <p className="text-sm text-psa-chalk">{label}</p>
    </div>
  );
}
