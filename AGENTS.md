# Agent guide — PSA Ministry of Meat

Full-stack PSA operations console: Python backend (`backend/`), React frontend (`web/`). For API, domain, and deployment work, see `docs/`. **This file focuses on design and UI polish** — the skills below are vendored under `.cursor/skills/` so the whole team shares the same protocols.

Read the relevant `SKILL.md` before editing UI.

## Start here (UI polish)

```
psa-ui → brainstorming → impeccable init/shape (or hallmark redesign) → build →
impeccable polish/audit (or hallmark audit) → verification-before-completion
```

| Step | Skill | Why |
|------|-------|-----|
| 1 | **psa-ui** | Lock approved layout, dark terminal language, API/state rules |
| 2 | **brainstorming** | Explore direction before large redesigns |
| 3 | **impeccable** `init` / `shape` | Capture product context and plan UX |
| 4 | Build | Use hallmark, gsap-*, shadcn, modern-web-guidance as needed |
| 5 | **impeccable** `polish` / `audit` | Final quality pass |
| 6 | **verification-before-completion** | Run tests and verify before claiming done |

**Approved UI spec (canonical for disputes):** `docs/superpowers/specs/2026-08-23-psa-ui-phase2-phase3-design.md` — do not re-brainstorm layout without user approval.

## Detector

Impeccable hooks are enabled in `.cursor/hooks.json` (auto-checks UI file edits).

Manual scan (either works):

```bash
npx impeccable detect web/src
# or
node .cursor/skills/impeccable/scripts/detect.mjs web/src
```

Hook status: `node .cursor/skills/impeccable/scripts/hook-admin.mjs status`

## Prerequisites (optional skills)

| Skill | Requires |
|-------|----------|
| **figma-design-to-code** | Figma MCP plugin enabled in Cursor |
| **scan-and-fix-accessibility** | BrowserStack MCP plugin enabled in Cursor |

**brainstorming** and **verification-before-completion** are vendored from the [Superpowers](https://cursor.com/docs/plugins) plugin. The local copies work without installing the plugin; install Superpowers for the full set (TDD, debugging, plans, etc.).

## Skill index

### Project context (read first)

| Skill | Path | When to use |
|-------|------|-------------|
| **psa-ui** | `.cursor/skills/psa-ui/SKILL.md` | Any UI work on the operations console |

### Process / planning

| Skill | Path | When to use |
|-------|------|-------------|
| **brainstorming** | `.cursor/skills/brainstorming/SKILL.md` | Before large UI redesigns — explore approaches |
| **verification-before-completion** | `.cursor/skills/verification-before-completion/SKILL.md` | Before claiming polish is done — run tests, verify visually |

### Core design polish (anti-slop)

| Skill | Path | When to use |
|-------|------|-------------|
| **impeccable** | `.cursor/skills/impeccable/SKILL.md` | Design, critique, audit, polish, animate, layout, typography. `/impeccable init` once per major redesign |
| **hallmark** | `.cursor/skills/hallmark/SKILL.md` | Greenfield pages, anti-template layouts. `hallmark audit`, `hallmark redesign`, `hallmark study` |
| **deslopify** | `.cursor/skills/deslopify/SKILL.md` | Refactor vibe-coded UI. Say "deslopify" or "refactor UI" |

### GSAP motion

This is a **React** project — start with **gsap-react** and **gsap-scrolltrigger**. Skip **gsap-frameworks** unless integrating Vue/Svelte/Astro.

| Skill | Path | When to use |
|-------|------|-------------|
| **gsap-core** | `.cursor/skills/gsap-core/SKILL.md` | Tweens, easing, stagger, matchMedia, reduced-motion |
| **gsap-timeline** | `.cursor/skills/gsap-timeline/SKILL.md` | Sequenced multi-step animation |
| **gsap-scrolltrigger** | `.cursor/skills/gsap-scrolltrigger/SKILL.md` | Scroll-driven reveals, parallax, pin |
| **gsap-react** | `.cursor/skills/gsap-react/SKILL.md` | GSAP in React (useGSAP, refs, cleanup) |
| **gsap-plugins** | `.cursor/skills/gsap-plugins/SKILL.md` | Flip, Draggable, MorphSVG, etc. |
| **gsap-utils** | `.cursor/skills/gsap-utils/SKILL.md` | clamp, mapRange, snap helpers |
| **gsap-performance** | `.cursor/skills/gsap-performance/SKILL.md` | Animation perf, will-change, batching |
| **gsap-frameworks** | `.cursor/skills/gsap-frameworks/SKILL.md` | Vue, Svelte, Astro only — not needed for this repo |

### Vercel / React UI protocols

| Skill | Path | When to use |
|-------|------|-------------|
| **react-best-practices** | `.cursor/skills/react-best-practices/SKILL.md` | React 19 component quality, a11y, perf (64 Vercel rules) |
| **shadcn** | `.cursor/skills/shadcn/SKILL.md` | Adding shadcn/ui components, theming, Tailwind v4 integration |

### Modern web & design handoff

| Skill | Path | When to use |
|-------|------|-------------|
| **modern-web-guidance** | `.cursor/skills/modern-web-guidance/SKILL.md` | CSS features, view transitions, scroll-driven CSS, CWV — run **first** for layout/motion tasks |
| **figma-design-to-code** | `.cursor/skills/figma-design-to-code/SKILL.md` | Implementing screens from Figma (requires Figma MCP) |

### Accessibility

| Skill | Path | When to use |
|-------|------|-------------|
| **scan-and-fix-accessibility** | `.cursor/skills/scan-and-fix-accessibility/SKILL.md` | WCAG scans and a11y fixes (requires BrowserStack MCP) |

## Stack

- **Frontend:** React 19 + Vite + Tailwind CSS v4 (`web/`)
- **Motion:** GSAP — add when needed; use **gsap-react** skill
- **Components:** Plain React today; use **shadcn** skill if adopting shadcn/ui
- **Verify UI changes:** `cd web && npm run typecheck && npm test`
