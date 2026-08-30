import type { ReactNode } from "react";

export function Panel({
  children,
  className = "",
  nested = false,
}: {
  children: ReactNode;
  className?: string;
  nested?: boolean;
}) {
  return (
    <section
      className={`rounded-[10px] px-4 py-4 ${nested ? "psa-surface-nested" : "psa-surface"} ${className}`}
    >
      {children}
    </section>
  );
}
