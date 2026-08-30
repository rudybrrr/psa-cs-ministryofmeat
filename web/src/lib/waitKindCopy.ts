export interface WaitKindPresentation {
  label: string;
  detail: string;
}

export const WAIT_KIND_COPY: Record<string, WaitKindPresentation> = {
  NEW_OPERATIONAL_EVIDENCE: {
    label: "Operational evidence needed",
    detail: "Waiting for updated yard forecast before the agent can continue.",
  },
  REQUEST_APPROVAL: {
    label: "Carrier request approval",
    detail: "Operator approval required for the carrier recovery request.",
  },
  CARRIER_RESPONSE_OR_TIMEOUT: {
    label: "Awaiting carrier response",
    detail: "Waiting for an external carrier response.",
  },
  COUNTER_APPROVAL: {
    label: "Carrier counter approval",
    detail: "Operator approval required for the carrier counter proposal.",
  },
  HUMAN_TRADEOFF_DECISION: {
    label: "Tradeoff decision required",
    detail: "Operator must select one persisted feasible tradeoff option.",
  },
};

export function waitKindPresentation(
  waitKind: string | null | undefined,
): WaitKindPresentation | null {
  if (!waitKind) {
    return null;
  }
  return (
    WAIT_KIND_COPY[waitKind] ?? {
      label: "Agent waiting",
      detail: "The recovery agent is paused until prerequisites are satisfied.",
    }
  );
}
