---
name: psa-ui
description: >-
  Project-specific UI constraints for the PSA Ministry of Meat operations console.
  Use for any frontend work in web/ — preserves approved hybrid-ops layout, dark
  terminal visual language, API-driven state, and carrier-recovery UX rules.
---

# PSA Operations Console UI

## Before editing

1. Read `docs/superpowers/specs/2026-08-23-psa-ui-phase2-phase3-design.md` (approved — do not re-brainstorm without user sign-off).
2. Load **impeccable** for polish/audit work or **hallmark** for structural redesign.
3. Run from `web/`: `npm run typecheck` and `npm test` after substantive UI changes.

## Product mode

This is **Operate** mode (impeccable): scanability, consistency, and task completion outrank decorative expression. Brand lives in precise details — typography, spacing, state clarity — not marketing flair.

## Visual identity to preserve

- Dark terminal / operations-console aesthetic
- Existing primitives: `SyntheticBanner`, `ActorBadge`/`ActorLegend`, `AuditTimeline`
- Single-screen console — no router overhaul, no multipage marketing layout

## Architecture constraints (non-negotiable)

- `App.tsx` stays thin; `OperationsConsole` is the shell
- No Redux, Zustand, XState, or WebSockets
- `useRecoveryConsole()` owns loaded state and mutations — **no recovery policy in React**
- POST mutation → durable API response → refresh persisted resources → re-render
- Do not modify backend source for UI tasks
- Visible state comes from persisted backend APIs after mutations

## Screen structure (top → bottom)

1. Incident header
2. Recovery summary (live from scarcity evaluation — never hard-coded counts)
3. Main container recovery workspace
4. Contextual right-side carrier recovery panel (connection-scoped, state-driven)
5. Audit / decision history
6. Synthetic demo control — visibly separated `DEMO CONTROL` section

## Carrier recovery panel states

| Case state | Operator controls |
|------------|-------------------|
| No case | Prepare (if valid) |
| `AWAITING_REQUEST_APPROVAL` | Approve / Reject request |
| `AWAITING_CARRIER` | Waiting only — never auto-send |
| `AWAITING_COUNTER_APPROVAL` | Approve / Reject counter |
| `COMPLETED` / `ESCALATED` | Read-only evidence |

Human oversight: never auto-click approve, send, counter, or timeout.

## Polish guidance for this project

- Improve hierarchy, density, motion, and micro-interactions within the terminal language
- Use **gsap-react** + **gsap-scrolltrigger** for purposeful motion (panel transitions, timeline reveals) — respect `prefers-reduced-motion`
- Use **modern-web-guidance** before adopting new CSS APIs
- Use **react-best-practices** when touching multiple TSX components
- Consider **shadcn** for complex primitives (dialogs, command palette) if adding component library surface area

## Out of scope

Phase 4 DG UI scope changes, Phase 5 agent UI scope changes, backend changes, auth, WebSockets, deployment, new recovery algorithms.
