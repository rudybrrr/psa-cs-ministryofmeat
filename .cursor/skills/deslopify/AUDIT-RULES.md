# AUDIT-RULES — Deslopify Violation Catalog

Complete reference for PHASE 1 (AUDIT) and PHASE 6 (VERIFY).
Each section includes: identifier, detection signal, BEFORE and AFTER example.

---

## DESIGN

### D-01 — Gradient on background or text

**Detect:** `linear-gradient`, `radial-gradient`, `bg-gradient-to-*`, `background-clip: text`, `text-transparent bg-clip-text`

```tsx
// BEFORE — slop
<div className="bg-gradient-to-br from-purple-600 to-blue-500 p-8 rounded-xl">
  <h1 className="text-transparent bg-clip-text bg-gradient-to-r from-white to-purple-200">
    Bem-vindo ao Futuro
  </h1>
</div>

// AFTER — flat
<div className="bg-zinc-900 p-8 rounded-xl border border-zinc-800">
  <h1 className="text-white">
    Bem-vindo ao Futuro
  </h1>
</div>
```

---

### D-02 — Glassmorphism

**Detect:** `backdrop-blur`, `backdrop-filter`, `bg-white/[0-9]`, `bg-black/[0-9]`, `border-white/[0-9]`, `saturate-`

```tsx
// BEFORE — slop
<div className="backdrop-blur-md bg-white/10 border border-white/20 rounded-2xl p-6">
  <p className="text-white/80">Conteúdo aqui</p>
</div>

// AFTER — flat
<div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
  <p className="text-zinc-300">Conteúdo aqui</p>
</div>
```

---

### D-03 — AI purple/blue combo

**Detect:** coexistence of `purple-*` + `blue-*` classes (or `indigo-*` + `violet-*`) in a gradient, or hex `#6366f1`, `#8b5cf6`, `#7c3aed`, `#3b82f6` used together.

```tsx
// BEFORE — slop
<Button className="bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700">
  Começar Agora
</Button>

// AFTER — flat with single accent
<Button className="bg-indigo-600 hover:bg-indigo-700 text-white">
  Começar Agora
</Button>
```

---

### D-04 — Orb / floating decorative element

**Detect:** `animate-pulse` or `animate-bounce` on divs with no functional content; elements with `blur-[0-9]`, `opacity-[0-9]`, and large fixed dimensions with no layout purpose.

```tsx
// BEFORE — slop
<div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500 rounded-full opacity-20 blur-3xl animate-pulse" />
<div className="absolute -bottom-20 -left-20 w-60 h-60 bg-blue-500 rounded-full opacity-10 blur-2xl" />

// AFTER — removed entirely. Zero decorative divs.
```

---

### D-05 — Excessive shadow / glow effect

**Detect:** `shadow-[color]`, `shadow-purple-*`, `drop-shadow`, box-shadow with chromatic color.

```tsx
// BEFORE — slop
<button className="bg-purple-600 shadow-lg shadow-purple-500/50 hover:shadow-purple-500/75">
  CTA Principal
</button>

// AFTER — flat
<button className="bg-purple-600 hover:bg-purple-700 transition-colors">
  CTA Principal
</button>
```

---

### D-06 — Excessive border radius ("pill everything")

**Detect:** `rounded-full` on cards or rectangular containers; `rounded-3xl` or larger on elements that are not tags/badges.

```tsx
// BEFORE — slop
<div className="rounded-3xl bg-zinc-800 p-8 border border-zinc-700">

// AFTER — proportional to context
<div className="rounded-lg bg-zinc-800 p-8 border border-zinc-800">
```

---

## TYPOGRAPHY

### T-01 — Multiple font families without justification

**Detect:** more than one distinct `font-*` other than `font-mono` applied to non-code text.

```tsx
// BEFORE — slop
<h1 className="font-display text-5xl">Headline</h1>
<p className="font-body text-base">Texto corrido aqui.</p>

// AFTER — single typeface
<h1 className="font-sans text-4xl font-bold">Headline</h1>
<p className="font-sans text-base">Texto corrido aqui.</p>
```

---

### T-02 — Oversized heading without hierarchy

**Detect:** `text-6xl`, `text-7xl`, `text-8xl` in hero sections without adequate supporting spacing.

```tsx
// BEFORE — slop
<h1 className="text-7xl font-black text-transparent bg-clip-text bg-gradient-to-r from-white to-purple-300">
  Revolucione Tudo
</h1>

// AFTER — size with purpose
<h1 className="text-4xl font-bold text-white tracking-tight">
  {/* TODO: real copy */}
</h1>
```

---

### T-03 — Line-height on body text

**Detect:** `leading-none` or `leading-tight` on `<p>` or body-text spans.

```tsx
// BEFORE — slop (illegible)
<p className="text-base leading-none text-zinc-400">
  Longa descrição da feature que fica toda espremida.
</p>

// AFTER
<p className="text-base leading-relaxed text-zinc-400">
  Longa descrição da feature que fica toda espremida.
</p>
```

---

## COPYWRITING

### C-01 — Banned words

**Detect (case-insensitive):** match against the appropriate list for the copy language. Use both lists when auditing mixed-language UI.

**English — banned words / phrases:** "revolutionize", "empower", "transform", "synergy", "innovative", "disruptive", "game-changer", "game changer", "unlock", "next-generation", "cutting-edge", "seamless", "powerful solution", "next level".

**Portuguese (Brazil) — banned words / phrases:** "revolucionar", "revolucione", "empoderar", "transformar", "sinergia", "inovador", "disruptivo", "solução poderosa", "próxima geração", "de ponta", "sem fricção", "nível superior", "desbloquear", "game changer", "game-changer" (common anglicisms in Brazilian marketing copy).

```tsx
// BEFORE — slop
<h2>Revolucione sua empresa com nossa poderosa solução inovadora</h2>
<p>Empoderamos times com tecnologia de próxima geração.</p>

// AFTER — straight to the point (or flagged for review)
<h2>{/* TODO: real copy — what exactly does the product do? */}</h2>
<p>{/* TODO: real copy — measurable outcome for the user */}</p>
```

---

### C-02 — Feature card without real data

**Detect:** `<FeatureCard>` or equivalent with generic `title`, `description`, and `icon`; `✨`, `🚀`, `💡` icons in component props.

```tsx
// BEFORE — slop
<FeatureCard
  icon={<Sparkles />}
  title="Incrível Performance"
  description="Nossa plataforma é incrivelmente rápida e poderosa."
/>

// AFTER — placeholder for real data
{/*
  TODO: Real feature card
  - Replace with screenshot of the feature in action, OR
  - Add real metric: "Loads in < 200ms (p95)" with source
  - Suggested component: https://21st.dev/s/features
*/}
<FeatureCard
  title={/* TODO: direct feature title */}
  description={/* TODO: measurable benefit */}
  media={/* TODO: screenshot or demo */}
/>
```

---

### C-03 — Fictional social proof

**Detect:** "trusted by X+ companies/teams/users", generic names in testimonials (Alex Johnson, Sarah Miller, Michael Chen), `randomuser.me` in avatar `src`.

```tsx
// BEFORE — slop
<TestimonialCard
  name="Alex Johnson"
  role="CEO at TechFlow"
  avatar="https://randomuser.me/api/portraits/men/32.jpg"
  text="This product changed everything for our team!"
/>

// AFTER — structure kept, fictional data removed
{/*
  TODO: Real testimonials — fill with:
  - Verifiable full name
  - Real role and company
  - Real avatar (with permission)
  - Authentic quote
*/}
```

---

## UX

### U-01 — Loading spinner in content area

**Detect:** `animate-spin`, `<Spinner`, `<Loader`, `role="status"` with spinning circle in a content area (not a submit button).

```tsx
// BEFORE — slop
{isLoading && <Spinner className="text-purple-500 animate-spin h-8 w-8" />}

// AFTER — structural skeleton loader
{isLoading && <CardSkeleton />}

// CardSkeleton — see full snippet in PATTERNS.md
```

---

### U-02 — Icon-only button without tooltip

**Detect:** `<button>` or `<Button>` whose children are only an icon component (Lucide, Heroicons, SVG) with no visible text and no `title` or `<Tooltip>`.

```tsx
// BEFORE — slop (inaccessible)
<Button variant="ghost" size="icon">
  <Trash2 className="h-4 w-4" />
</Button>

// AFTER — accessible
<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="ghost" size="icon" aria-label="Excluir item">
      <Trash2 className="h-4 w-4" />
    </Button>
  </TooltipTrigger>
  <TooltipContent>Excluir item</TooltipContent>
</Tooltip>

// If the project has no shadcn Tooltip, minimum acceptable:
<Button variant="ghost" size="icon" title="Excluir item" aria-label="Excluir item">
  <Trash2 className="h-4 w-4" />
</Button>
```

---

## ENGINEERING

### E-01 — Mutation without optimistic rendering

**Detect:** async function that calls `fetch`/`axios` for PUT/PATCH/DELETE/POST and only updates state in `.then()` or after `await`, with no prior local state update.

```tsx
// BEFORE — slow UX
async function handleToggleLike(postId: string) {
  const res = await fetch(`/api/posts/${postId}/like`, { method: 'POST' });
  const data = await res.json();
  setPosts(prev => prev.map(p => p.id === postId ? data : p));
}

// AFTER — optimistic
function handleToggleLike(postId: string) {
  const previousPosts = posts;

  setPosts(prev =>
    prev.map(p => p.id === postId ? { ...p, liked: !p.liked, likes: p.liked ? p.likes - 1 : p.likes + 1 } : p)
  );

  fetch(`/api/posts/${postId}/like`, { method: 'POST' })
    .then(res => { if (!res.ok) throw new Error(); })
    .catch(() => {
      setPosts(previousPosts);
      toast.error('Não foi possível registrar o like. Tente novamente.');
    });
}
```

---

### E-02 — Fetch without cache

**Detect:** `useEffect` with `fetch`/`axios` without `SWR`, `useQuery`, `React.cache`, or `next/cache`; calls that re-run on every mount.

```tsx
// BEFORE — re-fetch on every render/mount
useEffect(() => {
  fetch('/api/products').then(r => r.json()).then(setProducts);
}, []);

// AFTER — with SWR (see full snippet in PATTERNS.md)
const { data: products, error, isLoading } = useSWR('/api/products', fetcher, {
  staleTime: 60_000,
  revalidateOnFocus: false,
});
```

---

## Verification Checklist (PHASE 6)

Before reporting completion, confirm **all items below are false** in the modified code:

- [ ] `linear-gradient` or `radial-gradient` on visual elements
- [ ] `bg-gradient-to-*` on any element
- [ ] `backdrop-blur` or `backdrop-filter`
- [ ] `bg-white/` or `bg-black/` + transparency on cards/modals
- [ ] `shadow-[chromatic color]` or `drop-shadow` with color
- [ ] Non-functional div with `animate-pulse`/`animate-bounce`
- [ ] More than one active non-monospace font family
- [ ] `text-6xl` or larger without layout justification
- [ ] Banned words from list C-01 (English and/or Portuguese as applicable)
- [ ] Fictional names (Alex Johnson, Sarah Miller, etc.) in testimonials
- [ ] `randomuser.me` in any `src`
- [ ] `animate-spin` in a content area (outside submit button)
- [ ] `<button>` with icon only and no `title` or `<Tooltip>`
- [ ] Async mutation with no prior optimistic update
- [ ] `useEffect` with fetch and no caching strategy
