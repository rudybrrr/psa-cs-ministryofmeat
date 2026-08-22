# Frozen Decisions

This document is append-only. Add entries only for approved or proposed changes to frozen interfaces, architecture, or scope. Never rewrite or remove an earlier entry.

## 2026-08-21 — Canonical specification location

- Status: Approved
- Decision: `docs/specs/psa-code-sprint-final-plan.md` is the canonical repository location for the owner-supplied “PSA Code Sprint 2.0: Final Plan.”
- Consequence: The implementation plan points to that file. Agents must not invent missing source-plan text.

## 2026-08-21 — Tuas synthetic terminal

- Status: Approved
- Decision: Synthetic terminal data uses `SYN-TUAS-TERMINAL` because the canonical project is Tuas-based.
- Consequence: Pasir Panjang identifiers are not used in this slice.

## 2026-08-21 — Deterministic audit attribution

- Status: Approved
- Decision: Deterministic workflow and state-machine actions are attributed to `SYSTEM`.
- Consequence: `AuditActor.AGENT` remains in the contract but is reserved for later actions actually performed by an LLM agent.

## 2026-08-21 — Future RTA terminology and carrier responses

- Status: Approved
- Decision: The future timing-request action is `REQUEST_RTA`. A `CarrierResponse` uses the explicit values `ACCEPT` or `COUNTER` and may include a counter ETA/PTA.
- Consequence: Silence is represented by the absence of a response after a future timeout/deadline, never as a `CarrierResponse`. `REQUEST_CARRIER_REBOOK` and an `accepted` boolean are not frozen into the contracts.

## 2026-08-21 — Complete recovery decision action vocabulary

- Status: Approved
- Decision: `DecisionAction` contains exactly `EXPEDITE`, `REQUEST_RTA`, `ROLL`, and `ESCALATE` at the Task 2 base.
- Consequence: The two additional actions are frozen contract vocabulary only. Task 2 does not implement roll, escalation workflow behavior, carrier negotiation, or any optimizer.

## 2026-08-22 — Human authority over genuine recovery trade-offs

- Status: Approved
- Decision: The solver produces feasible, Pareto-efficient alternatives. An established deterministic dominance policy may select only when one alternative clearly dominates. If alternatives retain a genuine business trade-off, a human operator decides. The agent gathers information, manages the evolving exception, handles authorised tools and counterparties, and explains the trade-off; an LLM does not replace arbitrary numerical weights with arbitrary prose judgment.
- Consequence: No agent workflow may silently rank or select business trade-offs that deterministic policy cannot resolve. Such alternatives remain visible for operator decision.

## 2026-08-22 — Canonical full-demo outcome decomposition

- Status: Approved
- Decision: The canonical 18-preserved target is decomposed into 5 preserved without intervention, 8 preserved through scarce yard expedition, and 5 intended to be preserved through the later carrier/RTA recovery phase. The remaining target outcomes are 5 rolled and 1 escalated.
- Consequence: Phase 2 proves only the 13-beneficiary/eight-slot scarce-capacity portion. The later RTA phase must empirically establish its intended five recoveries, and the implementation must report observed evidence rather than hard-code an 18/5/1 result when evidence differs.

## 2026-08-22 — Carrier recovery preservation decision action

- Status: Approved
- Decision: Add `DecisionAction.PRESERVE_VIA_RTA` as the sole frozen Phase 1/2 contract mutation for Phase 3.
- Consequence: `PRESERVE_VIA_RTA` is container-level recovery semantics only after valid carrier timing and p90 evidence. `REQUEST_RTA` remains connection-level request/authorization semantics and is never container-level.
