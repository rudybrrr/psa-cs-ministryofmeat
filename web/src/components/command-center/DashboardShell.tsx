import type { ReactNode } from "react";

export function DashboardShell({
  sidebar,
  header,
  children,
}: {
  sidebar: ReactNode;
  header: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-psa-void text-psa-snow">
      <div className="flex min-h-0 flex-1">
        {sidebar}
        <div className="flex min-w-0 flex-1 flex-col">
          {header}
          <main className="min-w-0 flex-1 overflow-x-hidden px-4 py-4 lg:px-6 lg:py-5">
            <div className="mx-auto w-full max-w-[1400px] space-y-4">{children}</div>
          </main>
        </div>
      </div>
    </div>
  );
}
