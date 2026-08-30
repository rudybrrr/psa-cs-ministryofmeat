import type { ReactNode } from "react";

export type ChapterEvidenceTone =
  | "optimize"
  | "adapt"
  | "coordinate"
  | "respond"
  | "protect";

export function ChapterFrame({
  label,
  title,
  children,
  evidence,
  quiet = false,
}: {
  label: string;
  title: string;
  children: ReactNode;
  evidence?: ChapterEvidenceTone;
  quiet?: boolean;
}) {
  return (
    <section className="rounded-[12px] border border-white/8 bg-psa-charcoal/40 px-5 py-5" data-chapter-panel>
      {!quiet ? <p className="psa-meta">{label}</p> : null}
      <h2
        className={`font-medium tracking-[-0.02em] text-psa-snow ${
          quiet ? "text-base" : "mt-1.5 text-lg"
        }`}
      >
        {title}
      </h2>
      <div className="mt-3 space-y-4 divide-y divide-white/8 [&>*:first-child]:pt-0 [&>*]:pt-4">
        {children}
      </div>
      {evidence ? <span className="sr-only" data-evidence-tone={evidence} /> : null}
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
    <div className="min-w-0 !pt-0">
      <p className="psa-meta">{label}</p>
      <p className={`psa-kpi mt-1 text-xl ${accent ? "text-psa-signal" : "text-psa-snow"}`}>
        {value}
      </p>
    </div>
  );
}

export function ComparisonColumn({
  heading,
  children,
  tone,
  light = false,
}: {
  heading: string;
  children: ReactNode;
  tone?: ChapterEvidenceTone;
  light?: boolean;
}) {
  const resolvedTone = tone ?? (light ? "adapt" : undefined);

  if (resolvedTone) {
    return (
      <div className={`psa-evidence psa-evidence--${resolvedTone} !pt-4 px-3 py-3 sm:px-4`}>
        <p className="psa-evidence__title text-[12px] font-medium">{heading}</p>
        <div className="mt-3 space-y-2 text-sm text-psa-data-ink">{children}</div>
      </div>
    );
  }

  return (
    <div className="min-w-0 !pt-4">
      <p className="psa-meta">{heading}</p>
      <div className="mt-2 space-y-2 text-sm text-psa-chalk">{children}</div>
    </div>
  );
}

export function EvidencePanel({
  title,
  tone,
  children,
}: {
  title: string;
  tone: ChapterEvidenceTone;
  children: ReactNode;
}) {
  return (
    <div className={`psa-evidence psa-evidence--${tone} !pt-4 px-3 py-3 sm:px-4`}>
      <p className="psa-evidence__title text-[12px] font-medium">{title}</p>
      <div className="mt-2 space-y-2 text-sm text-psa-data-ink">{children}</div>
    </div>
  );
}
