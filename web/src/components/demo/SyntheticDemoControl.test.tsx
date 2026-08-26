import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CanonicalReplayStageView } from "../../api/types";
import type { AutoReplayProgress } from "../../lib/autoReplayController";
import { AUTO_REPLAY_DISCLOSURE } from "../../api/canonicalReplay";
import { SyntheticDemoControl } from "./SyntheticDemoControl";

function stage(overrides: Partial<CanonicalReplayStageView> = {}): CanonicalReplayStageView {
  return {
    stage: "READY_FOR_PRE_DISCHARGE",
    ordinal: 2,
    progress_label: "Stage 2 of 16",
    status: "PENDING_ACTION",
    explanation: "Canonical incident and scarcity evaluation exist; bootstrap PRE_DISCHARGE yard evidence.",
    next_allowed_action: "BOOTSTRAP_PRE_DISCHARGE",
    guided_can_execute: true,
    auto_replay_may_execute: true,
    requires_human_authority: false,
    deviation_reason: null,
    ...overrides,
  };
}

const idleAuto: AutoReplayProgress = { running: false, actionsUsed: 0, currentAction: null, log: [], halt: null };

afterEach(() => cleanup());

const baseHandlers = () => ({
  onCreateIncident: vi.fn(),
  onRefresh: vi.fn(),
  onBootstrap: vi.fn(),
  onStartDemoAgentRun: vi.fn(),
  onAdvanceAgent: vi.fn(),
  onPublishActive: vi.fn(),
  onSimulateCarrierResponse: vi.fn(),
  onApproveRequest: vi.fn(),
  onRejectRequest: vi.fn(),
  onApproveCounter: vi.fn(),
  onRejectCounter: vi.fn(),
  onCreateSafetyReview: vi.fn(),
});

function renderGuided(view: CanonicalReplayStageView, handlers = baseHandlers(), props: Partial<Parameters<typeof SyntheticDemoControl>[0]> = {}) {
  return render(
    <SyntheticDemoControl
      incidentId="inc-1"
      loading={false}
      stage={view}
      error={null}
      approvalFingerprint={null}
      {...handlers}
      {...props}
    />,
  );
}

describe("SyntheticDemoControl guided demo (default and primary)", () => {
  it("defaults to the guided mode tab and renders the projected stage header", () => {
    renderGuided(stage());
    expect(screen.getByRole("button", { name: /guided demo/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("READY_FOR_PRE_DISCHARGE")).toBeInTheDocument();
    expect(screen.getByText("Stage 2 of 16")).toBeInTheDocument();
    expect(screen.getByText(/bootstrap pre_discharge yard evidence/i)).toBeInTheDocument();
    expect(screen.getByText("OPERATOR ACTION")).toBeInTheDocument();
  });

  it("gates guided buttons to exactly the projected next action", async () => {
    const handlers = baseHandlers();
    renderGuided(stage({ next_allowed_action: "ADVANCE_AGENT" }), handlers);
    const advance = screen.getByRole("button", { name: /^advance agent$/i });
    expect(advance).toBeEnabled();
    await userEvent.setup().click(advance);
    expect(handlers.onAdvanceAgent).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /^bootstrap pre_discharge$/i })).toBeDisabled();
    expect(handlers.onBootstrap).not.toHaveBeenCalled();
  });

  it("renders the human approval badge with the exact persisted fingerprint and both decisions", () => {
    renderGuided(
      stage({
        stage: "REQUEST_APPROVAL_REQUIRED",
        ordinal: 8,
        status: "WAITING_HUMAN",
        explanation: "The prepared JV2 request needs operator approval.",
        next_allowed_action: "APPROVE_REQUEST",
        requires_human_authority: true,
      }),
      undefined,
      { approvalFingerprint: "fingerprint-abc123" },
    );
    expect(screen.getByText("HUMAN APPROVAL REQUIRED")).toBeInTheDocument();
    expect(screen.getByText("OUTBOUND_REQUEST")).toBeInTheDocument();
    expect(screen.getByText("fingerprint-abc123")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^approve request$/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /reject request/i })).toBeEnabled();
  });

  it("renders terminal safe escalation prominently", () => {
    renderGuided(stage({ stage: "SAFETY_BLOCKED", ordinal: 16, status: "TERMINAL_SUCCESS", explanation: "Cargo-safety contradiction blocked automation.", next_allowed_action: "NONE", guided_can_execute: false }));
    expect(screen.getByText("ESCALATED / SAFETY_REVIEW_REQUIRED")).toBeInTheDocument();
    expect(screen.getByText(/safe escalation/i)).toBeInTheDocument();
  });

  it("renders stage-accurate completed-run copy instead of escalation copy", () => {
    renderGuided(stage({ stage: "COMPLETE", ordinal: 16, status: "TERMINAL_SUCCESS", explanation: "AgentRun completed with all actionable recovery work resolved.", next_allowed_action: "NONE", guided_can_execute: false }));
    expect(screen.getByText("RUN COMPLETED")).toBeInTheDocument();
    expect(screen.getByText(/completed without requiring escalation/i)).toBeInTheDocument();
    expect(screen.queryByText("ESCALATED / SAFETY_REVIEW_REQUIRED")).not.toBeInTheDocument();
  });

  it("explains off-canonical deviations and offers a fresh canonical replay", async () => {
    const handlers = baseHandlers();
    renderGuided(stage({ stage: "OFF_CANONICAL_PATH", ordinal: 8, status: "TERMINAL_HALTED", explanation: "The outbound request was rejected.", next_allowed_action: "NONE", guided_can_execute: false, deviation_reason: "REQUEST_REJECTED" }), handlers);
    expect(screen.getByText(/left the canonical hero path/i)).toBeInTheDocument();
    expect(screen.getByText("REQUEST_REJECTED")).toBeInTheDocument();
    const restart = screen.getByRole("button", { name: /start new canonical replay/i });
    await userEvent.setup().click(restart);
    expect(handlers.onCreateIncident).toHaveBeenCalledTimes(1);
  });

  it("never renders hidden autoplay controls in guided mode", () => {
    renderGuided(stage());
    expect(screen.queryByRole("button", { name: /^run all$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^auto start$/i })).not.toBeInTheDocument();
  });
});

describe("SyntheticDemoControl synthetic auto replay (secondary)", () => {
  it("keeps auto replay behind its own tab that never starts by itself", async () => {
    const handlers = baseHandlers();
    renderGuided(stage(), handlers, { autoReplay: { progress: idleAuto, canStart: true, onStart: vi.fn(), onStop: vi.fn() } });
    await userEvent.setup().click(screen.getByRole("button", { name: /^auto replay$/i }));
    expect(AUTO_REPLAY_DISCLOSURE).toBeTruthy();
    expect(screen.getByText(/synthetic-demo-operator/)).toBeInTheDocument();
    expect(screen.getByText(/Production authority boundaries remain unchanged\./)).toBeInTheDocument();
    expect(handlers.onCreateIncident).not.toHaveBeenCalled();
  });

  it("shows start/stop, budget, current action, and the append-only log while running", async () => {
    const running: AutoReplayProgress = {
      running: true,
      actionsUsed: 3,
      currentAction: "ADVANCE_AGENT",
      log: [
        { ordinal: 2, stage: "READY_FOR_PRE_DISCHARGE", action: "BOOTSTRAP_PRE_DISCHARGE", outcome: "ok" },
        { ordinal: 3, stage: "READY_TO_START_AGENT", action: "START_DEMO_AGENT_RUN", outcome: "ok" },
        { ordinal: 4, stage: "READY_TO_ADVANCE_TO_EVIDENCE_WAIT", action: "ADVANCE_AGENT", outcome: "ok" },
      ],
      halt: null,
    };
    const onStop = vi.fn();
    renderGuided(stage(), undefined, { autoReplay: { progress: running, canStart: false, onStart: vi.fn(), onStop } });
    await userEvent.setup().click(screen.getByRole("button", { name: /^auto replay$/i }));
    expect(screen.getByText(/3 \/ 40/)).toBeInTheDocument();
    expect(screen.getByText(/current action:/i)).toBeInTheDocument();
    expect(screen.getAllByText("ADVANCE_AGENT").length).toBeGreaterThan(0);
    expect(screen.getByText("BOOTSTRAP_PRE_DISCHARGE")).toBeInTheDocument();
    const stop = screen.getByRole("button", { name: /^stop$/i });
    await userEvent.setup().click(stop);
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it("renders the halted state with its reason after the loop stops", async () => {
    const halted: AutoReplayProgress = {
      running: false,
      actionsUsed: 14,
      currentAction: null,
      log: [{ ordinal: 16, stage: "SAFETY_BLOCKED", action: "NONE", outcome: "halted" }],
      halt: "terminal-success",
    };
    renderGuided(stage({ stage: "SAFETY_BLOCKED", ordinal: 16, status: "TERMINAL_SUCCESS", next_allowed_action: "NONE", guided_can_execute: false }), undefined, {
      autoReplay: { progress: halted, canStart: false, onStart: vi.fn(), onStop: vi.fn() },
    });
    await userEvent.setup().click(screen.getByRole("button", { name: /^auto replay$/i }));
    expect(screen.getByText(/terminal-success/i)).toBeInTheDocument();
  });
});
