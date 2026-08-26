import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CanonicalReplayStageView } from "../api/types";
import type { AutoReplayCallbacks, AutoReplayProgress } from "../lib/autoReplayController";
import { useAutoReplay } from "./useAutoReplay";

function stage(overrides: Partial<CanonicalReplayStageView> = {}): CanonicalReplayStageView {
  return {
    stage: "READY_TO_START_AGENT",
    ordinal: 3,
    progress_label: "Stage 3 of 16",
    status: "PENDING_ACTION",
    explanation: "explanation",
    next_allowed_action: "START_DEMO_AGENT_RUN",
    guided_can_execute: true,
    auto_replay_may_execute: true,
    requires_human_authority: false,
    deviation_reason: null,
    ...overrides,
  };
}

function callbacks(reads: CanonicalReplayStageView[]): AutoReplayCallbacks & { executed: string[] } {
  const executed: string[] = [];
  let index = 0;
  return {
    executed,
    async fetchStage() {
      const view = reads[Math.min(index, reads.length - 1)];
      index += 1;
      return view;
    },
    async execute(action) {
      executed.push(action);
      return { ok: true, conflict: false };
    },
  };
}

const terminal = () =>
  stage({ stage: "SAFETY_BLOCKED", ordinal: 16, status: "TERMINAL_SUCCESS", next_allowed_action: "NONE", auto_replay_may_execute: false });

describe("useAutoReplay", () => {
  it("is idle until explicitly started, then surfaces running state and final halt", async () => {
    const harness = callbacks([stage(), terminal()]);
    const { result } = renderHook(() => useAutoReplay(harness));
    expect(result.current.progress).toEqual({ running: false, actionsUsed: 0, currentAction: null, log: [], halt: null });
    await act(async () => {
      result.current.start();
    });
    expect(result.current.progress.halt).toBe("terminal-success");
    expect(harness.executed).toEqual(["START_DEMO_AGENT_RUN"]);
  });

  it("stop halts the loop between actions", async () => {
    const harness = callbacks([stage(), stage(), stage(), terminal()]);
    const { result } = renderHook(() => useAutoReplay(harness));
    await act(async () => {
      result.current.start();
      result.current.stop();
    });
    expect(result.current.progress.halt).toBe("stopped");
    expect(harness.executed.length).toBeLessThanOrEqual(2);
  });

  it("resets to idle on unmount (reload) so a restart resumes from projected state", async () => {
    const harness = callbacks([stage(), terminal()]);
    const { result, unmount } = renderHook(() => useAutoReplay(harness));
    await act(async () => {
      result.current.start();
    });
    unmount();
    const secondHarness = callbacks([stage(), terminal()]);
    const remounted = renderHook(() => useAutoReplay(secondHarness));
    expect(remounted.result.current.progress.running).toBe(false);
    expect(remounted.result.current.progress.actionsUsed).toBe(0);
  });

  it("reports progress snapshots through running/current/log fields", async () => {
    const snapshots: AutoReplayProgress[] = [];
    const harness = callbacks([stage(), terminal()]);
    const { result } = renderHook(() => useAutoReplay(harness, undefined, (snapshot) => snapshots.push(snapshot)));
    await act(async () => {
      result.current.start();
    });
    expect(snapshots.length).toBeGreaterThan(0);
    expect(snapshots.some((snapshot) => snapshot.running)).toBe(true);
    expect(result.current.progress.log[0].action).toBe("START_DEMO_AGENT_RUN");
  });
});
