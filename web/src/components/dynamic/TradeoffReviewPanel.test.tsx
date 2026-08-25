import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TradeoffReviewPanel } from "./TradeoffReviewPanel";
describe("TradeoffReviewPanel", () => {
  it("renders only persisted options and emits its exact ID", async () => {
    const onSelect = vi.fn(); const user = userEvent.setup();
    render(<TradeoffReviewPanel reviews={[{ id: "review", incident_id: "i", reconsideration_assessment_id: "a", option_ids: ["persisted"], options_fingerprint: "fp", state: "OPEN", created_at: "" }]} options={[{ id: "persisted", review_id: "review", allocated_container_ids: ["C1"], preserved_connection_total: 10, expected_preserved_connections: 1.5 }, { id: "other", review_id: "other-review", allocated_container_ids: ["C2"], preserved_connection_total: 9, expected_preserved_connections: 1 }]} loading={false} onSelect={onSelect} />);
    await user.click(screen.getByRole("button", { name: /persisted/i }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "review" }), "persisted");
    expect(screen.queryByText(/other/)).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
