import type { ReactNode } from "react";

export function ChapterFrame({
  label,
  title,
  children,
}: {
  label: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="psa-surface rounded-[12px] px-5 py-5" data-chapter-panel>
      <p className="psa-label text-psa-signal">{label}</p>
      <h2 className="mt-2 text-lg font-medium tracking-[-0.02em] text-psa-snow">{title}</h2>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

export function MetricCard({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="psa-surface-nested rounded-[8px] px-3 py-3">
      <p className="psa-label">{label}</p>
      <p className={`psa-kpi mt-1 text-xl ${accent ? "text-psa-signal" : "text-psa-snow"}`}>
        {value}
      </p>
    </div>
  );
}

export function ComparisonColumn({
  heading,
  children,
  light = false,
}: {
  heading: string;
  children: ReactNode;
  light?: boolean;
}) {
  return (
    <div
      className={
        light
          ? "psa-data-surface rounded-[8px] px-4 py-4"
          : "psa-surface-nested rounded-[8px] px-4 py-4"
      }
    >
      <p className={light ? "text-[11px] font-medium uppercase tracking-[0.12em] text-psa-data-ink/60" : "psa-label"}>
        {heading}
      </p>
      <div
        className={`mt-3 space-y-2 text-sm ${light ? "text-psa-data-ink" : "text-psa-chalk"}`}
      >
        {children}
      </div>
    </div>
  );
}
