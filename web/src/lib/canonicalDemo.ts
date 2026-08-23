export type CanonicalDemoRunId = "ACCEPT-RUN" | "COUNTER-RUN" | "SILENT-RUN";

export interface CanonicalDemoRun {
  runId: CanonicalDemoRunId;
  fixtureId: string;
  connectionId: string;
  outcome: "ACCEPT" | "COUNTER" | "SILENT";
  counterEtaPta?: string;
}

export const CANONICAL_DEMO_SUITE_ID = "SYN-CANONICAL-CARRIER-DEMO-V1";

export const CANONICAL_DEMO_RUNS: CanonicalDemoRun[] = [
  {
    runId: "ACCEPT-RUN",
    fixtureId: "SYN-CANONICAL-24-V1",
    connectionId: "SYN-CONN-JV2",
    outcome: "ACCEPT",
  },
  {
    runId: "COUNTER-RUN",
    fixtureId: "SYN-CANONICAL-24-V1",
    connectionId: "SYN-CONN-JV2",
    outcome: "COUNTER",
    counterEtaPta: "2026-08-22T06:45:00Z",
  },
  {
    runId: "SILENT-RUN",
    fixtureId: "SYN-CANONICAL-24-V1",
    connectionId: "SYN-CONN-EC3",
    outcome: "SILENT",
  },
];

export const CARRIER_DEMO_TIMESTAMPS = {
  preparedAt: "2026-08-22T07:00:00Z",
  requestedEtaPta: "2026-08-22T08:00:00Z",
  responseDeadline: "2026-08-22T09:00:00Z",
  simulateAt: "2026-08-22T08:30:00Z",
  timeoutAt: "2026-08-22T09:05:00Z",
} as const;

export function demoRunById(runId: CanonicalDemoRunId): CanonicalDemoRun {
  const run = CANONICAL_DEMO_RUNS.find((item) => item.runId === runId);
  if (!run) {
    throw new Error(`Unknown demo run ${runId}`);
  }
  return run;
}
