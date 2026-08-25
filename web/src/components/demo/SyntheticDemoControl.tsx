import { useState } from "react";

import type { CanonicalReplayActionType, CanonicalReplayStageView } from "../../api/types";
import { MAX_AUTO_ACTIONS } from "../../api/canonicalReplay";
import type { AutoReplayProgress } from "../../lib/autoReplayController";

interface AutoReplayProps {
  progress: AutoReplayProgress;
  canStart: boolean;
  onStart(): void;
  onStop(): void;
}

interface SyntheticDemoControlProps {
  incidentId: string | null; loading: boolean;
  stage: CanonicalReplayStageView;
  error: { status: number; detail: string } | null;
  approvalFingerprint: string | null;
  onCreateIncident(): void; onRefresh(): void; onBootstrap(): void; onStartDemoAgentRun(): void; onAdvanceAgent(): void; onPublishActive(): void; onSimulateCarrierResponse(): void; onApproveRequest(): void; onRejectRequest(): void; onApproveCounter(): void; onRejectCounter(): void; onCreateSafetyReview(): void;
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
  const [mode, setMode] = useState<"guided" | "auto">("guided");
  const stage = props.stage;

  const actionButton = (label: string, action: CanonicalReplayActionType, onClick: () => void) => {
    const enabled = !props.loading && stage.guided_can_execute && stage.next_allowed_action === action;
    return <button type="button" disabled={!enabled} onClick={onClick} className="rounded border border-fuchsia-500/40 px-3 py-2 font-mono text-[11px] uppercase disabled:opacity-40">{label}</button>;
  };

  const isApprovalStage = stage.requires_human_authority && (stage.next_allowed_action === "APPROVE_REQUEST" || stage.next_allowed_action === "APPROVE_COUNTER");
  const terminalSuccess = stage.stage === "SAFETY_BLOCKED" || stage.stage === "COMPLETE";

  return (
    <section aria-labelledby="demo-control-heading" className="rounded border border-fuchsia-500/40 bg-fuchsia-950/20 px-4 py-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-fuchsia-300">CANONICAL DEMO HARNESS</p>
      <h2 id="demo-control-heading" className="mt-1 text-sm font-semibold text-slate-100">Canonical replay control</h2>
      <div className="mt-3 flex gap-2">
        <button type="button" aria-pressed={mode === "guided"} onClick={() => setMode("guided")} className={`rounded border px-3 py-1 font-mono text-[11px] uppercase ${mode === "guided" ? "border-fuchsia-400 bg-fuchsia-500/20 text-fuchsia-100" : "border-slate-700 text-slate-400"}`}>Guided Demo</button>
        <button type="button" aria-pressed={mode === "auto"} onClick={() => setMode("auto")} className={`rounded border px-3 py-1 font-mono text-[11px] uppercase ${mode === "auto" ? "border-fuchsia-400 bg-fuchsia-500/20 text-fuchsia-100" : "border-slate-700 text-slate-400"}`}>Auto Replay</button>
      </div>

      <div className="mt-4 rounded border border-slate-800 bg-slate-950/60 px-3 py-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-mono text-xs font-semibold text-slate-100">{stage.stage}</span>
          <span className="font-mono text-[11px] text-slate-400">{stage.progress_label}</span>
          <span className="rounded border border-slate-700 px-2 py-0.5 font-mono text-[10px] uppercase text-slate-300">{STATUS_LABELS[stage.status] ?? stage.status}</span>
          {isApprovalStage && <span className="rounded border border-amber-400/60 bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] uppercase text-amber-200">HUMAN APPROVAL REQUIRED</span>}
        </div>
        <p className="mt-2 text-sm text-slate-300">{stage.explanation}</p>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10px] uppercase text-slate-500">
          {ACTOR_LABEL[stage.next_allowed_action] && <span>{ACTOR_LABEL[stage.next_allowed_action]}</span>}
          {stage.deviation_reason && <span className="text-rose-300">deviation:</span>}
        </div>
        {stage.deviation_reason && <p className="font-mono text-xs font-semibold uppercase text-rose-200">{stage.deviation_reason}</p>}
        {terminalSuccess && (
          <div className="mt-3 rounded border border-emerald-500/50 bg-emerald-950/30 px-3 py-2">
            <p className="font-mono text-xs font-semibold uppercase text-emerald-200">ESCALATED / SAFETY_REVIEW_REQUIRED</p>
            <p className="mt-1 text-xs text-emerald-100/80">Safe escalation reached. The deterministic cargo-safety policy blocked automation; success was never reinterpreted as automatic recovery.</p>
          </div>
        )}
        {isApprovalStage && (
          <div className="mt-3 rounded border border-amber-500/40 bg-amber-950/20 px-3 py-2">
            <p className="font-mono text-[10px] uppercase text-amber-200">{stage.next_allowed_action === "APPROVE_COUNTER" ? "COUNTER_PROPOSAL" : "OUTBOUND_REQUEST"}</p>
            <p className="mt-1 break-all font-mono text-[11px] text-amber-100">{props.approvalFingerprint ?? "(binding not loaded yet)"}</p>
            <p className="mt-1 font-mono text-[10px] uppercase text-amber-200/70">{props.approvalFingerprint ? "Approvals submit this exact fingerprint from the persisted ApprovalBinding." : "Refresh to load the persisted binding."}</p>
          </div>
        )}
      </div>

      {mode === "guided" && (
        <>
          <p className="mt-3 text-sm text-slate-400">Every action reads persisted state and performs exactly one endpoint call. No autoplay or hidden agent progression.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {actionButton("Create canonical incident", "CREATE_CANONICAL_INCIDENT", props.onCreateIncident)}
            {actionButton("Bootstrap PRE_DISCHARGE", "BOOTSTRAP_PRE_DISCHARGE", props.onBootstrap)}
            {actionButton("Start canonical demo AgentRun", "START_DEMO_AGENT_RUN", props.onStartDemoAgentRun)}
            {actionButton("Advance Agent", "ADVANCE_AGENT", props.onAdvanceAgent)}
            {actionButton("Publish DISCHARGE_ACTIVE", "PUBLISH_DISCHARGE_ACTIVE", props.onPublishActive)}
            {actionButton("Simulate carrier COUNTER", "SIMULATE_CARRIER_RESPONSE", props.onSimulateCarrierResponse)}
            {actionButton("Approve Request", "APPROVE_REQUEST", props.onApproveRequest)}
            {actionButton("Approve Counter", "APPROVE_COUNTER", props.onApproveCounter)}
            {actionButton("Persist canonical SYN-CNT-010 contradiction", "PERSIST_SAFETY_REVIEW", props.onCreateSafetyReview)}
            <button type="button" disabled={props.loading || !props.incidentId} onClick={props.onRefresh} className="rounded border border-slate-600 px-3 py-2 font-mono text-[11px] uppercase disabled:opacity-40">Refresh</button>
          </div>
          {isApprovalStage && (
            <div className="mt-2 flex flex-wrap gap-2">
              <button type="button" disabled={props.loading || stage.next_allowed_action !== "APPROVE_REQUEST"} onClick={props.onRejectRequest} className="rounded border border-rose-500/40 px-3 py-2 font-mono text-[11px] uppercase text-rose-200 disabled:opacity-40">Reject Request (leaves hero path)</button>
              <button type="button" disabled={props.loading || stage.next_allowed_action !== "APPROVE_COUNTER"} onClick={props.onRejectCounter} className="rounded border border-rose-500/40 px-3 py-2 font-mono text-[11px] uppercase text-rose-200 disabled:opacity-40">Reject Counter (leaves hero path)</button>
            </div>
          )}
          {stage.stage === "OFF_CANONICAL_PATH" && (
            <div className="mt-3 rounded border border-rose-500/40 bg-rose-950/30 px-3 py-2">
              <p className="text-sm text-rose-100">The run has left the canonical hero path and will not be forced back on it.</p>
              <button type="button" disabled={props.loading} onClick={props.onCreateIncident} className="mt-2 rounded border border-rose-400/50 px-3 py-2 font-mono text-[11px] uppercase text-rose-100 disabled:opacity-40">Start new canonical replay</button>
            </div>
          )}
        </>
      )}

      {mode === "auto" && props.autoReplay && (
        <div className="mt-3 space-y-3">
          <p className="rounded border border-amber-500/40 bg-amber-950/20 px-3 py-2 text-xs text-amber-100">{`Demo harness automatically performs operator actions using a synthetic operator identity (synthetic-demo-operator). Production authority boundaries remain unchanged.`}</p>
          <div className="flex flex-wrap items-center gap-2">
            {!props.autoReplay.progress.running && (
              <button type="button" disabled={props.loading || !props.autoReplay.canStart} onClick={props.autoReplay.onStart} className="rounded border border-fuchsia-500/50 px-3 py-2 font-mono text-[11px] uppercase disabled:opacity-40">Auto Start</button>
            )}
            {props.autoReplay.progress.running && (
              <button type="button" onClick={props.autoReplay.onStop} className="rounded border border-rose-500/50 px-3 py-2 font-mono text-[11px] uppercase">Stop</button>
            )}
            <span className="font-mono text-[11px] text-slate-400">{props.autoReplay.progress.actionsUsed} / {MAX_AUTO_ACTIONS} actions</span>
            {props.autoReplay.progress.running && <span className="font-mono text-[11px] uppercase text-fuchsia-300">Running…</span>}
            {props.autoReplay.progress.halt && <span className="font-mono text-[11px] uppercase text-slate-300">halt: {props.autoReplay.progress.halt}</span>}
          </div>
          {props.autoReplay.progress.currentAction && <p className="font-mono text-[11px] text-slate-300">current action: <span className="text-fuchsia-200">{props.autoReplay.progress.currentAction}</span></p>}
          <ol className="max-h-48 overflow-y-auto rounded border border-slate-800 bg-slate-950/70 px-3 py-2 font-mono text-[11px] text-slate-400">
            {props.autoReplay.progress.log.length === 0 && <li>No auto replay actions in this session.</li>}
            {props.autoReplay.progress.log.map((entry, index) => (
              <li key={`${entry.ordinal}-${entry.action}-${index}`} className="whitespace-nowrap"><span>{`[${index + 1}] `}</span><span className="text-slate-300">{entry.stage}</span><span>{" -> "}</span><span className="text-fuchsia-200">{entry.action}</span><span>{` : ${entry.outcome}`}</span></li>
            ))}
          </ol>
        </div>
      )}

      {props.error && (
        <div className="mt-3 rounded border border-rose-500/50 bg-rose-950/40 px-3 py-2 text-sm text-rose-100">
          <p className="font-semibold">Replay harness error</p>
          <p className="mt-1 font-mono text-xs">{props.error.status}: {props.error.detail}</p>
        </div>
      )}
    </section>
  );
}
