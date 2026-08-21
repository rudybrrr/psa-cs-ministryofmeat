export function SyntheticBanner() {
  return (
    <div className="border-b border-amber-500/40 bg-amber-950/80 px-4 py-2 text-amber-100">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-amber-300">
          Synthetic operations data
        </p>
        <p className="text-sm">
          All vessel, container, yard, and timing values shown here are{" "}
          <span className="font-semibold text-amber-200">SYNTHETIC</span> demo
          fixtures for Tuas terminal recovery operations.
        </p>
      </div>
    </div>
  );
}
