# UI Review — Command Center Dashboard

Source: design critique of `web/src/components/OperationsConsole.tsx` and `web/src/components/command-center/**`. Detector (mechanical scan) came back clean — palette/tokens are solid. The problems below are structural/compositional, not token-level.

## P1 — Fix first

### 1. Nested box-in-box everywhere ("cards on cards")
`KpiCard`, `MetricCard`, `ComparisonColumn`, `ChapterFrame`, `StageActionCard`, `EvidencePanel` are all the same shape: rounded, bordered div with a `psa-meta` label over a value. They get nested 2-3 deep — e.g. `ObserveChapter.tsx` (~lines 33-66) stacks `ChapterFrame` > grid > `ComparisonColumn`/`EvidencePanel`, each independently bordered and radiused.

**Change:** Only the outer `ChapterFrame` should carry a border/background. Everything nested inside it should use dividers (`border-t` hairline), typographic weight, or spacing to separate content — not a second/third rounded rect. Audit every component under `command-center/` and `command-center/chapters/` for a `rounded-*` + `border` combo that's nested inside another one; strip the inner border.

**Files:** `command-center/ChapterFrame.tsx`, `command-center/chapters/ObserveChapter.tsx`, `AdaptChapter.tsx`, `CoordinateChapter.tsx`, `RespondChapter.tsx`, `ProtectChapter.tsx`, `IncidentChapter.tsx`, plus wherever `ComparisonColumn`/`EvidencePanel`/`MetricCard`/`KpiCard` are defined.

### 2. Raw internal state strings shown to users
`wait_kind` enum values like `NEW_OPERATIONAL_EVIDENCE` and `HUMAN_TRADEOFF_DECISION` render verbatim as mono labels instead of human copy.

**Change:** Route every enum through the existing `waitCopy` / `guidedActionPresentation` mapping. Never render a raw constant in the UI — if a mapping is missing for a value, add it rather than falling back to the raw string.

**Files:** `command-center/StageActionCard.tsx` (~line 88), `command-center/chapters/GuidedAgentStrip.tsx` (~line 35).

### 3. Error state reads as a crash
The error UI dumps `{status}: {detail}` in monospace with a red border and no way to recover.

**Change:** Translate the status into plain language ("Couldn't reach the server" instead of raw HTTP text), and add a retry button in the error card itself.

**Files:** `OperationsConsole.tsx` (~lines 283-293).

## P2 — Fix next

### 4. Sidebar mixes two navigation systems with no visual separation
The 5 workspace tabs (Recovery/Containers/Carrier/Evidence/Overview) and the 3 presentation modes (Guided/Auto/Explore) sit in the same 236px rail, distinguished only by a small caption label.

**Change:** Visually separate them — group with a divider, different control style (e.g. segmented control for modes vs. list for tabs), or move modes to a different location entirely (top bar).

**Files:** `command-center/DashboardSidebar.tsx` (~lines 29-33, 61-101).

### 5. No visual emphasis on the actual demo climax
The safety-escalation success state renders in the same `text-sm font-medium` weight as a routine "agent waiting" status — the one moment the demo is built to prove lands flat.

**Change:** Give terminal/escalation states distinct treatment — larger text, stronger color, a brief transition/motion — so it visually registers as different from routine step transitions.

**Files:** `command-center/StageActionCard.tsx` (~lines 112-116).

### 6. Loading state has no motion
"Contacting backend and loading persisted incident state…" renders as a static gray box. During a live demo this reads as frozen, not loading.

**Change:** Add a spinner or pulse animation to the loading state.

**Files:** `OperationsConsole.tsx` (~lines 278-280).

## P3 — Polish

### 7. Empty "Explore" mode has no orientation
A first-time viewer who clicks "Explore" before an incident loads gets 5 empty tabs with no explanation of what each will eventually show.

**Change:** Add a lightweight empty-state per tab explaining what populates it, or default new sessions into Guided mode instead of leaving Explore selectable as a cold start.

### 8. Repeated label pattern flattens hierarchy
The `psa-meta` "STEP X · ACTOR" label pattern is identical across `StageActionCard`, `ChapterFrame`, `ChapterProgress`, and `RecoveryKpiStrip` — makes it hard to tell "this is the primary action" from "this is a KPI strip" at a glance.

**Change:** Give the primary action card (`StageActionCard`) a distinct label treatment (size/weight/color) from purely informational sections.

### 9. Hardcoded copy that will drift from real data
`GuidedIntroSurface` has hardcoded stats ("24 transshipment containers at risk — 8 expedite slots available") not derived from the actual `summary` data prop.

**Change:** Wire this copy to the live summary values so it can't silently go stale.

**Files:** `command-center/GuidedIntroSurface.tsx`.

### 10. Inconsistent light/dark evidence signal
Light-toned `EvidencePanel`/`ComparisonColumn` variants (meant to signal "this is evidence" vs. dark chrome) aren't applied consistently — `ObserveChapter` uses a plain dark `ComparisonColumn` while other chapters use the tinted evidence variant.

**Change:** Audit every chapter and apply the evidence-tone variant consistently wherever the content is evidence, so "light = evidence" becomes a reliable, learnable rule.

**Files:** `command-center/chapters/ObserveChapter.tsx` and sibling chapter files.

### 11. No undo, only full reset
Once a guided action executes there's no way to step back — the only escape hatch is "Start fresh," which resets the whole incident.

**Change:** Add a lightweight "back one step" affordance, at least for non-destructive advances, separate from the full reset.

---

**Not a problem:** the design token system (`web/src/styles/tokens.css`) — palette, hairlines, evidence-tone colors — is solid and intentional. Don't touch it; the fixes above are all about composition/structure, not colors or fonts.
