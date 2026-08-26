import { request } from "./client";
import type { AgentRun, CanonicalReplayStageView } from "./types";

export const CANONICAL_REPLAY_MODEL_NAME = "canonical-replay-agent-v1";
export const SYNTHETIC_DEMO_OPERATOR_ID = "synthetic-demo-operator";
export const GUIDED_OPERATOR_ID = "operator-console";
export const CANONICAL_SAFETY_CONTAINER_ID = "SYN-CNT-010";
export const CANONICAL_SAFETY_NOTE_TEXT =
  "Manifest declares general cargo; free-text handling note identifies corrosive material and requires safety review.";
export const CANONICAL_SAFETY_NOTE_SOURCE = "synthetic-canonical-cargo-note";
export const CANONICAL_COUNTER_EFFECTIVE_AT = "2026-08-23T05:00:00Z";
export const CANONICAL_TOTAL_STAGES = 16;
export const MAX_AUTO_ACTIONS = 40;

export const AUTO_REPLAY_DISCLOSURE =
  "Demo harness automatically performs operator actions using a synthetic operator identity (synthetic-demo-operator). Production authority boundaries remain unchanged.";

export function initialCanonicalStageView(): CanonicalReplayStageView {
  return {
    stage: "READY_TO_CREATE",
    ordinal: 1,
    progress_label: `Stage 1 of ${CANONICAL_TOTAL_STAGES}`,
    status: "PENDING_ACTION",
    explanation:
      "No incident is loaded yet; create a canonical scarcity incident to begin the replay.",
    next_allowed_action: "CREATE_CANONICAL_INCIDENT",
    guided_can_execute: true,
    auto_replay_may_execute: true,
    requires_human_authority: false,
    deviation_reason: null,
  };
}

export async function fetchCanonicalReplayStage(
  incidentId: string,
): Promise<CanonicalReplayStageView> {
  return request<CanonicalReplayStageView>(
    `/synthetic/scenarios/${incidentId}/canonical-replay/stage`,
  );
}

export async function createCanonicalDemoAgentRun(
  incidentId: string,
): Promise<AgentRun> {
  return request<AgentRun>(
    `/synthetic/scenarios/${incidentId}/canonical-replay/agent-runs`,
    { method: "POST" },
  );
}
