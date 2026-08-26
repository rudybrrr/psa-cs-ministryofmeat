import type { CanonicalReplayActionType, CanonicalReplayStageView } from "../api/types";
import { MAX_AUTO_ACTIONS } from "../api/canonicalReplay";

export type AutoReplayHaltReason =
  | "terminal-success"
  | "off-canonical-path"
  | "tradeoff"
  | "budget-exhausted"
  | "conflict"
  | "error"
  | "stopped";

export interface AutoReplayLogEntry {
  ordinal: number;
  stage: string;
  action: string;
  outcome: "ok" | "conflict-upgraded" | "halted";
}

export interface MutationOutcomeLike {
  ok: boolean;
  conflict: boolean;
}

export interface AutoReplayCallbacks {
  fetchStage(): Promise<CanonicalReplayStageView>;
  execute(action: CanonicalReplayActionType): Promise<MutationOutcomeLike>;
}

export interface AutoReplayProgress {
  running: boolean;
  actionsUsed: number;
  currentAction: string | null;
  log: AutoReplayLogEntry[];
  halt: AutoReplayHaltReason | null;
}

export function idleAutoReplayProgress(): AutoReplayProgress {
  return { running: false, actionsUsed: 0, currentAction: null, log: [], halt: null };
}

const TERMINAL_SUCCESS_STAGES = new Set(["SAFETY_BLOCKED", "COMPLETE"]);
const TERMINAL_HALTED_STAGES = new Set(["FAILED", "OFF_CANONICAL_PATH"]);

export async function runAutoReplay(
  callbacks: AutoReplayCallbacks,
  options: { maxActions?: number } = {},
  signal: { aborted: boolean },
  onProgress: (progress: AutoReplayProgress) => void,
): Promise<AutoReplayProgress> {
  const maxActions = options.maxActions ?? MAX_AUTO_ACTIONS;
  const progress: AutoReplayProgress = { running: true, actionsUsed: 0, currentAction: null, log: [], halt: null };
  const emit = () => onProgress({ ...progress, log: [...progress.log] });

  emit();
  while (true) {
    if (signal.aborted) {
      progress.currentAction = null;
      progress.halt = "stopped";
      break;
    }

    let stage: CanonicalReplayStageView;
    try {
      stage = await callbacks.fetchStage();
    } catch {
      progress.currentAction = null;
      progress.halt = "error";
      break;
    }

    if (TERMINAL_SUCCESS_STAGES.has(stage.stage)) {
      progress.currentAction = null;
      progress.halt = "terminal-success";
      break;
    }
    if (TERMINAL_HALTED_STAGES.has(stage.stage)) {
      progress.log.push({ ordinal: stage.ordinal, stage: stage.stage, action: "NONE", outcome: "halted" });
      progress.currentAction = null;
      progress.halt = "off-canonical-path";
      break;
    }

    const action = stage.next_allowed_action;
    if (action === "SELECT_TRADEOFF_OPTION") {
      progress.log.push({ ordinal: stage.ordinal, stage: stage.stage, action, outcome: "halted" });
      progress.currentAction = null;
      progress.halt = "tradeoff";
      break;
    }
    if (action === "NONE" || !stage.auto_replay_may_execute) {
      progress.log.push({ ordinal: stage.ordinal, stage: stage.stage, action, outcome: "halted" });
      progress.currentAction = null;
      progress.halt = "error";
      break;
    }
    if (progress.actionsUsed >= maxActions) {
      progress.currentAction = null;
      progress.halt = "budget-exhausted";
      break;
    }

    progress.actionsUsed += 1;
    progress.currentAction = action;
    emit();

    let outcome: MutationOutcomeLike;
    try {
      outcome = await callbacks.execute(action);
    } catch {
      progress.log.push({ ordinal: stage.ordinal, stage: stage.stage, action, outcome: "halted" });
      progress.currentAction = null;
      progress.halt = "error";
      break;
    }

    if (outcome.ok) {
      progress.log.push({ ordinal: stage.ordinal, stage: stage.stage, action, outcome: "ok" });
      progress.currentAction = null;
      emit();
      continue;
    }

    if (outcome.conflict) {
      // Refresh persisted truth by re-projecting once; continue ONLY when the
      // re-projected stage permits a different legal action (the documented
      // AWAITING_COUNTER_APPROVAL -> COUNTER_APPROVAL upgrade advance).
      let projected: CanonicalReplayStageView;
      try {
        projected = await callbacks.fetchStage();
      } catch {
        progress.log.push({ ordinal: stage.ordinal, stage: stage.stage, action, outcome: "halted" });
        progress.currentAction = null;
        progress.halt = "error";
        break;
      }
      if (projected.next_allowed_action !== action && projected.next_allowed_action !== "NONE") {
        progress.log.push({ ordinal: stage.ordinal, stage: stage.stage, action, outcome: "conflict-upgraded" });
        progress.currentAction = null;
        emit();
        continue;
      }
      progress.log.push({ ordinal: stage.ordinal, stage: stage.stage, action, outcome: "halted" });
      progress.currentAction = null;
      progress.halt = "conflict";
      break;
    }

    progress.log.push({ ordinal: stage.ordinal, stage: stage.stage, action, outcome: "halted" });
    progress.currentAction = null;
    progress.halt = "error";
    break;
  }

  progress.running = false;
  emit();
  return progress;
}
