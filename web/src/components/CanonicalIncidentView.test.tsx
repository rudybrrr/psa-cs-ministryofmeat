import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { CanonicalIncidentView } from "./CanonicalIncidentView";

function containerTable() {
  return screen.getByRole("table", { name: /affected containers/i });
}

function containerRows() {
  return within(containerTable())
    .getAllByRole("row")
    .filter((row) => /SYN-CNT-/.test(row.textContent ?? ""));
}

describe("CanonicalIncidentView", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the canonical incident overview from the frozen fixture", () => {
    render(<CanonicalIncidentView />);

    expect(screen.getByText("ASX-17")).toBeInTheDocument();
    expect(screen.getByText(/195-minute delay/i)).toBeInTheDocument();
    expect(screen.getByText("SYN-TUAS-TERMINAL")).toBeInTheDocument();
    expect(screen.getByText(/24 affected containers/i)).toBeInTheDocument();
    expect(screen.getAllByText("SF1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("JV2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("EC3").length).toBeGreaterThan(0);
    expect(screen.getByText(/SYNTHETIC DATA/i)).toBeInTheDocument();
  });

  it("makes the 13-candidate / 8-slot scarcity conflict legible without claiming allocations", () => {
    render(<CanonicalIncidentView />);

    expect(screen.getByText(/13 p50 expedition candidates/i)).toBeInTheDocument();
    expect(screen.getByText(/8 available expedite slots/i)).toBeInTheDocument();
    expect(
      screen.getByText(/has not selected allocations yet/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/13 containers are expedited/i)).not.toBeInTheDocument();
  });

  it("renders SF1 / JV2 / EC3 service cards with PTA and boundary times", () => {
    render(<CanonicalIncidentView />);

    const sf1 = screen.getByRole("article", { name: /SF1/i });
    expect(within(sf1).getByText(/9 containers/i)).toBeInTheDocument();
    expect(within(sf1).getByText(/PTA 05:00Z/i)).toBeInTheDocument();
    expect(within(sf1).getByText(/boundary 05:35Z/i)).toBeInTheDocument();

    const jv2 = screen.getByRole("article", { name: /JV2/i });
    expect(within(jv2).getByText(/8 containers/i)).toBeInTheDocument();
    expect(within(jv2).getByText(/PTA 05:20Z/i)).toBeInTheDocument();
    expect(within(jv2).getByText(/boundary 05:55Z/i)).toBeInTheDocument();

    const ec3 = screen.getByRole("article", { name: /EC3/i });
    expect(within(ec3).getByText(/7 containers/i)).toBeInTheDocument();
    expect(within(ec3).getByText(/PTA 07:00Z/i)).toBeInTheDocument();
    expect(within(ec3).getByText(/boundary 07:35Z/i)).toBeInTheDocument();
  });

  it("renders exactly 24 canonical containers", () => {
    render(<CanonicalIncidentView />);

    const rows = containerRows();
    expect(rows).toHaveLength(24);
    for (let index = 1; index <= 24; index += 1) {
      const id = `SYN-CNT-${String(index).padStart(3, "0")}`;
      expect(within(containerTable()).getByText(id)).toBeInTheDocument();
    }
  });

  it("filters the container table by service, cargo type, and classification", async () => {
    const user = userEvent.setup();
    render(<CanonicalIncidentView />);

    await user.selectOptions(screen.getByLabelText(/filter by service/i), "SF1");
    expect(containerRows()).toHaveLength(9);

    await user.selectOptions(screen.getByLabelText(/filter by cargo type/i), "DG");
    expect(containerRows()).toHaveLength(2);
    expect(within(containerTable()).getByText("SYN-CNT-004")).toBeInTheDocument();
    expect(within(containerTable()).getByText("SYN-CNT-009")).toBeInTheDocument();

    await user.selectOptions(
      screen.getByLabelText(/filter by classification/i),
      "expedition candidate",
    );
    expect(containerRows()).toHaveLength(1);
    expect(within(containerTable()).getByText("SYN-CNT-004")).toBeInTheDocument();
    expect(within(containerTable()).queryByText("SYN-CNT-009")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/filter by service/i), "all");
    await user.selectOptions(screen.getByLabelText(/filter by cargo type/i), "all");
    await user.selectOptions(
      screen.getByLabelText(/filter by classification/i),
      "all",
    );
    expect(containerRows()).toHaveLength(24);
  });

  it("displays structural DG and reefer constraints without semantic DG analysis", () => {
    render(<CanonicalIncidentView />);

    const unclearedDg = within(containerTable()).getByRole("row", {
      name: /SYN-CNT-009/,
    });
    expect(unclearedDg).toHaveTextContent("DG");
    expect(unclearedDg).toHaveTextContent(/not structurally cleared/i);
    expect(unclearedDg).toHaveTextContent(/expedition cannot preserve/i);

    const clearedDg = within(containerTable()).getByRole("row", {
      name: /SYN-CNT-004/,
    });
    expect(clearedDg).toHaveTextContent("DG");
    expect(clearedDg).toHaveTextContent(/structurally cleared/i);
    expect(clearedDg).not.toHaveTextContent(/semantic/i);

    const reeferGap = within(containerTable()).getByRole("row", {
      name: /SYN-CNT-023/,
    });
    expect(reeferGap).toHaveTextContent("REEFER");
    expect(reeferGap).toHaveTextContent(/continuity unavailable/i);

    expect(screen.queryByText(/UN class/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/inferred UN/i)).not.toBeInTheDocument();
  });

  it("shows simultaneous capacity limits rather than summed quotas", () => {
    render(<CanonicalIncidentView />);

    const capacity = screen.getByRole("region", { name: /expedite capacity/i });
    expect(
      within(capacity).getByText(/Total critical-overlap slots:\s*8/i),
    ).toBeInTheDocument();
    expect(within(capacity).getByText(/SYN-A-EQ1:\s*4/)).toBeInTheDocument();
    expect(within(capacity).getByText(/SYN-B-EQ2:\s*3/)).toBeInTheDocument();
    expect(within(capacity).getByText(/SYN-C-EQ3:\s*3/)).toBeInTheDocument();
    expect(within(capacity).getByText(/reefer:\s*3/i)).toBeInTheDocument();
    expect(
      within(capacity).getByText(/structurally cleared DG:\s*1/i),
    ).toBeInTheDocument();
    expect(
      within(capacity).getByText(/simultaneous hard constraints/i),
    ).toBeInTheDocument();
  });
});
