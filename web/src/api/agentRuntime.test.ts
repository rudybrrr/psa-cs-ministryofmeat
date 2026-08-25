import { expect, it, vi } from "vitest";
import { jsonResponse } from "../test/fixtures";
import { advanceAgentRun, createAgentRun } from "./agentRuntime";
it("posts agent create and one explicit advance", async () => { const fetch = vi.fn(async () => jsonResponse({ id: "run", incident_id: "i" }, 201)); vi.stubGlobal("fetch", fetch); await createAgentRun("i"); await advanceAgentRun("run"); expect(fetch.mock.calls.map(([url]) => url)).toEqual(["/incidents/i/agent-runs", "/agent-runs/run/advance"]); });
