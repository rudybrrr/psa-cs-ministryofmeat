import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CarrierRecoveryPanel } from "./CarrierRecoveryPanel";

const selectedContainer = {
  containerId: "SYN-CNT-017",
  serviceId: "JV2",
  connectionId: "SYN-CONN-JV2",
  cargoKind: "DRY",
  expediteAllocated: false,
  decisionAction: "ROLL",
  decisionStatus: "APPROVED",
  decisionId: "d1",
  carrierCaseState: "AWAITING_REQUEST_APPROVAL",
  displayDisposition: "roll",
};

describe("CarrierRecoveryPanel", () => {
  it("shows approve controls only in awaiting request approval", () => {
    render(
      <CarrierRecoveryPanel
        selectedContainer={selectedContainer}
        carrierCase={{
          id: "case-1",
          incident_id: "inc",
          connection_id: "SYN-CONN-JV2",
          source_evaluation_id: "eval",
          affected_container_ids: ["SYN-CNT-017"],
          state: "AWAITING_REQUEST_APPROVAL",
          created_at: "2026-08-22T08:00:00Z",
          updated_at: "2026-08-22T08:00:00Z",
        }}
        history={{
          case: {
            id: "case-1",
            incident_id: "inc",
            connection_id: "SYN-CONN-JV2",
            source_evaluation_id: "eval",
            affected_container_ids: ["SYN-CNT-017"],
            state: "AWAITING_REQUEST_APPROVAL",
            created_at: "2026-08-22T08:00:00Z",
            updated_at: "2026-08-22T08:00:00Z",
          },
          request: null,
          request_context: {
            case_id: "case-1",
            request_id: "req",
            payload_fingerprint: "fp",
            prepared_at: "2026-08-22T07:00:00Z",
            response_deadline: "2026-08-22T09:00:00Z",
            sent_at: null,
            closed_at: null,
            close_reason: null,
            timeout_observed_at: null,
          },
          bindings: [],
          approvals: [],
          carrier_responses: [],
          effective_timings: [],
          decision_links: [],
          decisions: [],
          results: [],
          audit_events: [],
        }}
        decisions={[]}
        loading={false}
        onPrepare={() => undefined}
        onApproveRequest={() => undefined}
        onRejectRequest={() => undefined}
        onSend={() => undefined}
        onSimulate={() => undefined}
        onApproveCounter={() => undefined}
        onRejectCounter={() => undefined}
        onEvaluateTimeout={() => undefined}
      />,
    );

    expect(screen.getByRole("button", { name: /approve request/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve counter/i })).not.toBeInTheDocument();
  });
});

afterEach(() => cleanup());
