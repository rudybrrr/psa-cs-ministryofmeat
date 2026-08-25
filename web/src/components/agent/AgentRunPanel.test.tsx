import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgentRunPanel } from "./AgentRunPanel";

const run = (state: any, wait_kind: any = null, escalation_reason: string | null = null) => ({ id: "agent-123456", incident_id: "i", state, model_name: "model", prompt_version: "v1", step_count: 1, max_steps: 5, wait_kind, wait_subject_id: "subject", escalation_reason, started_at: "", updated_at: "", completed_at: null });
const renderPanel = (agent = run("RUNNING"), canAdvance = true) => render(<AgentRunPanel run={agent} history={null} loading={false} canAdvance={canAdvance} onStart={vi.fn()} onAdvance={vi.fn()} onRefresh={vi.fn()} />);
describe("AgentRunPanel", () => {
  afterEach(cleanup);
  it("enables a running run", () => { renderPanel(); expect(screen.getByRole("button", { name: /advance agent/i })).toBeEnabled(); });
  it("blocks evidence wait before evidence and enables it after", () => { const { rerender } = renderPanel(run("WAITING", "NEW_OPERATIONAL_EVIDENCE"), false); expect(screen.getByRole("button", { name: /advance agent/i })).toBeDisabled(); rerender(<AgentRunPanel run={run("WAITING", "NEW_OPERATIONAL_EVIDENCE")} history={null} loading={false} canAdvance onStart={vi.fn()} onAdvance={vi.fn()} onRefresh={vi.fn()} />); expect(screen.getByRole("button", { name: /advance agent/i })).toBeEnabled(); });
  it.each(["REQUEST_APPROVAL", "COUNTER_APPROVAL", "HUMAN_TRADEOFF_DECISION"])("uses persisted eligibility for %s", (wait) => { renderPanel(run("WAITING", wait), false); expect(screen.getByRole("button", { name: /advance agent/i })).toBeDisabled(); });
  it("disables terminal and shows escalation", () => { renderPanel(run("ESCALATED", null, "SAFETY_REVIEW_REQUIRED")); expect(screen.getByRole("button", { name: /advance agent/i })).toBeDisabled(); expect(screen.getByText(/SAFETY_REVIEW_REQUIRED/)).toBeInTheDocument(); });
  it("renders exact wait copy", () => { renderPanel(run("WAITING", "CARRIER_RESPONSE_OR_TIMEOUT"), false); expect(screen.getByText(/waiting for carrier response/i)).toBeInTheDocument(); });
});
