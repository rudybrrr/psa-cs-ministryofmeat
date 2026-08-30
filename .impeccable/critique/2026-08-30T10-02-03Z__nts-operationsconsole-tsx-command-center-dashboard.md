---
target: web/src/components/OperationsConsole.tsx (command center dashboard)
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-08-30T10-02-03Z
slug: nts-operationsconsole-tsx-command-center-dashboard
---
Method: dual-agent (A: design-review · B: detector/browser-evidence)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Loading state is a static gray string, no spinner |
| 2 | Match System / Real World | 2 | Raw enum strings surfaced verbatim to judges |
| 3 | User Control and Freedom | 2 | No undo/back once a guided step executes |
| 4 | Consistency and Standards | 4 | Token system and button variants applied consistently |
| 5 | Error Prevention | 3 | Disable/loading gating on buttons is real |
| 6 | Recognition Rather Than Recall | 3 | "What changed" region doesn't say since when |
| 7 | Flexibility and Efficiency | 2 | Mode switch and workspace tabs compete in one rail |
| 8 | Aesthetic and Minimalist Design | 3 | Restrained palette undercut by 3-deep nested boxes |
| 9 | Error Recovery | 2 | Error state dumps raw status:detail, no retry |
| 10 | Help and Documentation | 2 | No inline explanation of workspace tabs |
| **Total** | | **26/40** | Strong token discipline, held back by structural repetition |

## Design Specificity Verdict

Not shadcn-default slop at the token level — real authored palette (`--color-psa-void` etc), deliberate hairlines, evidence-tone colors per chapter. Detector (`detect.mjs`) ran clean, exit 0, zero findings across OperationsConsole.tsx and all 29 command-center files, verified with --no-config and per-file globbing.

The slop feeling is structural: KpiCard, MetricCard, ComparisonColumn, ChapterFrame, StageActionCard, EvidencePanel are all the same bordered rounded-div-with-label shape, nested inside each other (ObserveChapter.tsx:33-66 stacks 3 levels). The bespoke chapter narrative (Observe/Adapt/Coordinate/Respond/Protect) is undercut because every chapter renders as an interchangeable box stack — data-evidence-tone (ChapterFrame.tsx:34) does nothing but mark an sr-only span.

Browser overlay evidence: unavailable, no browser automation tool exposed this session.

## Priority Issues

[P1] Nested box-in-box repetition — reserve borders for outer ChapterFrame only, use dividers/weight for inner hierarchy. /impeccable layout
[P1] Raw wait_kind enum strings shown to judges (StageActionCard.tsx:88, GuidedAgentStrip.tsx:35) — route through existing waitCopy mapping. /impeccable clarify
[P1] Error state is a raw status:detail dump, no retry (OperationsConsole.tsx:283-293). /impeccable harden
[P2] Sidebar conflates workspace tabs + presentation modes with no visual separation (DashboardSidebar.tsx:61-101). /impeccable layout
[P2] No emotional peak treatment for safety-escalation climax (StageActionCard.tsx:112-116) — same weight as routine waiting state. /impeccable delight

## Persona Red Flags

First-time judge: 8 simultaneous nav choices before any incident context; Explore mode is an empty unoriented shell.
Power user: no undo on guided actions, only full reset via "Start fresh."

## Minor Observations

psa-meta label pattern repeats identically across 4 components, flattening hierarchy. GuidedIntroSurface copy is hardcoded, will drift from fixture data. Light-evidence-panel-in-dark-shell signal inconsistently applied across chapters.

## Questions to Consider

- Where's the visual signature making each chapter feel different, beyond copy?
- Was the token-system care spent on container chrome instead of the emotional climax?
- Is Explore mode meant for judges, or only for self-demoing engineers?
