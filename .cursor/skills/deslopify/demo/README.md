# Deslopify Demo

Side-by-side examples of **AI slop** vs a **deslopped** landing page for GenericaAI.

## Before — AI slop

**Path:** [`ai-slop/`](ai-slop/)

- Purple/blue gradients, glow orbs, emoji feature cards
- Generic copy ("revolutionary", "10x faster", fake social proof)

```bash
# Open directly — no build step
start ai-slop/index.html   # Windows
open ai-slop/index.html    # macOS
```

## After — Deslopped

### Static HTML (fastest preview)

**Path:** [`deslopped-static/`](deslopped-static/)

- Flat dark UI, bento-style features, structured hero with product checklist
- No framework — single `index.html` + `styles.css`

```bash
start deslopped-static/index.html
```

### React + Vite (full component tree)

**Path:** [`deslopped/`](deslopped/)

- Same direction as static, built with React, Tailwind, and shadcn/ui-style components

```bash
cd deslopped
npm install
npm run dev
```

## What to compare

| Element | `ai-slop` | `deslopped` / `deslopped-static` |
|---------|-----------|----------------------------------|
| Hero background | Gradient + orbs | Solid dark + subtle dot grid |
| Headline | Gradient text clip | Bold solid typography |
| Feature cards | Emoji + vague copy | Bento grid + screenshot placeholders |
| CTA | Glow gradient button | Flat accent button |
| Social proof | Fake logos / counts | Removed or structured for real data |

These demos are reference material for the [Deslopify skill](../SKILL.md) — not production apps.
