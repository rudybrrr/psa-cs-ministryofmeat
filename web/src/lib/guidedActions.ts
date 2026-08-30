import type { CanonicalReplayActionType } from "../api/types";

export interface GuidedActionPresentation {
  actor: string;
  headline: string;
  detail: string;
  buttonLabel: string;
  variant: "primary" | "authority" | "evidence" | "carrier" | "safety";
}

const GUIDED_ACTIONS: Partial<
  Record<CanonicalReplayActionType, GuidedActionPresentation>
> = {
  CREATE_CANONICAL_INCIDENT: {
    actor: "Operator",
    headline: "Open the recovery scenario",
    detail:
      "Load the approved synthetic disruption fixture and begin the seven-stage recovery walkthrough.",
    buttonLabel: "Start recovery demo",
    variant: "primary",
  },
  BOOTSTRAP_PRE_DISCHARGE: {
    actor: "Yard evidence",
    headline: "Publish pre-discharge forecast",
    detail:
      "Seed wide PRE_DISCHARGE uncertainty before the recovery agent can observe discharge signals.",
    buttonLabel: "Publish yard forecast",
    variant: "evidence",
  },
  START_DEMO_AGENT_RUN: {
    actor: "Recovery agent",
    headline: "Start recovery orchestration",
    detail:
      "Open a durable agent run that pauses at evidence and authority boundaries instead of guessing.",
    buttonLabel: "Start recovery agent",
    variant: "primary",
  },
  ADVANCE_AGENT: {
    actor: "Recovery agent",
    headline: "Advance recovery orchestration",
    detail:
      "Execute the next persisted step once wait conditions and evidence requirements are satisfied.",
    buttonLabel: "Advance orchestration",
    variant: "primary",
  },
  PUBLISH_DISCHARGE_ACTIVE: {
    actor: "Yard evidence",
    headline: "Publish discharge-active evidence",
    detail:
      "Tighten the forecast band and unlock allocation reconsideration under locked commitments.",
    buttonLabel: "Publish discharge evidence",
    variant: "evidence",
  },
  APPROVE_REQUEST: {
    actor: "Human authority required",
    headline: "Approve carrier recovery request",
    detail: "The agent may prepare the JV2 recovery request. It cannot authorize transmission.",
    buttonLabel: "Approve request",
    variant: "authority",
  },
  SIMULATE_CARRIER_RESPONSE: {
    actor: "External carrier",
    headline: "Carrier counter received",
    detail: "Inject the synthetic counter proposal for operator review before recomputation.",
    buttonLabel: "Simulate carrier response",
    variant: "carrier",
  },
  APPROVE_COUNTER: {
    actor: "Human authority required",
    headline: "Approve carrier counter",
    detail: "Counter ETA binds only after explicit operator approval.",
    buttonLabel: "Approve counter",
    variant: "authority",
  },
  PERSIST_SAFETY_REVIEW: {
    actor: "Cargo safety",
    headline: "Record cargo safety evidence",
    detail:
      "Persist the structured manifest versus free-text handling note for semantic and policy review.",
    buttonLabel: "Record SYN-CNT-010 safety evidence",
    variant: "safety",
  },
  SELECT_TRADEOFF_OPTION: {
    actor: "Human authority required",
    headline: "Select allocation tradeoff",
    detail: "Choose one persisted feasible option before recovery can continue.",
    buttonLabel: "Select tradeoff option",
    variant: "authority",
  },
  NONE: {
    actor: "System",
    headline: "Recovery sequence complete",
    detail: "No further operator action is required for this scenario.",
    buttonLabel: "No action",
    variant: "primary",
  },
};

export function guidedActionPresentation(
  action: CanonicalReplayActionType,
): GuidedActionPresentation {
  return (
    GUIDED_ACTIONS[action] ?? {
      actor: "System",
      headline: action.replaceAll("_", " ").toLowerCase(),
      detail: "Execute the next allowed recovery action.",
      buttonLabel: action.replaceAll("_", " "),
      variant: "primary",
    }
  );
}
