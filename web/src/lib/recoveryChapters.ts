import type { CanonicalReplayStage } from "../api/types";

export const RECOVERY_CHAPTERS = [
  {
    id: "INCIDENT",
    label: "Incident",
    summary: "Disruption creates the recovery problem.",
  },
  {
    id: "OPTIMIZE",
    label: "Optimize",
    summary: "Scarce expedite capacity is allocated under uncertainty.",
  },
  {
    id: "OBSERVE",
    label: "Observe",
    summary: "Agent pauses while operational evidence remains incomplete.",
  },
  {
    id: "ADAPT",
    label: "Adapt",
    summary: "DISCHARGE_ACTIVE evidence changes forecasts and allocation.",
  },
  {
    id: "COORDINATE",
    label: "Coordinate",
    summary: "Agent prepares carrier recovery and stops at human authority.",
  },
  {
    id: "RESPOND",
    label: "Respond",
    summary: "Carrier counter arrives; operator approves; recovery recomputes.",
  },
  {
    id: "PROTECT",
    label: "Protect",
    summary: "Cargo contradiction triggers deterministic safety policy.",
  },
] as const;

export type RecoveryChapterId = (typeof RECOVERY_CHAPTERS)[number]["id"];

const STAGE_TO_CHAPTER: Record<CanonicalReplayStage, RecoveryChapterId> = {
  READY_TO_CREATE: "INCIDENT",
  READY_FOR_PRE_DISCHARGE: "OPTIMIZE",
  READY_TO_START_AGENT: "OBSERVE",
  READY_TO_ADVANCE_TO_EVIDENCE_WAIT: "OBSERVE",
  WAITING_FOR_ACTIVE_EVIDENCE: "OBSERVE",
  READY_TO_RECONSIDER: "ADAPT",
  READY_TO_PREPARE_RTA: "COORDINATE",
  REQUEST_APPROVAL_REQUIRED: "COORDINATE",
  REQUEST_APPROVED_READY_TO_SEND: "COORDINATE",
  WAITING_FOR_CARRIER: "RESPOND",
  CARRIER_COUNTER_RECEIVED: "RESPOND",
  COUNTER_APPROVAL_REQUIRED: "RESPOND",
  COUNTER_APPROVED_READY_TO_RESUME: "RESPOND",
  READY_FOR_SAFETY_EVIDENCE: "PROTECT",
  SAFETY_REVIEW_PENDING: "PROTECT",
  SAFETY_BLOCKED: "PROTECT",
  COMPLETE: "PROTECT",
  FAILED: "PROTECT",
  TRADEOFF_DECISION_REQUIRED: "ADAPT",
  OFF_CANONICAL_PATH: "INCIDENT",
};

export function chapterForStage(stage: CanonicalReplayStage): RecoveryChapterId {
  return STAGE_TO_CHAPTER[stage] ?? "INCIDENT";
}

export function chapterIndex(chapterId: RecoveryChapterId): number {
  return RECOVERY_CHAPTERS.findIndex((chapter) => chapter.id === chapterId);
}

export function chapterMeta(chapterId: RecoveryChapterId) {
  return RECOVERY_CHAPTERS[chapterIndex(chapterId)] ?? RECOVERY_CHAPTERS[0];
}
