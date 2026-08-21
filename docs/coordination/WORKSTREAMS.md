# Workstreams

This file is maintained only by the lead/integration workflow. Individual agents edit only their assigned file under `docs/coordination/logs/`.

| Workstream | Owner log | Branch | Base | Status | Scope |
| --- | --- | --- | --- | --- | --- |
| Task 1: foundation and contracts | `win-codex.md` | `main` | unborn branch | Complete; pending contract approval | Result `0271bb7c24f2d97af7bdf86628c55df3a5a9f07c`; plan hygiene, coordination baseline, project metadata, frozen domain contracts, and contract tests |
| Task 2: state and persistence | `win-codex.md` | `main` | `0373384567b5ca32ea41ed007987bf0b75a9d2de` | Complete; pending Task 3 authorization | Result `2f868e8e48d7569ac0945bed8e25f13ea2944fef`; explicit state machine, SQLModel/SQLite repositories, and append-only audit service/tests only |
| Task 3: deterministic vertical slice | `win-codex.md` | `main` | `a5eeccbb5c081430d309c71da8484ffee0abdb6e` | Complete; handoff accepted | Result `5dd81723b4b5b27513de0d3cb593c421afa109e8`; synthetic services, feasibility, deterministic dominance policy, persisted one-container workflow, and audit evidence only |
| Task 4: minimal FastAPI surface | `win-codex.md` | `main` | `1a5af0ab43c2c90c2c94d5421c6d4bc9f9b92a9c` | Complete; pending owner review | Result `d8573f4cf8aa0dffd5bce2be4602a4ca8c530053`; app factory/lifespan, dependency-overridden API tests, synthetic workflow trigger, three repository-backed inspection routes, and authority-boundary regression only |

## Coordination rules

- The lead/integration workflow alone edits this file.
- Every agent edits only its own environment log.
- Every completed log entry records timestamp, task, branch, base SHA, resulting HEAD SHA, files changed, tests and results, interfaces/contracts changed, deliberate deferrals, blockers, and recommended next step.
- `DECISIONS.md` is append-only and only records changes to frozen interfaces, architecture, or scope.
- No agent may silently change a frozen domain contract. Stop and record or propose the change in `DECISIONS.md` before implementation.
