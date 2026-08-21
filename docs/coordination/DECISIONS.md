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
