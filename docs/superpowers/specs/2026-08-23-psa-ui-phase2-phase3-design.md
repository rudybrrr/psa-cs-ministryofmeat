# PSA UI Phase 2 + Phase 3 Design

**Date:** 2026-08-23  
**Status:** Approved — do not re-brainstorm UI

## Goal

Build a **hybrid operations console**: a credible operational recovery tool with a clearly separated synthetic demo control for judges. One primary screen, no router/multipage architecture. All visible state comes from persisted backend APIs after mutations.

## Screen structure (top → bottom)

1. **Incident header** — active incident metadata from `GET /incidents/{id}`
2. **Recovery summary** — derived from canonical fixture + `GET /incidents/{id}/scarcity-evaluation` (live, not hard-coded counts)
3. **Main container recovery workspace** — table joined from fixture + scarcity evaluation + decisions + carrier cases
4. **Contextual right-side panel** — connection-scoped carrier recovery workflow (state-driven)
5. **Audit / decision history** — `AuditTimeline` + decision lineage
6. **Synthetic demo control** — visibly separated `DEMO CONTROL` section

## Architecture constraints

- Keep `App.tsx` thin; `OperationsConsole` is the shell only
- No Redux, Zustand, XState, or WebSockets
- `useRecoveryConsole()` owns loaded state and mutation commands; **no recovery policy in React**
- POST mutation → durable response → refresh persisted resources → re-render
- Preserve dark terminal visual language, `SyntheticBanner`, `ActorBadge`/`ActorLegend`, `AuditTimeline`, Vite API-base handling
- Do not modify backend source

## Phase 2 API integration

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/synthetic/scenarios/canonical-scarcity` | Create canonical scarcity incident |
| GET | `/synthetic/scenarios/canonical-scarcity/fixture` | Canonical 24-container fixture |
| GET | `/incidents/{id}/scarcity-evaluation` | Persisted scarcity report |
| GET | `/incidents/{id}` | Incident |
| GET | `/incidents/{id}/decisions` | Decisions (includes `PRESERVE_VIA_RTA`) |
| GET | `/incidents/{id}/audit-events` | Audit trail |

The frozen 24-container view becomes **live**: fixture + scarcity evaluation + decisions. Never label static fixture as allocation result.

### Recovery summary (from `ScarcityEvaluationReport`)

Display evidence such as:

- Containers at risk (fixture profile count)
- Baseline expected preserved connections (`baseline.expected_preserved_connections`)
- Scenario-aware expected preserved (`selected_allocation` strategy evaluation)
- Expected rollovers, selected expedite slot count, scenario count, reproducibility key

No hard-coded `5 → 18` or final recovery counts.

### Container table view model

Join backend facts (may not recalculate policy):

| Column | Source |
|--------|--------|
| Container ID | fixture profile |
| Service / connection | profile service + `onward_connection.id` |
| Cargo kind | profile |
| Expedite allocated | `selected_allocation.allocated_container_ids` |
| Current decision/action | latest non-superseded decision per container |
| Decision status | decision.status |
| Carrier recovery state | case for container's connection |
| Display disposition | decision action + carrier case state |

## Phase 3 API integration (nine routes)

| Method | Path |
|--------|------|
| POST | `/incidents/{id}/carrier-recovery-cases` |
| POST | `/carrier-recovery-cases/{id}/request-approval` |
| POST | `/carrier-recovery-cases/{id}/send` |
| POST | `/carrier-recovery-cases/{id}/simulate-carrier-response` |
| POST | `/carrier-recovery-cases/{id}/counter-approval` |
| POST | `/carrier-recovery-cases/{id}/evaluate-timeout` |
| GET | `/incidents/{id}/carrier-recovery-cases` |
| GET | `/carrier-recovery-cases/{id}` |
| GET | `/carrier-recovery-cases/{id}/history` |

TypeScript types mirror merged Pydantic contracts in `backend/app/domain/` — do not invent enums.

## Carrier recovery UX (connection-scoped)

Right panel when container selected:

```
Carrier Recovery
Connection: JV2 (SYN-CONN-JV2)
Affected snapshot: N containers
```

State-driven panels:

| Case state | Panel content | Operator controls |
|------------|---------------|-------------------|
| No case | Container evidence | Prepare (if valid) |
| `AWAITING_REQUEST_APPROVAL` | RTA proposal evidence | Approve / Reject request |
| `AWAITING_CARRIER` | Sent request | Waiting (no auto-send) |
| `AWAITING_COUNTER_APPROVAL` | Carrier counter evidence | Approve / Reject counter |
| `COMPLETED` | Reconsideration result + lineage | None |
| `ESCALATED` | Escalation evidence | None |

Human oversight: never auto-click approve/send/counter/timeout. COUNTER must show operator waiting state before counter approval.

## Decision lineage

Use persisted `supersedes`, `supersession_reason`, decision IDs from history — not heuristics.

Example display:

```
ROLL
↓ superseded
PRESERVE VIA RTA
```

## Audit actors

Distinguish SYSTEM, POLICY, OPERATOR, CARRIER via existing badges.

- ACCEPT/COUNTER → CARRIER evidence
- SILENT → **no** `CarrierResponse`, no CARRIER response event
- Timeout → SYSTEM observation
- Operator approvals → OPERATOR
- Recovery outcomes → POLICY

## Canonical demo suite

Visually separated `DEMO CONTROL — Synthetic counterparty behavior`.

Three independent runs from `shared/fixtures/canonical-carrier-response-plan.json`:

| Run | Connection | Outcome |
|-----|------------|---------|
| ACCEPT-RUN | SYN-CONN-JV2 | ACCEPT |
| COUNTER-RUN | SYN-CONN-JV2 | COUNTER |
| SILENT-RUN | SYN-CONN-EC3 | SILENT + explicit timeout |

Each run creates a **separate** canonical Phase 2 incident via `POST /synthetic/scenarios/canonical-scarcity`. Demo control does not fabricate React state.

UI:

```
CANONICAL CARRIER DEMO SUITE
[Run ACCEPT] [Run COUNTER] [Run SILENT]
Active run: COUNTER | Incident: … | Connection: SYN-CONN-JV2
```

**Note:** Live backend defaults simulator to `COUNTER-RUN`; ACCEPT/SILENT representability is proven via frontend integration tests with mocked API responses. SILENT live path uses explicit `evaluate-timeout` without carrier response.

## Error handling

| Status | Meaning | UI action |
|--------|---------|-----------|
| 404 | Missing resource | Show message |
| 409 | Stale/invalid workflow | Show message + refresh |
| 422 | Invalid input | Show validation detail |
| 5xx / network | System failure | Show error |

## Out of scope

Phase 4 DG UI, Phase 5 agent UI, backend changes, auth, WebSockets, deployment, state-management libraries, router overhaul, production carrier integration, new recovery algorithms.

## File layout (target)

```
web/src/
  api/{client,types,scarcity,carrierRecovery}.ts
  components/
    OperationsConsole.tsx
    incident/{IncidentHeader,RecoverySummary}.tsx
    recovery/{ContainerRecoveryTable,RecoveryStatusBadge}.tsx
    carrier/{CarrierRecoveryPanel,RTAProposal,RequestApprovalControls,
             CarrierResponsePanel,CounterApprovalControls,
             ReconsiderationResult,DecisionLineage}.tsx
    demo/SyntheticDemoControl.tsx
  hooks/useRecoveryConsole.ts
  lib/{recoverySelectors,formatters}.ts
  canonical/adapter.ts (refactored for API fixture)
```

Create files only when abstraction justifies them.
