# Phase 3 Carrier Recovery Design

**Status:** Approved architectural design, pending implementation-plan approval
**Date:** 2026-08-22
**Scope:** Carrier Recovery + Human Authorization + Reconsideration

## 1. Problem and scope

Phase 2 has already detected the canonical disruption, evaluated the 24-container fixture, allocated the frozen eight scarce expedite slots, persisted the resulting `EXPEDITE` decisions, and terminally resolved its incident. Phase 3 adds the deterministic, external-authority recovery path for containers whose recovery depends on an onward carrier.

PSA cannot change a carrier schedule locally. The system may prepare a representative RTA request, obtain explicit human authorization, send that exact request, receive an external response, and recompute the affected recovery decisions. The carrier may accept, counter, or remain silent. There is one carrier negotiation round only.

Phase 3 includes carrier RTA requests, explicit operator approval, deterministic carrier simulation, response timeout, recomputation, immutable decision supersession, persistence, APIs, and audit evidence. It does not include an LLM agent, DG free-text analysis, authentication, a production carrier adapter, a background scheduler, a second negotiation round, frontend work, or Phase 2 tuning.

The prototype uses DCSA's published Estimated / Requested / Planned / Actual timing interaction as a representative standards-grounded counterparty negotiation. It does not claim that PSA currently uses this exact operational lever. Deployment adapters must map the same authority boundary to PSA's actual interfaces and operating model.

## 2. Authority model and Phase 2 compatibility

The public authority boundary remains intentionally narrow:

- Available: `request_expedite_feasibility()`, `prepare_rta_request()`, `send_authorised_rta_request()`, `roll_container()`, and `escalate_case()`.
- Impossible: `hold_feeder()`, `change_carrier_schedule()`, `override_dg_rule()`, and `set_yard_capacity()`.

No Phase 3 component may locally modify a carrier schedule. A request, carrier response, or effective-timing evidence is not a local schedule mutation.

The existing `IncidentState` machine remains unchanged. In particular, its `RESOLVED` state remains terminal. A Phase 2 scarcity incident therefore means “the Phase 2 scarce-capacity workflow has completed,” not “all external recovery possibilities have completed.”

Phase 3 adds a connection-scoped `CarrierRecoveryCase` linked to that original, resolved incident. The original incident ID remains the shared key for `Decision` and `AuditEvent` history. Phase 3 adds structured case links to make carrier-recovery provenance explicit. A future overall end-to-end recovery status is a derived, additive view; it must not mutate or reinterpret `IncidentState`.

Existing one-container routes and the Phase 2 canonical scarcity routes remain unchanged. A client runs the existing canonical scarcity workflow, then explicitly prepares one or more Phase 3 cases against its resolved incident. Cases for different outbound connections are independent.

## 3. CarrierRecoveryCase lifecycle

`CarrierRecoveryCase` is connection-scoped and unique for `(incident_id, connection_id)`. It contains an immutable snapshot of its affected containers and a reference to the source Phase 2 scarcity evaluation.

The case lifecycle is:

```text
PREPARED
  -> AWAITING_REQUEST_APPROVAL
  -> AWAITING_CARRIER
       -> RECOMPUTING                 (ACCEPT or timeout)
       -> AWAITING_COUNTER_APPROVAL   (COUNTER)
            -> RECOMPUTING            (counter approval or rejection)
  -> COMPLETED | ESCALATED
```

`PREPARED` records the initial recovery artifacts; a successful prepare operation activates the case into `AWAITING_REQUEST_APPROVAL`. Request rejection enters `RECOMPUTING`, rather than leaving an unresolved dead-end. An `ACCEPT` and an approved counter also enter `RECOMPUTING`. A counter rejection and a timeout recompute against the original timing. `COMPLETED` means every affected container reached a non-escalated disposition. `ESCALATED` means at least one affected container requires human judgment; other containers in that same case may still have completed results.

Only the following transitions are valid. All other state-changing commands fail closed.

- A request approval/rejection is valid only in `AWAITING_REQUEST_APPROVAL`.
- Send is valid only in `AWAITING_REQUEST_APPROVAL` with an exact approved authorization.
- Carrier simulation is valid only in `AWAITING_CARRIER`, before the response deadline.
- Counter approval/rejection is valid only in `AWAITING_COUNTER_APPROVAL` and only for the persisted counter.
- Timeout evaluation is valid only for a sent request in `AWAITING_CARRIER` with no persisted response and a reached deadline.
- Reconsideration is an internal consequence of a valid response, rejection, or timeout; it is not a free API that can rerun Phase 2 allocation.

## 4. Additive contracts and the minimal frozen change

All new Phase 3 contracts are additive and belong in a dedicated carrier-recovery domain module. Existing models remain frozen.

### 4.1 Approved frozen-contract change

Add exactly one frozen enum value:

```text
DecisionAction.PRESERVE_VIA_RTA
```

This decision action is container-level. It may be created only after valid effective carrier timing exists, all hard constraints remain satisfied, and deterministic p90 recovery passes. It does not send an RTA request and it does not imply local carrier-schedule control. This approved change must later be appended to `docs/coordination/DECISIONS.md` and added to the exact frozen enum tests. This design document records the decision only; it makes no production-code or `DECISIONS.md` change.

`REQUEST_RTA` remains exclusively connection-scoped request and authorization semantics.

### 4.2 New contracts

- `CarrierRecoveryCase`: case ID, original incident ID, connection ID, source scarcity evaluation ID, immutable affected-container IDs, case state, and lifecycle timestamps.
- `RTARequestContext`: links the existing immutable `RTARequest` to its case; stores the request ID/version, canonical payload fingerprint, explicit response deadline, send evidence, and close evidence. The existing RTA request ID is the request version identity. Its timing payload is never overwritten.
- `ApprovalBinding`: an immutable, persisted authorization-subject binding created with one case-level proposal. It contains that proposal decision ID, a subject kind (`OUTBOUND_REQUEST` or `COUNTER_PROPOSAL`), the exact request or persisted response ID, and that subject's canonical fingerprint. A later existing `Approval` binds to it through the same proposal decision ID.
- `EffectiveConnectionTiming`: immutable evidence for one accepted request or operator-approved counter; includes case ID, request ID, response ID, source kind, effective ETA/PTA, and creation time.
- `CarrierRecoveryDecisionLink`: connects a case to each fallback, connection-level authorization, replacement, or escalation decision without changing the frozen `Decision` shape.
- `CarrierRecoveryDisposition`: `PRESERVED_VIA_RTA`, `STILL_ROLL`, or `ESCALATE`.
- `ContainerReconsiderationResult`: one immutable result per affected container; contains case ID, container ID, disposition, original fallback decision ID, optional replacement decision ID, applicable timing/timeout evidence, preserved-world count, world count, hard-constraint result, and creation time.

### 4.3 Connection-scoped authorization

An existing `Approval` is used honestly, not as a proxy for an arbitrary container:

1. Preparation creates a connection-level `Decision` with `container_id=None`, `action=REQUEST_RTA`, and `status=PROPOSED`.
2. It atomically creates the immutable pending `ApprovalBinding` for that proposal, case, exact subject, and fingerprint.
3. The proposal means “authorize use of the RTA recovery lever for this connection at the exact timing payload identified by its binding.”
4. The operator creates an immutable `Approval` referencing that decision ID. `Approval.operator_id` must be a non-empty explicit identifier and is mandatory evidence of the approving or rejecting operator even though authentication is deferred.
5. The `Approval` and already-persisted `ApprovalBinding`, joined by proposal decision ID, prove the exact case, subject, and fingerprint authorized by that approval.

Authorization is derived from the pair `Approval + ApprovalBinding`; the frozen `Decision` is never updated. A fresh case-level `REQUEST_RTA` proposal and pending binding are required for a `COUNTER`, followed by a fresh approval joined to that proposal. Case-level authorization decisions never participate in container decision supersession. Rejection of the original request closes its pending request artifact before fallback recomputation.

An approval is stale and invalid if its case is no longer in the matching authorization state, its request or response fingerprint does not match, its subject is not the current case subject, it has already been consumed by the relevant transition, the case is terminal, or a response/timeout has made the command contradictory. Phase 3 provides no cancellation or second-request path; it must not invent one.

## 5. RTA preparation and authorized send

`prepare_rta_request()` is connection-scoped. It verifies that the incident is the resolved Phase 2 incident, loads its persisted scarcity evaluation, finds the requested connection in the frozen canonical fixture, regenerates the exact source scenario worlds from the report's seed and scenario count, and keeps the selected Phase 2 expedite allocation fixed.

The affected snapshot contains only containers on that connection that are structurally safe and have zero preserved worlds under the original timing with that fixed allocation. For each affected container, preparation atomically creates a deterministic fallback `ROLL` decision with `status=APPROVED` and a decision link. These are recovery decisions, not immediate local carrier operations. The case-level `REQUEST_RTA` proposal is separate from them.

Fallback `ROLL` lineage is explicit and immutable. Before creating each fallback, preparation resolves the container's current recovery decision in the original incident: the unique container-level decision that no later decision supersedes. If that current decision exists, fallback `ROLL.supersedes` must reference it and `supersession_reason` must name the evidence-driven Phase 3 finding: zero preserved worlds under original timing with the frozen Phase 2 allocation. If no current recovery decision exists, fallback `ROLL.supersedes` is `None`. If the lineage is ambiguous, preparation fails closed with `409 Conflict` rather than guessing. `STILL_ROLL` leaves that fallback `ROLL` current. A later `PRESERVE_VIA_RTA` or `ESCALATE` decision supersedes that fallback `ROLL`. This generic rule applies even when the canonical fixture does not exercise every branch; it prevents unsuperseded, contradictory Phase 2 and Phase 3 recovery decisions.

Preparation accepts a requested ETA/PTA and a response deadline. Both command timestamps must be explicit UTC input: their source text must use `Z` or `+00:00`; another non-zero timezone offset is rejected even if timezone-aware. Persisted values are normalized to canonical UTC. The deadline must be later than the preparation timestamp. No duration is invented by the workflow.

`send_authorised_rta_request()` is the only outbound dispatch boundary. It succeeds only when all of the following are true:

- the case is awaiting request approval;
- the exact RTA request is pending and its stored payload fingerprint matches;
- an approved `Approval + ApprovalBinding` exists for that connection-level proposal and exact request payload;
- no response, timeout, terminal state, or contradictory prior dispatch exists.

On success, it atomically records the sent payload and timestamp, changes the request lifecycle to `SENT`, moves the case to `AWAITING_CARRIER`, and appends the corresponding audit event. Repeating the exact same dispatch returns the already-sent durable result and creates no second dispatch.

## 6. Deterministic carrier simulator and response semantics

The synthetic carrier simulator reads a versioned, deterministic response plan keyed by connection. Tests may inject an equivalent fixed plan. It has no global randomness and no authority to change local schedule data.

`simulate-carrier-response` accepts an explicit UTC `effective_at` input, using the same strict `Z`/`+00:00` and canonical-persistence rule as other Phase 3 command timestamps. It may operate only before the response deadline. Repeating an identical simulation returns the existing result; attempting a conflicting second result fails closed.

- **ACCEPT:** The simulator persists exactly one `CarrierResponse` with `response=ACCEPT` before deadline. The response is valid only when it references the exact sent request, the approved payload equals the sent payload, the authorization remains historically valid for that dispatch, and the effective timing is exactly the requested ETA/PTA. The request is closed. The system records immutable `EffectiveConnectionTiming` from the request and begins recomputation automatically. No additional operator approval is required.
- **COUNTER:** The simulator persists exactly one `CarrierResponse` with `response=COUNTER` and a required `counter_eta_pta` before deadline. It closes the response channel and moves the case to `AWAITING_COUNTER_APPROVAL`. The counter has no effective timing until a new, counter-specific case-level proposal, approval, and binding are approved. Counter approval creates immutable effective timing and starts recomputation. Counter rejection starts fallback recomputation with original timing. No second carrier negotiation round exists.
- **SILENT:** A configured silent simulation may return a command-level result stating that no response was emitted, but it persists no `CarrierResponse` and no `CARRIER` audit event. The absence becomes evidence only through a valid explicit timeout evaluation.

## 7. Silence, timeout, and explicit effective time

Timeout is a deterministic synthetic/demo clock boundary, not a background scheduler. A production adapter may later call the same domain operation from a trusted scheduler or event system without altering domain logic.

`evaluate-timeout` accepts explicit UTC `effective_at`, persists it canonically in UTC, and is valid only if:

- the request was actually sent;
- a response deadline exists;
- no `CarrierResponse` exists for the request; and
- `effective_at >= response_deadline`.

The operation records a `SYSTEM` observation of absent response, closes the request, moves the case to recomputation, and uses original connection timing as fallback evidence. It does not create a fake `CarrierResponse(SILENT)`. If a response already exists, the command is rejected rather than creating contradictory state. Exact timeout retries are idempotent and cannot duplicate timeout events, reconsideration results, superseding decisions, or fallback actions.

## 8. Reconsideration and immutable decisions

The recomputer consumes only:

- the original frozen canonical fixture;
- the source Phase 2 scarcity evaluation's fixture ID, seed, and scenario count;
- the exact scenario worlds regenerated from that seed/count;
- the frozen selected Phase 2 expedite allocation;
- the case's immutable affected-container snapshot; and
- original timing, accepted timing, approved counter timing, or timeout evidence for that one connection.

It never resamples worlds, changes fixture data, changes safety constraints, or reruns scarcity allocation. The eight Phase 2 allocations remain fixed. It recomputes only the affected containers, using the affected connection's effective ready boundary: effective PTA plus 35 minutes. All other connections and their Phase 2 decisions remain untouched.

The prototype's explicit, non-PSA-calibrated autonomy policy is p90. A hard-constraint failure always persists `ESCALATE` and creates an approved existing `ESCALATE` decision superseding the fallback `ROLL`; it never produces automated preservation or a still-roll disposition. Otherwise, for each affected container:

- **Preservation at least 90% of frozen worlds:** persist `PRESERVED_VIA_RTA`; create an approved `PRESERVE_VIA_RTA` decision that supersedes the fallback `ROLL` and records the evidence-driven supersession reason.
- **Zero preserved worlds:** persist `STILL_ROLL`; leave the fallback `ROLL` unchanged and create no replacement decision.
- **Positive preservation below 90%:** persist `ESCALATE`; create an approved existing `ESCALATE` decision that supersedes the fallback `ROLL`, because human judgment is required instead of automatic roll or recovery.

Every `ContainerReconsiderationResult` is immutable. A case may have mixed results; it stores every per-container result and derives its summary. This prevents a connection-level result from hiding that some containers were preserved, some remain rolled, and some require escalation. `PRESERVE_VIA_RTA` is never used for connection-level request authorization, and `REQUEST_RTA` is never used as a container-level recovery disposition.

## 9. Persistence and transactions

Add these persistence records and constraints:

- `carrier_recovery_cases`, unique by `(incident_id, connection_id)`;
- `rta_requests` and request-context records, unique per case;
- `approvals` for the existing approval model and `approval_bindings`, unique by authorization proposal decision ID and created before the operator action;
- `carrier_responses`, unique by request ID;
- `effective_connection_timings`, unique per applied carrier outcome;
- `carrier_recovery_decision_links`, unique by linked decision ID;
- `container_reconsideration_results`, unique by `(case_id, container_id)`; and
- `carrier_recovery_audit_links`, unique by audit event ID and keyed by case ID.

Each state-changing command uses one transaction for its case state, request/response or approval evidence, decision links and results, and audit records. A unique constraint or persisted state is the durable idempotency guard. A command either commits all of its durable outcome or none of it.

Every Phase 3 audit payload also contains `recovery_case_id`. `carrier_recovery_audit_links` is the structured, queryable case-to-audit relation; case history must not depend on brittle filtering of JSON audit payloads. Ordered history uses the existing append-only audit sequence.

## 10. API and fail-closed errors

The additive API is:

- `POST /incidents/{incident_id}/carrier-recovery-cases` — prepare a case with `connection_id`, requested ETA/PTA, and response deadline.
- `POST /carrier-recovery-cases/{case_id}/request-approval` — operator approval or rejection for one exact outbound request proposal. Its body identifies `proposal_decision_id`, `request_id`, `expected_payload_fingerprint`, non-empty `operator_id`, and approve/reject intent.
- `POST /carrier-recovery-cases/{case_id}/send` — exact authorized dispatch.
- `POST /carrier-recovery-cases/{case_id}/simulate-carrier-response` — run the fixed carrier plan at `effective_at`.
- `POST /carrier-recovery-cases/{case_id}/counter-approval` — operator approval or rejection for one exact persisted counter proposal. Its body identifies `proposal_decision_id`, `carrier_response_id`, `expected_payload_fingerprint`, non-empty `operator_id`, and approve/reject intent.
- `POST /carrier-recovery-cases/{case_id}/evaluate-timeout` — deterministic timeout evaluation at `effective_at`.
- `GET /incidents/{incident_id}/carrier-recovery-cases` — list cases for the original incident.
- `GET /carrier-recovery-cases/{case_id}` — current case state and summary.
- `GET /carrier-recovery-cases/{case_id}/history` — case artifacts, approvals, responses, effective timing or timeout evidence, per-container results, linked decisions, and ordered case-scoped audit events.

Commands fail closed:

- Approval commands never mean “approve whatever is active for this case.” The server first recognizes an exact retry by its already-persisted approval and matching binding, returning that durable approval unchanged. Otherwise, it looks up the persisted pending `ApprovalBinding` by the supplied proposal decision ID and verifies the supplied request or response ID and expected fingerprint against that exact binding and current case state before creating `Approval`. Any stale proposal, mismatched subject, altered fingerprint, or conflicting intent returns **409 Conflict**.
- Return **409 Conflict** for stale authorization, wrong case state, altered payload, mismatched approval binding, response after deadline, a conflicting second simulation, a response/timeout contradiction, ambiguous fallback lineage, or any other stale/conflicting workflow command.
- An exact retry of a completed command returns the original durable result without duplicate dispatches, responses, audits, decisions, or results. A configured silent simulation's exact retry returns the same no-response-emitted command result without persisting carrier evidence.
- Return **404 Not Found** for unknown incidents, cases, requests, or dependencies.
- Return **422 Unprocessable Content** for malformed payloads, non-UTC command timestamps, invalid deadline ordering, and other field-level validation errors.

This is workflow authority enforcement, not authentication. Operators still provide explicit `operator_id`; identity verification and authorization infrastructure are deferred.

## 11. Audit actors and events

`AuditActor.AGENT` remains unused.

- `SYSTEM`: case creation and state transitions, authorized dispatch, timeout observation, effective-time application orchestration, and recomputation execution.
- `OPERATOR`: request and counter approval/rejection, with `actor_id` equal to the explicit operator ID in the approval artifact.
- `CARRIER`: persisted `ACCEPT` and `COUNTER` only.
- `POLICY`: p90 evaluation, per-container disposition, and creation of `PRESERVE_VIA_RTA` or `ESCALATE` replacement decisions.
- `SOLVER`: not used in Phase 3, because allocation is frozen rather than rerun.

Representative event families are `carrier_recovery.case_created`, `rta.request_prepared`, `rta.authorization_recorded`, `rta.request_sent`, `carrier.response_received`, `carrier.counter_awaiting_approval`, `carrier.timing_effective`, `carrier.response_timed_out`, `carrier_recovery.recomputation_completed`, `carrier_recovery.disposition_recorded`, and `decision.created`. Every superseding decision audit payload identifies both the prior and replacement decision IDs and its recovery-case evidence.

## 12. Deterministic canonical demo

The demo retains the existing canonical Phase 2 workflow and its frozen benchmark evidence. It then:

1. prepares independent connection-scoped carrier-recovery cases using fixed UTC request/deadline values;
2. shows explicit operator request approval and authorized send;
3. invokes the versioned carrier plan to demonstrate accept, counter, and silent outcomes;
4. records a separate explicit approval or rejection for the counter;
5. evaluates silence with an explicit UTC timeout timestamp; and
6. displays the structured case history, timing/absence evidence, p90 world evidence, mixed container results, decision supersession, and actor-attributed audit trail.

The response plan determines the observed count of containers preserved via RTA. The demo reports that observed evidence. It must not hard-code five carrier recoveries or assert the canonical 18/5/1 target if the implemented synthetic evidence differs.

## 13. Authority invariants and testing strategy

Tests must preserve all existing one-container and Phase 2 behavior and add coverage for:

- exact frozen enum coverage including the approved `PRESERVE_VIA_RTA` addition;
- case uniqueness by incident and connection, valid state transitions, and transactional rollback;
- strict UTC `Z`/`+00:00` validation and canonical UTC persistence for command timestamps;
- connection-scoped affected snapshots and prohibition on container-scoped RTA requests;
- fallback-roll lineage from an existing current Phase 2 decision, no-prior-decision lineage, still-roll continuity, and later replacement supersession;
- no send without an exact approved request binding, approval-command subject matching, exact approval retries, and rejection of stale or altered authorization;
- mandatory fresh counter proposal/binding/approval;
- exact accept timing, counter timing, and one-response-only behavior;
- configured silent simulation with no `CarrierResponse` and no `CARRIER` event;
- timeout preconditions, contradiction rejection, and idempotent timeout retry;
- fixed Phase 2 allocation and exact scenario reuse without resampling or solver invocation;
- p90 preserve, zero still-roll, and partial-probability escalation branches;
- immutable decision supersession and mixed per-container case outcomes;
- deterministic case history scoped through `carrier_recovery_audit_links`;
- explicit operator identity in approval and audit evidence; and
- authority-boundary regression scanning of all new public modules and routes for forbidden schedule-control operations.

The authority regression must prove that no exposed callable or route contains `hold_feeder`, `change_carrier_schedule`, `override_dg_rule`, or `set_yard_capacity`. It must also prove that no implementation represents silence as `CarrierResponse(SILENT)`.

## 14. Deliberate deferrals

Phase 3 deliberately defers:

- LLM prompts, tool selection, and autonomous agent reasoning;
- DG free-text semantic contradiction analysis;
- authentication and production operator authorization infrastructure;
- production PSA and carrier integrations;
- background schedulers, WebSockets, and deployment;
- frontend polish beyond stable API contracts;
- any second carrier negotiation round;
- arbitrary business scoring or PSA-calibrated claims for the synthetic p90 policy; and
- changes to Phase 2 fixture data, benchmark methodology, scenario distribution, allocation, solver, or holdout evidence.

The implementation plan must stop before those deferred areas.
