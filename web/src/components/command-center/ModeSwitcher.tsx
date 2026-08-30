export type ConsoleMode = "guided" | "auto" | "explore";

export function ModeSwitcher({
  mode,
  onChange,
}: {
  mode: ConsoleMode;
  onChange(mode: ConsoleMode): void;
}) {
  const items: Array<{ id: ConsoleMode; label: string }> = [
    { id: "guided", label: "Guided demo" },
    { id: "auto", label: "Auto replay" },
    { id: "explore", label: "Explore" },
  ];

  return (
    <div
      className="psa-surface-nested inline-flex gap-1 rounded-[10px] p-1"
      role="group"
      aria-label="Console mode"
    >
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          aria-pressed={mode === item.id}
          onClick={() => onChange(item.id)}
          className={`rounded-[8px] px-3 py-1.5 text-xs font-medium transition-colors ${
            mode === item.id
              ? "bg-psa-charcoal text-psa-snow"
              : "text-psa-fog hover:text-psa-chalk"
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
