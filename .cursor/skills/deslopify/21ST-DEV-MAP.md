# 21ST-DEV-MAP — Deslopify × 21st.dev Mapping

Reference for PHASE 2 (QUESTIONNAIRE PER COMPONENT). For each category, there is a **default recommendation** — what I offer the user first. Search `https://21st.dev/s/[slug]` for newer options beyond those listed.

**To install any component:**
```bash
npx shadcn@latest add "https://21st.dev/r/[autor]/[componente]"
```

**Universal filter:** components with `backdrop-blur`, `bg-gradient-to-*`, `background-clip: text`, decorative orbs, or glassmorphism are **rejected** — even when sourced from 21st.dev.

---

## HERO SECTIONS

**Slop detected:** purple/blue gradient background, text in `bg-clip-text`, vague subtitle, CTA with glow, no room for a real product screenshot.

**Search URL:** `https://21st.dev/s/hero`

**Default recommendation:** hero with solid dark or light background, bold heading with `tracking-tight`, descriptive subtitle (placeholder for real copy), flat CTA + ghost CTA, and a prominent area for a product screenshot/demo.

**Selection criteria:**
- Solid background, no gradient
- Clear typographic hierarchy (does not rely on text gradient for emphasis)
- Structured space for a real image/screenshot
- Primary CTA without chromatic shadow

**Rejection criteria:**
- Animated orbs in the background
- `bg-clip-text` gradient
- Fictional "As seen on" baked into the component
- Infinite-loop entry animations with no control

**Validated components:**
| Recommendation | Author | Preview | Install |
|---|---|---|---|
| ⭐ Hero Section (shadcn/ui) | moumensoliman | [view](https://21st.dev/r/moumensoliman/hero-section-shadcnui) | `npx shadcn@latest add "https://21st.dev/r/moumensoliman/hero-section-shadcnui"` |
| Animated Hero | ravikatiyar162 | [view](https://21st.dev/r/ravikatiyar162/animated-hero-section-1) | `npx shadcn@latest add "https://21st.dev/r/ravikatiyar162/animated-hero-section-1"` |
| Glow Hero | dhileepkumargm | [view](https://21st.dev/r/dhileepkumargm/glow-hero-section) | `npx shadcn@latest add "https://21st.dev/r/dhileepkumargm/glow-hero-section"` |

---

## FEATURE SECTIONS / CARDS

**Slop detected:** uniform grid of 3–6 identical cards with `✨`/`🚀` icons, vague title, generic description. No real data. No product evidence.

**Search URL:** `https://21st.dev/s/features`

**Default recommendation:** bento grid or asymmetric list mixing a text card with a card that has space for screenshot/demo. Visual variation without uniformity — layout conveys hierarchy without gradient.

**Selection criteria:**
- Layout that prioritizes space for screenshot, real metric, or demo
- Size variation across items (bento > uniform grid)
- No decorative icons as the sole visual content

**Rejection criteria:**
- Grid of identical icon + title + text cards
- Cards with glassmorphism or gradient border
- Animated icons without functional purpose

**Validated components:**
| Recommendation | Author | Preview | Install |
|---|---|---|---|
| ⭐ Bento Grid | lavikatiyar | [view](https://21st.dev/r/lavikatiyar/bento-grid) | `npx shadcn@latest add "https://21st.dev/r/lavikatiyar/bento-grid"` |
| Feature Card | ravikatiyar162 | [view](https://21st.dev/r/ravikatiyar162/feature-card) | `npx shadcn@latest add "https://21st.dev/r/ravikatiyar162/feature-card"` |

---

## BUTTONS

**Slop detected:** `bg-gradient-to-r from-purple-500 to-blue-600`, glow via `shadow-purple-500/50`, decorative `animate-pulse`, two competing primary CTAs.

**Search URL:** `https://21st.dev/s/button`

**Default recommendation:** native shadcn/ui buttons with the accent color defined in PHASE 0. They are the best choice — no overhead, no extra dependency, well-defined states. Search 21st.dev only for specific variants.

**When to search 21st.dev for buttons:**
- Button with inline counter (e.g. "Star 1.2k")
- Split button (primary action + dropdown)
- Button with animated icon on hover (e.g. arrow slide)

**Rejection criteria:**
- Color gradient on the background
- Colored shadow (glow)
- Decorative `animate-shimmer` on loop

---

## PRICING SECTIONS

**Slop detected:** "Popular" card with gradient or glassmorphism, "Most Popular" badge with no logic, "30-day money back" with no link, hardcoded prices, fictional star ratings.

**Search URL:** `https://21st.dev/s/pricing`

**Default recommendation:** pricing table differentiated by border (not gradient), working monthly/annual toggle, feature list with real checks, room to wire Stripe Price IDs.

**Selection criteria:**
- Plan differentiation via `ring-2 ring-accent` or `border-accent` (not gradient)
- Functional toggle (not visual-only)
- Features with real `<CheckIcon>`, not `✨`
- Prices as props/variables (not hardcoded)

**Rejection criteria:**
- "Popular" card with gradient or glassmorphism background
- Literal hardcoded prices with no variable
- Guarantee/money-back with no verifiable link

**Validated components:**
| Recommendation | Author | Preview | Install |
|---|---|---|---|
| ⭐ Pricing Card (multi) | sshahaider | [view](https://21st.dev/r/sshahaider/pricing-card) | `npx shadcn@latest add "https://21st.dev/r/sshahaider/pricing-card"` |
| Pricing Section | bigbogiballer | [view](https://21st.dev/r/bigbogiballer/pricing-section) | `npx shadcn@latest add "https://21st.dev/r/bigbogiballer/pricing-section"` |

---

## TESTIMONIALS

**Slop detected:** `randomuser.me` avatars, generic names (Alex Johnson, Sarah Miller), invented companies, universal 5/5 rating, auto-play carousel without accessible controls.

**Search URL:** `https://21st.dev/s/testimonial`

**Default recommendation:** static layout (not carousel) with one card per testimonial, room for real name + role + company + real photo (optional). No rating — star reviews without a source are slop.

**Selection criteria:**
- Structure that fits real data without forcing a profile photo
- Static layout or user-controlled scroll (not auto-play)
- No star rating built into the component

**Rejection criteria:**
- Infinite auto-play without controls
- Embedded placeholder avatars from external services
- Component with hardcoded fictional data and no clear replacement slot

**On install:** remove **all** sample data and replace with `{/* TODO: real testimonials */}` before any commit.

---

## TEXT ANIMATIONS

**Slop detected:** animated gradient `background-clip: text`, `animate-pulse` on heading, typewriter repeating marketing copy in a loop, `text-7xl` text that "flies" across the screen.

**Search URL:** `https://21st.dev/s/text`

**Default recommendation:** solid text with strong typographic hierarchy. If the project requires text animation by design decision, use Text Shimmer from 21st.dev with controlled `duration` — on a single focal element only.

**Selection criteria:**
- Controllable speed (`duration` prop)
- No infinite loop on static marketing content
- Animation serves the content (shimmer on loading, emphasis on CTA) — not decorative

**Rejection criteria:**
- `background-clip: text` with chromatic gradient
- Typewriter repeating marketing copy
- Animation longer than 3s without functional reason

**Validated components:**
| Recommendation | Author | Preview | Install |
|---|---|---|---|
| ⭐ Text Shimmer | 21st.dev | [view](https://21st.dev/r/21st.dev/text-shimmer) | `npx shadcn@latest add "https://21st.dev/r/21st.dev/text-shimmer"` |

**Usage rule:** Text Shimmer only in loading states or on **one** focal element per page. Never on the main marketing H1.

---

## CALLS TO ACTION (CTA SECTIONS)

**Slop detected:** full-width section with gradient, giant title in `bg-clip-text`, vague subtitle, two buttons with glow.

**Search URL:** `https://21st.dev/s/cta`

**Default recommendation:** section with inverted background (dark if the page is light, or `bg-muted`), direct heading with action verb, **one** flat primary CTA + one outline secondary. No gradient.

**Selection criteria:**
- Solid differentiated background (not gradient)
- A single clear primary CTA
- Heading with direct copy (not "Transform your business")

**Rejection criteria:**
- Gradient background
- Two primary CTAs (dilutes action)
- Generic non-editable copy

---

## NAVIGATION / NAVBAR

**Slop detected:** `backdrop-blur + bg-white/70` (glassmorphism), gradient logo, links with no visible active state, mobile menu without accessible focus.

**Search URL:** `https://21st.dev/s/navbar`

**Default recommendation:** navbar with solid background (`bg-background`), `border-b border-border`, logo without gradient, active link with underline or accent color, mobile menu with focus trap.

**Selection criteria:**
- Solid background, no transparency
- Visible active link state, no gradient
- Accessible mobile menu (focus trap, `aria-expanded`)

**Rejection criteria:**
- `backdrop-blur` on the header
- Logo with gradient or glow
- Mega-menu with glassmorphism

---

## ANIMATED BACKGROUNDS / SHADERS

**Slop detected:** decorative WebGL shaders, floating particles, animated grids with no purpose, noise textures only to "look tech".

**Search URL:** `https://21st.dev/s/shaders`

**Default rule:** **remove and replace with intentional negative space.**
A clean background with strong typography and generous spacing outperforms a decorative shader.

**Exception — when to offer a 21st.dev shader:**
Only if the user explicitly asks for a unique background for a visual-product hero (e.g. game, creative app). Criteria:
- Subtle shader (low contrast with content above, does not compete)
- No flicker or aggressive loop
- Performance: 60fps without jank on mid-range mobile

**Default replacement for removed background:** `bg-background` with a subtle grid pattern via CSS:
```css
background-image: radial-gradient(circle, hsl(var(--border)) 1px, transparent 1px);
background-size: 24px 24px;
```
This adds texture without chromatic gradient and works in dark/light mode via tokens.

---

## LOADING / SKELETON

**Slop detected:** `animate-spin` over content area, blank screen with centered spinner, loading that blocks the entire UI.

**Replacement:** native snippets in `PATTERNS.md` — skeleton loaders with structural `animate-pulse`.
Do not use 21st.dev for skeleton; native is simpler, controllable, and dependency-free.

**When to search 21st.dev:** only for very specific layouts not covered (e.g. complex chart skeleton, map skeleton). Search: `https://21st.dev/s/skeleton`.

---

## RESEARCH PROTOCOL (PHASE 2)

For each problematic element found, before presenting options:

1. Check whether the category is mapped here
2. Review validated components in the category table
3. Search `https://21st.dev/s/[slug]` for newer options
4. Filter using the universal rejection criterion + category criteria
5. Select the **default recommendation** (⭐) + 1–2 alternatives
6. Present in PHASE 2 question format with my explicit recommendation
