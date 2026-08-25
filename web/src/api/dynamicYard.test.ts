import { expect, it, vi } from "vitest";
import { jsonResponse } from "../test/fixtures";
import { selectTradeoff } from "./dynamicYard";
it("submits only the exact persisted tradeoff payload", async () => { const fetch = vi.fn(async () => jsonResponse({})); vi.stubGlobal("fetch", fetch); await selectTradeoff("review", { selected_option_id: "option", expected_options_fingerprint: "a".repeat(64), operator_id: "operator-console" }); expect(fetch).toHaveBeenCalledWith("/allocation-tradeoff-reviews/review/selection", expect.objectContaining({ body: JSON.stringify({ selected_option_id: "option", expected_options_fingerprint: "a".repeat(64), operator_id: "operator-console" }) })); });
