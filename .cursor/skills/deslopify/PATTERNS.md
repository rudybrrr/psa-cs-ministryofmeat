# PATTERNS — Deslopify Reference Snippets

Replacements with genuine visual character — not just dry flat layouts.
The goal is for the outcome to have **more presence** than the original slop, not less.

---

## 1. Characterful Replacements (Design)

### 1.1 — Glassmorphism Card → Card with Personality

```tsx
// BEFORE — glassmorphism slop
<div className="backdrop-blur-md bg-white/10 border border-white/20 rounded-2xl p-6">
  <h3 className="text-white font-semibold">Amazing Feature</h3>
  <p className="text-white/70 text-sm mt-2">Vague description here.</p>
</div>

// AFTER — flat with character
// Character comes from: defined border, generous spacing, typographic weight, accent on the icon
<div className="rounded-lg border border-border bg-card p-6 space-y-3 hover:border-accent/50 transition-colors">
  <div className="flex items-center gap-3">
    {/* Functional icon with accent — not decorative */}
    <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent/10">
      <Icon className="h-4 w-4 text-accent" />
    </div>
    <h3 className="text-sm font-semibold text-foreground">{title}</h3>
  </div>
  <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
  {/* Structured space for screenshot or demo */}
  {media && (
    <div className="mt-4 overflow-hidden rounded-md border border-border bg-muted">
      {media}
    </div>
  )}
</div>
```

---

### 1.2 — Gradient Hero → Hero with Strong Typography

```tsx
// BEFORE — slop
<section className="bg-gradient-to-br from-purple-900 to-blue-900 min-h-screen flex items-center">
  <h1 className="text-7xl text-transparent bg-clip-text bg-gradient-to-r from-white to-purple-300">
    Revolutionize your business
  </h1>
  <div className="absolute inset-0 opacity-20 blur-3xl">
    {/* decorative orb */}
  </div>
</section>

// AFTER — flat with real presence
// Character comes from: high contrast, tuned tracking, subtle grid pattern, label above the H1
<section className="relative bg-background min-h-screen flex items-center overflow-hidden">
  {/* Subtle grid pattern — texture without chromatic gradient */}
  <div
    className="absolute inset-0 opacity-[0.03] dark:opacity-[0.06]"
    style={{
      backgroundImage: 'radial-gradient(circle, hsl(var(--foreground)) 1px, transparent 1px)',
      backgroundSize: '24px 24px',
    }}
  />

  <div className="relative mx-auto max-w-5xl px-6 py-24 text-center space-y-8">
    {/* Functional badge — not "🚀 Announcing v2.0" */}
    <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground">
      <span className="h-1.5 w-1.5 rounded-full bg-accent" />
      {/* TODO: real announcement / current version — copy real aqui */}
    </div>

    <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
      {/* TODO: real copy here — what the product does in one sentence */}
    </h1>

    <p className="mx-auto max-w-xl text-base leading-relaxed text-muted-foreground">
      {/* TODO: direct user benefit */}
    </p>

    <div className="flex items-center justify-center gap-3 flex-wrap">
      <Button size="lg" className="bg-accent text-accent-foreground hover:bg-accent/90">
        {/* TODO: primary CTA */}
      </Button>
      <Button size="lg" variant="outline">
        {/* TODO: secondary CTA */}
      </Button>
    </div>

    {/* Structured area for real product screenshot/demo */}
    <div className="mt-12 overflow-hidden rounded-xl border border-border bg-muted shadow-sm">
      {/* TODO: product screenshot 16:9, or <video autoPlay muted loop playsInline> */}
      <div className="aspect-video flex items-center justify-center text-sm text-muted-foreground">
        Screenshot / product demo here
      </div>
    </div>
  </div>
</section>
```

---

### 1.3 — Gradient Text → Typography with Hierarchy

```tsx
// BEFORE — slop
<h1 className="text-6xl font-black text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-blue-400">
  Transform your business today
</h1>

// AFTER — hierarchy via weight + tracking + targeted accent
// Emphasis without gradient: keyword in solid accent color
<h1 className="text-4xl font-bold tracking-tight text-foreground">
  {/* TODO: real copy */}
  The platform that{' '}
  <span className="text-accent">{/* keyword */}</span>{' '}
  {/* rest of copy */}
</h1>
```

---

### 1.4 — Testimonials Section without Real Data

```tsx
// BEFORE — slop
<TestimonialCard
  name="Alex Johnson"
  role="CEO at TechFlow"
  avatar="https://randomuser.me/api/portraits/men/32.jpg"
  text="This product absolutely revolutionized our workflow!"
  rating={5}
/>

// AFTER — worthy structure awaiting real data
// Layout preserved, fake data removed, structured placeholder
function TestimonialPlaceholder() {
  return (
    <div className="rounded-lg border border-border bg-card p-6 space-y-4">
      <p className="text-sm leading-relaxed text-muted-foreground italic">
        {/* TODO: real testimonial — straightforward line about the outcome achieved */}
      </p>
      <div className="flex items-center gap-3">
        {/* Optional avatar — only use if you have a real image with permission */}
        <div className="h-9 w-9 rounded-full bg-muted border border-border flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold text-foreground">
            {/* TODO: real full name */}
          </p>
          <p className="text-xs text-muted-foreground">
            {/* TODO: role, Company */}
          </p>
        </div>
      </div>
    </div>
  );
}
```

---

### 1.5 — Background with Grid Pattern (replaces decorative shader/orb)

Subtle texture that gives the background presence without a chromatic gradient. Works in dark/light mode via CSS tokens.

```tsx
// Reusable textured background component
function GridBackground({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative overflow-hidden">
      {/* Dots grid */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.04] dark:opacity-[0.07]"
        style={{
          backgroundImage: 'radial-gradient(circle, hsl(var(--foreground)) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />
      {/* Edge fade so it does not cut off abruptly */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-background" />
      <div className="relative">{children}</div>
    </div>
  );
}
```

---

## 2. Skeleton Loaders

### 2.1 — Generic Card Skeleton

```tsx
export function CardSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-card p-5 space-y-3">
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-md bg-muted animate-pulse flex-shrink-0" />
        <div className="h-4 w-2/3 rounded bg-muted animate-pulse" />
      </div>
      <div className="h-3 w-full rounded bg-muted animate-pulse" />
      <div className="h-3 w-4/5 rounded bg-muted animate-pulse" />
      <div className="h-24 w-full rounded-md bg-muted animate-pulse mt-2" />
    </div>
  );
}

export function CardListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => <CardSkeleton key={i} />)}
    </div>
  );
}
```

### 2.2 — Table Skeleton

```tsx
export function TableRowSkeleton({ columns = 4 }: { columns?: number }) {
  return (
    <tr className="border-b border-border">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 rounded bg-muted animate-pulse" style={{ width: `${55 + (i % 3) * 15}%` }} />
        </td>
      ))}
    </tr>
  );
}

export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <tbody>
      {Array.from({ length: rows }).map((_, i) => (
        <TableRowSkeleton key={i} columns={columns} />
      ))}
    </tbody>
  );
}
```

### 2.3 — Hero Skeleton

```tsx
export function HeroSkeleton() {
  return (
    <section className="flex flex-col items-center gap-6 py-24 px-6 text-center">
      <div className="h-5 w-32 rounded-full bg-muted animate-pulse" />
      <div className="space-y-3 w-full max-w-xl">
        <div className="h-10 w-full rounded bg-muted animate-pulse" />
        <div className="h-10 w-4/5 mx-auto rounded bg-muted animate-pulse" />
      </div>
      <div className="space-y-2 w-full max-w-md">
        <div className="h-4 w-full rounded bg-muted animate-pulse" />
        <div className="h-4 w-3/4 mx-auto rounded bg-muted animate-pulse" />
      </div>
      <div className="flex gap-3 pt-2">
        <div className="h-10 w-32 rounded-md bg-muted animate-pulse" />
        <div className="h-10 w-28 rounded-md bg-muted animate-pulse" />
      </div>
      <div className="mt-8 w-full max-w-3xl aspect-video rounded-xl bg-muted animate-pulse" />
    </section>
  );
}
```

---

## 3. Optimistic Rendering

### 3.1 — Like/Favorite Hook

```tsx
// hooks/useLike.ts
import { useState } from 'react';
import { toast } from 'sonner';

export function useLike(initialLiked: boolean, initialCount: number, onToggle: (liked: boolean) => Promise<void>) {
  const [liked, setLiked] = useState(initialLiked);
  const [count, setCount] = useState(initialCount);

  async function toggle() {
    const prevLiked = liked;
    const prevCount = count;

    setLiked(!prevLiked);
    setCount(prevLiked ? prevCount - 1 : prevCount + 1);

    try {
      await onToggle(!prevLiked);
    } catch {
      setLiked(prevLiked);
      setCount(prevCount);
      toast.error('Could not save. Please try again.');
    }
  }

  return { liked, count, toggle };
}
```

### 3.2 — Optimistic Delete in a List

```tsx
async function handleDelete(id: string) {
  const previousItems = items;
  setItems(prev => prev.filter(item => item.id !== id));

  try {
    const res = await fetch(`/api/items/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } catch {
    setItems(previousItems);
    toast.error('Could not delete. Please try again.');
  }
}
```

### 3.3 — Optimistic Field Update

```tsx
async function handleUpdate(id: string, patch: Partial<Item>) {
  const previousItems = items;
  setItems(prev => prev.map(item => item.id === id ? { ...item, ...patch } : item));

  try {
    const res = await fetch(`/api/items/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    if (!res.ok) throw new Error();
  } catch {
    setItems(previousItems);
    toast.error('Could not save your changes.');
  }
}
```

---

## 4. API Caching

### 4.1 — SWR

```tsx
// lib/fetcher.ts
export const fetcher = (url: string) =>
  fetch(url).then(res => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  });

// Usage
const { data, error, isLoading } = useSWR('/api/products', fetcher, {
  revalidateOnFocus: false,
  dedupingInterval: 60_000,
});

if (isLoading) return <CardListSkeleton />;
if (error) return <ErrorState />;
```

### 4.2 — React Query

```tsx
export function useProducts() {
  return useQuery({
    queryKey: ['products'],
    queryFn: () => fetch('/api/products').then(r => r.json()),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
```

### 4.3 — Next.js App Router (Server Component)

```tsx
async function getProducts(): Promise<Product[]> {
  const res = await fetch('https://api.example.com/products', {
    next: { revalidate: 60 },
  });
  if (!res.ok) throw new Error('Failed to fetch products');
  return res.json();
}
```

---

## 5. Flat Design with Character — Tokens

### 5.1 — Accent color via CSS var (single hue)

```css
/* globals.css */
:root {
  --accent: 221 83% 53%;           /* replace with accent defined in PHASE 0 */
  --accent-foreground: 0 0% 98%;
}

.dark {
  --accent: 217 91% 60%;
}
```

### 5.2 — CTA button without glow

```tsx
<Button className="bg-accent text-accent-foreground hover:bg-accent/90 transition-colors">
  {/* Primary CTA */}
</Button>

<Button variant="outline" className="border-border hover:bg-muted transition-colors">
  {/* Secondary CTA */}
</Button>
```

### 5.3 — Section divider with character

```tsx
// Replaces the generic section that "floats on the gradient"
// Character via spacing + label above + side border on the title
<section className="border-t border-border py-20">
  <div className="mx-auto max-w-5xl px-6">
    <div className="flex items-start gap-6">
      {/* Side accent bar — visual element without being a gradient */}
      <div className="mt-1 h-12 w-1 rounded-full bg-accent flex-shrink-0" />
      <div>
        <p className="text-xs font-medium uppercase tracking-widest text-accent">
          {/* Section label */}
        </p>
        <h2 className="mt-1 text-3xl font-bold tracking-tight text-foreground">
          {/* Straightforward title */}
        </h2>
      </div>
    </div>
  </div>
</section>
```
