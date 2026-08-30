---
name: psa-ui
description: >-
  Recovery Command Center UI for PSA Ministry of Meat — Default visual foundation
  with Grafbase information hierarchy. Dark mission-control aesthetic, 7-chapter
  recovery narrative, guided/auto/explore modes. Frontend-only; backend locked.
---

# PSA Recovery Command Center

## Authority

This skill is the **canonical project design + product guide** for the final frontend rebuild.
Supersedes `docs/superpowers/specs/2026-08-23-psa-ui-phase2-phase3-design.md` for layout and visual language unless the user explicitly reverts.

Reference libraries (do not import wholesale):
- `.cursor/skills/default-design/` — surfaces, hairlines, bone CTAs, signal blue
- `.cursor/skills/grafbase-design/` — hierarchy, breathing room at key moments, low noise

## Synthesis (not an average)

| From Default | From Grafbase |
|--------------|---------------|
| Near-black canvas, graphite/charcoal surfaces | Ruthless hierarchy — one focal read per viewport |
| 0.5px white-alpha hairlines, inset highlights | Strong type scale, generous space at decision moments |
| Compact operational density | Minimal chromatic clutter |
| Signal blue = system/active/info | Clear primary vs secondary actions |
| Bone (#f2f2f2) primary CTA, dark ink text | Product state is the hero, not chrome |
| Green/red/amber **only** for semantics | Simple compositions |

**Do not import:** light-mode foundation, 90px marketing heroes, rainbow subsystem colors, glassmorphism, gradients, neon cyberpunk, Linear-clone layouts, decorative shadows.

## Semantic color system

| Token | Role |
|-------|------|
| `--psa-void` | Page canvas `#0b0c0e` |
| `--psa-graphite` | Primary surface `#131416` |
| `--psa-charcoal` | Nested surface `#1f1f21` |
| `--psa-snow` | Primary text |
| `--psa-steel` / `--psa-fog` | Secondary / metadata |
| `--psa-signal` | Blue — agent, system, active, informational `#3b82f6` |
| `--psa-amber` | Human authority required |
| `--psa-fern` | Verified / completed / successful |
| `--psa-coral` | Safety block / destructive / failure |
| `--psa-bone` | Primary action fill `#f2f2f2` |

No per-subsystem decorative colors (no violet yard / emerald carrier / fuchsia demo).

## Typography

- **Inter** only — load with `ss01`, `ss03` features when possible
- Display/command: weight 400–500, tight tracking (Default whisper, not Grafbase 90px)
- Body: 14–16px weight 400
- Labels/metadata: 11–12px uppercase tracking `0.12em` max — use sparingly
- KPI numbers: tabular nums, 20–28px weight 500

## Surfaces & borders

- Elevation via surface tier + `0.5px` hairline `rgba(255,255,255,0.08)` — not drop shadows
- Optional inset highlight: `box-shadow: inset 0 1px 0 rgba(255,255,255,0.04)`
- Card radius: 10–12px; buttons: 8–10px pills
- Spacing base 4px; compact density with **breathing room** around authority gates and safety finale

## Components

### Buttons
- **Primary:** bone fill, ink text, no chromatic fill
- **Secondary:** charcoal fill, hairline border, snow text
- **Authority:** amber hairline + inset wash; distinct from primary
- **Destructive:** coral text/border only when semantically required

### Status badges
- Neutral default; semantic fill only for verified/blocked/authority
- Never rainbow role colors

### Tables
- Hairline row dividers, compact row height, hover `graphite` lift
- Container IDs acceptable in tables; not in command header

### Drawers (evidence)
- Right slide-over, charcoal surface, progressive disclosure
- Raw JSON, fingerprints, model metadata live here only

### Timeline / progress
- 7-chapter stepper (not 16 raw enums)
- Current chapter: signal blue indicator; complete: fern dot; pending: steel

### Actor colors
- AGENT → signal blue
- OPERATOR / HUMAN → amber when authority required; else steel
- CARRIER / SYNTHETIC / POLICY → neutral steel; semantic only when blocking

## Motion

- Communicate state change only (chapter transition, KPI tick, R0→R1 swap, drawer)
- GSAP Flip for allocation movement **after** layout is correct
- Respect `prefers-reduced-motion`
- No animated gradients, parallax, or decorative stagger

## Responsive

- Single command column to `xl`; contextual viz stacks below KPIs on narrow viewports
- 7-chapter progress becomes horizontal scroll under `md`
- Explore workspace full-width tables with horizontal scroll

## Product: Recovery Command Center

Backend canonical replay (16 stages) → **7 chapters**:

1. **INCIDENT** — disruption creates the problem
2. **OPTIMIZE** — scarce expedite allocation under uncertainty
3. **OBSERVE** — agent pauses; PRE_DISCHARGE evidence incomplete
4. **ADAPT** — DISCHARGE_ACTIVE; R0→R1; 12.02→12.04; 601→602
5. **COORDINATE** — carrier request; stops at human authority
6. **RESPOND** — counter, approval, recomputation
7. **PROTECT** — cargo contradiction; deterministic policy blocks automation

Terminal hero: **ESCALATED / SAFETY_REVIEW_REQUIRED** — successful safety outcome.

## First viewport (before presenter speaks)

1. Incident command header (vessel/disruption, not UUIDs)
2. 3–4 recovery KPIs
3. Current chapter + explanation
4. Next action + actor boundary
5. Compact 7-stage progress
6. Contextual visualization for current chapter

Hide in hero: fixture IDs, hashes, raw enums, JSON, model metadata.

## Three UX modes

| Mode | Behavior |
|------|----------|
| **Guided** | Projector determines one dominant next action; single hero CTA |
| **Auto** | Existing auto-replay; chapter progress + current action |
| **Explore** | Full tables, agent history, tools, manual controls, audit, raw evidence |

## Architecture (frontend)

- `App.tsx` thin; `OperationsConsole` shell
- `useRecoveryConsole()` owns state/mutations — **no recovery policy in React**
- `fetchCanonicalReplayStage`, `useAutoReplay`, `recoverySelectors` preserved
- Incident ID in `localStorage` (`psa:active-incident:v1`); resume vs start fresh
- Do **not** modify backend

## Anti-patterns

- Student dashboard / generic shadcn admin / neon AI dashboard
- One-panel-per-subsystem rainbow layout
- Exposing all guided buttons at once in Guided mode
- LLM-owned safety policy copy (policy is deterministic)
- Marketing whitespace and display type above 32px in ops UI

## Verification

```bash
cd web && npm run typecheck && npm test
```

Use **impeccable polish/audit** before claiming done.
