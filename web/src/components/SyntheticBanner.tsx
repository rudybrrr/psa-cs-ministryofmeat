export function SyntheticBanner() {
  return (
    <div className="border-b border-white/10 bg-psa-graphite px-4 py-2">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
        <p className="psa-label text-psa-amber">SYNTHETIC DATA</p>
        <p className="text-sm text-psa-chalk">
          All vessel, container, yard, and timing values shown here are{" "}
          <span className="font-medium text-psa-snow">SYNTHETIC</span> demo fixtures
          for Tuas terminal recovery operations.
        </p>
      </div>
    </div>
  );
}
