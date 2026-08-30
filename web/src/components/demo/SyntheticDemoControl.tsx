import { useState } from "react";

import type { CanonicalReplayActionType, CanonicalReplayStageView } from "../../api/types";
import { AUTO_REPLAY_DISCLOSURE, MAX_AUTO_ACTIONS } from "../../api/canonicalReplay";
import type { AutoReplayProgress } from "../../lib/autoReplayController";
import type { ConsoleMode } from "../command-center/ModeSwitcher";

interface AutoReplayProps {
  progress: AutoReplayProgress;
  canStart: boolean;
  onStart(): void;
  onStop(): void;
}

interface SyntheticDemoControlProps {
  incidentId: string | null;
  loading: boolean;
  stage: CanonicalReplayStageView;
  error: { status: number; detail: string } | null;
  approvalFingerprint: string | null;
  mode?: ConsoleMode;
  hideModeTabs?: boolean;
  compact?: boolean;
  onCreateIncident(): void;
  onRefresh(): void;
  onBootstrap(): void;
  onStartDemoAgentRun(): void;
  onAdvanceAgent(): void;
  onPublishActive(): void;
  onSimulateCarrierResponse(): void;
  onApproveRequest(): void;
  onRejectRequest(): void;
  onApproveCounter(): void;
  onRejectCounter(): void;
  onCreateSafetyReview(): void;
  autoReplay?: AutoReplayProps;
}

const ACTOR_LABEL: Partial<Record<CanonicalReplayActionType, string>> = {
  ADVANCE_AGENT: "AGENT ACTION",
  APPROVE_REQUEST: "OPERATOR ACTION",
  APPROVE_COUNTER: "OPERATOR ACTION",
  SELECT_TRADEOFF_OPTION: "OPERATOR ACTION",
  CREATE_CANONICAL_INCIDENT: "OPERATOR ACTION",
  BOOTSTRAP_PRE_DISCHARGE: "OPERATOR ACTION",
  START_DEMO_AGENT_RUN: "OPERATOR ACTION",
  PUBLISH_DISCHARGE_ACTIVE: "SYNTHETIC EVIDENCE ACTION",
  PERSIST_SAFETY_REVIEW: "SYNTHETIC EVIDENCE ACTION",
  SIMULATE_CARRIER_RESPONSE: "SYNTHETIC EVIDENCE ACTION",
};

const STATUS_LABELS: Record<string, string> = {
  PENDING_ACTION: "PENDING ACTION",
  WAITING_HUMAN: "WAITING FOR HUMAN AUTHORITY",
  WAITING_EXTERNAL: "WAITING FOR EXTERNAL PARTY",
  TERMINAL_SUCCESS: "TERMINAL SUCCESS",
  TERMINAL_HALTED: "TERMINAL HALT",
};

export function SyntheticDemoControl(props: SyntheticDemoControlProps) {
  const [internalMode, setInternalMode] = useState<"guided" | "auto">("guided");
  const harnessMode = props.hideModeTabs
    ? props.mode === "auto"
      ? "auto"
      : "guided"
    : internalMode;
  const stage = props.stage;

  const actionButton = (
    label: string,
    action: CanonicalReplayActionType,
    onClick: () => void,
  ) => {
    if (props.compact && stage.next_allowed_action === action) {
      return null;
    }
    const enabled =
      !props.loading &&
      stage.guided_can_execute &&
      stage.next_allowed_action === action;
    return (
      <button
        type="button"
        disabled={!enabled}
        onClick={onClick}
        className="rounded-[8px] border border-white/10 bg-psa-charcoal px-3 py-2 text-[11px] uppercase tracking-wide text-psa-chalk disabled:opacity-40"
      >
        {label}
      </button>
    );
  };

  const isApprovalStage =
    stage.requires_human_authority &&
    (stage.next_allowed_action === "APPROVE_REQUEST" ||
      stage.next_allowed_action === "APPROVE_COUNTER");
  const terminalSuccess = stage.stage === "SAFETY_BLOCKED";
  const completedRun = stage.stage === "COMPLETE";
  const actionGridClass = props.compact ? "sr-only" : "mt-3 flex flex-wrap gap-2";

  return (
    <section
      aria-labelledby="demo-control-heading"
      className="psa-surface rounded-[10px] px-4 py-4"
    >
      <p className="psa-label">CANONICAL DEMO HARNESS</p>
      <h2 id="demo-control-heading" className="mt-1 text-sm font-medium text-psa-snow">
        Canonical replay control
      </h2>

      {!props.hideModeTabs ? (
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            aria-pressed={harnessMode === "guided"}
            onClick={() => setInternalMode("guided")}
            className={`rounded-[8px] border px-3 py-1 text-[11px] uppercase ${
              harnessMode === "guided"
                ? "border-psa-signal/50 bg-psa-signal/10 text-psa-snow"
                : "border-white/10 text-psa-fog"
            }`}
          >
            Guided Demo
          </button>
          <button
            type="button"
            aria-pressed={harnessMode === "auto"}
            onClick={() => setInternalMode("auto")}
            className={`rounded-[8px] border px-3 py-1 text-[11px] uppercase ${
              harnessMode === "auto"
                ? "border-psa-signal/50 bg-psa-signal/10 text-psa-snow"
                : "border-white/10 text-psa-fog"
            }`}
          >
            Auto Replay
          </button>
        </div>
      ) : null}

      <div className="mt-4 psa-surface-nested rounded-[8px] px-3 py-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-psa-fog">
          <span className="font-medium text-psa-chalk">{stage.stage}</span>
          <span>{stage.progress_label}</span>
          <span className="rounded border border-white/10 px-2 py-0.5 text-[10px] uppercase">
            {STATUS_LABELS[stage.status] ?? stage.status}
          </span>
          {isApprovalStage ? (
            <span className="text-psa-amber">HUMAN APPROVAL REQUIRED</span>
          ) : null}
        </div>
        <p className="mt-2 text-sm text-psa-chalk">{stage.explanation}</p>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] uppercase text-psa-steel">
          {ACTOR_LABEL[stage.next_allowed_action] ? (
            <span>{ACTOR_LABEL[stage.next_allowed_action]}</span>
          ) : null}
          {stage.deviation_reason ? (
            <span className="text-psa-coral">deviation:</span>
          ) : null}
        </div>
        {stage.deviation_reason ? (
          <p className="font-mono text-xs font-semibold uppercase text-psa-coral">
            {stage.deviation_reason}
          </p>
        ) : null}
        {terminalSuccess ? (
          <div className="mt-3 rounded-[8px] border border-psa-fern/40 bg-psa-fern/10 px-3 py-2">
            <p className="text-xs font-medium uppercase text-psa-snow">
              ESCALATED / SAFETY_REVIEW_REQUIRED
            </p>
            <p className="mt-1 text-xs text-psa-chalk">
              Safe escalation reached. The deterministic cargo-safety policy blocked
              automation; success was never reinterpreted as automatic recovery.
            </p>
          </div>
        ) : null}
        {completedRun ? (
          <div className="mt-3 rounded-[8px] border border-psa-fern/40 bg-psa-fern/10 px-3 py-2">
            <p className="text-xs font-medium uppercase text-psa-snow">RUN COMPLETED</p>
            <p className="mt-1 text-xs text-psa-chalk">
              All actionable recovery work resolved deterministically; the run
              completed without requiring escalation.
            </p>
          </div>
        ) : null}
        {isApprovalStage ? (
          <div className="mt-3 rounded-[8px] border border-psa-amber/30 bg-psa-amber/10 px-3 py-2">
            <p className="text-[10px] uppercase text-psa-amber">
              {stage.next_allowed_action === "APPROVE_COUNTER"
                ? "COUNTER_PROPOSAL"
                : "OUTBOUND_REQUEST"}
            </p>
            <p className="mt-1 break-all font-mono text-[11px] text-psa-chalk">
              {props.approvalFingerprint ?? "(binding not loaded yet)"}
            </p>
          </div>
        ) : null}
      </div>

      {harnessMode === "guided" ? (
        <>
          <p className="mt-3 text-sm text-psa-steel">
            Every action reads persisted state and performs exactly one endpoint call.
            No autoplay or hidden agent progression.
          </p>
          <div className={actionGridClass}>
            {!props.compact
              ? actionButton(
                  "Create canonical incident",
                  "CREATE_CANONICAL_INCIDENT",
                  props.onCreateIncident,
                )
              : null}
            {actionButton(
              "Bootstrap PRE_DISCHARGE",
              "BOOTSTRAP_PRE_DISCHARGE",
              props.onBootstrap,
            )}
            {actionButton(
              "Start canonical demo AgentRun",
              "START_DEMO_AGENT_RUN",
              props.onStartDemoAgentRun,
            )}
            {actionButton("Advance Agent", "ADVANCE_AGENT", props.onAdvanceAgent)}
            {actionButton(
              "Publish DISCHARGE_ACTIVE",
              "PUBLISH_DISCHARGE_ACTIVE",
              props.onPublishActive,
            )}
            {actionButton(
              "Simulate carrier COUNTER",
              "SIMULATE_CARRIER_RESPONSE",
              props.onSimulateCarrierResponse,
            )}
            {actionButton("Approve Request", "APPROVE_REQUEST", props.onApproveRequest)}
            {actionButton("Approve Counter", "APPROVE_COUNTER", props.onApproveCounter)}
            {actionButton(
              "Persist canonical SYN-CNT-010 contradiction",
              "PERSIST_SAFETY_REVIEW",
              props.onCreateSafetyReview,
            )}
            <button
              type="button"
              disabled={props.loading || !props.incidentId}
              onClick={props.onRefresh}
              className="rounded-[8px] border border-white/10 px-3 py-2 text-[11px] uppercase disabled:opacity-40"
            >
              Refresh
            </button>
          </div>
          {isApprovalStage ? (
            <div className={`${props.compact ? "sr-only" : "mt-2"} flex flex-wrap gap-2`}>
              <button
                type="button"
                disabled={props.loading || stage.next_allowed_action !== "APPROVE_REQUEST"}
                onClick={props.onRejectRequest}
                className="rounded-[8px] border border-psa-coral/40 px-3 py-2 text-[11px] uppercase text-psa-coral disabled:opacity-40"
              >
                Reject Request (leaves hero path)
              </button>
              <button
                type="button"
                disabled={props.loading || stage.next_allowed_action !== "APPROVE_COUNTER"}
                onClick={props.onRejectCounter}
                className="rounded-[8px] border border-psa-coral/40 px-3 py-2 text-[11px] uppercase text-psa-coral disabled:opacity-40"
              >
                Reject Counter (leaves hero path)
              </button>
            </div>
          ) : null}
          {stage.stage === "OFF_CANONICAL_PATH" ? (
            <div className="mt-3 rounded-[8px] border border-psa-coral/40 bg-psa-coral/10 px-3 py-2">
              <p className="text-sm text-psa-chalk">
                The run has left the canonical hero path and will not be forced back
                on it.
              </p>
              <button
                type="button"
                disabled={props.loading}
                onClick={props.onCreateIncident}
                className="mt-2 rounded-[8px] border border-psa-coral/50 px-3 py-2 text-[11px] uppercase text-psa-snow disabled:opacity-40"
              >
                Start new canonical replay
              </button>
            </div>
          ) : null}
        </>
      ) : null}

      {harnessMode === "auto" && props.autoReplay ? (
        <div className="mt-3 space-y-3">
          <p className="rounded-[8px] border border-psa-amber/30 bg-psa-amber/10 px-3 py-2 text-xs text-psa-chalk">
            {AUTO_REPLAY_DISCLOSURE}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            {!props.autoReplay.progress.running ? (
              <button
                type="button"
                disabled={props.loading || !props.autoReplay.canStart}
                onClick={props.autoReplay.onStart}
                className="rounded-[8px] bg-psa-bone px-3 py-2 text-[11px] font-medium uppercase text-psa-ink disabled:opacity-40"
              >
                Auto Start
              </button>
            ) : (
              <button
                type="button"
                onClick={props.autoReplay.onStop}
                className="rounded-[8px] border border-psa-coral/40 px-3 py-2 text-[11px] uppercase text-psa-coral"
              >
                Stop
              </button>
            )}
            <span className="text-[11px] text-psa-steel">
              {props.autoReplay.progress.actionsUsed} / {MAX_AUTO_ACTIONS} actions
            </span>
            {props.autoReplay.progress.running ? (
              <span className="text-[11px] uppercase text-psa-signal">Running…</span>
            ) : null}
            {props.autoReplay.progress.halt ? (
              <span className="text-[11px] uppercase text-psa-chalk">
                halt: {props.autoReplay.progress.halt}
              </span>
            ) : null}
          </div>
          {props.autoReplay.progress.currentAction ? (
            <p className="text-[11px] text-psa-steel">
              current action:{" "}
              <span className="text-psa-signal">{props.autoReplay.progress.currentAction}</span>
            </p>
          ) : null}
          <ol className="max-h-48 overflow-y-auto rounded-[8px] border border-white/10 bg-psa-void/60 px-3 py-2 font-mono text-[11px] text-psa-steel">
            {props.autoReplay.progress.log.length === 0 ? (
              <li>No auto replay actions in this session.</li>
            ) : null}
            {props.autoReplay.progress.log.map((entry, index) => (
              <li key={`${entry.ordinal}-${entry.action}-${index}`} className="whitespace-nowrap">
                <span>{`[${index + 1}] `}</span>
                <span className="text-psa-chalk">{entry.stage}</span>
                <span>{" -> "}</span>
                <span className="text-psa-signal">{entry.action}</span>
                <span>{` : ${entry.outcome}`}</span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {props.error && !props.hideModeTabs ? (
        <div
          role="alert"
          className="mt-3 rounded-[8px] border border-psa-coral/50 bg-psa-coral/10 px-3 py-2 text-sm text-psa-snow"
        >
          <p className="font-semibold">Replay harness error</p>
          <p className="mt-1 font-mono text-xs">
            {props.error.status}: {props.error.detail}
          </p>
        </div>
      ) : null}
    </section>
  );
}
