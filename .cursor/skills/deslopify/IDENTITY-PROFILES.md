# IDENTITY-PROFILES — Reference Design Profiles

Consult during PHASE 0 (P2) when the user provides a product name or URL as a known reference.
Each profile defines the design tokens that guide all PHASE 2 decisions.

**How to use:** when the user says "I want something like Linear", read the Linear profile and apply the tokens as context for 21st.dev suggestions and manual refactors.

---

## Linear

**Site:** https://linear.app
**Tone:** technical, information-dense, fast — built by and for product engineers

| Token | Value |
|---|---|
| Background | `#0f0f11` (near black, not pure black) |
| Surface | `#1a1a1f` |
| Border | `#2a2a35` |
| Foreground | `#f4f4f5` |
| Muted | `#71717a` |
| Accent | `#5e6ad2` (functional blue-violet, not decorative) |
| Font | `Inter` — `font-medium` for UI, `font-normal` for body |
| Radius | `rounded-md` (6px) — no `rounded-2xl` |
| Shadow | none or structural `shadow-xs` |

**Component patterns:**
- Hero: dark, bold headline `tracking-tight`, product emphasis with screenshot or keyboard-driven demo
- Cards: subtle border, generous padding, no colored header
- Buttons: flat with accent, hover via `opacity` or `brightness`, no glow
- Typography: restrained scale — max `text-3xl` on headline, `text-sm` in UI

**21st.dev filter for this profile:** prefer dark-first components, no flashy animations, no gradients. Search for "minimal dark" or "technical".

---

## Stripe

**Site:** https://stripe.com
**Tone:** corporate trust with luxury detail — functional but carefully polished

| Token | Value |
|---|---|
| Background | `#ffffff` / `#f6f9fc` (cool off-white) |
| Surface | `#ffffff` with `border border-[#e3e8ee]` |
| Border | `#e3e8ee` |
| Foreground | `#0a2540` (corporate dark blue, not black) |
| Muted | `#425466` |
| Accent | `#635bff` (Stripe purple — CTAs only, not as gradient) |
| Font | `Sohne` / fallback `system-ui` — weight 400 body, 600 headings |
| Radius | `rounded-md` (4–6px) — extremely restrained |
| Shadow | structural `shadow-sm`, very soft |

**Component patterns:**
- Hero: light background, large headline `font-bold text-[#0a2540]`, primary CTA with solid accent
- Cards: thin `#e3e8ee` border, generous padding, no differentiated fill
- Buttons: solid accent `#635bff`, hover `brightness-95`, no glow
- Animations: subtle, purposeful (e.g. dashboard panel sliding smoothly)

**21st.dev filter for this profile:** prefer light-first, clean components with structural borders. Reject anything that feels overly "startup".

---

## Vercel

**Site:** https://vercel.com
**Tone:** ruthless clarity — absolute black/white with typography as the centerpiece

| Token | Value |
|---|---|
| Background dark | `#000000` |
| Background light | `#ffffff` |
| Surface | no gradation — pure black or white |
| Border | `#333333` (dark) / `#eaeaea` (light) |
| Foreground | `#ffffff` (dark) / `#000000` (light) |
| Muted | `#888888` |
| Accent | none — hierarchy via black/white + gray contrast |
| Font | `Geist` — `font-bold` headings, `font-normal` body |
| Radius | `rounded` (4px) or zero — no decorative curves |
| Shadow | zero |

**Component patterns:**
- Hero: full black, huge headline `font-bold tracking-tighter`, subtitle `text-[#888]`, solid white CTA
- Cards: `#333` border, `#111` fill, symmetric padding
- Grid: code and terminal are visual elements — not text alone
- No colored accent: emphasis via size and font weight

**21st.dev filter for this profile:** monochrome components, zero colored accent, aggressive typography. Reject any color beyond black/white/gray.

---

## Notion

**Site:** https://notion.so
**Tone:** warm, editorial, human — productive without feeling cold

| Token | Value |
|---|---|
| Background | `#ffffff` / `#f7f7f5` (slightly warm off-white) |
| Surface | `#f7f7f5` |
| Border | `#e9e9e7` |
| Foreground | `#37352f` (dark brown, not pure black) |
| Muted | `#9b9a97` |
| Accent | `#2eaadc` (light blue — used very sparingly) |
| Font | `ui-sans-serif` (system sans) — no obvious custom face |
| Radius | `rounded-sm` (3px) — almost flat |
| Shadow | very soft `shadow-sm` |

**Component patterns:**
- Hero: off-white background, editorial headline with mixed weights, illustrations or product screenshot
- Cards: no visible border on light background, hover `bg-[#f7f7f5]`
- Typography: mixed weights as editorial device (bold + regular on the same line)
- Overall tone: documents, text, content — not "enterprise software"

**21st.dev filter for this profile:** warm-white-first, editorial components. Reject aggressive dark mode or "technical SaaS" styling.

---

## Raycast

**Site:** https://raycast.com
**Tone:** dark premium, fast, keyboard-first — built for power users

| Token | Value |
|---|---|
| Background | `#1c1c1e` (not pure black — charcoal gray) |
| Surface | `#242426` / `#2c2c2e` |
| Border | `#3a3a3c` |
| Foreground | `#f2f2f7` |
| Muted | `#8e8e93` |
| Accent | `#ff6363` (coral red — used sparingly) |
| Font | `Inter` — `font-medium` in UI |
| Radius | `rounded-lg` (10–12px) — rounder than Linear |
| Shadow | `shadow-md` with `shadow-black/50` — dark shadow, not colored |

**Component patterns:**
- Hero: dark with app screenshot centered, platform badge (macOS/Windows)
- Cards: background slightly different from page, no heavy border
- Coral accent: primary CTAs and active indicators only
- Micro-animations: soft, functional (e.g. command palette opening)

**21st.dev filter for this profile:** dark, polished, keyboard-centric. Accept subtle animations that reinforce "speed". Reject glassmorphism and gradients.

---

## Loom

**Site:** https://www.loom.com
**Tone:** friendly, fast, visual — focused on video and async communication

| Token | Value |
|---|---|
| Background | `#ffffff` |
| Surface | `#f9f9f9` |
| Border | `#e5e5e5` |
| Foreground | `#1a1a1a` |
| Muted | `#6b7280` |
| Accent | `#625DF5` (functional purple — not as gradient) |
| Font | `Inter` — `font-semibold` headings, `font-normal` body |
| Radius | `rounded-xl` (12px) — softer, friendly |
| Shadow | `shadow-md` — more prominent, consumer product |

**Component patterns:**
- Hero: product screenshot emphasis (video thumbnail), direct copy, solid accent CTA
- Cards: rounded, with preview thumbnail
- Tone: young but professional — neither startup cliché nor enterprise stiff

**21st.dev filter for this profile:** light, rounded components with room for media. More consumer than B2B.

---

## Figma

**Site:** https://figma.com
**Tone:** bold, editorial, design product — functional colors with intent

| Token | Value |
|---|---|
| Background | `#1e1e1e` (dark default) |
| Surface | `#2c2c2c` |
| Accent | Functional multicolor (each tool has its color) — but NOT as gradient |
| Foreground | `#ffffff` |
| Font | `Inter` — hierarchy heavily tuned |
| Radius | `rounded-sm` (4px) in UI, `rounded-lg` on product cards |

**Note:** Figma style is specific to design tools — do not apply literally to generic B2B SaaS. Use only when the product clearly targets creators/designers.

---

## How to Use This File

When the user provides a reference in P2:

1. Locate the profile in this file
2. Extract tokens: background, foreground, accent, font, radius, shadow
3. Use those tokens as context for PHASE 2 options:
   - "Aligned with Linear’s style, I recommend component X because it uses `font-medium` typography, subtle `#2a2a35` borders, and no chromatic shadow"
4. Filter 21st.dev suggestions by the profile’s tone (dark/light, technical/friendly, minimal/editorial)
5. If the user provided a URL not listed here: open the URL and extract the tokens above manually

**If the reference is not in this file:** visit the reference site and identify: background color, text color, accent color, type family, dominant border-radius, presence or absence of shadow. Capture that as context before proceeding.
