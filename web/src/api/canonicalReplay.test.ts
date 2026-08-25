import { expect, it, vi } from "vitest";
import { jsonResponse } from "../test/fixtures";
import {
  AUTO_REPLAY_DISCLOSURE,
  createCanonicalDemoAgentRun,
  fetchCanonicalReplayStage,
  initialCanonicalStageView,
} from "./canonicalReplay";

const STAGE_VIEW = {
  stage: "READY_FOR_PRE_DISCHARGE",
  ordinal: 2,
  progress_label: "Stage 2 of 16",
  status: "PENDING_ACTION",
  explanation: "bootstrap",
  next_allowed_action: "BOOTSTRAP_PRE_DISCHARGE",
  guided_can_execute: true,
  auto_replay_may_execute: true,
  requires_human_authority: false,
  deviation_reason: null,
};

it("fetches the projected replay stage read-only", async () => {
  const fetch = vi.fn(async () => jsonResponse(STAGE_VIEW));
  vi.stubGlobal("fetch", fetch);
  const view = await fetchCanonicalReplayStage("inc-1");
  expect(view.stage).toBe("READY_FOR_PRE_DISCHARGE");
  expect(fetch.mock.calls.map(([url]) => url)).toEqual([
    "/synthetic/scenarios/inc-1/canonical-replay/stage",
  ]);
});

it("creates the canonical demo agent run on the synthetic route", async () => {
  const fetch = vi.fn(async () =>
    jsonResponse({ id: "run-1", incident_id: "inc-1", model_name: "canonical-replay-agent-v1" }, 201),
  );
  vi.stubGlobal("fetch", fetch);
  const run = await createCanonicalDemoAgentRun("inc-1");
  expect(run.id).toBe("run-1");
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe("/synthetic/scenarios/inc-1/canonical-replay/agent-runs");
  expect((init as RequestInit).method).toBe("POST");
  expect((init as RequestInit).body).toBeUndefined();
});

it("exposes the exact synthetic-operator disclosure and initial view", () => {
  expect(AUTO_REPLAY_DISCLOSURE).toContain("synthetic-demo-operator");
  expect(AUTO_REPLAY_DISCLOSURE).toContain("Production authority boundaries remain unchanged.");
  const initial = initialCanonicalStageView();
  expect(initial.stage).toBe("READY_TO_CREATE");
  expect(initial.next_allowed_action).toBe("CREATE_CANONICAL_INCIDENT");
});
