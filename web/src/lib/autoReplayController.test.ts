import { describe, expect, it } from "vitest";

import { AUTO_REPLAY_DISCLOSURE, MAX_AUTO_ACTIONS } from "../api/canonicalReplay";
import type { CanonicalReplayActionType, CanonicalReplayStageView } from "../api/types";
import {
  runAutoReplay,
  type AutoReplayCallbacks,
  type AutoReplayLogEntry,
  type AutoReplayProgress,
} from "./autoReplayController";

type StageFactory = (iteration: number) => CanonicalReplayStageView;

function stage(overrides: Partial<CanonicalReplayStageView>): CanonicalReplayStageView {
  return {
    stage: "READY_FOR_PRE_DISCHARGE",
    ordinal: 2,
    progress_label: "Stage 2 of 16",
    status: "PENDING_ACTION",
    explanation: "explanation",
    next_allowed_action: "BOOTSTRAP_PRE_DISCHARGE",
    guided_can_execute: true,
    auto_replay_may_execute: true,
    requires_human_authority: false,
    deviation_reason: null,
    ...overrides,
  };
}

interface ScriptedHarnessOptions {
  /** One factory per stage READ, in order. Every fetchStage call consumes the next factory. */
  stages: StageFactory[];
  outcomes?: Record<string, { ok: boolean; conflict: boolean } | ((callCount: number) => { ok: boolean; conflict: boolean })>;
  maxActions?: number;
}

function scriptedHarness({ stages, outcomes = {}, maxActions }: ScriptedHarnessOptions) {
  let read = 0;
  const executed: CanonicalReplayActionType[] = [];
  const callCounts: Record<string, number> = {};
  const callbacks: AutoReplayCallbacks = {
    async fetchStage() {
      const factory = stages[Math.min(read, stages.length - 1)];
      read += 1;
      return factory(read - 1);
    },
    async execute(action) {
      executed.push(action);
      callCounts[action] = (callCounts[action] ?? 0) + 1;
      const configured = outcomes[action];
      if (typeof configured === "function") return configured(callCounts[action]);
      return configured ?? { ok: true, conflict: false };
    },
  };
  return { callbacks, executed, maxActions };
}

async function drive(options: ScriptedHarnessOptions, abortAfter?: number): Promise<{ progress: AutoReplayProgress; executed: CanonicalReplayActionType[] }> {
  const harness = scriptedHarness(options);
  const signal = { aborted: false };
  if (abortAfter !== undefined) {
    let iterations = 0;
    const originalFetch = harness.callbacks.fetchStage;
    harness.callbacks.fetchStage = async () => {
      iterations += 1;
      if (iterations > abortAfter) signal.aborted = true;
      return originalFetch();
    };
  }
  const progress = await runAutoReplay(harness.callbacks, { maxActions: options.maxActions ?? MAX_AUTO_ACTIONS }, signal, () => {});
  return { progress, executed: harness.executed };
}

describe("runAutoReplay", () => {
  it("drives the canonical hero through stage-authorized actions and halts at safe escalation", async () => {
    const heroStages: StageFactory[] = [
      () => stage({ stage: "READY_TO_CREATE", ordinal: 1, next_allowed_action: "CREATE_CANONICAL_INCIDENT" }),
      () => stage({ stage: "READY_FOR_PRE_DISCHARGE", ordinal: 2, next_allowed_action: "BOOTSTRAP_PRE_DISCHARGE" }),
      () => stage({ stage: "READY_TO_START_AGENT", ordinal: 3, next_allowed_action: "START_DEMO_AGENT_RUN" }),
      () => stage({ stage: "READY_TO_ADVANCE_TO_EVIDENCE_WAIT", ordinal: 4, next_allowed_action: "ADVANCE_AGENT" }),
      () => stage({ stage: "WAITING_FOR_ACTIVE_EVIDENCE", ordinal: 5, status: "WAITING_EXTERNAL", next_allowed_action: "PUBLISH_DISCHARGE_ACTIVE" }),
      () => stage({ stage: "WAITING_FOR_ACTIVE_EVIDENCE", ordinal: 5, status: "PENDING_ACTION", next_allowed_action: "ADVANCE_AGENT" }),
      () => stage({ stage: "READY_TO_PREPARE_RTA", ordinal: 7, next_allowed_action: "ADVANCE_AGENT" }),
      () => stage({ stage: "REQUEST_APPROVAL_REQUIRED", ordinal: 8, status: "WAITING_HUMAN", next_allowed_action: "APPROVE_REQUEST", requires_human_authority: true }),
      () => stage({ stage: "REQUEST_APPROVED_READY_TO_SEND", ordinal: 9, next_allowed_action: "ADVANCE_AGENT" }),
      () => stage({ stage: "WAITING_FOR_CARRIER", ordinal: 10, status: "WAITING_EXTERNAL", next_allowed_action: "SIMULATE_CARRIER_RESPONSE" }),
      () => stage({ stage: "CARRIER_COUNTER_RECEIVED", ordinal: 11, next_allowed_action: "ADVANCE_AGENT" }),
      () => stage({ stage: "COUNTER_APPROVAL_REQUIRED", ordinal: 12, status: "WAITING_HUMAN", next_allowed_action: "APPROVE_COUNTER", requires_human_authority: true }),
      () => stage({ stage: "COUNTER_APPROVED_READY_TO_RESUME", ordinal: 13, next_allowed_action: "PERSIST_SAFETY_REVIEW" }),
      () => stage({ stage: "COUNTER_APPROVED_READY_TO_RESUME", ordinal: 13, next_allowed_action: "ADVANCE_AGENT" }),
      () => stage({ stage: "SAFETY_BLOCKED", ordinal: 16, status: "TERMINAL_SUCCESS", next_allowed_action: "NONE", guided_can_execute: false, auto_replay_may_execute: false }),
    ];
    const { progress, executed } = await drive({ stages: heroStages });
    expect(executed).toEqual([
      "CREATE_CANONICAL_INCIDENT",
      "BOOTSTRAP_PRE_DISCHARGE",
      "START_DEMO_AGENT_RUN",
      "ADVANCE_AGENT",
      "PUBLISH_DISCHARGE_ACTIVE",
      "ADVANCE_AGENT",
      "ADVANCE_AGENT",
      "APPROVE_REQUEST",
      "ADVANCE_AGENT",
      "SIMULATE_CARRIER_RESPONSE",
      "ADVANCE_AGENT",
      "APPROVE_COUNTER",
      "PERSIST_SAFETY_REVIEW",
      "ADVANCE_AGENT",
    ]);
    expect(progress.halt).toBe("terminal-success");
    expect(progress.running).toBe(false);
    expect(progress.actionsUsed).toBe(14);
    expect(progress.log.map((entry) => entry.outcome)).toEqual(Array(14).fill("ok"));
  });

  it("halts at genuine tradeoff decisions without selecting an option", async () => {
    const { progress, executed } = await drive({
      stages: [() => stage({ stage: "TRADEOFF_DECISION_REQUIRED", ordinal: 6, status: "WAITING_HUMAN", next_allowed_action: "SELECT_TRADEOFF_OPTION", requires_human_authority: true })],
    });
    expect(executed).toEqual([]);
    expect(progress.halt).toBe("tradeoff");
  });

  it("continues once after the known 409 wait-upgrade because the re-projected stage permits a different action", async () => {
    const { progress, executed } = await drive({
      stages: [
        () => stage({ stage: "CARRIER_COUNTER_RECEIVED", ordinal: 11, next_allowed_action: "ADVANCE_AGENT" }),
        // conflict re-projection read:
        () => stage({ stage: "COUNTER_APPROVAL_REQUIRED", ordinal: 12, status: "WAITING_HUMAN", next_allowed_action: "APPROVE_COUNTER", requires_human_authority: true }),
        () => stage({ stage: "COUNTER_APPROVAL_REQUIRED", ordinal: 12, status: "WAITING_HUMAN", next_allowed_action: "APPROVE_COUNTER", requires_human_authority: true }),
        () => stage({ stage: "SAFETY_BLOCKED", ordinal: 16, status: "TERMINAL_SUCCESS", next_allowed_action: "NONE", guided_can_execute: false, auto_replay_may_execute: false }),
      ],
      outcomes: { ADVANCE_AGENT: { ok: false, conflict: true } },
    });
    expect(executed[0]).toBe("ADVANCE_AGENT");
    expect(executed[1]).toBe("APPROVE_COUNTER");
    expect(executed).toHaveLength(2);
    expect(progress.log.some((entry) => entry.outcome === "conflict-upgraded")).toBe(true);
    expect(progress.halt).toBe("terminal-success");
  });

  it("halts on a repeated conflict instead of blindly retrying the mutation", async () => {
    const { progress, executed } = await drive({
      stages: [
        () => stage({ stage: "REQUEST_APPROVAL_REQUIRED", ordinal: 8, status: "WAITING_HUMAN", next_allowed_action: "APPROVE_REQUEST", requires_human_authority: true }),
        () => stage({ stage: "REQUEST_APPROVAL_REQUIRED", ordinal: 8, status: "WAITING_HUMAN", next_allowed_action: "APPROVE_REQUEST", requires_human_authority: true }),
      ],
      outcomes: { APPROVE_REQUEST: { ok: false, conflict: true } },
    });
    expect(executed.filter((action) => action === "APPROVE_REQUEST")).toHaveLength(1);
    expect(progress.halt).toBe("conflict");
  });

  it("halts immediately when the stage read fails (404/network)", async () => {
    const executed: CanonicalReplayActionType[] = [];
    const progress = await runAutoReplay(
      {
        fetchStage: async () => {
          throw new Error("404 incident gone");
        },
        execute: async (action) => {
          executed.push(action);
          return { ok: true, conflict: false };
        },
      },
      {},
      { aborted: false },
      () => {},
    );
    expect(executed).toEqual([]);
    expect(progress.halt).toBe("error");
  });

  it("halts when an executed action fails with a non-conflict error", async () => {
    const { progress } = await drive({
      stages: [() => stage()],
      outcomes: { BOOTSTRAP_PRE_DISCHARGE: { ok: false, conflict: false } },
    });
    expect(progress.halt).toBe("error");
    expect(progress.log.at(-1)?.outcome).toBe("halted");
  });

  it("halts at the action budget", async () => {
    const { progress, executed } = await drive(
      {
        stages: [() => stage({ stage: "READY_TO_ADVANCE_TO_EVIDENCE_WAIT", ordinal: 4, next_allowed_action: "ADVANCE_AGENT" })],
        maxActions: 3,
      },
    );
    expect(executed).toHaveLength(3);
    expect(progress.halt).toBe("budget-exhausted");
    expect(MAX_AUTO_ACTIONS).toBe(40);
  });

  it("stops between actions when the abort flag is set", async () => {
    const { progress, executed } = await drive(
      {
        stages: [
          () => stage(),
          () => stage(),
          () => stage(),
          () => stage(),
          () => stage(),
        ],
      },
      1,
    );
    expect(executed.length).toBeLessThanOrEqual(2);
    expect(progress.halt).toBe("stopped");
  });

  it("halts at off-canonical-path with the deviation preserved", async () => {
    const { progress } = await drive({
      stages: [() => stage({ stage: "OFF_CANONICAL_PATH", status: "TERMINAL_HALTED", next_allowed_action: "NONE", guided_can_execute: false, auto_replay_may_execute: false, deviation_reason: "REQUEST_REJECTED" })],
    });
    expect(progress.halt).toBe("off-canonical-path");
    expect(progress.log.at(-1)?.stage).toBe("OFF_CANONICAL_PATH");
  });

  it("appends an append-only structured log", async () => {
    const { progress } = await drive({
      stages: [
        () => stage(),
        () => stage({ stage: "READY_TO_START_AGENT", ordinal: 3, next_allowed_action: "START_DEMO_AGENT_RUN" }),
        () => stage({ stage: "SAFETY_BLOCKED", ordinal: 16, status: "TERMINAL_SUCCESS", next_allowed_action: "NONE", auto_replay_may_execute: false, guided_can_execute: false }),
      ],
    });
    const entries: AutoReplayLogEntry[] = progress.log;
    expect(entries.map((entry) => entry.action)).toEqual(["BOOTSTRAP_PRE_DISCHARGE", "START_DEMO_AGENT_RUN"]);
    expect(entries[0].ordinal).toBe(2);
  });

  it("keeps the permanent synthetic-operator disclosure exact", () => {
    expect(AUTO_REPLAY_DISCLOSURE).toBe(
      "Demo harness automatically performs operator actions using a synthetic operator identity (synthetic-demo-operator). Production authority boundaries remain unchanged.",
    );
  });
});
